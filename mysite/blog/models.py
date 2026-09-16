"""blog/models.py"""
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from wagtail.models import Page

from django.db import models
from wagtail.models import Page
from wagtail.fields import StreamField
from wagtail import blocks
from wagtail.admin.panels import FieldPanel
from wagtail.documents.blocks import DocumentChooserBlock
from odf.odf2xhtml import ODF2XHTML
from io import BytesIO
import zipfile

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
            # Открываем файл документа
            with document.file.open('rb') as odt_file:
                odt_content = odt_file.read()
            
            # Используем встроенную утилиту odf2xhtml для конвертации
            # Создаем HTML-конвертер с настройками
            converter = ODF2XHTML(
                odt_content,
                # Можно передать дополнительные параметры
                # для управления выводом
            )
            
            # Получаем HTML-представление
            html_output = converter.convert()
            
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
    Страница для загрузки ODT-файла и отображения его HTML-версии
    """
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
            # Открываем файл документа
            with document.file.open('rb') as odt_file:
                odt_content = odt_file.read()
            
            # Используем встроенную утилиту odf2xhtml для конвертации
            # Создаем HTML-конвертер с настройками
            converter = ODF2XHTML(
                odt_content,
                # Можно передать дополнительные параметры
                # для управления выводом
            )
            
            # Получаем HTML-представление
            html_output = converter.convert()
            
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
