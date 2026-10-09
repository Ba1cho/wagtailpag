"""Тесты поиска: страницы по части слова и документы по (изменённой) ссылке."""
from django.test import TestCase

from wagtail.documents.models import Document
from wagtail.models import Page, Site

from blog.models import BlogListingPage, BlogPostPage, StreamFieldDemoPage
from home.models import HomePage
from search.views import search_documents, search_pages


class SearchFixtureMixin:
    """Общая фикстура: главная → блог → статья со ссылкой на документ."""

    def create_search_fixture(self):
        root = Page.get_first_root_node()
        if not Site.objects.exists():
            Site.objects.create(
                hostname="testsite", root_page=root, is_default_site=True
            )

        # главная страница создаётся миграцией home.0002 — переиспользуем её
        self.homepage = root.get_children().type(HomePage).first()
        if self.homepage is None:
            self.homepage = HomePage(title="Home", slug="home")
            root.add_child(instance=self.homepage)

        self.listing = BlogListingPage(title="Блог", slug="blog")
        self.homepage.add_child(instance=self.listing)

        # Документ: ищем и по названию, и по имени файла
        self.document = Document(title="Итоговый отчёт")
        self.document.file.name = "documents/itogoviy_otchet.pdf"
        self.document.save()

        # Текст ссылки изменён редактором и не совпадает с названием документа
        self.link_text = "Изменённый текст тотальный"
        self.link_html = (
            f'<a linktype="document" id="{self.document.pk}">{self.link_text}</a>'
        )
        self.post = BlogPostPage(
            title="Как работает поиск",
            slug="kak-rabotaet-poisk",
            intro="<p>Новая поисковая система колледжа</p>",
            body=f"<p>Подробности в {self.link_html}</p>",
        )
        self.listing.add_child(instance=self.post)
        return self.post


class PagePartialWordSearchTests(SearchFixtureMixin, TestCase):
    """Поиск страниц должен работать по части слова, а не только по целому."""

    def setUp(self):
        self.create_search_fixture()

    def test_partial_word_finds_page(self):
        # «поисков» — часть слова «поисковая» из вступления
        results = list(search_pages("поисков"))
        self.assertIn(self.post, results)

    def test_partial_word_finds_page_by_title(self):
        # «работа» — часть слова «работает» из заголовка
        results = list(search_pages("работа"))
        self.assertIn(self.post, results)

    def test_full_word_still_finds_page(self):
        results = list(search_pages("поисковая"))
        self.assertIn(self.post, results)

    def test_page_found_by_document_link_text(self):
        # часть изменённого текста ссылки на документ
        results = list(search_pages("тотальн"))
        self.assertIn(self.post, results)

    def test_no_results_for_unrelated_query(self):
        self.assertEqual(list(search_pages("квантовый")), [])

    def test_empty_query_returns_nothing(self):
        self.assertEqual(list(search_pages("   ")), [])


class DocumentPartialWordSearchTests(SearchFixtureMixin, TestCase):
    """Документ должен возвращаться по части слова, а не только по полной ссылке."""

    def setUp(self):
        self.create_search_fixture()

    @staticmethod
    def _result_pks(results):
        return [item["document"].pk for item in results]

    @staticmethod
    def _result_page_pks(results, document_pk):
        return [
            page.pk
            for item in results
            if item["document"].pk == document_pk
            for page in item["pages"]
        ]

    def test_full_link_text_still_works(self):
        results = search_documents(self.link_text)
        self.assertIn(self.document.pk, self._result_pks(results))
        self.assertIn(self.post.pk, self._result_page_pks(results, self.document.pk))

    def test_partial_word_of_link_text_finds_document(self):
        results = search_documents("тотальн")
        self.assertIn(self.document.pk, self._result_pks(results))
        self.assertIn(self.post.pk, self._result_page_pks(results, self.document.pk))

    def test_partial_word_of_title_finds_document(self):
        # «итогов» — часть слова «Итоговый»
        self.assertIn(self.document.pk, self._result_pks(search_documents("итогов")))
        # «тчёт» — часть слова «отчёт»
        self.assertIn(self.document.pk, self._result_pks(search_documents("тчёт")))

    def test_partial_word_of_filename_finds_document(self):
        # «otchet» — часть пути файла documents/itogoviy_otchet.pdf
        self.assertIn(self.document.pk, self._result_pks(search_documents("otchet")))

    def test_query_with_spaces_matches_all_words(self):
        results = search_documents("изменённый тотальный")
        self.assertIn(self.document.pk, self._result_pks(results))

    def test_no_results_for_unrelated_query(self):
        self.assertEqual(search_documents("квантовый"), [])
        self.assertEqual(search_documents("  "), [])


class SearchViewTests(SearchFixtureMixin, TestCase):
    """Страница выдачи поиска (/search/)."""

    def setUp(self):
        self.create_search_fixture()

    def test_partial_word_returns_page_and_document(self):
        response = self.client.get("/search/", {"query": "тотальн"})
        self.assertEqual(response.status_code, 200)
        # документ найден по части слова изменённого текста ссылки
        self.assertContains(response, self.document.title)
        # страница с этим документом тоже показана
        self.assertContains(response, self.post.title)

    def test_partial_word_returns_page_by_content(self):
        response = self.client.get("/search/", {"query": "поисков"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.post.title)

    def test_query_is_trimmed(self):
        response = self.client.get("/search/", {"query": "  поисков  "})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.post.title)
        self.assertEqual(response.context["search_query"], "поисков")

    def test_empty_query_shows_form_only(self):
        response = self.client.get("/search/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(list(response.context["search_results"]), [])
        self.assertEqual(response.context["document_results"], [])


class StreamFieldDocumentSearchTests(SearchFixtureMixin, TestCase):
    """Ссылки на документы внутри StreamField: RichTextBlock, ListBlock, StructBlock."""

    def setUp(self):
        self.create_search_fixture()

        self.stream_link_text = "Уникальный стрим-документ"
        self.list_link_text = "элемент список"
        self.struct_link_text = "структура блок"
        doc_id = self.document.pk

        self.demo = StreamFieldDemoPage(
            title="Демо-стрим с документами",
            slug="demo-stream-docs",
            content=[
                (
                    "richtext",
                    f'<p>Врезка: <a linktype="document" id="{doc_id}">'
                    f"{self.stream_link_text}</a></p>",
                ),
                (
                    "list_items",
                    [
                        "<p>обычный пункт</p>",
                        f'<p><a linktype="document" id="{doc_id}">'
                        f"{self.list_link_text}</a></p>",
                    ],
                ),
                (
                    "info",
                    {
                        "heading": "Информация",
                        "text": (
                            f'<a linktype="document" id="{doc_id}">'
                            f"{self.struct_link_text}</a>"
                        ),
                        "tags": ["stream"],
                    },
                ),
            ],
        )
        self.homepage.add_child(instance=self.demo)

    @staticmethod
    def _result_pks(results):
        return [item["document"].pk for item in results]

    @staticmethod
    def _result_page_pks(results, document_pk):
        return [
            page.pk
            for item in results
            if item["document"].pk == document_pk
            for page in item["pages"]
        ]

    def assert_document_found(self, query):
        results = search_documents(query)
        self.assertIn(
            self.document.pk,
            self._result_pks(results),
            f"документ не найден по запросу {query!r}",
        )
        self.assertIn(
            self.demo.pk,
            self._result_page_pks(results, self.document.pk),
            f"страница с документом не найдена по запросу {query!r}",
        )

    def test_full_link_text_from_richtext_block(self):
        self.assert_document_found(self.stream_link_text)

    def test_partial_word_from_richtext_block(self):
        self.assert_document_found("уникальн")

    def test_full_link_text_from_list_block(self):
        self.assert_document_found(self.list_link_text)

    def test_partial_word_from_list_block(self):
        # «спис» — часть слова «список» (после «спис» идёт «о», а не «к»)
        self.assert_document_found("элемент спис")

    def test_full_link_text_from_struct_block(self):
        self.assert_document_found(self.struct_link_text)

    def test_partial_word_from_struct_block(self):
        self.assert_document_found("структур")

    def test_partial_word_finds_page_by_streamfield_content(self):
        results = list(search_pages("уникальн"))
        self.assertIn(self.demo, results)

    def test_full_query_finds_page_by_streamfield_content(self):
        results = list(search_pages(self.stream_link_text))
        self.assertIn(self.demo, results)



