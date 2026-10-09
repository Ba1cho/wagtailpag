import html as html_lib
import re
from collections.abc import Sequence

from django.contrib.contenttypes.models import ContentType
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import models
from django.template.response import TemplateResponse
from django.utils.html import strip_tags

from wagtail.documents import get_document_model
from wagtail.documents.models import Document
from wagtail.fields import StreamField
from wagtail.models import Page, ReferenceIndex
from wagtail.rich_text import RichText

# To enable logging of search queries for use with the "Promoted search results" module
# <https://docs.wagtail.org/en/stable/reference/contrib/searchpromotions.html>
# uncomment the following line and the lines indicated in the search function
# (after adding wagtail.contrib.search_promotions to INSTALLED_APPS):

# from wagtail.contrib.search_promotions.models import Query


def _get_document_model():
    return get_document_model()


# Ссылка на документ в RichText (DB-формат Wagtail):
#   <a linktype="document" id="7">Пользовательский текст ссылки</a>
# Порядок атрибутов не гарантирован (в БД встречается и
# <a id="7" linktype="document">…</a>), поэтому атрибуты разбираются отдельно.
# В отрендеренном HTML ссылка выглядит как <a href="/documents/7/file.pdf">…
_ANCHOR_RE = re.compile(r"<a\s[^>]*>.*?</a>", re.DOTALL | re.IGNORECASE)
_ATTR_RE = re.compile(r"""([\w-]+)\s*=\s*(["'])(.*?)\2""", re.DOTALL)
_DOC_HREF_RE = re.compile(r"/documents/(\d+)/", re.IGNORECASE)


def _iter_document_links_from_html(html):
    """
    Перебирает (id_документа, текст_ссылки) по всем ссылкам на документы в HTML.

    Понимает и DB-формат (linktype="document"), и отрендеренный вид
    (href="/documents/<id>/<filename>"), независимо от порядка атрибутов.
    """
    if not html or "<a" not in html:
        return
    for match in _ANCHOR_RE.finditer(html):
        tag = match.group(0)
        attrs = {name.lower(): value for name, _quote, value in _ATTR_RE.findall(tag)}

        doc_id = None
        if (
            attrs.get("linktype", "").lower() == "document"
            and attrs.get("id", "").isdigit()
        ):
            doc_id = attrs["id"]
        else:
            href_match = _DOC_HREF_RE.search(attrs.get("href", ""))
            if href_match:
                doc_id = href_match.group(1)

        if doc_id is None:
            continue

        start = tag.find(">")
        inner_html = tag[start + 1:-4] if start != -1 else ""
        text = html_lib.unescape(strip_tags(inner_html)).strip()
        yield int(doc_id), text


def _document_haystack(document):
    """Всё, по чему можно искать документ: название, имя файла, путь и URL."""
    try:
        url = document.url or ""
    except Exception:
        url = ""
    parts = [
        document.title or "",
        document.filename or "",
        document.file.name if document.file else "",
        url,
    ]
    return " ".join(part for part in parts if part)


def _iter_document_references_from_block(block_def, value):
    """
    Рекурсивно обходит блоки StreamField (StreamBlock), StructBlock и ListBlock
    и находит ссылки/значения документов.

    Возвращает (id_документа, текст_ссылки).
    """
    # Блок DocumentChooserBlock хранит выбранный Document в value
    if isinstance(value, Document):
        yield value.pk, _document_haystack(value)
        return

    # RichText (значение RichTextBlock внутри StreamField): DB-разметка
    # хранится в .source (в старых версиях Wagtail — в .raw), например
    # <a linktype="document" id="3">текст ссылки</a>
    if isinstance(value, RichText):
        yield from _iter_document_links_from_html(value.source)
        return

    raw = getattr(value, "raw", None)
    if isinstance(raw, str):
        yield from _iter_document_links_from_html(raw)
        return

    # Просто строка с HTML-ссылкой на документ
    if isinstance(value, str):
        yield from _iter_document_links_from_html(value)
        return

    # Значение StreamBlock (в т.ч. вложенный StreamField): у детей есть .block
    if hasattr(value, "stream_block"):
        if not value:
            return
        for child in value:
            yield from _iter_document_references_from_block(
                getattr(child, "block", block_def), child.value
            )
        return

    # StructBlock: значение — StructValue (dict), определения детей лежат
    # в block_def.child_blocks (имена → блоки)
    if isinstance(value, dict):
        if not value:
            return
        child_blocks = getattr(block_def, "child_blocks", None)
        for name, child_value in value.items():
            child_block = child_blocks.get(name) if child_blocks else None
            yield from _iter_document_references_from_block(child_block, child_value)
        return

    # ListBlock: значение — ListValue (наследует MutableSequence, а не list),
    # дети — ListChild с атрибутами .block и .value
    if isinstance(value, Sequence) or isinstance(value, (set, frozenset)):
        if not value:
            return
        child_block = getattr(block_def, "child_block", None)
        for item in value:
            yield from _iter_document_references_from_block(
                getattr(item, "block", child_block),
                getattr(item, "value", item),
            )
        return


def _iter_document_references(page):
    """
    Извлекает (id_документа, текст_ссылки) из RichText- и StreamField-полей страницы.

    Текст ссылки может быть изменён редактором и не совпадать с названием
    документа — по нему тоже нужно находить документ и страницу.
    """
    specific = page.specific_class
    for field in specific._meta.get_fields():
        # 1) RichText-текстовые поля
        if isinstance(field, models.TextField) and hasattr(page, field.attname):
            html = getattr(page, field.attname) or ""
            if "<a" in html:
                yield from _iter_document_links_from_html(html)
        # 2) StreamField — рекурсивно проходим по блокам
        elif isinstance(field, StreamField) and hasattr(page, field.attname):
            for block in getattr(page, field.attname) or ():
                yield from _iter_document_references_from_block(
                    block.block, block.value
                )


# ---------------------------------------------------------------------------
# Совпадение по части слова и извлечение текста страницы
# ---------------------------------------------------------------------------

def _query_terms(query):
    """Слова запроса в нижнем регистре (запрос уже должен быть .strip()'нут)."""
    return [term for term in query.lower().split() if term]


def _text_matches(text, query_lower, terms):
    """
    Совпадение по части слова: подстрока целиком либо каждое слово запроса
    встречается в тексте (порядок слов не важен).
    """
    if not text or not query_lower:
        return False
    if query_lower in text:
        return True
    return all(term in text for term in terms)


_SEARCH_FIELDS_CACHE = {}


def _search_field_names(page_class):
    """Имена полей, участвующих в поиске (SearchField / AutocompleteField)."""
    names = _SEARCH_FIELDS_CACHE.get(page_class)
    if names is None:
        names = []
        try:
            search_fields = page_class.get_searchable_search_fields()
        except Exception:
            search_fields = []
        for field in search_fields:
            name = getattr(field, "field_name", None)
            if name and name not in names:
                names.append(name)
        _SEARCH_FIELDS_CACHE[page_class] = names
    return names


def _value_to_text(value):
    """Превращает значение поля (RichText, StreamField, структуры) в текст."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, RichText):
        # DB-HTML без рендера шаблона; теги вырезаются в _page_search_text
        return value.source or ""
    if isinstance(value, Document):
        return _document_haystack(value)
    if isinstance(value, dict):  # StructValue (StructBlock)
        return " ".join(_value_to_text(item) for item in value.values())
    if hasattr(value, "stream_block"):  # StreamValue
        return " ".join(
            _value_to_text(getattr(child, "value", child)) for child in value
        )
    if hasattr(value, "block") and hasattr(value, "value"):  # StreamChild/ListChild
        return _value_to_text(value.value)
    # list, tuple, set и ListValue (наследует MutableSequence, а не list)
    if isinstance(value, Sequence) or isinstance(value, (set, frozenset)):
        return " ".join(_value_to_text(item) for item in value)
    if isinstance(value, (int, float)):
        return str(value)
    return ""


def _page_search_text(page):
    """
    Текст страницы для поиска по подстроке: заголовок, slug, все поисковые
    поля (RichText, StreamField, ссылки на документы и т.д.).
    Возвращает текст в нижнем регистре.
    """
    parts = [page.title or "", page.slug or ""]
    for name in _search_field_names(type(page)):
        try:
            parts.append(_value_to_text(getattr(page, name, None)))
        except Exception:
            # некорректное значение поля не должно ломать поиск
            continue

    # Совместимость со страницами, определяющими собственный searchable_content()
    searchable = getattr(page, "searchable_content", None)
    if callable(searchable):
        try:
            parts.append(searchable() or "")
        except Exception:
            pass

    text = html_lib.unescape(strip_tags(" ".join(part for part in parts if part)))
    return re.sub(r"\s+", " ", text).lower()


def search_documents(query):
    """
    Модельно-независимый поиск документов и страниц, где они используются.

    Ищет документы по части слова в названии, имени файла, пути и URL, а также
    по (возможно изменённому редактором) тексту ссылки на документ в RichText и
    StreamField. Страницы, ссылающиеся на документ (RichText
    <a linktype="document">, StreamField DocumentChooser, ForeignKey и т.д.),
    находятся через ReferenceIndex — Wagtail ведёт его автоматически для всех
    типов страниц, поэтому никакие специальные методы в моделях страниц не
    нужны. Текст ссылки в RichText может быть любым (в т.ч. устаревшим после
    переименования) — ссылка резолвится по id документа, а не по тексту.
    """
    query = (query or "").strip()
    if not query:
        return []
    query_lower = query.lower()
    terms = _query_terms(query_lower)

    document_model = _get_document_model()

    # 1) Совпадение по части слова в названии / имени файла / пути / URL
    document_ids = {}
    for document in document_model.objects.all().iterator():
        if _text_matches(_document_haystack(document).lower(), query_lower, terms):
            document_ids[document.pk] = document

    document_content_type = ContentType.objects.get_for_model(document_model)

    # 2) Входящие ссылки на найденные документы — одним запросом
    refs = ReferenceIndex.objects.filter(
        to_content_type_id=document_content_type.pk,
        to_object_id__in=list(document_ids),
    ).order_by("to_object_id")

    pages_by_document = {pk: set() for pk in document_ids}
    page_ids = set()
    for ref in refs:
        model = ref.content_type.model_class()
        # интересуют только ссылки, исходящие из страниц
        if model is not None and issubclass(model, Page):
            to_id = int(ref.to_object_id)
            pages_by_document.setdefault(to_id, set()).add(int(ref.object_id))
            page_ids.add(int(ref.object_id))

    specific_pages = {}
    if page_ids:
        for page in Page.objects.filter(id__in=page_ids).specific():
            specific_pages[page.pk] = page

    # 3) Тексты ссылок на документы в RichText и StreamField — по всем живым
    # страницам. Страницы, уже найденные через ReferenceIndex, НЕ пропускаются:
    # на одной странице может быть несколько документов, и совпадение по
    # изменённому тексту ссылки одного из них не должно теряться.
    for page in Page.objects.filter(live=True).specific().iterator():
        for doc_id, ref_text in _iter_document_references(page):
            if not ref_text or not _text_matches(
                ref_text.lower(), query_lower, terms
            ):
                continue
            if doc_id not in document_ids:
                document = document_model.objects.filter(pk=doc_id).first()
                if document is None:
                    continue
                document_ids[doc_id] = document
                pages_by_document.setdefault(doc_id, set())
            pages_by_document[doc_id].add(page.pk)
            specific_pages[page.pk] = page

    results = []
    for pk, document in document_ids.items():
        pages = [
            specific_pages[pid]
            for pid in sorted(pages_by_document.get(pk, set()))
            if pid in specific_pages and specific_pages[pid].live
        ]
        # Always return the document, even if no pages currently reference it.
        results.append({"document": document, "pages": pages})
    return results


def _search_pages_by_substring(query):
    """
    Find live pages where the query appears as a part of a word in the page
    content (title, search fields, rich text, stream fields, document link
    texts). Unlike the full-text index, this matches substrings, so a query
    like "поисков" finds a page containing "поисковая".
    """
    query = (query or "").strip()
    if not query:
        return []

    query_lower = query.lower()
    terms = _query_terms(query_lower)
    pages = []

    for page in Page.objects.live().specific().iterator():
        try:
            content = _page_search_text(page)
        except Exception:
            # ignore pages where content extraction fails
            continue
        if _text_matches(content, query_lower, terms):
            pages.append(page)
    return pages


def search_pages(query):
    """
    Поиск страниц: полнотекстовый индекс Wagtail + поиск по части слова.
    Результаты объединяются без дубликатов.
    """
    query = (query or "").strip()
    if not query:
        return Page.objects.none()

    page_ids = {result.pk for result in Page.objects.live().search(query)}
    for page in _search_pages_by_substring(query):
        page_ids.add(page.pk)

    if not page_ids:
        return Page.objects.none()

    return (
        Page.objects.live()
        .filter(pk__in=page_ids)
        .specific()
        .order_by("-first_published_at", "-pk")
    )


def search(request):
    search_query = request.GET.get("query", "")
    search_query = search_query.strip() or None
    page = request.GET.get("page", 1)

    # Search
    if search_query:
        # полнотекстовый поиск Wagtail + поиск по части слова
        search_results = search_pages(search_query)
        document_results = search_documents(search_query)
    else:
        search_results = Page.objects.none()
        document_results = []

    # Pagination
    paginator = Paginator(search_results, 10)
    try:
        search_results = paginator.page(page)
    except PageNotAnInteger:
        search_results = paginator.page(1)
    except EmptyPage:
        search_results = paginator.page(paginator.num_pages)

    return TemplateResponse(
        request,
        "search/search.html",
        {
            "search_query": search_query,
            "search_results": search_results,
            "document_results": document_results,
        },
    )




