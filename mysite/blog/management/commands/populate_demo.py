"""
Наполнение сайта демонстрационным контентом.
Запуск: python manage.py populate_demo
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from wagtail.models import Page, Site

from blog.models import BlogListingPage, BlogPostPage, ODTDocumentPage
from home.models import AboutPage, HomePage
from wagtail.documents import get_document_model


class Command(BaseCommand):
    help = "Создаёт демонстрационные страницы с RichText-контентом и документами."

    def handle(self, *args, **options):
        site = Site.objects.filter(is_default_site=True).first()
        if not site:
            self.stdout.write(self.style.ERROR("Сайт по умолчанию не найден."))
            return

        home = site.root_page.specific
        if not isinstance(home, HomePage):
            home = (
                home.get_children().type(HomePage).specific().first()
                or HomePage(title="Главная", slug="home")
            )
            if home.pk is None:
                site.root_page.add_child(instance=home)

        home.show_in_menus = True
        home.save_revision().publish()

        self._create_about(home)
        self._create_blog(home)
        self._create_odt_page()
        self._create_schedule(home)
        self._link_about(home)

        from django.core.management import call_command
        call_command("rebuild_references_index", verbosity=0)
        call_command("update_index", verbosity=0)

        self.stdout.write(self.style.SUCCESS(
            "Демо-контент создан: О нас, Статьи и документы (+3 статьи, ODT-страница)."
        ))

    def _create_about(self, home):
        about = AboutPage.objects.child_of(home).first()
        if not about:
            about = AboutPage(
                title="О колледже",
                slug="about",
                show_in_menus=True,
                intro=(
                    "<p>Мы — современное учебное заведение, которое готовит "
                    "квалифицированных специалистов в области информационных "
                    "технологий, экономики и дизайна.</p>"
                ),
                body=(
                    "<h2>Наша миссия</h2>"
                    "<p>Дать студентам практические знания и навыки, востребованные "
                    "на рынке труда, в дружелюбной и современной среде.</p>"
                    "<h2>Почему выбирают нас</h2>"
                    "<ul>"
                    "<li>Опытные преподаватели-практики;</li>"
                    "<li>Современные компьютерные лаборатории;</li>"
                    "<li>Партнёрства с IT-компаниями;</li>"
                    "<li>Богатая библиотека с электронными документами.</li>"
                    "</ul>"
                    "<blockquote>Учись сегодня — лидируй завтра!</blockquote>"
                    "<p>Подробное расписание занятий доступно в разделе "
                    "«Расписание», а учебные материалы — в разделе «Статьи».</p>"
                ),
            )
            home.add_child(instance=about)
        about.save_revision().publish()

    def _create_blog(self, home):
        listing = BlogListingPage.objects.child_of(home).first()
        if not listing:
            listing = BlogListingPage(
                title="Статьи и документы",
                slug="articles",
                show_in_menus=True,
                intro=(
                    "<p>В этом разделе публикуются статьи и учебные материалы. "
                    "К каждой статье могут быть прикреплены документы — "
                    "они участвуют в поиске по сайту.</p>"
                ),
            )
            home.add_child(instance=listing)
        listing.save_revision().publish()

        Document = get_document_model()
        document = Document.objects.first()

        posts_data = self._get_posts_data()

        for i, data in enumerate(posts_data, start=1):
            post = BlogPostPage.objects.child_of(listing).filter(title=data["title"]).first()
            if not post:
                post = BlogPostPage(
                    title=data["title"],
                    slug=f"post-{i}",
                    date=data["date"],
                    intro=data["intro"],
                    body=data["body"],
                )
                if document:
                    post.attached_documents = [("document", document)]
                listing.add_child(instance=post)
            post.show_in_menus = False
            post.save_revision().publish()

        self.listing = listing

    def _create_odt_page(self):
        if not getattr(self, "listing", None):
            return
        Document = get_document_model()
        document = Document.objects.first()
        if not document:
            return
        odt_page = ODTDocumentPage.objects.child_of(self.listing).first()
        if not odt_page:
            odt_page = ODTDocumentPage(
                title="Пример ODT-документа",
                slug="primer-odt-dokumenta",
            )
            odt_page.odt_document = [("document", document)]
            self.listing.add_child(instance=odt_page)
        odt_page.save_revision().publish()

    def _create_schedule(self, home):
        from home.models import SchedulePage

        schedule = SchedulePage.objects.child_of(home).first()
        if not schedule:
            schedule = SchedulePage(
                title="Расписание",
                slug="schedule",
                show_in_menus=True,
            )
            home.add_child(instance=schedule)
        schedule.show_in_menus = True
        schedule.save_revision().publish()

    def _link_about(self, home):
        """Добавляет в RichText страницы «О колледже» живые ссылки на разделы.

        Внутренние ссылки в RichText хранятся Wagtail'ом как
        ``<a linktype="page" id="N">Текст</a>``: href вычисляется при рендере
        по id, поэтому смена slug или перенос страницы не ломают ссылку.
        Текст же сохраняется в HTML — синхронизировать его с актуальным
        заголовком можно командой ``manage.py sync_richtext_links``.
        """
        from home.models import AboutPage, SchedulePage

        about = AboutPage.objects.child_of(home).first()
        if not about or "Полезные ссылки" in about.body:
            return
        links = []
        schedule = SchedulePage.objects.child_of(home).first()
        if schedule:
            links.append(
                f'<a linktype="page" id="{schedule.id}">расписанием занятий</a>'
            )
        if self.listing:
            links.append(
                f'<a linktype="page" id="{self.listing.id}">Статьи и документы</a>'
            )
        if links:
            about.body = about.body + "<p>Полезные ссылки: " + " и ".join(links) + ".</p>"
            about.save_revision().publish()

    def _get_posts_data(self):
        return [
            {
                "title": "Как пользоваться поиском по документам",
                "date": date.today() - timedelta(days=1),
                "intro": "<p>Новая система поиска находит не только страницы, но и прикреплённые к ним документы.</p>",
                "body": (
                    "<h2>Что ищет поисковая система</h2>"
                    "<p>Поисковый индекс охватывает:</p>"
                    "<ul>"
                    "<li>заголовки и текст всех опубликованных страниц;</li>"
                    "<li>RichText-содержимое статей и разделов;</li>"
                    "<li>название, имя файла и <strong>содержимое</strong> прикреплённых ODT-документов;</li>"
                    "<li>документы, прикреплённые в StreamField, RichText и других полях.</li>"
                    "</ul>"
                    "<h2>Как это работает</h2>"
                    "<p>Wagtail ведёт <em>ReferenceIndex</em> — индекс всех связей "
                    "между страницами и документами. Поэтому по запросу «отчёт» "
                    "вы увидите и сам файл, и страницы, где он прикреплён.</p>"
                ),
            },
            {
                "title": "Учебные материалы по программированию",
                "date": date.today() - timedelta(days=5),
                "intro": "<p>Сборник материалов для студентов первого курса направления «Информационные системы».</p>",
                "body": (
                    "<h2>Темы первого семестра</h2>"
                    "<ol>"
                    "<li>Основы алгоритмизации;</li>"
                    "<li>Введение в Python;</li>"
                    "<li>Базы данных и SQL;</li>"
                    "<li>Основы веб-разработки.</li>"
                    "</ol>"
                    "<h2>Рекомендуемая литература</h2>"
                    "<p>Полные конспекты лекций доступны в формате ODT — "
                    "прикреплённый документ можно скачать ниже.</p>"
                ),
            },
            {
                "title": "Новости кампуса: осенний семестр",
                "date": date.today() - timedelta(days=12),
                "intro": "<p>Краткий обзор событий осеннего семестра: расписания, мероприятия и обновления библиотеки.</p>",
                "body": (
                    "<p>Осенний семестр стартовал! Обновлённое расписание уже "
                    "доступно в разделе «Расписание».</p>"
                    "<h2>Мероприятия</h2>"
                    "<ul>"
                    "<li>День открытых дверей IT-лаборатории;</li>"
                    "<li>Хакатон среди студентов второго курса;</li>"
                    "<li>Экскурсия в библиотеку и цифровой архив.</li>"
                    "</ul>"
                    "<p>Следите за обновлениями — материалы мероприятий будут "
                    "публиковаться здесь вместе с документами.</p>"
                ),
            },
        ]
