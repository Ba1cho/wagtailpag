"""Тесты страниц приложения home."""
from datetime import date, time

from wagtail.models import Page, Site
from wagtail.test.utils import WagtailPageTestCase

from home.models import (
    GroupModel,
    GroupPage,
    HomePage,
    SchedulePage,
    SubjectModel,
    SubjectPage,
    TeacherModel,
    TeacherPage,
)


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

        self.subject_page = SubjectPage(title="Предметы")
        self.homepage.add_child(instance=self.subject_page)
        self.subject = SubjectModel.objects.create(
            subject_page=self.subject_page, name="Математика"
        )

        self.teacher_page = TeacherPage(title="Преподаватели")
        self.homepage.add_child(instance=self.teacher_page)
        self.teacher = TeacherModel.objects.create(
            teacher_page=self.teacher_page, name="Иванов И.И."
        )

        self.group_page = GroupPage(title="Группы")
        self.homepage.add_child(instance=self.group_page)
        self.group = GroupModel.objects.create(
            group_page=self.group_page, name="ПИ-20", curator_name="Петров П.П."
        )
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


class TeacherChooserTests(WagtailPageTestCase):
    """Проверяем инлайн-преподавателей и chooser на основе ChooserViewSet."""

    def setUp(self):
        root_page = Page.get_first_root_node()
        Site.objects.create(
            hostname="testsite", root_page=root_page, is_default_site=True
        )
        self.homepage = HomePage(title="Home")
        root_page.add_child(instance=self.homepage)

        self.teacher_page = TeacherPage(title="Преподаватели")
        self.homepage.add_child(instance=self.teacher_page)
        self.teacher = TeacherModel.objects.create(
            teacher_page=self.teacher_page, name="Иванов И.И."
        )

    def test_teacher_is_inline_child_of_teacher_page(self):
        # Преподаватель доступен через related_name страницы-справочника.
        self.assertEqual(list(self.teacher_page.teachers.all()), [self.teacher])
        self.assertEqual(self.teacher.teacher_page, self.teacher_page)

    def test_chooser_block_targets_teacher_model(self):
        from home.models import TeacherChooserBlock

        block = TeacherChooserBlock(required=False, label="Преподаватель")
        block.set_name("teacher")
        # target_model хранится как строка, model_class резолвит её в класс.
        self.assertEqual(block.target_model, "home.TeacherModel")
        self.assertIs(block.model_class, TeacherModel)
        # Блок корректно деконструируется (нужно для миграций StreamField).
        path, args, kwargs = block.deconstruct()
        self.assertEqual(path, "home.models.TeacherChooserBlock")

    def test_chooser_viewset_urls_registered(self):
        from django.urls import reverse

        # ChooserViewSet зарегистрирован через wagtail_hooks и отдаёт URL.
        self.assertEqual(reverse("teacher_chooser:choose"), "/admin/teacher-chooser/")
        self.assertEqual(
            reverse("teacher_chooser:choose_results"),
            "/admin/teacher-chooser/results/",
        )

    def test_chooser_lists_teachers(self):
        self.login()
        response = self.client.get("/admin/teacher-chooser/results/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Иванов И.И.")

    def test_teacher_page_edit_shows_inline_panel(self):
        self.login()
        response = self.client.get(
            f"/admin/pages/{self.teacher_page.pk}/edit/"
        )
        self.assertEqual(response.status_code, 200)
        # Инлайн-панель преподавателей присутствует в форме редактирования.
        self.assertContains(response, "teachers")


class SubjectChooserTests(WagtailPageTestCase):
    """Проверяем инлайн-предметы и chooser на основе ChooserViewSet."""

    def setUp(self):
        root_page = Page.get_first_root_node()
        Site.objects.create(
            hostname="testsite", root_page=root_page, is_default_site=True
        )
        self.homepage = HomePage(title="Home")
        root_page.add_child(instance=self.homepage)

        self.subject_page = SubjectPage(title="Предметы")
        self.homepage.add_child(instance=self.subject_page)
        self.subject = SubjectModel.objects.create(
            subject_page=self.subject_page, name="Математика"
        )

    def test_subject_is_inline_child_of_subject_page(self):
        self.assertEqual(list(self.subject_page.subjects.all()), [self.subject])
        self.assertEqual(self.subject.subject_page, self.subject_page)

    def test_chooser_block_targets_subject_model(self):
        from home.models import SubjectChooserBlock

        block = SubjectChooserBlock(required=True, label="Предмет")
        block.set_name("subject")
        self.assertEqual(block.target_model, "home.SubjectModel")
        self.assertIs(block.model_class, SubjectModel)
        path, args, kwargs = block.deconstruct()
        self.assertEqual(path, "home.models.SubjectChooserBlock")

    def test_chooser_viewset_urls_registered(self):
        from django.urls import reverse

        self.assertEqual(reverse("subject_chooser:choose"), "/admin/subject-chooser/")
        self.assertEqual(
            reverse("subject_chooser:choose_results"),
            "/admin/subject-chooser/results/",
        )

    def test_chooser_lists_subjects(self):
        self.login()
        response = self.client.get("/admin/subject-chooser/results/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Математика")

    def test_subject_page_edit_shows_inline_panel(self):
        self.login()
        response = self.client.get(
            f"/admin/pages/{self.subject_page.pk}/edit/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "subjects")


class GroupChooserTests(WagtailPageTestCase):
    """Проверяем инлайн-группы (со студентами) и chooser на основе ChooserViewSet."""

    def setUp(self):
        root_page = Page.get_first_root_node()
        Site.objects.create(
            hostname="testsite", root_page=root_page, is_default_site=True
        )
        self.homepage = HomePage(title="Home")
        root_page.add_child(instance=self.homepage)

        self.group_page = GroupPage(title="Группы")
        self.homepage.add_child(instance=self.group_page)
        self.group = GroupModel.objects.create(
            group_page=self.group_page, name="ПИ-20", curator_name="Петров П.П."
        )
        GroupStudent = self.group.students.model
        GroupStudent.objects.create(
            group=self.group, first_name="Иван", last_name="Сидоров"
        )

    def test_group_is_inline_child_of_group_page(self):
        self.assertEqual(list(self.group_page.groups.all()), [self.group])
        self.assertEqual(self.group.group_page, self.group_page)

    def test_student_is_inline_child_of_group(self):
        # Студенты переехали со страницы на группу GroupModel.
        self.assertEqual(self.group.students.count(), 1)
        student = self.group.students.first()
        self.assertEqual(student.group, self.group)

    def test_chooser_block_targets_group_model(self):
        from home.models import GroupChooserBlock

        block = GroupChooserBlock(label="Группы")
        block.set_name("group")
        self.assertEqual(block.target_model, "home.GroupModel")
        self.assertIs(block.model_class, GroupModel)
        path, args, kwargs = block.deconstruct()
        self.assertEqual(path, "home.models.GroupChooserBlock")

    def test_chooser_viewset_urls_registered(self):
        from django.urls import reverse

        self.assertEqual(reverse("group_chooser:choose"), "/admin/group-chooser/")
        self.assertEqual(
            reverse("group_chooser:choose_results"),
            "/admin/group-chooser/results/",
        )

    def test_chooser_lists_groups(self):
        self.login()
        response = self.client.get("/admin/group-chooser/results/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "ПИ-20")

    def test_group_page_edit_shows_inline_panel(self):
        self.login()
        response = self.client.get(
            f"/admin/pages/{self.group_page.pk}/edit/"
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "groups")


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
