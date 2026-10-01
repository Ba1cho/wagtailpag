"""
Синхронизирует текст внутренних ссылок в RichText-полях с актуальными
заголовками страниц и документов.

В Wagtail внутренние ссылки в RichText хранятся в DB-формате:
    <a linktype="page" id="42">Старый текст</a>
    <a linktype="document" id="7">Старое имя файла</a>
href вычисляется при рендере по id (смена slug/перенос не ломают ссылку),
но ТЕКСТ ссылки сохранён в HTML и не меняется сам, когда в админке
переименовали страницу или документ. Эта команда находит такие ссылки
и заменяет их текст актуальным заголовком (у страниц — draft_title).

Использование:  python manage.py sync_richtext_links
"""

import re

from django.core.management.base import BaseCommand
from django.db import models
from wagtail.models import Page, get_page_models

from wagtail.documents import get_document_model

LINK_RE = re.compile(
    r"<a\s([^>]*?linktype=\"(?P<type>page|document)\"[^>]*?)>(?P<text>.*?)</a>",
    re.DOTALL,
)
ID_RE = re.compile(r"id=\"(\d+)\"")


def _actual_title(link_type, obj_id):
    """Актуальный заголовок цели ссылки или None, если цель удалена."""
    if link_type == "page":
        page = Page.objects.filter(id=obj_id).first()
        if page is None:
            return None
        return page.draft_title or page.title
    return get_document_model().objects.filter(id=obj_id).values_list("title", flat=True).first()


def sync_html(html):
    """Заменяет текст ссылок в html; возвращает (новый_html, количество замен)."""
    if not html or "linktype=" not in html:
        return html, 0

    replaced = 0

    def _sub(match):
        nonlocal replaced
        attrs, link_type, text = match.group(1), match.group(2), match.group(3)
        id_match = ID_RE.search(attrs)
        if not id_match:
            return match.group(0)
        title = _actual_title(link_type, int(id_match.group(1)))
        if not title or text == title:
            return match.group(0)
        replaced += 1
        return f"<a {attrs}>{title}</a>"

    return LINK_RE.sub(_sub, html), replaced


class Command(BaseCommand):
    help = (
        "Обновляет текст внутренних ссылок (linktype=\"page\"/\"document\") "
        "во всех RichText-полях до актуальных заголовков страниц и документов."
    )

    def handle(self, *args, **options):
        total = 0
        for page in Page.objects.all().specific():
            changed = False
            for field in page.specific_class._meta.get_fields():
                if not isinstance(field, models.TextField) or not hasattr(
                    page, field.attname
                ):
                    continue
                value = getattr(page, field.attname)
                new_value, count = sync_html(value)
                if count:
                    setattr(page, field.attname, new_value)
                    changed = True
                    total += count
                    self.stdout.write(
                        f"{page.title} (id={page.id}) .{field.attname}: "
                        f"обновлено ссылок: {count}"
                    )
            if changed:
                page.save()
                page.save_revision().publish()

        self.stdout.write(
            self.style.SUCCESS(f"Готово. Обновлено ссылок: {total}.")
        )
