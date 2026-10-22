"""Classroom scoring with validation, stale-cell checks, and atomic batch saves."""
from django.utils.translation import gettext
from config.numbers import compact_number
import hashlib
import json
from decimal import Decimal
from datetime import date
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from apps.academics.models import Enrollment
from apps.assessments.models import Assignment, Attendance, ClassroomAssignmentRecord, Criterion, Score
from .grading import assignment_result
from .schemes import decimal_value, scheme_ready, export_scheme
from .classroom_records import classroom_notes_data, validate_classroom_notes


class ScoreProblem(ValueError):
    def __init__(self, message, status=400):
        super().__init__(message)
        self.status = status


def parse_mark(value, maximum):
    if value is None or value == "":
        return None
    try:
        return decimal_value(value, gettext("Score"), maximum=maximum)
    except ValidationError as error:
        raise ScoreProblem(" ".join(error.messages)) from error


def classroom_enrollments(assignment, classroom):
    return assignment.offering.enrollments.filter(is_active=True, student__memberships__student_class=classroom).select_related("student").order_by("student__roll_number", "student__student_number")


def scoring_date(assignment, classroom):
    return ClassroomAssignmentRecord.objects.filter(assignment=assignment, classroom=classroom).values_list("learning_date", flat=True).first() or date.today()


def roster_signature(enrollments, day=None):
    # Detect edits to student identity/status as well as enrolment changes.
    rows = sorted((item.pk, item.student.pk, item.student.student_id, item.student.full_name,
                   item.student.roll_number, item.student.status,
                   str(item.student.resignation_date)) for item in enrollments)
    return hashlib.sha256(json.dumps([rows, str(day)]).encode()).hexdigest()


def grid_data(assignment, classroom):
    categories = list(assignment.categories.prefetch_related("criteria"))
    roster = list(classroom_enrollments(assignment, classroom))
    day = scoring_date(assignment, classroom)
    enrollments = [item for item in roster if item.student.studying_on(day)]
    criteria = [item for category in categories for item in category.criteria.all()]
    existing = {(score.enrollment_id, score.criterion_id): score.value for score in Score.objects.filter(enrollment__in=enrollments, criterion__in=criteria)}
    attendance = dict(Attendance.objects.filter(assignment=assignment, classroom=classroom, enrollment__in=enrollments).values_list("enrollment_id", "present"))
    rows = []
    for enrollment in enrollments:
        values = {item.pk: existing.get((enrollment.pk, item.pk)) for item in criteria}
        row = {"enrollment_id": enrollment.pk, "student_id": enrollment.student.student_id, "roll_number": enrollment.student.roll_number, "student_name": enrollment.student.full_name, "present": attendance.get(enrollment.pk, True)}
        row.update({f"c_{item.pk}": str(values[item.pk]) if values[item.pk] is not None else None for item in criteria})
        result = assignment_result(assignment, categories, values)
        for category in categories:
            category_result = result["categories"][category.pk]
            row[f"subtotal_{category.pk}"] = compact_number(category_result["subtotal"]) if category_result["marked"] else "—"
            row[f"evaluation_{category.pk}"] = category_result["evaluation"] or gettext("Pending")
        row["entered_total"] = compact_number(result["total"])
        rows.append(row)
    return {
        "rows": rows,
        "categories": export_scheme(assignment),
        "scheme_ready": scheme_ready(categories),
        "mode": assignment.calculation_mode,
        "scheme_revision": assignment.scheme_revision,
        "roster_signature": roster_signature(roster, day),
        "roster_date": day.isoformat(),
        "classroom_notes": classroom_notes_data(assignment, classroom),
    }


@transaction.atomic
def save_scores(assignment_pk, classroom_pk, payload, user=None):
    assignment = Assignment.objects.select_for_update().select_related("offering").get(pk=assignment_pk)
    if not assignment.offering.classrooms.filter(pk=classroom_pk).exists():
        raise ScoreProblem(gettext("This classroom is not enrolled in the module's course."), 404)
    if not isinstance(payload, dict):
        raise ScoreProblem(gettext("Send a score batch containing changes."))
    if type(payload.get("scheme_revision")) is not int or payload["scheme_revision"] != assignment.scheme_revision:
        raise ScoreProblem(gettext("The marking scheme changed. Reload the page before saving."), 409)
    enrollments = list(assignment.offering.enrollments.filter(is_active=True, student__memberships__student_class_id=classroom_pk).select_related("student"))
    day = scoring_date(assignment, classroom_pk)
    if payload.get("roster_signature") != roster_signature(enrollments, day):
        raise ScoreProblem(gettext("The classroom roster changed. Reload the page before saving."), 409)
    changes, attendance_changes = payload.get("changes", []), payload.get("attendance_changes", [])
    if not isinstance(changes, list) or not isinstance(attendance_changes, list) or len(changes) + len(attendance_changes) > 10000:
        raise ScoreProblem(gettext("Save at most 10,000 cell changes at a time."))
    notes = None
    record = None
    if "classroom_notes" in payload:
        try:
            notes = validate_classroom_notes(payload["classroom_notes"])
        except ValidationError as error:
            raise ScoreProblem(" ".join(error.messages)) from error
        record = ClassroomAssignmentRecord.objects.select_for_update().filter(assignment=assignment, classroom_id=classroom_pk).first()
        if notes["revision"] != (record.revision if record else 0):
            raise ScoreProblem(gettext("Classroom comments changed in another window. Reload before saving."), 409)
    if not changes and not attendance_changes and notes is None:
        return {"saved": 0, "attendance_saved": 0, "notes_saved": 0, "scheme_locked": assignment.scheme_locked}
    if notes is None:
        record = ClassroomAssignmentRecord.objects.filter(assignment=assignment, classroom_id=classroom_pk).first()
        if not record or record.module_status not in ClassroomAssignmentRecord.Completion.values:
            raise ScoreProblem(gettext("Choose Module completed or Module uncompleted before saving."))
    if changes and not scheme_ready(list(assignment.categories.prefetch_related("criteria"))):
        raise ScoreProblem(gettext("Add at least one subcategory to every marking category before entering scores."))
    target_day = (notes["learning_date"] or date.today()) if notes is not None else day
    allowed = {item.pk: item for item in enrollments if item.student.studying_on(target_day)}
    ineligible = {item.pk for item in enrollments if not item.student.studying_on(target_day)}
    for change in changes + attendance_changes:
        if isinstance(change, dict) and type(change.get("enrollment_id")) is int and change["enrollment_id"] in ineligible:
            raise ScoreProblem(gettext("This student resigned on or before the teaching date. Save the teaching date separately, then reload the roster before entering scores."), 409)
    criteria = {item.pk: item for item in Criterion.objects.filter(category__assignment=assignment)}
    stored = {(score.enrollment_id, score.criterion_id): score for score in Score.objects.filter(enrollment_id__in=allowed, criterion_id__in=criteria)}
    prepared, seen = [], set()
    for change in changes:
        if not isinstance(change, dict):
            raise ScoreProblem(gettext("Each changed cell must identify a student and scoring subcategory."))
        enrollment_id, criterion_id = change.get("enrollment_id"), change.get("criterion_id")
        if type(enrollment_id) is not int or type(criterion_id) is not int or enrollment_id not in allowed or criterion_id not in criteria:
            raise ScoreProblem(gettext("A changed cell does not belong to this classroom and module."))
        key = (enrollment_id, criterion_id)
        if key in seen:
            raise ScoreProblem(gettext("The same score cell appears more than once in this batch."))
        seen.add(key)
        if "value" not in change or "previous" not in change:
            raise ScoreProblem(gettext("Each changed cell needs its new and previous values."))
        value = parse_mark(change["value"], criteria[criterion_id].maximum)
        previous = parse_mark(change["previous"], Decimal("999999.99"))
        old = stored.get(key)
        if previous != (old.value if old else None):
            raise ScoreProblem(gettext("Student %(student)s has a score changed in another window. Reload before saving.") % {"student": allowed[enrollment_id].student.full_name}, 409)
        prepared.append((key, old, value))
    stored_attendance = {item.enrollment_id: item for item in Attendance.objects.filter(assignment=assignment, classroom_id=classroom_pk, enrollment_id__in=allowed)}
    prepared_attendance, seen_attendance = [], set()
    for change in attendance_changes:
        if not isinstance(change, dict) or type(change.get("enrollment_id")) is not int or change["enrollment_id"] not in allowed:
            raise ScoreProblem(gettext("An attendance change does not belong to this classroom and module."))
        enrollment_id = change["enrollment_id"]
        if enrollment_id in seen_attendance:
            raise ScoreProblem(gettext("The same student appears more than once in the attendance changes."))
        seen_attendance.add(enrollment_id)
        if type(change.get("value")) is not bool or type(change.get("previous")) is not bool:
            raise ScoreProblem(gettext("Attendance must be checked or unchecked."))
        old = stored_attendance.get(enrollment_id)
        if change["previous"] != (old.present if old else True):
            raise ScoreProblem(gettext("Attendance changed in another window. Reload before saving."), 409)
        prepared_attendance.append((enrollment_id, old, change["value"]))
    should_lock = assignment.scheme_locked or any(value is not None for _, _, value in prepared)
    written = Assignment.objects.filter(pk=assignment.pk, score_revision=assignment.score_revision, scheme_revision=assignment.scheme_revision).update(score_revision=F("score_revision") + 1, scheme_locked=should_lock)
    if not written:
        raise ScoreProblem(gettext("The module changed during this save. Try again."), 409)
    for (enrollment_id, criterion_id), old, value in prepared:
        if value is None:
            if old:
                old.delete()
        elif old:
            old.value, old.updated_by = value, user
            old.save(update_fields=["value", "updated_by", "updated_at"])
        else:
            Score.objects.create(enrollment_id=enrollment_id, criterion_id=criterion_id, value=value, updated_by=user)
    for enrollment_id, old, present in prepared_attendance:
        if old:
            old.present = present
            old.save(update_fields=["present", "updated_at"])
        else:
            Attendance.objects.create(assignment=assignment, classroom_id=classroom_pk, enrollment_id=enrollment_id, present=present)
    if notes is not None:
        values = {field: notes[field] for field in ["problem", "suggestion", "problem_choices", "suggestion_choices", "suggestion_details", "module_status", "learning_date"]}
        if record:
            for field, value in values.items():
                setattr(record, field, value)
            record.revision += 1
            record.save(update_fields=[*values, "revision", "updated_at"])
        else:
            record = ClassroomAssignmentRecord.objects.create(assignment=assignment, classroom_id=classroom_pk, revision=1, **values)
        notes["revision"] = record.revision
    return {"saved": len(prepared), "attendance_saved": len(prepared_attendance), "notes_saved": int(notes is not None), "classroom_notes": notes, "scheme_locked": should_lock, "reload_required": target_day != day}
