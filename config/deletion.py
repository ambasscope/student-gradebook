"""Explicit deletion plans for protected gradebook relationships.

Keep model-level PROTECT behavior. Only this reviewed, confirmed operation
removes dependent rows, in a transaction and in foreign-key order.
"""
from dataclasses import dataclass
import hashlib
import json

from django.core.serializers.json import DjangoJSONEncoder
from django.db.models import Q
from django.utils.translation import gettext as _

from apps.students.models import Student, StudentClass, ClassMembership
from apps.academics.models import Course, CourseUnit, CourseOffering, ClassroomEnrollment, Enrollment
from apps.assessments.models import Assignment, MarkingCategory, Criterion, Score, Attendance, ClassroomAssignmentRecord

ROOT_MODELS = {'classroom': StudentClass, 'student': Student, 'course': Course,
               'unit': CourseUnit, 'module': Assignment}
# Children first: scores protect criteria/enrolments; modules protect units/periods.
DELETE_ORDER = [Score, Attendance, ClassroomAssignmentRecord, Criterion,
                MarkingCategory, Assignment, Enrollment, ClassroomEnrollment,
                ClassMembership, Student, CourseUnit, CourseOffering, Course, StudentClass]


def label(model):
    return {StudentClass: _('Classrooms'), Student: _('Students'), Course: _('Courses'),
            CourseUnit: _('Units'), CourseOffering: _('Teaching periods'),
            Assignment: _('Modules'), MarkingCategory: _('Marking categories'),
            Criterion: _('Subcategories'), Score: _('Saved scores'),
            Attendance: _('Attendance records'), ClassroomAssignmentRecord: _('Classroom module records'),
            Enrollment: _('Student course enrolments'), ClassMembership: _('Classroom memberships'),
            ClassroomEnrollment: _('Classroom course enrolments')}[model]


def display_rows(model, ids):
    query = model.objects.filter(pk__in=ids[:50]).order_by('pk')
    related = {
        Score: ('enrollment__student', 'criterion__category__assignment'),
        Attendance: ('enrollment__student', 'assignment', 'classroom'),
        ClassroomAssignmentRecord: ('assignment', 'classroom'),
        Enrollment: ('student', 'offering__course'),
        ClassMembership: ('student', 'student_class'),
        ClassroomEnrollment: ('classroom', 'offering__course'),
        CourseOffering: ('course',), MarkingCategory: ('assignment',),
        Criterion: ('category__assignment',), Assignment: ('offering__course',),
    }
    if model in related:
        query = query.select_related(*related[model])
    result = []
    for obj in query[:50]:
        if model is Score:
            text = f'{obj.enrollment.student} · {obj.criterion.category.assignment} · {obj.criterion.name}'
        elif model is Attendance:
            text = f'{obj.enrollment.student} · {obj.assignment} · {obj.classroom}'
        elif model is ClassroomAssignmentRecord:
            text = f'{obj.assignment} · {obj.classroom}'
        elif model is Enrollment:
            text = f'{obj.student} · {obj.offering}'
        elif model is ClassMembership:
            text = f'{obj.student} · {obj.student_class}'
        elif model is ClassroomEnrollment:
            text = f'{obj.classroom} · {obj.offering}'
        else:
            text = str(obj)
        result.append(text)
    return result


@dataclass
class DeletionPlan:
    kind: str
    pk: int
    rows: dict

    @property
    def fingerprint(self):
        payload = {'kind': self.kind, 'pk': self.pk,
                   'records': {model._meta.label: values for model, values in self.rows.items()}}
        encoded = json.dumps(payload, cls=DjangoJSONEncoder, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(encoded.encode('utf-8')).hexdigest()

    @property
    def summary(self):
        groups = []
        for model, rows in reversed(list(self.rows.items())):
            if rows:
                groups.append({'label': label(model), 'count': len(rows),
                               'items': display_rows(model, [row['id'] for row in rows]),
                               'remaining': max(0, len(rows) - 50)})
        return groups

    @property
    def total(self):
        return sum(len(rows) for rows in self.rows.values())

    def delete(self):
        for model, rows in self.rows.items():
            ids = [row['id'] for row in rows]
            # Stay below SQLite's parameter limit, including large scorebooks.
            for start in range(0, len(ids), 400):
                model.objects.filter(pk__in=ids[start:start + 400]).delete()


def build_plan(kind, obj):
    queries = {model: model.objects.none() for model in DELETE_ORDER}
    queries[ROOT_MODELS[kind]] = ROOT_MODELS[kind].objects.filter(pk=obj.pk)
    if kind == 'classroom':
        # Include generated IDs whose original membership may have been removed,
        # as well as legacy/shared student records currently in this classroom.
        queries[Student] = Student.objects.filter(Q(identifier_class=obj) | Q(memberships__student_class=obj)).distinct()
        queries[ClassroomEnrollment] = ClassroomEnrollment.objects.filter(classroom=obj)
    elif kind == 'course':
        queries[CourseUnit] = CourseUnit.objects.filter(course=obj)
        queries[CourseOffering] = CourseOffering.objects.filter(course=obj)
        queries[Assignment] = Assignment.objects.filter(Q(offering__course=obj) | Q(unit__course=obj))
    elif kind == 'unit':
        queries[Assignment] = Assignment.objects.filter(unit=obj)

    student_ids = queries[Student].values('pk')
    offering_ids = queries[CourseOffering].values('pk')
    module_ids = queries[Assignment].values('pk')
    queries[Enrollment] = Enrollment.objects.filter(Q(student_id__in=student_ids) | Q(offering_id__in=offering_ids))
    enrollment_ids = queries[Enrollment].values('pk')
    queries[ClassMembership] = ClassMembership.objects.filter(student_id__in=student_ids)
    queries[ClassroomEnrollment] = ClassroomEnrollment.objects.filter(
        Q(pk__in=queries[ClassroomEnrollment].values('pk')) | Q(offering_id__in=offering_ids))
    queries[MarkingCategory] = MarkingCategory.objects.filter(assignment_id__in=module_ids)
    queries[Criterion] = Criterion.objects.filter(category__assignment_id__in=module_ids)
    queries[Score] = Score.objects.filter(Q(enrollment_id__in=enrollment_ids) | Q(criterion__category__assignment_id__in=module_ids))
    classroom_filter = Q(classroom=obj) if kind == 'classroom' else Q(pk__in=[])
    queries[Attendance] = Attendance.objects.filter(
        Q(assignment_id__in=module_ids) | Q(enrollment_id__in=enrollment_ids) | classroom_filter)
    queries[ClassroomAssignmentRecord] = ClassroomAssignmentRecord.objects.filter(
        Q(assignment_id__in=module_ids) | classroom_filter)
    rows = {model: list(queries[model].order_by('pk').values()) for model in DELETE_ORDER}
    return DeletionPlan(kind, obj.pk, rows)
