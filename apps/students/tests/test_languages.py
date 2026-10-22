import gettext as python_gettext
from unittest.mock import patch
from django.conf import settings
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import translation
from apps.students.models import StudentClass, Student, ClassMembership
from apps.academics.models import Course, CourseOffering
from apps.assessments.models import Assignment
from apps.assessments.services.presets import default_scheme
from apps.assessments.services.schemes import replace_scheme
from config.identifiers import student_identifier, assignment_identifier


class LanguageTests(TestCase):
    def tearDown(self):
        translation.activate("en")

    def switch(self, language, next_url="/"):
        return self.client.post(reverse("set_language"), {"language": language, "next": next_url})

    def test_switch_persists_cookie_and_returns_to_current_page(self):
        target = reverse("students:index") + "?year=2569"
        response = self.switch("th", target)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, target)
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, "th")
        self.assertContains(self.client.get(target), '<html lang="th">')
        with translation.override("th"):
            expected = translation.gettext("Overview")
        self.assertContains(self.client.get(reverse("home")), expected)
        self.switch("en")
        self.assertContains(self.client.get(reverse("home")), "Overview")

    def test_browser_language_and_blank_thai_entries_fall_back_correctly(self):
        response = self.client.get(reverse("home"), HTTP_ACCEPT_LANGUAGE="th")
        with translation.override("th"):
            expected = translation.gettext("Your students, coursework, and results in one place.")
            self.assertEqual(translation.gettext("Untranslated fallback test phrase"), "Untranslated fallback test phrase")
        self.assertContains(response, expected)

    def test_language_selection_is_protected_by_csrf(self):
        client = Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(reverse("set_language"), {"language": "th"}).status_code, 403)
        client.get(reverse("home"))
        response = client.post(reverse("set_language"), {"language": "th", "next": "/", "csrfmiddlewaretoken": client.cookies["csrftoken"].value})
        self.assertEqual(response.cookies[settings.LANGUAGE_COOKIE_NAME].value, "th")

    def test_external_redirect_and_unsupported_language_are_rejected(self):
        response = self.switch("th", "https://example.invalid/")
        self.assertEqual(response.url, "/")
        response = self.switch("xx")
        self.assertNotIn(settings.LANGUAGE_COOKIE_NAME, response.cookies)

    def test_python_labels_and_untranslated_validation_message(self):
        self.switch("th")
        response = self.client.get(reverse("students:add"))
        with translation.override("th"):
            expected = translation.gettext("Student name")
        self.assertContains(response, expected)
        with translation.override("th"):
            from config.identifiers import local_number
            from django.core.exceptions import ValidationError
            expected = translation.gettext("%(label)s: enter a whole number from 1 to 99.") % {"label": translation.gettext("Number")}
            with self.assertRaisesMessage(ValidationError, expected):
                local_number(100)

    def test_javascript_catalog_contains_examples_and_named_placeholders(self):
        self.switch("th")
        response = self.client.get(reverse("javascript-catalog"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "django.catalog")
        self.assertContains(response, "gettext")
        with (settings.BASE_DIR / "locale/th/LC_MESSAGES/djangojs.mo").open("rb") as stream:
            catalog = python_gettext.GNUTranslations(stream)
        self.assertIn("2", catalog.gettext("Saved %(count)s score change(s).") % {"count": 2})

    def test_language_does_not_change_identifiers_or_preset_data(self):
        english = default_scheme()
        with translation.override("th"):
            self.assertEqual(default_scheme(), english)
            self.assertEqual(student_identifier("2569", "4/1", 3), "256940103")
            self.assertEqual(assignment_identifier("2569", "MATH101", 3), "2569MATH10103")

    def test_translated_assignment_form_can_create_records(self):
        course = Course.objects.create(course_id="MATH101", name="Mathematics as entered")
        period = CourseOffering.objects.create(course=course, academic_year="2569", semester="Semester 1")
        self.switch("th")
        response = self.client.get(reverse("assessments:add"))
        with translation.override("th"):
            expected = translation.gettext("Save assignment")
        self.assertContains(response, expected)
        self.assertContains(response, "Mathematics as entered")
        response = self.client.post(reverse("assessments:add"), {"assignment_number": 1, "name": "ชื่องานที่ผู้ใช้ป้อน", "offering": period.pk, "calculation_mode": "points", "scheme_json": response.context["form"]["scheme_json"].value()})
        self.assertEqual(response.status_code, 302)
        assignment = Assignment.objects.get()
        self.assertEqual(assignment.assignment_id, "2569MATH10101")
        self.assertEqual(assignment.name, "ชื่องานที่ผู้ใช้ป้อน")

    def test_all_templates_compile_and_scoring_renders_in_both_languages(self):
        from django.template.loader import get_template
        for root in [settings.BASE_DIR / "templates", settings.BASE_DIR / "apps"]:
            for path in root.rglob("*.html"):
                if "templates" in path.parts:
                    name = str(path).split("/templates/", 1)[1]
                    get_template(name)
        group = StudentClass.objects.create(class_number="4/1", academic_year="2569")
        student = Student.objects.create(identifier_class=group, roll_number=3, full_name="Example Student")
        ClassMembership.objects.create(student=student, student_class=group)
        course = Course.objects.create(course_id="MATH101", name="Mathematics")
        period = CourseOffering.objects.create(course=course, academic_year="2569", semester="Semester 1")
        period.classrooms.add(group)
        assignment = Assignment.objects.create(assignment_number=1, name="Example", offering=period)
        replace_scheme(assignment, default_scheme())
        for language in ["en", "th"]:
            self.switch(language)
            response = self.client.get(reverse("assessments:scores", args=[assignment.pk, group.pk]))
            self.assertContains(response, reverse("javascript-catalog"))
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.context["missing_students"], 1)

    def test_update_and_compile_commands_exclude_runtime_and_preserve_scope(self):
        import io
        with patch("apps.students.management.commands.update_translations.call_command") as command, patch("apps.students.management.commands.update_translations.gettext_tools"):
            call_command("update_translations", stdout=io.StringIO())
        self.assertEqual([call.kwargs["domain"] for call in command.call_args_list], ["django", "djangojs"])
        self.assertIn("static/vendor/*", command.call_args.kwargs["ignore_patterns"])
        self.assertIn("*/migrations/*", command.call_args.kwargs["ignore_patterns"])
