from django.db import models
from django.utils.translation import gettext_lazy as _

from wagtail.admin.panels import FieldPanel, MultiFieldPanel
from wagtail.models import Page


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
    subject = models.CharField(_("Предмет"), max_length=150)
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


class SchedulePage(Page):
    """Страница с расписанием занятий по группам."""

    parent_page_types = ["home.HomePage"]

    def get_context(self, request, *args, **kwargs):
        context = super().get_context(request, *args, **kwargs)
        context["schedule_groups"] = (
            Group.objects.prefetch_related("students", "lessons")
            .order_by("name")
        )
        context["weekday_choices"] = Weekday.choices
        context["hours"] = range(6, 23)
        return context


class HomePage(Page):
    pass
