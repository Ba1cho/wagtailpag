from datetime import date, timedelta

from django.db import models
from django.utils.translation import gettext_lazy as _

from modelcluster.fields import ParentalKey
from modelcluster.models import ClusterableModel

from wagtail import blocks
from wagtail.admin.panels import FieldPanel, InlinePanel
from wagtail.admin.viewsets.chooser import ChooserViewSet
from wagtail.fields import StreamField
from wagtail.models import Orderable, Page


# ---------------------------------------------------------------------------
# Chooser'ы справочников (предметы, преподаватели, группы) для блока
# расписания. Каждый chooser — модалка выбора соответствующей инлайн-модели.
# ---------------------------------------------------------------------------


class SubjectChooserViewSet(ChooserViewSet):
    """Chooser-модалка для выбора предмета из SubjectModel."""

    model = "home.SubjectModel"
    icon = "doc-full-inverse"
    # Виджет не нужно навязывать всем ForeignKey на SubjectModel —
    # используем его только в блоке расписания.
    register_widget = False
    choose_one_text = _("Выберите предмет")
    choose_another_text = _("Выберите другой предмет")


subject_chooser_viewset = SubjectChooserViewSet(
    "subject_chooser", url_prefix="subject-chooser"
)

SubjectChooserBlock = subject_chooser_viewset.get_block_class(
    name="SubjectChooserBlock", module_path="home.models"
)


class TeacherChooserViewSet(ChooserViewSet):
    """Chooser-модалка для выбора преподавателя из TeacherModel."""

    model = "home.TeacherModel"
    icon = "user"
    # Виджет не нужно навязывать всем ForeignKey на TeacherModel —
    # используем его только в блоке расписания.
    register_widget = False
    choose_one_text = _("Выберите преподавателя")
    choose_another_text = _("Выберите другого преподавателя")


teacher_chooser_viewset = TeacherChooserViewSet(
    "teacher_chooser", url_prefix="teacher-chooser"
)

# Блок-chooser для StreamField. module_path указывает, откуда класс можно
# импортировать при деconstruction в миграциях.
TeacherChooserBlock = teacher_chooser_viewset.get_block_class(
    name="TeacherChooserBlock", module_path="home.models"
)


class GroupChooserViewSet(ChooserViewSet):
    """Chooser-модалка для выбора группы из GroupModel."""

    model = "home.GroupModel"
    icon = "group"
    # Виджет не нужно навязывать всем ForeignKey на GroupModel —
    # используем его только в блоке расписания.
    register_widget = False
    choose_one_text = _("Выберите группу")
    choose_another_text = _("Выберите другую группу")


group_chooser_viewset = GroupChooserViewSet(
    "group_chooser", url_prefix="group-chooser"
)

GroupChooserBlock = group_chooser_viewset.get_block_class(
    name="GroupChooserBlock", module_path="home.models"
)


# ---------------------------------------------------------------------------
# Справочные страницы (бывшие сниппеты)
# ---------------------------------------------------------------------------


class SubjectModel(Orderable):
    """Учебный предмет (инлайн-объект страницы-справочника предметов)."""

    subject_page = ParentalKey(
        "home.SubjectPage",
        verbose_name=_("Страница предметов"),
        on_delete=models.CASCADE,
        related_name="subjects",
    )
    name = models.CharField(_("Название"), max_length=200)
    description = models.TextField(_("Описание"), blank=True)

    panels = [
        FieldPanel("name"),
        FieldPanel("description"),
    ]

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Предмет")
        verbose_name_plural = _("Предметы")


class SubjectPage(Page):
    """Страница-справочник со списком предметов (заполняется инлайном)."""

    parent_page_types = ["home.HomePage"]
    subpage_types = []

    content_panels = Page.content_panels + [
        InlinePanel("subjects", label=_("Предметы")),
    ]

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = _("Предметы")
        verbose_name_plural = _("Предметы")


class TeacherModel(Orderable):
    """Преподаватель (инлайн-объект страницы-справочника преподавателей)."""

    teacher_page = ParentalKey(
        "home.TeacherPage",
        verbose_name=_("Страница преподавателей"),
        on_delete=models.CASCADE,
        related_name="teachers",
    )
    name = models.CharField(_("ФИО"), max_length=200)
    email = models.EmailField(_("Email"), blank=True)
    phone = models.CharField(_("Телефон"), max_length=30, blank=True)

    panels = [
        FieldPanel("name"),
        FieldPanel("email"),
        FieldPanel("phone"),
    ]

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Преподаватель")
        verbose_name_plural = _("Преподаватели")


class TeacherPage(Page):
    """Страница-справочник со списком преподавателей (заполняется инлайном)."""

    parent_page_types = ["home.HomePage"]
    subpage_types = []

    content_panels = Page.content_panels + [
        InlinePanel("teachers", label=_("Преподаватели")),
    ]

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = _("Преподаватели")
        verbose_name_plural = _("Преподаватели")


class CuratorModel(Orderable):
    """Куратор (инлайн-объект страницы-справочника кураторов)."""

    curator_page = ParentalKey(
        "home.CuratorPage",
        verbose_name=_("Страница кураторов"),
        on_delete=models.CASCADE,
        related_name="curators",
    )
    name = models.CharField(_("ФИО"), max_length=200)
    phone = models.CharField(_("Номер телефона"), max_length=30, blank=True)

    panels = [
        FieldPanel("name"),
        FieldPanel("phone"),
    ]

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Куратор")
        verbose_name_plural = _("Кураторы")


class CuratorPage(Page):
    """Страница-справочник со списком кураторов (заполняется инлайном)."""

    parent_page_types = ["home.HomePage"]
    subpage_types = []

    content_panels = Page.content_panels + [
        InlinePanel("curators", label=_("Кураторы")),
    ]

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = _("Кураторы")
        verbose_name_plural = _("Кураторы")


class GroupStudent(ClusterableModel):
    """Студент, принадлежащий группе GroupModel (инлайн-объект)."""

    group = ParentalKey(
        "home.GroupModel",
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


class GroupModel(Orderable, ClusterableModel):
    """Учебная группа (инлайн-объект) с куратором и студентами."""

    group_page = ParentalKey(
        "home.GroupPage",
        verbose_name=_("Страница групп"),
        on_delete=models.CASCADE,
        related_name="groups",
    )
    name = models.CharField(_("Название"), max_length=200)
    curator = models.ForeignKey(
        "home.CuratorModel",
        verbose_name=_("Куратор"),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="groups",
    )

    panels = [
        FieldPanel("name"),
        FieldPanel("curator"),
        InlinePanel("students", label=_("Студенты")),
    ]

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Группа")
        verbose_name_plural = _("Группы")


class GroupPage(Page):
    """Страница-справочник со списком групп (заполняется инлайном)."""

    parent_page_types = ["home.HomePage"]
    subpage_types = []

    content_panels = Page.content_panels + [
        InlinePanel("groups", label=_("Группы")),
    ]

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = _("Группы")
        verbose_name_plural = _("Группы")


# ---------------------------------------------------------------------------
# Блоки расписания
# ---------------------------------------------------------------------------


class LessonBlock(blocks.StructBlock):
    """Одно занятие внутри дня расписания."""

    subject = SubjectChooserBlock(required=True, label=_("Предмет"))
    teacher = TeacherChooserBlock(required=False, label=_("Преподаватель"))
    start_time = blocks.TimeBlock(required=True, label=_("Начало"))
    end_time = blocks.TimeBlock(required=True, label=_("Конец"))
    room = blocks.CharBlock(required=False, label=_("Аудитория"))
    groups = blocks.ListBlock(
        GroupChooserBlock(),
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

    # родительный падеж месяцев для подписей недель («12–16 октября 2026»)
    RU_MONTHS = (
        "января",
        "февраля",
        "марта",
        "апреля",
        "мая",
        "июня",
        "июля",
        "августа",
        "сентября",
        "октября",
        "ноября",
        "декабря",
    )

    @classmethod
    def build_weeks(cls):
        """Периодичный фильтр дат: недели пн–пт текущего и следующего года.

        Каждая неделя — с понедельника по пятницу, например
        «12–16 октября 2026» (12–16, 19–23, 26–30 октября и т.д.).
        """
        today = date.today()
        year = today.year
        first_monday = date(year, 1, 1)
        first_monday -= timedelta(days=first_monday.weekday())
        last_monday = date(year + 1, 12, 31)
        last_monday -= timedelta(days=last_monday.weekday())

        weeks = []
        monday = first_monday
        while monday <= last_monday:
            friday = monday + timedelta(days=4)
            if monday.month == friday.month:
                label = (
                    f"{monday.day}–{friday.day} "
                    f"{cls.RU_MONTHS[friday.month - 1]} {friday.year}"
                )
            else:
                label = (
                    f"{monday.day} {cls.RU_MONTHS[monday.month - 1]} – "
                    f"{friday.day} {cls.RU_MONTHS[friday.month - 1]} {friday.year}"
                )
            weeks.append(
                {
                    "start_iso": monday.isoformat(),
                    "end_iso": friday.isoformat(),
                    "label": label,
                    "is_current": monday <= today <= friday,
                }
            )
            monday += timedelta(days=7)
        return weeks

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)

        # Группы для фильтра (все группы из справочника GroupModel) и кураторы:
        # сначала выбирается куратор, затем видны его группы и занятия.
        schedule_groups = list(
            GroupModel.objects.select_related("curator").order_by("name")
        )
        context["schedule_groups"] = schedule_groups
        context["curators"] = list(CuratorModel.objects.order_by("name"))
        context["schedule_weeks"] = self.build_weeks()
        context["hours"] = range(6, 23)

        # Список дней недели для фильтра: (ключ, подпись).
        context["weekdays"] = list(zip(self.WEEKDAY_KEYS, self.RU_WEEKDAYS))

        # Цвет группы в палитре таймлайна (_LEGEND_ порядок = schedule_groups).
        group_colors = {
            group.pk: index % self.WEEK_TIMELINE_COLORS
            for index, group in enumerate(schedule_groups)
        }

        # Недельный таймлайн: пять колонок пн–пт. Даты в шапке подставляет JS
        # по выбранной неделе, занятия группируются по дню недели.
        today = date.today()
        week_monday = today - timedelta(days=today.weekday())
        weekday_columns = [
            {
                "key": self.WEEKDAY_KEYS[index],
                "label": self.RU_WEEKDAYS[index],
                "date": week_monday + timedelta(days=index),
                "lessons": [],
            }
            for index in range(5)
        ]

        # Занятия: общий список для карточек + колонки таймлайна по дням недели.
        lessons_by_group = {group.pk: [] for group in schedule_groups}
        for day_block in self.schedule:
            if day_block.block_type != "day" or not day_block.value["date"]:
                continue
            day_date = day_block.value["date"]
            lessons = []
            for lesson_block in day_block.value["lessons"]:
                if lesson_block.block_type != "lesson":
                    continue
                value = lesson_block.value
                subject = value["subject"]
                teacher = value["teacher"]
                lesson_groups = [g for g in value["groups"] if g is not None]
                lesson = {
                    "start": value["start_time"],
                    "end": value["end_time"],
                    "start_hour": value["start_time"].hour,
                    "end_hour": value["end_time"].hour,
                    "subject": subject,
                    "teacher": teacher,
                    "room": value["room"] or "",
                    "groups": lesson_groups,
                    "group_pks": ",".join(str(g.pk) for g in lesson_groups),
                    "group_names": ", ".join(g.name for g in lesson_groups),
                    "color": (
                        group_colors.get(lesson_groups[0].pk, 0)
                        if lesson_groups
                        else self.WEEK_TIMELINE_COLORS - 1
                    ),
                    "date": day_date,
                    "date_iso": day_date.isoformat(),
                    "weekday_key": self.WEEKDAY_KEYS[day_date.weekday()],
                    "weekday_label": self.RU_WEEKDAYS[day_date.weekday()],
                }
                lessons.append(lesson)
                for group in lesson_groups:
                    lessons_by_group.setdefault(group.pk, []).append(lesson)
            lessons.sort(key=lambda lesson: (lesson["start"], lesson["end"]))
            # Только пн–пт попадает в недельный таймлайн (выходные не показываем).
            if day_date.weekday() < 5:
                weekday_columns[day_date.weekday()]["lessons"].extend(lessons)
        for column in weekday_columns:
            column["lessons"].sort(
                key=lambda lesson: (lesson["date"], lesson["start"], lesson["end"])
            )
        context["weekday_columns"] = weekday_columns

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


