from django.contrib.contenttypes.models import ContentType
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db.models import Q
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


def search_documents(query):
    """
    Ищет документы по названию и имени файла и возвращает список словарей:
    {'document': Document, 'pages': [Page, ...]}

    Страницы, на которых прикреплён документ (в StreamField, RichText,
    DocumentChooser и т.д.), находятся через ReferenceIndex, который Wagtail
    ведёт автоматически для всех типов ссылок на документы.
    """
    document_model = _get_document_model()
    documents = document_model.objects.filter(
        Q(title__icontains=query) | Q(file__icontains=query)
    ).distinct()

    document_content_type = ContentType.objects.get_for_model(document_model)

    results = []
    for document in documents:
        page_ids = []
        # входящие ссылки на документ: Wagtail ведёт их автоматически
        # (StreamField, RichText, DocumentChooser, ForeignKey и т.д.)
        refs = ReferenceIndex.objects.filter(
            to_content_type_id=document_content_type.pk,
            to_object_id=document.pk,
        )
        for ref in refs:
            model = ref.content_type.model_class()
            # нас интересуют только ссылки, исходящие из страниц
            if model is not None and issubclass(model, Page):
                if ref.object_id not in page_ids:
                    page_ids.append(ref.object_id)
        pages = []
        if page_ids:
            pages = list(
                Page.objects.live().filter(id__in=page_ids).specific()
            )
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
