import json
from decimal import Decimal
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.db import OperationalError
from django.test import TestCase
from django.urls import reverse
from apps.academics.forms import OfferingForm
from apps.academics.models import Course, CourseOffering, Enrollment
from apps.academics.services.enrollment import sync_roster
from apps.students.models import Student, StudentClass, ClassMembership
from apps.assessments.models import Assignment, Criterion, Score
from apps.assessments.services.grading import assignment_result
from apps.assessments.services.schemes import validate_scheme, replace_scheme
from apps.assessments.services.scoring import grid_data


def scheme():
    return [
        {"code": "A", "name": "Content", "weight": "60", "items": [{"code": "Ai", "name": "Understanding", "maximum": "10"}, {"code": "Aii", "name": "Analysis", "maximum": "20"}]},
        {"code": "B", "name": "Presentation", "weight": "40", "items": [{"code": "Bi", "name": "Clarity", "maximum": "5"}]},
    ]


class AssignmentTests(TestCase):
    def setUp(self):
        self.group = StudentClass.objects.create(class_number="3A", academic_year="2026")
        self.other_group = StudentClass.objects.create(class_number="3B", academic_year="2026")
        self.course = Course.objects.create(course_id="MATH101", name="Mathematics")
        self.period = CourseOffering.objects.create(course=self.course, academic_year="2026", semester="Semester 1")
        self.period.classrooms.add(self.group, self.other_group)
        self.student = Student.objects.create(student_number="00017", student_id="S0017", full_name="Example Alice")
        self.other_student = Student.objects.create(student_number="00018", full_name="Example Bob")
        ClassMembership.objects.create(student=self.student, student_class=self.group)
        ClassMembership.objects.create(student=self.other_student, student_class=self.other_group)
        sync_roster(self.period)
        self.assignment = Assignment.objects.create(assignment_number=1, name="Homework", offering=self.period)
        replace_scheme(self.assignment, validate_scheme(scheme(), "points"))
        self.items = list(Criterion.objects.filter(category__assignment=self.assignment).order_by("pk"))
        self.enrollment = self.period.enrollments.get(student=self.student)

    def payload(self, changes=None):
        data = grid_data(Assignment.objects.get(pk=self.assignment.pk), self.group)
        return {"scheme_revision": data["scheme_revision"], "roster_signature": data["roster_signature"], "changes": changes if changes is not None else [{"enrollment_id": self.enrollment.pk, "criterion_id": self.items[0].pk, "value": "8", "previous": None}]}

    def save(self, payload=None, classroom=None):
        return self.client.post(reverse("assessments:save-scores", args=[self.assignment.pk, (classroom or self.group).pk]), data=json.dumps(payload or self.payload()), content_type="application/json")

    def test_create_assignment_and_scheme_together(self):
        response = self.client.post(reverse("assessments:add"), {"assignment_number": "2", "name": "Second homework", "offering": self.period.pk, "calculation_mode": "points", "scheme_json": json.dumps(scheme())})
        created = Assignment.objects.get(assignment_id="2026MATH10102")
        self.assertRedirects(response, reverse("assessments:detail", args=[created.pk]))
        self.assertEqual(created.categories.count(), 2)
        self.assertEqual(Criterion.objects.filter(category__assignment=created).count(), 3)

    def test_invalid_scheme_does_not_create_assignment(self):
        response = self.client.post(reverse("assessments:add"), {"assignment_number": "2", "name": "Second homework", "offering": self.period.pk, "calculation_mode": "points", "scheme_json": "[]"})
        self.assertContains(response, "Add between 1 and 30 categories")
        self.assertFalse(Assignment.objects.filter(assignment_id="2026MATH10102").exists())

    def test_assignment_id_unique(self):
        response = self.client.post(reverse("assessments:add"), {"assignment_number": "1", "name": "Duplicate", "offering": self.period.pk, "calculation_mode": "points", "scheme_json": json.dumps(scheme())})
        self.assertEqual(response.status_code, 200)
        self.assertIn("assignment_number", response.context["form"].errors)
        self.assertEqual(Assignment.objects.count(), 1)

    def test_scheme_rejects_duplicate_codes_empty_children_bad_maxima(self):
        malformed = [[], [{"code": "A", "name": "Content", "items": []}], scheme() + [scheme()[0]]]
        for maximum in ["0", "-1", "NaN", "1.005", True]:
            data = scheme(); data[0]["items"][0]["maximum"] = maximum; malformed.append(data)
        duplicate = scheme(); duplicate[0]["items"].append(duplicate[0]["items"][0]); malformed.append(duplicate)
        for data in malformed:
            with self.subTest(data=data), self.assertRaises(ValidationError):
                validate_scheme(data, "points")

    def test_weighted_categories_require_100_percent(self):
        self.assertEqual(validate_scheme(scheme(), "weighted")[0]["weight"], Decimal("60.00"))
        invalid = scheme(); invalid[1]["weight"] = "30"
        with self.assertRaisesMessage(ValidationError, "100%"):
            validate_scheme(invalid, "weighted")

    def test_grid_only_contains_selected_classroom_and_active_enrolments(self):
        response = self.client.get(reverse("assessments:scores", args=[self.assignment.pk, self.group.pk]))
        rows = response.context["grid"]["rows"]
        self.assertEqual([row["student_id"] for row in rows], ["S0017"])
        self.enrollment.is_active = False; self.enrollment.save()
        self.assertEqual(grid_data(self.assignment, self.group)["rows"], [])

    def test_unenrolled_classroom_is_not_available(self):
        group = StudentClass.objects.create(class_number="4A", academic_year="2027")
        self.assertEqual(self.client.get(reverse("assessments:scores", args=[self.assignment.pk, group.pk])).status_code, 404)
        self.assertEqual(self.save(classroom=group).status_code, 404)

    def test_save_score_and_zero(self):
        self.assertEqual(self.save().status_code, 200)
        self.assertEqual(Score.objects.get().value, Decimal("8.00"))
        self.assertIsNone(Score.objects.get().updated_by)
        change = {"enrollment_id": self.enrollment.pk, "criterion_id": self.items[0].pk, "value": "0", "previous": "8"}
        self.assertEqual(self.save(self.payload([change])).status_code, 200)
        self.assertEqual(Score.objects.get().value, Decimal("0.00"))

    def test_anonymous_score_save_still_requires_csrf(self):
        from django.test import Client
        client = Client(enforce_csrf_checks=True)
        url = reverse("assessments:save-scores", args=[self.assignment.pk, self.group.pk])
        self.assertEqual(client.post(url, data=json.dumps(self.payload()), content_type="application/json").status_code, 403)
        self.assertFalse(Score.objects.exists())

    def test_clear_score_keeps_scheme_locked(self):
        self.save()
        change = {"enrollment_id": self.enrollment.pk, "criterion_id": self.items[0].pk, "value": None, "previous": "8"}
        self.assertEqual(self.save(self.payload([change])).status_code, 200)
        self.assertFalse(Score.objects.exists())
        self.assignment.refresh_from_db()
        self.assertTrue(self.assignment.scheme_locked)

    def test_invalid_numeric_scores_rejected(self):
        for value in ["11", "-1", "NaN", "Infinity", "1.005", True, [], {}]:
            change = {"enrollment_id": self.enrollment.pk, "criterion_id": self.items[0].pk, "value": value, "previous": None}
            with self.subTest(value=value):
                self.assertEqual(self.save(self.payload([change])).status_code, 400)
                self.assertFalse(Score.objects.exists())

    def test_partial_batch_with_one_bad_cell_saves_nothing(self):
        changes = self.payload()["changes"] + [{"enrollment_id": self.enrollment.pk, "criterion_id": self.items[2].pk, "value": "6", "previous": None}]
        self.assertEqual(self.save(self.payload(changes)).status_code, 400)
        self.assertFalse(Score.objects.exists())
        self.assignment.refresh_from_db(); self.assertFalse(self.assignment.scheme_locked)

    def test_scores_from_other_class_or_assignment_rejected(self):
        other_enrollment = self.period.enrollments.get(student=self.other_student)
        other = Assignment.objects.create(assignment_id="HW99", name="Other", offering=self.period)
        replace_scheme(other, validate_scheme(scheme(), "points"))
        wrong_item = Criterion.objects.filter(category__assignment=other).first()
        for enrollment, criterion in [(other_enrollment.pk, self.items[0].pk), (self.enrollment.pk, wrong_item.pk)]:
            change = {"enrollment_id": enrollment, "criterion_id": criterion, "value": "1", "previous": None}
            self.assertEqual(self.save(self.payload([change])).status_code, 400)
        self.assertFalse(Score.objects.exists())

    def test_duplicate_cells_and_boolean_identifiers_rejected(self):
        self.assertEqual(self.save(self.payload(self.payload()["changes"] * 2)).status_code, 400)
        change = self.payload()["changes"][0]; change["enrollment_id"] = True
        self.assertEqual(self.save(self.payload([change])).status_code, 400)

    def test_old_cell_value_cannot_overwrite_new_score(self):
        stale = self.payload()
        self.save()
        stale["changes"][0]["value"] = "5"
        self.assertEqual(self.save(stale).status_code, 409)
        self.assertEqual(Score.objects.get().value, Decimal("8.00"))

    def test_roster_change_rejects_old_batch(self):
        stale = self.payload()
        new = Student.objects.create(student_number="00019", full_name="Example New")
        ClassMembership.objects.create(student=new, student_class=self.group)
        sync_roster(self.period)
        self.assertEqual(self.save(stale).status_code, 409)
        self.assertFalse(Score.objects.exists())

    def test_scheme_change_rejects_old_batch(self):
        stale = self.payload()
        replace_scheme(self.assignment, validate_scheme(scheme(), "points"), self.assignment.scheme_revision)
        self.assertEqual(self.save(stale).status_code, 409)

    def test_late_database_failure_rolls_back_scores_and_lock(self):
        with patch.object(Score.objects, "create", side_effect=OperationalError("database is locked")):
            self.assertEqual(self.save().status_code, 409)
        self.assertFalse(Score.objects.exists())
        self.assignment.refresh_from_db(); self.assertFalse(self.assignment.scheme_locked)

    def test_marked_scheme_cannot_be_replaced(self):
        self.save(); self.assignment.refresh_from_db()
        with self.assertRaisesMessage(ValidationError, "locked"):
            replace_scheme(self.assignment, validate_scheme(scheme(), "points"))
        self.assertEqual(Score.objects.count(), 1)

    def test_editing_marked_assignment_keeps_scheme_and_course(self):
        self.save(); self.assignment.refresh_from_db()
        response = self.client.post(reverse("assessments:edit", args=[self.assignment.pk]), {"assignment_number": "1", "name": "Updated homework", "information": "New notes", "offering": "9999", "calculation_mode": "weighted", "scheme_json": "[]", "scheme_revision": "0"})
        self.assertRedirects(response, reverse("assessments:detail", args=[self.assignment.pk]))
        self.assignment.refresh_from_db()
        self.assertEqual(self.assignment.name, "Updated homework")
        self.assertEqual(self.assignment.calculation_mode, "points")
        self.assertEqual(self.assignment.offering_id, self.period.pk)
        self.assertEqual(Score.objects.count(), 1)

    def test_sum_total_and_blank_progress(self):
        categories = list(self.assignment.categories.prefetch_related("criteria"))
        result = assignment_result(self.assignment, categories, {self.items[0].pk: Decimal("8"), self.items[1].pk: Decimal("12")})
        self.assertEqual(result["total"], Decimal("20.00"))
        self.assertEqual(result["marked"], 2)
        self.assertFalse(result["complete"])

    def test_weighted_total_uses_category_normalization(self):
        self.assignment.calculation_mode = "weighted"
        self.assignment.save()
        replace_scheme(self.assignment, validate_scheme(scheme(), "weighted"))
        categories = list(self.assignment.categories.prefetch_related("criteria"))
        values = {item.pk: Decimal("5") for category in categories for item in category.criteria.all()}
        result = assignment_result(self.assignment, categories, values)
        self.assertEqual(result["total"], Decimal("60.00"))
        self.assertTrue(result["complete"])

    def test_shared_student_in_two_classes_has_one_score(self):
        ClassMembership.objects.create(student=self.student, student_class=self.other_group)
        self.save()
        data = grid_data(self.assignment, self.other_group)
        row = next(row for row in data["rows"] if row["enrollment_id"] == self.enrollment.pk)
        self.assertEqual(row[f"c_{self.items[0].pk}"], "8.00")
        self.assertEqual(Score.objects.count(), 1)

    def test_teaching_period_cannot_move_year_after_marking(self):
        self.save()
        form = OfferingForm({"academic_year": "2027", "semester": "Semester 1", "classrooms": []}, instance=self.period, course=self.course)
        self.assertFalse(form.is_valid())

    def test_malformed_json_and_get_save_rejected(self):
        url = reverse("assessments:save-scores", args=[self.assignment.pk, self.group.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url, data="broken", content_type="application/json").status_code, 400)
        self.assertEqual(self.client.post(url, data="[]", content_type="application/json").status_code, 400)

    def test_model_rejects_score_for_another_course_period(self):
        other = CourseOffering.objects.create(course=self.course, academic_year="2027", semester="Semester 1")
        enrollment = Enrollment.objects.create(offering=other, student=self.student)
        with self.assertRaises(ValidationError):
            Score(enrollment=enrollment, criterion=self.items[0], value=1).full_clean()
