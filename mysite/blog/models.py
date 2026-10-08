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



# ============================================================================
# Блоки для демо-страниц с StreamField
# ============================================================================

class ListItemBlock(blocks.RichTextBlock):
    """Один элемент списка."""
    pass


class InfoBlock(blocks.StructBlock):
    """
    Структурированный блок: заголовок, текст, теги.
    """
    heading = blocks.CharBlock(required=True, help_text="Заголовок блока")
    text = blocks.RichTextBlock(required=True, help_text="Текст блока")
    tags = blocks.ListBlock(
        blocks.CharBlock(max_length=100),
        required=False,
        help_text="Теги блока",
    )


class ContentStreamBlock(blocks.StreamBlock):
    """
    Пример стрим-поля: richtext, list, struct, документ.
    """
    richtext = blocks.RichTextBlock()
    list_items = blocks.ListBlock(ListItemBlock())
    info = InfoBlock()
    document = DocumentChooserBlock(required=False)


# ============================================================================
# Демо-страница с RichText / ListBlock / StructBlock внутри StreamField
# ============================================================================

class StreamFieldDemoPage(Page):
    """Страница для демонстрации поиска по StreamField с listblock, structblock, richtext."""

    content = StreamField(
        ContentStreamBlock(),
        use_json_field=True,
        blank=True,
        null=True,
    )

    # Указываем, что StreamField участвует в поиске
    search_fields = Page.search_fields + [
        index.SearchField('content'),
    ]

    content_panels = Page.content_panels + [
        FieldPanel('content'),
    ]

    parent_page_types = ['home.HomePage']
    subpage_types = []

    def __str__(self):
        return self.title


class ODTDocumentPage(Page):
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
class BlogListingPage(Page):
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
        index.SearchField('odt_document'),
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


class BlogPostPage(Page):
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
        index.SearchField('attached_documents'),
    ]

    content_panels = Page.content_panels + [
        FieldPanel('date'),
        FieldPanel('intro'),
        FieldPanel('body'),
        FieldPanel('attached_documents'),
    ]

    parent_page_types = ['blog.BlogListingPage']

