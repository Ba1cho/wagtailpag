from django.db import models
from django.utils.translation import gettext_lazy as _

from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel

from wagtail import blocks
from wagtail.admin.panels import FieldPanel, InlinePanel, MultiFieldPanel
from wagtail.fields import StreamField
from wagtail.models import Page


# ---------------------------------------------------------------------------
# Справочные страницы (бывшие сниппеты)
# ---------------------------------------------------------------------------


class SubjectPage(Page):
    """Учебный предмет (страница-справочник)."""

    description = models.TextField(_("Описание"), blank=True)

    parent_page_types = ["home.HomePage"]
    subpage_types = []

    content_panels = Page.content_panels + [
        FieldPanel("description"),
    ]

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = _("Предмет")
        verbose_name_plural = _("Предметы")


class TeacherPage(Page):
    """Преподаватель (страница-справочник)."""

    email = models.EmailField(_("Email"), blank=True)
    phone = models.CharField(_("Телефон"), max_length=30, blank=True)

    parent_page_types = ["home.HomePage"]
    subpage_types = []

    content_panels = Page.content_panels + [
        MultiFieldPanel([FieldPanel("email"), FieldPanel("phone")], _("Контакты")),
    ]

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = _("Преподаватель")
        verbose_name_plural = _("Преподаватели")


class GroupStudent(ClusterableModel):
    """Студент, принадлежащий странице группы (инлайн-объект)."""

    group = ParentalKey(
        "home.GroupPage",
        verbose_name=_("Группа"),
        on_delete=models.CASCADE,
        related_name="students",
    )
    first_name = models.CharField(_("Имя"), max_length=100)
    last_name = models.CharField(_("Фамилия"), max_length=100)

    panels = [
        FieldPanel("first_name"),
        FieldPanel("last_name"),
    ]

    def __str__(self):
        return f"{self.last_name} {self.first_name}"

    class Meta:
        verbose_name = _("Студент")
        verbose_name_plural = _("Студенты")


class GroupPage(Page):
    """Учебная группа (страница-справочник) с куратором и студентами."""

    curator_name = models.CharField(_("Имя куратора"), max_length=100, blank=True)
    curator_email = models.EmailField(_("Email куратора"), blank=True)
    curator_phone = models.CharField(_("Телефон куратора"), max_length=30, blank=True)

    parent_page_types = ["home.HomePage"]
    subpage_types = []

    content_panels = Page.content_panels + [
        MultiFieldPanel(
            [
                FieldPanel("curator_name"),
                FieldPanel("curator_email"),
                FieldPanel("curator_phone"),
            ],
            _("Куратор"),
        ),
        InlinePanel("students", label=_("Студенты")),
    ]

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = _("Группа")
        verbose_name_plural = _("Группы")


# ---------------------------------------------------------------------------
# Блоки расписания
# ---------------------------------------------------------------------------


class LessonBlock(blocks.StructBlock):
    """Одно занятие внутри дня расписания."""

    subject = blocks.PageChooserBlock(
        page_type="home.SubjectPage", required=True, label=_("Предмет")
    )
    teacher = blocks.PageChooserBlock(
        page_type="home.TeacherPage", required=False, label=_("Преподаватель")
    )
    start_time = blocks.TimeBlock(required=True, label=_("Начало"))
    end_time = blocks.TimeBlock(required=True, label=_("Конец"))
    room = blocks.CharBlock(required=False, label=_("Аудитория"))
    groups = blocks.ListBlock(
        blocks.PageChooserBlock(page_type="home.GroupPage"),
        min_num=1,
        label=_("Группы"),
    )

    class Meta:
        icon = "time"
        label = _("Занятие")


class DayScheduleBlock(blocks.StructBlock):
    """Одна дата расписания со списком занятий."""

    date = blocks.DateBlock(required=True, label=_("Дата"))
    lessons = blocks.StreamBlock(
        [("lesson", LessonBlock())],
        label=_("Занятия"),
    )

    class Meta:
        icon = "date"
        label = _("День расписания")


# ---------------------------------------------------------------------------
# Страницы
# ---------------------------------------------------------------------------


class SchedulePage(Page):
    """Страница с расписанием: даты (StreamField) и занятия внутри каждой даты."""

    schedule = StreamField(
        [("day", DayScheduleBlock())],
        use_json_field=True,
        blank=True,
        default=list,
        verbose_name=_("Расписание"),
    )

    parent_page_types = ["home.HomePage"]
    subpage_types = []

    content_panels = Page.content_panels + [
        FieldPanel("schedule"),
    ]

    # размер палитры цветов .sch-wk-g0 ... .sch-wk-g7 в шаблоне таймлайна
    WEEK_TIMELINE_COLORS = 8

    RU_WEEKDAYS = (
        _("Понедельник"),
        _("Вторник"),
        _("Среда"),
        _("Четверг"),
        _("Пятница"),
        _("Суббота"),
        _("Воскресенье"),
    )

    # те же ключи, что и в data-атрибутах шаблонов/JS (mon = понедельник)
    WEEKDAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)

        # Группы для чипов фильтра (все опубликованные группы).
        schedule_groups = list(
            GroupPage.objects.live().public().order_by("title")
        )
        context["schedule_groups"] = schedule_groups
        context["hours"] = range(6, 23)

        # Список дней недели для фильтра: (ключ, подпись).
        context["weekdays"] = list(zip(self.WEEKDAY_KEYS, self.RU_WEEKDAYS))

        # Цвет группы в палитре таймлайна (_LEGEND_ порядок = schedule_groups).
        group_colors = {
            group.pk: index % self.WEEK_TIMELINE_COLORS
            for index, group in enumerate(schedule_groups)
        }

        # Дни расписания: отсортированы по дате, занятия внутри — по времени начала.
        days = []
        lessons_by_group = {group.pk: [] for group in schedule_groups}
        for day_block in self.schedule:
            if day_block.block_type != "day" or not day_block.value["date"]:
                continue
            date = day_block.value["date"]
            lessons = []
            for lesson_block in day_block.value["lessons"]:
                if lesson_block.block_type != "lesson":
                    continue
                value = lesson_block.value
                subject_page = value["subject"]
                teacher_page = value["teacher"]
                lesson_groups = [g for g in value["groups"] if g is not None]
                lesson = {
                    "start": value["start_time"],
                    "end": value["end_time"],
                    "start_hour": value["start_time"].hour,
                    "end_hour": value["end_time"].hour,
                    "subject": subject_page,
                    "teacher": teacher_page,
                    "room": value["room"] or "",
                    "groups": lesson_groups,
                    "group_pks": ",".join(str(g.pk) for g in lesson_groups),
                    "group_names": ", ".join(g.title for g in lesson_groups),
                    "color": (
                        group_colors.get(lesson_groups[0].pk, 0)
                        if lesson_groups
                        else self.WEEK_TIMELINE_COLORS - 1
                    ),
                    "date": date,
                    "date_iso": date.isoformat(),
                    "weekday_key": self.WEEKDAY_KEYS[date.weekday()],
                    "weekday_label": self.RU_WEEKDAYS[date.weekday()],
                }
                lessons.append(lesson)
                for group in lesson_groups:
                    lessons_by_group.setdefault(group.pk, []).append(lesson)
            lessons.sort(key=lambda lesson: (lesson["start"], lesson["end"]))
            days.append(
                {
                    "date": date,
                    "date_iso": date.isoformat(),
                    "weekday_key": self.WEEKDAY_KEYS[date.weekday()],
                    "weekday_label": self.RU_WEEKDAYS[date.weekday()],
                    "lessons": lessons,
                }
            )
        days.sort(key=lambda day: day["date"])
        context["days"] = days

        # Карточки групп: заголовок, куратор, студенты и занятия группы.
        context["group_cards"] = [
            {
                "group": group,
                "students": list(group.students.all()),
                "lessons": sorted(
                    lessons_by_group.get(group.pk, []),
                    key=lambda lesson: (
                        lesson["date"],
                        lesson["start"],
                        lesson["end"],
                    ),
                ),
            }
            for group in schedule_groups
        ]
        return context


class HomePage(Page):
    pass


