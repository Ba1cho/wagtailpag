"""blog/models.py"""
from wagtail.search import index
from django.db import models
from wagtail.models import Page
from wagtail.fields import RichTextField, StreamField
from wagtail import blocks
from wagtail.admin.panels import FieldPanel
from wagtail.documents.blocks import DocumentChooserBlock
from odf.odf2xhtml import ODF2XHTML
from io import BytesIO
import re
import zipfile
from django.utils.text import slugify


# ---------------------------------------------------------------------------
# Сниппеты: предметы и прочее по занятиям (люди — в приложении home)
# ---------------------------------------------------------------------------

class Subject(models.Model):
    """Учебный предмет (сниппет)."""
    name = models.CharField("Название предмета", max_length=150, unique=True)
    slug = models.SlugField("Слаг", max_length=150, unique=True, blank=True,
                            help_text="Оставьте пустым — заполнится автоматически")
    description = models.TextField("Описание", blank=True)

    panels = [
        FieldPanel("name"),
        FieldPanel("description"),
    ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name, allow_unicode=True)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "предмет"
        verbose_name_plural = "предметы"



class ODTDocumentSearchMixin:
    """
    Общая логика для страниц с прикреплённым документом:
    извлечение текста документа для поискового индекса Wagtail.
    """

    # Метки-заглушки, которые возвращает convert_odt_to_html при ошибке
    _PLACEHOLDER_PREFIXES = ("<p>Документ", "<p>Файл", "<p>Ошибка")

    def get_document_object(self):
        """Возвращает объект wagtail.documents.Document или None."""
        if not self.odt_document:
            return None
        try:
            return self.odt_document[0].value
        except Exception:
            return None

    def get_document_text(self):
        """Текст содержимого документа (для ODT — через конвертацию в HTML)."""
        html = self.convert_odt_to_html()
        if not html or html.startswith(self._PLACEHOLDER_PREFIXES):
            return ""
        text = re.sub(r"<[^>]+>", " ", html)
        return " ".join(text.split())

    def get_document_search_text(self):
        """Название, имя файла и содержимое документа — для поиска по страницам."""
        document = self.get_document_object()
        if not document:
            return ""
        parts = [document.title or "", document.filename or ""]
        text = self.get_document_text()
        if text:
            parts.append(text)
        return " ".join(part for part in parts if part)

    search_fields = Page.search_fields + [
        index.SearchField("get_document_search_text", partial_match=True),
    ]


class ODTDocumentPage(ODTDocumentSearchMixin, Page):
    """
    Страница для загрузки ODT-файла и отображения его HTML-версии
    """
    # Поле для загрузки документа через стандартный DocumentChooser
    odt_document = StreamField(
        [
            ('document', DocumentChooserBlock(required=True)),
        ],
        use_json_field=True,
        blank=False,
    )
    
    # Кэш для хранения сконвертированного HTML
    _cached_html = None
    
    content_panels = Page.content_panels + [
        FieldPanel('odt_document'),
    ]
    
    def convert_odt_to_html(self):
        """
        Конвертирует загруженный ODT-файл в HTML с сохранением параграфов и стилей.
        """
        if self._cached_html:
            return self._cached_html
        
        # Получаем первый (и единственный) документ из StreamField
        if not self.odt_document:
            return "<p>Документ не загружен</p>"
        
        doc_block = self.odt_document[0]
        document = doc_block.value
        
        if not document or not document.file:
            return "<p>Файл документа недоступен</p>"
        
        try:
            # Читаем файл документа
            with document.file.open('rb') as odt_file:
                odt_content = odt_file.read()

            # Используем утилиту odf2xhtml: load() принимает путь или файловый объект
            from io import BytesIO

            converter = ODF2XHTML()
            converter.load(BytesIO(odt_content))
            html_output = converter.xhtml()

            # Кэшируем результат
            self._cached_html = html_output
            return html_output
            
        except Exception as e:
            # Логируем ошибку для отладки
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Ошибка конвертации ODT в HTML: {e}")
            return f"<p>Ошибка при обработке документа: {str(e)}</p>"
    
    def get_context(self, request, *args, **kwargs):
        """
        Передаем в шаблон сконвертированный HTML.
        """
        context = super().get_context(request, *args, **kwargs)
        context['document_html'] = self.convert_odt_to_html()
        return context
class BlogListingPage(ODTDocumentSearchMixin, Page):
    """
    Страница-листинг статей блога. Также может нести прикреплённый ODT-документ.
    """
    intro = RichTextField("Вступление", blank=True)

    # Поле для загрузки документа через стандартный DocumentChooser
    odt_document = StreamField(
        [
            ('document', DocumentChooserBlock(required=True)),
        ],
        use_json_field=True,
        blank=True,
        null=True,
    )

    # Кэш для хранения сконвертированного HTML
    _cached_html = None

    content_panels = Page.content_panels + [
        FieldPanel('intro'),
        FieldPanel('odt_document'),
    ]

    search_fields = Page.search_fields + [
        index.SearchField('intro'),
    ]

    parent_page_types = ['home.HomePage']
    subpage_types = ['blog.BlogPostPage', 'blog.ODTDocumentPage']

    def get_context(self, request, *args, **kwargs):
        """
        Список опубликованных статей + сконвертированный HTML документа.
        """
        context = super().get_context(request, *args, **kwargs)
        context['posts'] = (
            BlogPostPage.objects.child_of(self).live().order_by('-date')
        )
        if self.odt_document:
            context['document_html'] = self.convert_odt_to_html()
        return context

    def convert_odt_to_html(self):
        """
        Конвертирует загруженный ODT-файл в HTML с сохранением параграфов и стилей.
        """
        if self._cached_html:
            return self._cached_html

        # Получаем первый (и единственный) документ из StreamField
        if not self.odt_document:
            return "<p>Документ не загружен</p>"

        doc_block = self.odt_document[0]
        document = doc_block.value

        if not document or not document.file:
            return "<p>Файл документа недоступен</p>"

        try:
            # Читаем файл документа
            with document.file.open('rb') as odt_file:
                odt_content = odt_file.read()

            # Используем утилиту odf2xhtml: load() принимает путь или файловый объект
            from io import BytesIO

            converter = ODF2XHTML()
            converter.load(BytesIO(odt_content))
            html_output = converter.xhtml()

            # Кэшируем результат
            self._cached_html = html_output
            return html_output

        except Exception as e:
            # Логируем ошибку для отладки
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Ошибка конвертации ODT в HTML: {e}")
            return f"<p>Ошибка при обработке документа: {str(e)}</p>"


class BlogPostPage(ODTDocumentSearchMixin, Page):
    """
    Статья блога: RichText-интро, RichText-тело и (опционально)
    прикреплённые документы через DocumentChooserBlock.
    """
    date = models.DateField("Дата публикации", null=True, blank=True)
    intro = RichTextField("Вступление", blank=True)
    body = RichTextField("Текст статьи", blank=True)

    # Документы, прикреплённые к статье (участвуют в поиске)
    attached_documents = StreamField(
        [
            ('document', DocumentChooserBlock(required=True)),
        ],
        use_json_field=True,
        blank=True,
        null=True,
    )

    search_fields = Page.search_fields + [
        index.SearchField('intro'),
        index.SearchField('body'),
        index.SearchField('get_attachments_search_text', partial_match=True),
    ]

    content_panels = Page.content_panels + [
        FieldPanel('date'),
        FieldPanel('intro'),
        FieldPanel('body'),
        FieldPanel('attached_documents'),
    ]

    parent_page_types = ['blog.BlogListingPage']

    def get_document_object(self):
        """Для совместимости с поиском: у статьи несколько документов."""
        return None

    def get_attachments_search_text(self):
        """Название + имя файла каждого прикреплённого документа."""
        if not self.attached_documents:
            return ""
        parts = []
        for block in self.attached_documents:
            document = block.value
            if document:
                parts.append(document.title or "")
                parts.append(document.filename or "")
        return " ".join(p for p in parts if p)

