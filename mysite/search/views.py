import re

from django.contrib.contenttypes.models import ContentType
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
from django.db import models
from django.template.response import TemplateResponse

from wagtail.documents import get_document_model
from wagtail.models import Page, ReferenceIndex

# To enable logging of search queries for use with the "Promoted search results" module
# <https://docs.wagtail.org/en/stable/reference/contrib/searchpromotions.html>
# uncomment the following line and the lines indicated in the search function
# (after adding wagtail.contrib.search_promotions to INSTALLED_APPS):

# from wagtail.contrib.search_promotions.models import Query


def _get_document_model():
    return get_document_model()


# Ссылка на документ в RichText (DB-формат Wagtail):
# <a linktype="document" id="7">Пользовательский текст ссылки</a>
DOCUMENT_LINK_RE = re.compile(
    r'<a\s[^>]*linktype="document"[^>]*\bid="(?P<id>\d+)"[^>]*>'
    r"(?P<text>.*?)</a>",
    re.DOTALL | re.IGNORECASE,
)


def _iter_document_link_texts(page):
    """Извлекает (id_документа, текст_ссылки) из RichText-полей страницы."""
    for field in page.specific_class._meta.get_fields():
        if not isinstance(field, models.TextField) or not hasattr(
            page, field.attname
        ):
            continue
        html = getattr(page, field.attname) or ""
        if "linktype=" not in html:
            continue
        for match in DOCUMENT_LINK_RE.finditer(html):
            yield int(match.group("id")), match.group("text")


def search_documents(query):
    """
    Модельно-независимый поиск документов и страниц, где они используются.

    Ищет документы по названию и имени файла, а страницы, ссылающиеся на
    документ (RichText <a linktype="document">, StreamField DocumentChooser,
    ForeignKey и т.д.), находит через ReferenceIndex — Wagtail ведёт его
    автоматически для всех типов страниц, поэтому никакие специальные
    методы в моделях страниц не нужны. Текст ссылки в RichText может быть
    любым (в т.ч. устаревшим после переименования) — ссылка резолвится по
    id документа, а не по тексту.
    """
    document_model = _get_document_model()
    documents = document_model.objects.filter(
        Q(title__icontains=query) | Q(file__icontains=query)
    ).distinct()

    document_content_type = ContentType.objects.get_for_model(document_model)
    document_ids = {document.pk: document for document in documents}

    # Входящие ссылки на найденные документы — одним запросом
    refs = ReferenceIndex.objects.filter(
        to_content_type_id=document_content_type.pk,
        to_object_id__in=document_ids,
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

    # Дополнительно: поиск по тексту ссылок на документы в RichText.
    # Текст ссылки может быть изменён редактором и не совпадать с названием
    # документа — тогда по нему нужно тоже находить документ и страницу.
    rich_pages = Page.objects.filter(live=True).specific().iterator()
    for page in rich_pages:
        if page.pk in specific_pages:
            continue  # уже найдены через ReferenceIndex
        for doc_id, link_text in _iter_document_link_texts(page):
            if query.lower() in link_text.lower():
                if doc_id not in document_ids:
                    document = document_model.objects.filter(pk=doc_id).first()
                    if document is None:
                        continue
                    document_ids[doc_id] = document
                    pages_by_document[doc_id] = set()
                pages_by_document[doc_id].add(page.pk)
                specific_pages[page.pk] = page

    results = []
    for pk, document in document_ids.items():
        pages = [
            specific_pages[pid]
            for pid in sorted(pages_by_document.get(pk, set()))
            if pid in specific_pages and specific_pages[pid].live
        ]
        if pages:
            results.append({"document": document, "pages": pages})
    return results


def search(request):
    search_query = request.GET.get("query", None)
    page = request.GET.get("page", 1)

    # Search
    if search_query:
        search_results = Page.objects.live().search(search_query)
        document_results = search_documents(search_query)

        # To log this query for use with the "Promoted search results" module:

        # query = Query.get(search_query)
        # query.add_hit()

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
