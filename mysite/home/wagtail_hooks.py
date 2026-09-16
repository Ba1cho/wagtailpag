from django_filters import FilterSet

from wagtail.snippets.models import register_snippet
from wagtail.snippets.views.snippets import SnippetViewSet

from home import models as home_models

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
    list_display = ["name", "email", "phone"]
    search_fields = ["name", "email", "phone"]


class GroupViewSet(SnippetViewSet):
    model = Group
    icon = "group"
    list_display = ["name", "curator"]
    search_fields = ["name"]
    filterset_class = GroupFilterSet


class StudentViewSet(SnippetViewSet):
    model = Student
    icon = "user"
    list_display = ["last_name", "first_name"]
    search_fields = ["first_name", "last_name"]
    filterset_class = StudentFilterSet


class TeacherViewSet(SnippetViewSet):
    model = Teacher
    icon = "user"
    list_display = ["name", "email", "phone"]
    search_fields = ["name", "email", "phone"]


class LessonViewSet(SnippetViewSet):
    model = Lesson
    icon = "date"
    list_display = ["subject", "teacher", "weekday", "start_time", "end_time"]
    search_fields = ["subject", "teacher__name"]
    filterset_class = LessonFilterSet


register_snippet(CuratorViewSet)
register_snippet(GroupViewSet)
register_snippet(StudentViewSet)
register_snippet(TeacherViewSet)
register_snippet(LessonViewSet)
