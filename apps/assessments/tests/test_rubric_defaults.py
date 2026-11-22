import json
from decimal import Decimal
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, TestCase, TransactionTestCase
from django.urls import reverse
from apps.academics.models import Course, CourseOffering, CourseUnit, Enrollment
from apps.students.models import Student
from apps.assessments.forms import AssignmentForm
from apps.assessments.models import Assignment, Criterion, MarkingCategory, RubricPreset, RubricSettings, Score
from apps.assessments.services.evaluation import default_evaluation_rubric, validate_evaluation_rubric
from apps.assessments.services.presets import default_scheme
from apps.assessments.services.rubric_presets import current_default_evaluation_rubric, default_rubric_preset


class RubricDefaultTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(course_id="SCI", name="Science")
        self.period = CourseOffering.objects.create(course=self.course, academic_year="2569", semester="1")
        self.unit = CourseUnit.objects.create(course=self.course, unit_id="1", name="Unit one")
        self.module = Assignment.objects.create(offering=self.period, unit=self.unit, assignment_number=1, name="Existing module")
        self.category = MarkingCategory.objects.create(assignment=self.module, code="K", name="Knowledge")
        self.criterion = Criterion.objects.create(category=self.category, code="K1", name="Task", maximum=10)
        student = Student.objects.create(student_number="example-internal-id", full_name="Example student")
        self.enrollment = Enrollment.objects.create(offering=self.period, student=student)
        self.score = Score.objects.create(enrollment=self.enrollment, criterion=self.criterion, value=Decimal("8.5"))
        self.levels = validate_evaluation_rubric([
            {"minimum": "70", "label": "ผ่าน", "is_fail": False},
            {"minimum": "0", "label": "ไม่ผ่าน", "is_fail": True},
        ])
        self.preset = RubricPreset.objects.create(name="My seventy percent rubric", levels=self.levels)
        self.url = reverse("assessments:rubric-presets")

    def choose(self, key):
        response = self.client.post(self.url, {"preset_key": key})
        self.assertRedirects(response, self.url)

    def test_initial_default_is_starter_without_writing_settings(self):
        self.assertEqual(current_default_evaluation_rubric(), validate_evaluation_rubric(default_evaluation_rubric()))
        self.client.get(self.url)
        self.assertFalse(RubricSettings.objects.exists())

    def test_builtin_choice_persists_and_starts_all_library_categories(self):
        self.choose("builtin:pass-60")
        self.assertEqual(RubricSettings.objects.get().preset_key, "builtin:pass-60")
        response = self.client.get(self.url)
        self.assertEqual(response.context["default_form"]["preset_key"].value(), "builtin:pass-60")
        expected = current_default_evaluation_rubric()
        self.assertEqual(Decimal(expected[0]["minimum"]), 60)
        self.assertTrue(default_scheme())
        self.assertTrue(all(category["evaluation_rubric"] == expected for category in default_scheme()))

    def test_saved_default_is_used_by_new_module_even_when_category_has_no_explicit_rubric(self):
        self.choose(f"saved:{self.preset.pk}")
        response = self.client.post(reverse("assessments:add"), {
            "assignment_number": "2", "name": "New module", "offering": self.period.pk,
            "unit": self.unit.pk, "calculation_mode": "points",
            "scheme_json": json.dumps([{"name": "Knowledge", "items": [{"name": "Task", "maximum": "10"}]}]),
        })
        module = Assignment.objects.get(assignment_number=2)
        self.assertRedirects(response, reverse("assessments:detail", args=[module.pk]))
        self.assertEqual(module.evaluation_rubric, self.levels)
        self.assertEqual(module.categories.get().evaluation_rubric, self.levels)

    def test_existing_edit_and_copy_keep_original_rubrics_and_scores(self):
        original_module = self.module.evaluation_rubric
        original_category = self.category.evaluation_rubric
        self.choose(f"saved:{self.preset.pk}")
        self.module.refresh_from_db()
        self.category.refresh_from_db()
        self.score.refresh_from_db()
        self.assertEqual(self.module.evaluation_rubric, original_module)
        self.assertEqual(self.category.evaluation_rubric, original_category)
        self.assertEqual(self.score.value, Decimal("8.5"))
        for action in ("edit", "copy"):
            response = self.client.get(reverse(f"assessments:{action}", args=[self.module.pk]))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["initial_scheme"][0]["evaluation_rubric"], original_category)
            self.assertEqual(response.context["initial_evaluation"], original_module)
            # A newly added category uses the preference, without changing existing ones.
            self.assertEqual(response.context["default_evaluation"], self.levels)

    def test_default_resolves_latest_preset_edits_for_future_drafts(self):
        self.choose(f"saved:{self.preset.pk}")
        updated = validate_evaluation_rubric([{"minimum": 55, "label": "Achieved"}, {"minimum": 0, "label": "Fail"}])
        response = self.client.post(reverse("assessments:rubric-preset-edit", args=[self.preset.pk]), {
            "name": self.preset.name, "rubric_json": json.dumps(updated), "revision": self.preset.revision,
        })
        self.assertRedirects(response, self.url)
        form = AssignmentForm()
        self.assertEqual(json.loads(form["evaluation_json"].value()), updated)
        self.module.refresh_from_db()
        self.assertEqual(self.module.evaluation_rubric, default_evaluation_rubric())

    def test_delete_default_warns_then_falls_back_without_changing_scores(self):
        self.choose(f"saved:{self.preset.pk}")
        url = reverse("assessments:rubric-preset-delete", args=[self.preset.pk])
        self.assertContains(self.client.get(url), "This is your default rubric")
        self.assertRedirects(self.client.post(url, {"revision": self.preset.revision}), self.url)
        self.assertEqual(RubricSettings.objects.get().preset_key, "builtin:default")
        self.assertEqual(default_rubric_preset()["id"], "builtin:default")
        self.assertEqual(Score.objects.get(pk=self.score.pk).value, Decimal("8.5"))

    def test_invalid_or_missing_selection_does_not_replace_saved_preference(self):
        self.choose("builtin:thai-three")
        for key in ("saved:999999", "builtin:unknown", ""):
            response = self.client.post(self.url, {"preset_key": key})
            self.assertEqual(response.status_code, 200)
            self.assertIn("preset_key", response.context["default_form"].errors)
            self.assertEqual(RubricSettings.objects.get().preset_key, "builtin:thai-three")

    def test_get_does_not_change_default_and_post_requires_csrf(self):
        self.choose("builtin:thai-three")
        self.client.get(self.url, {"preset_key": "builtin:pass-50"})
        self.assertEqual(RubricSettings.objects.get().preset_key, "builtin:thai-three")
        self.assertEqual(Client(enforce_csrf_checks=True).post(self.url, {"preset_key": "builtin:pass-50"}).status_code, 403)

    def test_missing_or_invalid_saved_preference_falls_back_safely(self):
        for key in ("saved:999999", "saved:invalid", "builtin:missing"):
            RubricSettings.objects.update_or_create(pk=1, defaults={"preset_key": key})
            self.assertEqual(default_rubric_preset()["id"], "builtin:default")

    def test_invalid_module_rubric_shows_validation_error(self):
        response = self.client.post(reverse("assessments:add"), {
            "assignment_number": 2, "name": "Invalid", "offering": self.period.pk, "unit": self.unit.pk,
            "calculation_mode": "points", "evaluation_json": "broken JSON",
            "scheme_json": json.dumps([{"name": "Knowledge", "items": []}]),
        })
        self.assertEqual(response.status_code, 200)
        self.assertIn("evaluation_json", response.context["form"].errors)
        self.assertFalse(Assignment.objects.filter(assignment_number=2).exists())


class RubricSettingsMigrationTests(TransactionTestCase):
    def test_upgrade_adds_settings_without_rewriting_existing_modules_or_marks(self):
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        before = [(app, name) for app, name in latest if app != "assessments"] + [("assessments", "0012_marking_scheme_library")]
        executor.migrate(before)
        try:
            apps = executor.loader.project_state(before).apps
            course = apps.get_model("academics", "Course").objects.create(course_id="OLD", name="Existing course")
            period = apps.get_model("academics", "CourseOffering").objects.create(course=course, academic_year="2569", semester="1")
            module = apps.get_model("assessments", "Assignment").objects.create(offering=period, assignment_id="2569OLD01", name="Existing", evaluation_rubric=default_evaluation_rubric())
            category = apps.get_model("assessments", "MarkingCategory").objects.create(assignment=module, code="K", name="Knowledge", evaluation_rubric=default_evaluation_rubric())
            criterion = apps.get_model("assessments", "Criterion").objects.create(category=category, code="K1", name="Task", maximum=10)
            student = apps.get_model("students", "Student").objects.create(student_number="old-example", full_name="Existing example")
            enrollment = apps.get_model("academics", "Enrollment").objects.create(offering=period, student=student)
            score = apps.get_model("assessments", "Score").objects.create(enrollment=enrollment, criterion=criterion, value=Decimal("8.5"))
            MigrationExecutor(connection).migrate(latest)
            self.assertEqual(Assignment.objects.get(pk=module.pk).evaluation_rubric, default_evaluation_rubric())
            self.assertEqual(MarkingCategory.objects.get(pk=category.pk).evaluation_rubric, default_evaluation_rubric())
            self.assertEqual(Score.objects.get(pk=score.pk).value, Decimal("8.5"))
            self.assertFalse(RubricSettings.objects.exists())
        finally:
            MigrationExecutor(connection).migrate(latest)
