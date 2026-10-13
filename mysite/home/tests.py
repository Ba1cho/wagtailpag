"""Тесты страниц приложения home."""
from datetime import date, time

from wagtail.models import Page, Site
from wagtail.test.utils import WagtailPageTestCase

from home.models import GroupPage, HomePage, SchedulePage, SubjectPage, TeacherPage


class SchedulePageTests(WagtailPageTestCase):
    """Проверяем модель, контекст и отрисовку страницы расписания."""

    def setUp(self):
        root_page = Page.get_first_root_node()
        Site.objects.create(
            hostname="testsite", root_page=root_page, is_default_site=True
        )
        self.homepage = HomePage(title="Home")
        root_page.add_child(instance=self.homepage)

        self.schedule = SchedulePage(title="Расписание")
        self.homepage.add_child(instance=self.schedule)

        self.subject = SubjectPage(title="Математика")
        self.homepage.add_child(instance=self.subject)

        self.teacher = TeacherPage(title="Иванов И.И.")
        self.homepage.add_child(instance=self.teacher)

        self.group = GroupPage(title="ПИ-20", curator_name="Петров П.П.")
        self.homepage.add_child(instance=self.group)
        GroupStudent = self.group.students.model
        GroupStudent.objects.create(
            group=self.group, first_name="Иван", last_name="Сидоров"
        )

    def _schedule_stream(self):
        return [
            {
                "type": "day",
                "value": {
                    "date": date(2026, 10, 12),
                    "lessons": [
                        {
                            "type": "lesson",
                            "value": {
                                "subject": self.subject.pk,
                                "teacher": self.teacher.pk,
                                "start_time": time(10, 0),
                                "end_time": time(11, 30),
                                "room": "222",
                                "groups": [self.group.pk],
                            },
                        }
                    ],
                },
            },
            {
                "type": "day",
                "value": {
                    "date": date(2026, 10, 13),
                    "lessons": [],
                },
            },
        ]

    def test_schedule_page_is_renderable(self):
        self.schedule.schedule = self._schedule_stream()
        self.schedule.save()
        self.assertPageIsRenderable(self.schedule)

    def test_template_used(self):
        response = self.client.get(self.schedule.url)
        self.assertTemplateUsed(response, "home/schedule_page.html")

    def test_context_contains_days_and_group_cards(self):
        self.schedule.schedule = self._schedule_stream()
        self.schedule.save()

        response = self.client.get(self.schedule.url)
        context = response.context

        # Две даты, занятия отсортированы по дате.
        self.assertEqual([d["date"] for d in context["days"]],
                         [date(2026, 10, 12), date(2026, 10, 13)])
        self.assertEqual(context["days"][0]["weekday_key"], "mon")
        self.assertEqual(context["days"][0]["weekday_label"], "Понедельник")

        lesson = context["days"][0]["lessons"][0]
        self.assertEqual(lesson["subject"], self.subject)
        self.assertEqual(lesson["teacher"], self.teacher)
        self.assertEqual(lesson["room"], "222")
        self.assertEqual(lesson["groups"], [self.group])
        self.assertEqual(lesson["group_names"], "ПИ-20")

        # Карточка группы содержит её занятие.
        self.assertEqual(len(context["group_cards"]), 1)
        card = context["group_cards"][0]
        self.assertEqual(card["group"], self.group)
        self.assertEqual(len(card["lessons"]), 1)
        self.assertEqual(len(card["students"]), 1)

    def test_rendered_html_contains_lesson_data(self):
        self.schedule.schedule = self._schedule_stream()
        self.schedule.save()

        response = self.client.get(self.schedule.url)
        html = response.content.decode("utf-8")

        # Фильтр по группе, таблица группы, блок таймлайна.
        self.assertIn(f'data-group="{self.group.pk}"', html)
        self.assertIn('data-date="2026-10-12"', html)
        self.assertIn("10:00–11:30", html)
        self.assertIn("Математика", html)
        self.assertIn("Иванов И.И.", html)
        self.assertIn("ауд. 222", html)


class HomeSetUpTests(WagtailPageTestCase):
    """
    Tests for basic page structure setup and HomePage creation.
    """

    def test_root_create(self):
        root_page = Page.objects.get(pk=1)
        self.assertIsNotNone(root_page)

    def test_homepage_create(self):
        root_page = Page.objects.get(pk=1)
        homepage = HomePage(title="Home")
        root_page.add_child(instance=homepage)
        self.assertTrue(HomePage.objects.filter(title="Home").exists())


class HomeTests(WagtailPageTestCase):
    """
    Tests for homepage functionality and rendering.
    """

    def setUp(self):
        """
        Create a homepage instance for testing.
        """
        root_page = Page.get_first_root_node()
        Site.objects.create(hostname="testsite", root_page=root_page, is_default_site=True)
        self.homepage = HomePage(title="Home")
        root_page.add_child(instance=self.homepage)

    def test_homepage_is_renderable(self):
        self.assertPageIsRenderable(self.homepage)

    def test_homepage_template_used(self):
        response = self.client.get(self.homepage.url)
        self.assertTemplateUsed(response, "home/home_page.html")
