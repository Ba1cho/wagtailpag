"""Общие утилиты для приложения home."""

import logging

from odf.odf2xhtml import ODF2XHTML

logger = logging.getLogger(__name__)


def convert_odt_to_html(document):
    """
    Конвертирует загруженный ODT-документ в HTML.

    Единая точка конвертации для всего проекта — не дублировать логику
    в каждой модели/странице, которая работает с ODT-файлами.
    """
    if not document or not document.file:
        return ""

    try:
        with document.file.open("rb") as odt_file:
            converter = ODF2XHTML(odt_file.read())
            return converter.convert()
    except Exception as e:  # noqa: BLE001
        logger.error("ODT conversion error: %s", e)
        return f"<p>Ошибка при обработке документа: {e}</p>"
