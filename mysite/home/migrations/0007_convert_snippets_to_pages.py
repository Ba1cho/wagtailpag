"""Перенос данных из сниппетов в страницы и StreamField расписания.

Старые модели (Curator, Group, Student, Teacher, Lesson, Subject) читаются
как исторические, новые страницы создаются вручную с явными полями дерева
(path/depth/url_path), как в 0002_create_homepage.
"""
import uuid
from datetime import date, timedelta

from django.db import migrations
from django.utils.text import slugify

# соответствие кодов дня недели неделям Python (mon=0 ... sun=6)
WEEKDAYS = {"mon": 0, "tue": 1, "wed": 2, "thu": 3, "fri": 4, "sat": 5, "sun": 6}


def convert(apps, schema_editor):
    db_alias = schema_editor.connection.alias

    ContentType = apps.get_model("contenttypes", "ContentType")
    Locale = apps.get_model("wagtailcore", "Locale")
    Page = apps.get_model("wagtailcore", "Page")
    SubjectPage = apps.get_model("home", "SubjectPage")
    TeacherPage = apps.get_model("home", "TeacherPage")
    GroupPage = apps.get_model("home", "GroupPage")
    GroupStudent = apps.get_model("home", "GroupStudent")
    SchedulePage = apps.get_model("home", "SchedulePage")

    # Старые (сниппетные) модели — существуют до миграции 0008
    OldTeacher = apps.get_model("home", "Teacher")
    OldGroup = apps.get_model("home", "Group")
    OldLesson = apps.get_model("home", "Lesson")

    locale = Locale.objects.using(db_alias).first()
    if locale is None:
        # крайний случай: до миграции wagtailcore.0054 локаль создаётся всегда
        locale = Locale.objects.using(db_alias).create(language_code="en-us")

    # Корень новых страниц — корневая страница сайта (Home)
    root = Page.objects.using(db_alias).filter(depth=2).order_by("path").first()
    if root is None:
        return

    ct_cache = {}

    def content_type(model):
        key = model._meta.model_name
        if key not in ct_cache:
            ct, _ = ContentType.objects.using(db_alias).get_or_create(
                app_label="home", model=key
            )
            ct_cache[key] = ct
        return ct_cache[key]

    used_slugs = set(
        Page.objects.using(db_alias)
        .filter(path__startswith=root.path, depth=root.depth + 1)
        .values_list("slug", flat=True)
    )
    seq = [root.numchild]  # счётчик suffix в path

    def make_page(Model, title, **extra):
        """Создаёт дочернюю страницу с явными полями дерева."""
        base = slugify(title, allow_unicode=True) or "page"
        slug = base
        n = 2
        while slug in used_slugs:
            slug = f"{base}-{n}"
            n += 1
        used_slugs.add(slug)
        seq[0] += 1
        page = Model(
            title=title,
            draft_title=title,
            slug=slug,
            content_type=content_type(Model),
            locale=locale,
            translation_key=uuid.uuid4(),
            path=root.path + "%04d" % seq[0],
            depth=root.depth + 1,
            numchild=0,
            url_path=root.url_path + slug + "/",
            live=True,
            has_unpublished_changes=False,
            expired=False,
            locked=False,
            show_in_menus=False,
            seo_title="",
            search_description="",
            **extra,
        )
        page.save(using=db_alias)
        return page

    # --- Предметы: создаются по мере обхода занятий (Lesson.subject — текст) ---
    subject_map = {}  # название предмета -> pk страницы предмета

    # --- Преподаватели ---
    teacher_map = {}
    for teacher in OldTeacher.objects.using(db_alias):
        page = make_page(
            TeacherPage, teacher.name, email=teacher.email, phone=teacher.phone
        )
        teacher_map[teacher.pk] = page.pk

    # --- Группы + куратор + студенты ---
    group_map = {}
    for group in OldGroup.objects.using(db_alias).select_related("curator"):
        curator = group.curator
        page = make_page(
            GroupPage,
            group.name,
            curator_name=curator.name if curator else "",
            curator_email=curator.email if curator else "",
            curator_phone=curator.phone if curator else "",
        )
        group_map[group.pk] = page.pk
        for student in group.students.all():
            GroupStudent.objects.using(db_alias).create(
                group=page,
                first_name=student.first_name,
                last_name=student.last_name,
            )

    # --- Уроки -> поток дней расписания ---
    def effective_date(lesson):
        if lesson.date:
            return lesson.date
        # урок только по дню недели: берём ближайшее наступление этого дня
        idx = WEEKDAYS[lesson.weekday]
        today = date.today()
        return today + timedelta(days=(idx - today.weekday()) % 7)

    day_map = {}  # date -> [уроки]
    for lesson in OldLesson.objects.using(db_alias).select_related("teacher"):
        day_map.setdefault(effective_date(lesson), []).append(lesson)

    stream = []
    for day in sorted(day_map):
        lesson_items = []
        for lesson in sorted(day_map[day], key=lambda l: (l.start_time, l.end_time)):
            subject_title = lesson.subject
            if subject_title not in subject_map:
                page = make_page(SubjectPage, subject_title, description="")
                subject_map[subject_title] = page.pk
            lesson_groups = list(lesson.groups.all())
            lesson_items.append(
                {
                    "type": "lesson",
                    "id": uuid.uuid4().hex,
                    "value": {
                        "subject": subject_map[subject_title],
                        "teacher": teacher_map.get(lesson.teacher_id),
                        "start_time": lesson.start_time.strftime("%H:%M:%S"),
                        "end_time": lesson.end_time.strftime("%H:%M:%S"),
                        "room": lesson.room,
                        "groups": [
                            group_map[g.pk] for g in lesson_groups if g.pk in group_map
                        ],
                    },
                }
            )
        stream.append(
            {
                "type": "day",
                "id": uuid.uuid4().hex,
                "value": {"date": day.isoformat(), "lessons": lesson_items},
            }
        )

    for schedule_page in SchedulePage.objects.using(db_alias):
        schedule_page.schedule = stream
        schedule_page.save(using=db_alias)

    # обновляем счётчик дочерних страниц у корня
    Page.objects.using(db_alias).filter(pk=root.pk).update(numchild=seq[0])


def noop(apps, schema_editor):
    """Обратный перенос не выполняется: данные страниц не конвертируются
    обратно в сниппеты (старые таблицы восстанавливаются пустыми)."""
    return


class Migration(migrations.Migration):

    dependencies = [
        ("home", "0006_grouppage_subjectpage_teacherpage_and_more"),
    ]

    operations = [
        migrations.RunPython(convert, noop),
    ]
