"""Переиспользуемые блоки StreamField.

Определяются один раз и подключаются к любой странице в любом количестве
и в любых секциях. Данные на каждой странице — свои (каждое поле StreamField
хранит свою копию в базе).
"""

from wagtail import blocks
from wagtail.documents.blocks import DocumentChooserBlock
from wagtail.images.blocks import ImageChooserBlock


class DocumentBlock(blocks.StructBlock):
    """Один блок документа: файл + необязательный заголовок/описание."""

    document = DocumentChooserBlock(required=True, label="Документ")
    title = blocks.CharBlock(required=False, label="Заголовок")
    description = blocks.TextBlock(required=False, label="Описание")

    class Meta:
        icon = "doc-full"
        label = "Документ"


class QuoteBlock(blocks.StructBlock):
    """Одна цитата."""

    text = blocks.TextBlock(required=True, label="Текст цитаты")
    author = blocks.CharBlock(required=False, label="Автор")
    source = blocks.CharBlock(required=False, label="Источник")

    class Meta:
        icon = "openquote"
        label = "Цитата"


class CardBlock(blocks.StructBlock):
    """Одна карточка."""

    heading = blocks.CharBlock(required=True, label="Заголовок")
    text = blocks.TextBlock(required=False, label="Текст")
    image = ImageChooserBlock(required=False, label="Картинка")
    link_url = blocks.URLBlock(required=False, label="Ссылка")

    class Meta:
        icon = "site"
        label = "Карточка"


class ContentBlock(blocks.StructBlock):
    """Переиспользуемый модуль: изображение + заголовок + описание (rich text).

    Один шаблон (home/includes/blocks/content_block.html) используется на всех
    страницах и в любой секции — в него попадает разное изображение, заголовок
    и текст.
    """

    image = ImageChooserBlock(required=False, label="Изображение")
    heading = blocks.CharBlock(required=True, label="Заголовок")
    description = blocks.RichTextBlock(required=False, label="Описание")

    class Meta:
        icon = "image"
        template = "home/includes/blocks/content_block.html"
        label = "Заголовок + картинка + текст"


class AccordionItemBlock(blocks.StructBlock):
    """Одна вкладка аккордеона: заголовок + своё содержимое (другие блоки).

    Поле ``content`` определено ниже в теле класса (без аккордеона, чтобы
    избежать циклической ссылки при импорте модуля). Само вложение аккордеона
    в аккордеон добавляется после определения ``AccordionBlock``.
    """

    title = blocks.CharBlock(required=True, label="Заголовок вкладки")
    content = blocks.StreamBlock(
        [
            ("content", ContentBlock()),
            ("document", DocumentBlock()),
            ("quote", QuoteBlock()),
            ("card", CardBlock()),
        ],
        label="Содержимое вкладки",
    )

    class Meta:
        icon = "plus"
        label = "Элемент аккордеона"


class AccordionBlock(blocks.StructBlock):
    """Аккордеон: список вкладок. Внутри каждой вкладки — свои блоки контента,
    в том числе вложенный аккордеон."""

    items = blocks.StreamBlock(
        [("accordion_item", AccordionItemBlock())],
        label="Вкладки аккордеона",
    )

    class Meta:
        icon = "arrow-down"
        template = "home/includes/blocks/accordion.html"
        label = "Аккордеон"

    def check(self, **kwargs):
        # Аккордеон может содержать вложенный аккордеон (через content → accordion),
        # поэтому обычная рекурсивная проверка Wagtail уходит в бесконечную
        # рекурсию. Выполняем только базовую проверку блока без обхода потомков.
        from wagtail.blocks.base import Block

        return Block.check(self, **kwargs)

    def deconstruct_with_lookup(self, lookup):
        # Рекурсивный блок: не обходим дочерние блоки (иначе makemigrations
        # уходит в бесконечную рекурсию).
        return ("home.blocks.AccordionBlock", [], {"child_blocks": []})


# Рекурсивная вложенность: внутри содержимого вкладки аккордеона может быть
# ещё один аккордеон (и любой другой блок со страницы). Добавляем после того,
# как оба класса определены. set_name обязателен, иначе Wagtail ругается на
# пустое имя блока (wagtailcore.E001).
accordion_block = AccordionBlock()
accordion_block.set_name("accordion")
content_block = AccordionItemBlock.declared_blocks["content"]
content_block.base_blocks["accordion"] = accordion_block
content_block.child_blocks["accordion"] = accordion_block
