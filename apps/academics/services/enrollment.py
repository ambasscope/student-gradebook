"""One student roster per course teaching period, even across overlapping classes."""
from django.utils.translation import gettext
import hashlib
import json
from django.core.exceptions import ValidationError
from django.db import transaction
from apps.students.models import Student
from apps.academics.models import Enrollment


def roster_plan(offering):
    classrooms = list(offering.classrooms.all())
    if any(group.academic_year != offering.academic_year for group in classrooms):
        raise ValidationError(gettext("A classroom's academic year no longer matches this teaching period."))
    desired = set(Student.objects.filter(memberships__student_class__in=classrooms).values_list("pk", flat=True))
    active = set(offering.enrollments.filter(is_active=True).values_list("student_id", flat=True))
    payload = {"classes": sorted(group.pk for group in classrooms), "year": offering.academic_year, "semester": offering.semester, "desired": sorted(desired), "active": sorted(active)}
    fingerprint = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return {"desired": desired, "added_ids": desired - active, "removed_ids": active - desired, "fingerprint": fingerprint}


@transaction.atomic
def sync_roster(offering, expected_fingerprint=None):
    plan = roster_plan(offering)
    if expected_fingerprint is not None and expected_fingerprint != plan["fingerprint"]:
        raise ValidationError(gettext("The classroom roster changed after your preview. Review the latest changes before saving."))
    # Retain inactive rows so later assignment scores can keep their references.
    offering.enrollments.exclude(student_id__in=plan["desired"]).update(is_active=False)
    offering.enrollments.filter(student_id__in=plan["desired"]).update(is_active=True)
    known = set(offering.enrollments.values_list("student_id", flat=True))
    Enrollment.objects.bulk_create([Enrollment(offering=offering, student_id=student_id) for student_id in plan["desired"] - known])
    return plan
