import json
from decimal import Decimal
from django.test import TestCase
from django.urls import reverse
from apps.academics.models import Course, CourseOffering
from apps.assessments.forms import AssignmentForm
from apps.assessments.models import Assignment, Criterion
from apps.assessments.services.grading import assignment_result
from apps.assessments.services.presets import default_scheme, preset_catalog
from apps.assessments.services.schemes import export_scheme, replace_scheme, validate_scheme


class MarkingPresetTests(TestCase):
    def setUp(self):
        course = Course.objects.create(course_id="MATH101", name="Mathematics")
        self.period = CourseOffering.objects.create(course=course, academic_year="2569", semester="Semester 1")

    def data(self, number=1, **changes):
        return {"assignment_number": number, "name": "Example assignment", "offering": self.period.pk, "calculation_mode": "points", "scheme_json": json.dumps(default_scheme()), **changes}

    def test_new_assignment_has_exact_thai_preset(self):
        scheme = self.client.get(reverse("assessments:add")).context["initial_scheme"]
        self.assertEqual([(c["code"], c["name"]) for c in scheme], [("K", "คะแนนชิ้นงาน"), ("P", "สมรรถนะ"), ("A", "คุณลักษณะ")])
        self.assertEqual([(i["code"], i["name"], i["maximum"]) for c in scheme for i in c["items"]], [
            ("K1", "การอภิปราย", "10"), ("K2", "ชิ้นงาน", "10"), ("K3", "การตอบคำถามในชั้นเรียน", "10"),
            ("P1", "ความสามารถในการสื่อสาร", "3"), ("P2", "ความสามารถในการคิด", "3"),
            ("A1", "รักชาติ ศาสน์ กษัตริย์", "3"), ("A2", "ใฝ่เรียนใฝ่รู้", "3"), ("A3", "มุ่งมั่นในการทำงาน", "3"),
        ])
        self.assertEqual(Assignment.objects.count(), 0)

    def test_preset_returns_independent_copies(self):
        changed = default_scheme(); changed[0]["items"][0]["maximum"] = "999"
        catalog = preset_catalog(); catalog[0]["scheme"][0]["name"] = "Changed"
        self.assertEqual(default_scheme()[0]["items"][0]["maximum"], "10")
        self.assertEqual(default_scheme()[0]["name"], "คะแนนชิ้นงาน")

    def test_saved_presets_are_separate_and_total_45(self):
        for number in [1, 2]:
            self.assertEqual(self.client.post(reverse("assessments:add"), self.data(number)).status_code, 302)
        first, second = Assignment.objects.order_by("pk")
        categories = list(first.categories.prefetch_related("criteria"))
        values = {item.pk: item.maximum for category in categories for item in category.criteria.all()}
        result = assignment_result(first, categories, values)
        self.assertEqual(result["total"], Decimal("45.00"))
        self.assertEqual(result["item_count"], 8)
        first_item = Criterion.objects.filter(category__assignment=first, code="K1").get()
        first_item.maximum = Decimal("12"); first_item.save()
        self.assertEqual(Criterion.objects.get(category__assignment=second, code="K1").maximum, Decimal("10"))

    def test_custom_scheme_is_preserved_on_edit_and_invalid_submission(self):
        custom = [{"code": "X", "name": "Custom", "items": [{"code": "X1", "name": "Custom item", "maximum": "7"}]}]
        assignment = Assignment.objects.create(assignment_number=1, name="Custom", offering=self.period)
        replace_scheme(assignment, custom)
        response = self.client.get(reverse("assessments:edit", args=[assignment.pk]))
        self.assertEqual(response.context["initial_scheme"][0]["code"], "X")
        response = self.client.post(reverse("assessments:add"), self.data(2, name="", scheme_json=json.dumps(custom)))
        self.assertEqual(response.context["initial_scheme"], custom)
        self.assertEqual(Assignment.objects.count(), 1)

    def test_locked_assignment_has_no_preset_controls_and_keeps_scheme(self):
        assignment = Assignment.objects.create(assignment_number=1, name="Locked", offering=self.period, scheme_locked=False)
        replace_scheme(assignment, [{"code": "X", "name": "Custom", "items": [{"code": "X1", "name": "Custom item", "maximum": "7"}]}])
        Assignment.objects.filter(pk=assignment.pk).update(scheme_locked=True)
        response = self.client.get(reverse("assessments:edit", args=[assignment.pk]))
        self.assertNotContains(response, 'id="load-scheme-preset"')
        self.assertNotContains(response, 'id="scheme-presets"')
        response = self.client.post(reverse("assessments:edit", args=[assignment.pk]), self.data(name="Updated name"))
        self.assertEqual(response.status_code, 302)
        assignment.refresh_from_db()
        self.assertEqual(export_scheme(assignment)[0]["code"], "X")

    def test_weighted_mode_still_requires_user_selected_percentages(self):
        form = AssignmentForm(self.data(calculation_mode="weighted"))
        self.assertFalse(form.is_valid())
        self.assertIn("100%", str(form.errors))
        scheme = default_scheme()
        for category, weight in zip(scheme, [60, 20, 20]):
            category["weight"] = str(weight)
        self.assertEqual(sum(category["weight"] for category in validate_scheme(scheme, "weighted")), Decimal("100"))
