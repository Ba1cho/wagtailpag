from django.core.management.base import BaseCommand

from blog.models import StreamFieldDemoPage
from home.models import HomePage


class Command(BaseCommand):
    help = (
        "Создаёт демо-страницы с StreamField, содержащим ListBlock, StructBlock, "
        "RichText и (опционально) DocumentChooserBlock."
    )

    def handle(self, *args, **options):
        home = HomePage.objects.first()
        if not home:
            self.stdout.write(
                self.style.ERROR(
                    "Домашняя страница не найдена. "
                    "Создайте HomePage (например, через миграции home приложения) и запустите команду снова."
                )
            )
            return

        # Пример контента для StreamField. Блоки совпадают с ContentStreamBlock:
        # richtext, list_items, info, document
        demo_content = [
            {
                "type": "richtext",
                "value": (
                    "<p>Добро пожаловать на демо-страницу!</p>"
                    "<p>Здесь показаны возможности StreamField: RichText, списки, "
                    "структурированные блоки.</p>"
                ),
            },
            {
                "type": "list_items",
                "value": [
                    "Первый элемент списка",
                    "Второй элемент списка",
                    "Третий элемент списка с <strong>жирным</strong> текстом",
                ],
            },
            {
                "type": "info",
                "value": {
                    "heading": "Информационный блок",
                    "text": "<p>Это структурированный блок с заголовком и текстом.</p>",
                    "tags": ["demo", "streamfield"],
                },
            },
        ]

        # Создаём несколько страниц с одинаковым демо-контентом.
        # В отдельных задачах вы можете менять контент вручную или с помощью фикстур.
        for i in range(1, 5):
            title = f"Демо-страница потока {i}"
            slug = f"demo-stream-page-{i}"
            page = StreamFieldDemoPage(
                title=title,
                slug=slug,
                content=demo_content,
            )
            home.add_child(instance=page)
            page.save_revision().publish()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Создана страница «{page.title}» "
                    f"(id={page.id}, slug={page.slug})"
                )
            )
