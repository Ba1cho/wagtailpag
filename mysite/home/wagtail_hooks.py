from django_filters import FilterSet

from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet, SnippetViewSetGroup

from home import models as home_models
from blog.models import Subject

Curator = home_models.Curator
Group = home_models.Group
Student = home_models.Student
Teacher = home_models.Teacher
Lesson = home_models.Lesson


# --- Фильтры для списков сниппетов ---

class GroupFilterSet(FilterSet):
    class Meta:
        model = Group
        fields = ["curator"]


class StudentFilterSet(FilterSet):
    class Meta:
        model = Student
        fields = ["groups"]


class LessonFilterSet(FilterSet):
    class Meta:
        model = Lesson
        fields = ["weekday", "groups", "teacher"]


# --- ViewSets: список + поиск + фильтры ---

class CuratorViewSet(SnippetViewSet):
    model = Curator
    icon = "user"
    menu_label = "Кураторы"
    add_to_admin_menu = False
    list_display = ["name", "email", "phone"]
    search_fields = ["name", "email", "phone"]


class GroupViewSet(SnippetViewSet):
    model = Group
    icon = "group"
    menu_label = "Группы"
    add_to_admin_menu = False
    list_display = ["name", "curator"]
    search_fields = ["name"]
    filterset_class = GroupFilterSet


class StudentViewSet(SnippetViewSet):
    model = Student
    icon = "user"
    menu_label = "Студенты"
    add_to_admin_menu = False
    list_display = ["last_name", "first_name"]
    search_fields = ["first_name", "last_name"]
    filterset_class = StudentFilterSet


class TeacherViewSet(SnippetViewSet):
    model = Teacher
    icon = "user"
    menu_label = "Преподаватели"
    add_to_admin_menu = False
    list_display = ["name", "email", "phone"]
    search_fields = ["name", "email", "phone"]


class SubjectViewSet(SnippetViewSet):
    model = Subject
    icon = "doc-empty-inverse"
    menu_label = "Предметы"
    add_to_admin_menu = False
    list_display = ["name", "slug"]
    search_fields = ["name"]


class LessonViewSet(SnippetViewSet):
    model = Lesson
    icon = "date"
    menu_label = "Занятия"
    add_to_admin_menu = False
    list_display = ["subject", "teacher", "weekday", "start_time", "end_time"]
    search_fields = ["subject", "teacher__name"]
    filterset_class = LessonFilterSet


# ---------------------------------------------------------------------------
# Вложенные подгруппы (внутри единой группы)
# ---------------------------------------------------------------------------

class PeopleViewSetGroup(SnippetViewSetGroup):
    """Группа «Люди»: кураторы, студенты и преподаватели."""
    menu_label = "Люди"
    menu_icon = "group"
    add_to_admin_menu = False  # без собственного пункта меню — показывается внутри «Учебный процесс»
    items = (CuratorViewSet, StudentViewSet, TeacherViewSet)


class StudyViewSetGroup(SnippetViewSetGroup):
    """Группа «Учёба»: группы, предметы и прочее по занятиям."""
    menu_label = "Учёба"
    menu_icon = "folder-open-inverse"
    add_to_admin_menu = False
    items = (GroupViewSet, SubjectViewSet, LessonViewSet)


# ---------------------------------------------------------------------------
# Единая внешняя группа сниппетов
# ---------------------------------------------------------------------------
@register_snippet
class ScheduleViewSetGroup(SnippetViewSetGroup):
    """Единая группа всех сниппетов расписания с двумя подгруппами."""
    menu_label = "Учебный процесс"
    menu_icon = "folder-open-inverse"
    menu_order = 100
    add_to_admin_menu = False
    add_to_settings_menu = True  # подменю внутри меню «Settings»
    items = (PeopleViewSetGroup, StudyViewSetGroup)

