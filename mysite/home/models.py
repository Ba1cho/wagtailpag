from django.db import models
from django.utils.translation import gettext_lazy as _

from wagtail import blocks
from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.fields import RichTextField, StreamField
from wagtail.models import Page
from wagtail.search import index

from blog.models import Subject


class Curator(models.Model):
    name = models.CharField(_("Имя"), max_length=100)
    email = models.EmailField(_("Email"), blank=True)
    phone = models.CharField(_("Телефон"), max_length=30, blank=True)

    panels = [
        FieldPanel("name"),
        MultiFieldPanel([FieldPanel("email"), FieldPanel("phone")], _("Контакты")),
    ]

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Куратор")
        verbose_name_plural = _("Кураторы")


class Group(models.Model):
    name = models.CharField(_("Название группы"), max_length=100, unique=True)
    curator = models.ForeignKey(
        Curator,
        verbose_name=_("Куратор"),
        on_delete=models.PROTECT,
        related_name="groups",
    )

    panels = [
        FieldPanel("name"),
        FieldPanel("curator"),
    ]

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Группа")
        verbose_name_plural = _("Группы")


class Student(models.Model):
    first_name = models.CharField(_("Имя"), max_length=100)
    last_name = models.CharField(_("Фамилия"), max_length=100)
    groups = models.ManyToManyField(
        Group, verbose_name=_("Группы"), related_name="students"
    )

    panels = [
        MultiFieldPanel(
            [FieldPanel("first_name"), FieldPanel("last_name")], _("ФИО")
        ),
        FieldPanel("groups"),
    ]

    def __str__(self):
        return f"{self.last_name} {self.first_name}"

    class Meta:
        verbose_name = _("Студент")
        verbose_name_plural = _("Студенты")


class Weekday(models.TextChoices):
    MONDAY = "mon", _("Понедельник")
    TUESDAY = "tue", _("Вторник")
    WEDNESDAY = "wed", _("Среда")
    THURSDAY = "thu", _("Четверг")
    FRIDAY = "fri", _("Пятница")
    SATURDAY = "sat", _("Суббота")
    SUNDAY = "sun", _("Воскресенье")


class Teacher(models.Model):
    name = models.CharField(_("ФИО преподавателя"), max_length=150)
    email = models.EmailField(_("Email"), blank=True)
    phone = models.CharField(_("Телефон"), max_length=30, blank=True)

    panels = [
        FieldPanel("name"),
        MultiFieldPanel([FieldPanel("email"), FieldPanel("phone")], _("Контакты")),
    ]

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Преподаватель")
        verbose_name_plural = _("Преподаватели")


class Lesson(models.Model):
    subject = models.ForeignKey(
        Subject,
        verbose_name=_("Предмет"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lessons",
    )
    teacher = models.ForeignKey(
        Teacher,
        verbose_name=_("Преподаватель"),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="lessons",
    )
    weekday = models.CharField(
        _("День недели"), max_length=3, choices=Weekday.choices
    )
    date = models.DateField(
        _("Конкретная дата"), null=True, blank=True,
        help_text=_("Необязательно: задайте дату, если занятие привязано к конкретному дню"),
    )
    start_time = models.TimeField(_("Начало"))
    end_time = models.TimeField(_("Конец"))
    room = models.CharField(_("Аудитория"), max_length=50, blank=True)
    groups = models.ManyToManyField(
        Group, verbose_name=_("Группы"), related_name="lessons"
    )

    panels = [
        FieldPanel("subject"),
        FieldPanel("teacher"),
        MultiFieldPanel(
            [FieldPanel("start_time"), FieldPanel("end_time")],
            _("Время занятия"),
        ),
        FieldPanel("room"),
        MultiFieldPanel(
            [FieldPanel("weekday"), FieldPanel("date")], _("День / дата")
        ),
        FieldPanel("groups"),
    ]

    def __str__(self):
        return f"{self.subject} ({self.get_weekday_display()} {self.start_time:%H:%M}-{self.end_time:%H:%M})"

    class Meta:
        verbose_name = _("Занятие")
        verbose_name_plural = _("Занятия")
        ordering = ["weekday", "start_time"]


class LessonBlock(blocks.StructBlock):
    subject = blocks.CharBlock(max_length=150, label="Предмет")
    weekday = blocks.ChoiceBlock(Weekday.choices, label="День недели")
    date = blocks.DateBlock(required=False, label="Дата")
    start_time = blocks.TimeBlock(label="Начало")
    end_time = blocks.TimeBlock(label="Конец")
    room = blocks.CharBlock(max_length=50, required=False, label="Аудитория")
    groups = blocks.CharBlock(max_length=200, required=False, label="Группы (через запятую)")


class SchedulePage(Page):
    """Страница с расписанием занятий по группам."""

    parent_page_types = ["home.HomePage"]

    # размер палитры цветов .sch-wk-g0 ... .sch-wk-g7 в шаблоне таймлайна
    WEEK_TIMELINE_COLORS = 8

    # Каждый блок — одно занятие недели.
    lessons = StreamField(
        [("lesson", LessonBlock())],
        blank=True,
        use_json_field=True,
    )

    search_fields = Page.search_fields + [
        index.SearchField("schedule_search_content"),
    ]

    content_panels = Page.content_panels + [
        FieldPanel("lessons"),
    ]

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context["schedule_groups"] = (
            Group.objects.prefetch_related("students", "lessons")
            .order_by("name")
        )
        context["weekday_choices"] = Weekday.choices
        context["weekdays"] = [
            (Weekday.MONDAY.value, Weekday.MONDAY.label),
            (Weekday.TUESDAY.value, Weekday.TUESDAY.label),
            (Weekday.WEDNESDAY.value, Weekday.WEDNESDAY.label),
            (Weekday.THURSDAY.value, Weekday.THURSDAY.label),
            (Weekday.FRIDAY.value, Weekday.FRIDAY.label),
        ]
        context["hours"] = range(6, 23)

        schedule_groups = context["schedule_groups"]
        group_index = {g.pk: i for i, g in enumerate(schedule_groups)}
        name_to_pk = {}
        for group in schedule_groups:
            for name in [n.strip() for n in group.name.split(",") if n.strip()]:
                name_to_pk[name.lower()] = group.pk

        week_lessons = []
        lessons_by_group = {}

        for block in (self.lessons or []):
            value = block.value or {}
            subject = value.get("subject") or ""
            weekday = value.get("weekday")
            date = value.get("date")
            start_time = value.get("start_time")
            end_time = value.get("end_time")
            room = value.get("room") or ""
            groups_text = value.get("groups") or ""
            groups = [g.strip() for g in str(groups_text).split(",") if g.strip()]

            lesson_groups = []
            for gname in groups:
                pk = name_to_pk.get(gname.lower())
                if pk is not None:
                    lesson_groups.append({"pk": pk, "name": gname})

            group_names = ", ".join(g["name"] for g in lesson_groups)

            lesson = {
                "weekday": weekday,
                "date": date,
                "start_time": start_time,
                "end_time": end_time,
                "room": room,
                "subject": subject,
                "teacher": value.get("teacher") or "",
                "week_group_names": group_names,
                "week_group_pks": ",".join(str(g["pk"]) for g in lesson_groups),
                "week_color": (
                    group_index.get(lesson_groups[0]["pk"], 0)
                    % self.WEEK_TIMELINE_COLORS
                    if lesson_groups
                    else self.WEEK_TIMELINE_COLORS - 1
                ),
            }
            week_lessons.append(lesson)
            for group in lesson_groups:
                lessons_by_group.setdefault(group["pk"], []).append(lesson)

        context["week_lessons"] = week_lessons

        schedule_groups_with_lessons = []
        for group in schedule_groups:
            schedule_groups_with_lessons.append(
                {"group": group, "lessons": lessons_by_group.get(group.pk, [])}
            )
        context["schedule_groups_with_lessons"] = schedule_groups_with_lessons
        return context

    def schedule_search_content(self):
        parts = [self.title]
        for block in (self.lessons or []):
            value = block.value or {}
            parts.append(
                " ".join(
                    str(value.get(field)) or ""
                    for field in (
                        "subject",
                        "teacher",
                        "weekday",
                        "date",
                        "start_time",
                        "end_time",
                        "room",
                        "groups",
                    )
                )
            )
        return " ".join(parts)


class AboutPage(Page):
    """Страница «О нас» с RichText-содержимым."""

    parent_page_types = ["home.HomePage"]
    subpage_types = []

    intro = RichTextField("Вступление", blank=True)
    body = RichTextField("Содержимое", blank=True)

    search_fields = Page.search_fields + [
        index.SearchField("intro"),
        index.SearchField("body"),
    ]

    content_panels = Page.content_panels + [
        FieldPanel("intro"),
        FieldPanel("body"),
    ]


class HomePage(Page):
    """Главная страница: показывает карточки дочерних разделов."""

    subpage_types = [
        "home.AboutPage",
        "home.SchedulePage",
        "blog.BlogListingPage",
    ]

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context["sections"] = self.get_children().live().in_menu()
        return context
