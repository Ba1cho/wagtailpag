from wagtail import hooks

from home.models import (
    group_chooser_viewset,
    subject_chooser_viewset,
    teacher_chooser_viewset,
)


@hooks.register("register_admin_viewset")
def register_subject_chooser_viewset():
    return subject_chooser_viewset


@hooks.register("register_admin_viewset")
def register_teacher_chooser_viewset():
    return teacher_chooser_viewset


@hooks.register("register_admin_viewset")
def register_group_chooser_viewset():
    return group_chooser_viewset
