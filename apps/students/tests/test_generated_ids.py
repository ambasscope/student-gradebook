from importlib import import_module
from django.apps import apps
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from config.identifiers import student_identifier, assignment_identifier
from apps.students.forms import StudentClassForm, StudentForm
from apps.students.models import Student, StudentClass, ClassMembership
from apps.students.services.imports import build_plan, commit_import, suggest_mapping


def metadata(**changes):
    return {"class_number": "4/1", "academic_year": "2569", "class_notes": "", "update_existing": False, **changes}


def record(number="3", **changes):
    return {"row": 2, "roll_number": number, "full_name": "Example Student", "email": "", "notes": "", **changes}


class GeneratedStudentTests(TestCase):
    def test_fixed_width_formats(self):
        self.assertEqual(student_identifier("2569", "4/1", "3"), "256940103")
        self.assertEqual(student_identifier("2569", "4/01", "03"), "256940103")
        self.assertEqual(student_identifier("2569", "4/12", "99"), "256941299")
        self.assertEqual(assignment_identifier("2569", "MATH101", "3"), "2569MATH10103")

    def test_invalid_identity_components(self):
        for year, classroom, roll in [("69", "4/1", "3"), ("2569/2570", "4/1", "3"), ("2569", "10/1", "3"), ("2569", "4/100", "3"), ("2569", "4/0", "3"), ("2569", "3A", "3"), ("2569", "4/1", "0"), ("2569", "4/1", "100"), ("2569", "4/1", "3.5"), ("2569", "4/1", True)]:
            with self.subTest(values=(year, classroom, roll)), self.assertRaises(ValidationError):
                student_identifier(year, classroom, roll)

    def test_import_scopes_roll_to_class_and_year(self):
        for changes in [{}, {"class_number": "4/2"}, {"academic_year": "2570"}]:
            commit_import([record()], metadata(**changes))
        self.assertEqual(set(Student.objects.values_list("student_number", flat=True)), {"256940103", "256940203", "257040103"})
        self.assertEqual(ClassMembership.objects.count(), 3)

    def test_preview_and_reimport_show_generated_id(self):
        self.assertEqual(build_plan([record()], metadata())["rows"][0]["student_number"], "256940103")
        commit_import([record()], metadata())
        _, counts = commit_import([record("03")], metadata(class_number="4/01"))
        self.assertEqual(Student.objects.count(), 1)
        self.assertEqual(StudentClass.objects.count(), 1)
        self.assertEqual(counts["unchanged"], 1)

    def test_semantic_duplicate_rolls_and_invalid_rows_are_atomic(self):
        plan = build_plan([record("3"), record("03", row=3)], metadata())
        self.assertTrue(plan["errors"])
        from apps.students.services.imports import ImportProblem
        with self.assertRaises(ImportProblem):
            commit_import([record("3"), record("100", row=3)], metadata())
        self.assertFalse(Student.objects.exists())
        self.assertFalse(StudentClass.objects.exists())

    def test_manual_entry_and_tampered_edit_preserve_identity(self):
        group = StudentClass.objects.create(class_number="4/1", academic_year="2569")
        response = self.client.post(reverse("students:add"), {"student_class": group.pk, "roll_number": 3, "full_name": "Example Alice", "student_number": "tampered"})
        self.assertEqual(response.status_code, 302)
        student = Student.objects.get()
        self.assertEqual(student.student_number, "256940103")
        response = self.client.post(reverse("students:edit", args=[student.pk]), {"student_class": "9999", "roll_number": "99", "full_name": "Updated Alice"})
        self.assertEqual(response.status_code, 302)
        student.refresh_from_db()
        self.assertEqual((student.student_number, student.roll_number, student.full_name), ("256940103", 3, "Updated Alice"))
        self.assertFalse(StudentForm({"student_class": group.pk, "roll_number": 3, "full_name": "Duplicate"}).is_valid())

    def test_generated_classroom_cannot_move_year_or_class(self):
        group, _ = commit_import([record()], metadata())
        for changes in [{"academic_year": "2570"}, {"class_number": "4/2"}]:
            form = StudentClassForm({"class_number": "4/1", "academic_year": "2569", **changes}, instance=group)
            self.assertFalse(form.is_valid())

    def test_legacy_class_aliases_cannot_create_duplicate_namespaces(self):
        group = StudentClass.objects.create(class_number="4/01", academic_year="2569")
        self.assertFalse(StudentClassForm({"class_number": "4/1", "academic_year": "2569"}).is_valid())
        imported, _ = commit_import([record()], metadata())
        self.assertEqual(imported.pk, group.pk)
        self.assertEqual(StudentClass.objects.count(), 1)
        StudentClass.objects.create(class_number="4/1", academic_year="2569")
        self.assertTrue(build_plan([record()], metadata())["errors"])

    def test_roll_column_suggestion_and_search(self):
        self.assertEqual(suggest_mapping(["เลขที่", "student_name"])["roll_number"], "0")
        group, _ = commit_import([record()], metadata())
        response = self.client.get(reverse("students:classroom-detail", args=[group.pk]), {"q": "3"})
        self.assertContains(response, "Example Student")
        self.assertNotContains(response, "256940103")


class StudentConversionTests(TestCase):
    def convert(self):
        import_module("apps.students.migrations.0003_convert_safe_student_ids").convert_safe_ids(apps, None)

    def test_single_class_numeric_legacy_id_is_converted(self):
        group = StudentClass.objects.create(class_number="4/01", academic_year="2569")
        student = Student.objects.create(student_number="00003", full_name="Legacy Example")
        membership = ClassMembership.objects.create(student=student, student_class=group)
        self.convert()
        student.refresh_from_db(); group.refresh_from_db(); membership.refresh_from_db()
        self.assertEqual((student.student_number, student.roll_number, student.identifier_class_id), ("256940103", 3, group.pk))
        self.assertEqual(group.class_number, "4/1")
        self.assertEqual(membership.student_id, student.pk)

    def test_ambiguous_memberships_and_text_ids_are_preserved(self):
        first = StudentClass.objects.create(class_number="4/1", academic_year="2569")
        second = StudentClass.objects.create(class_number="4/2", academic_year="2569")
        shared = Student.objects.create(student_number="3", full_name="Shared Legacy")
        text = Student.objects.create(student_number="S0004", full_name="Text Legacy")
        for group in [first, second]:
            ClassMembership.objects.create(student=shared, student_class=group)
        ClassMembership.objects.create(student=text, student_class=first)
        self.convert()
        self.assertEqual(set(Student.objects.values_list("student_number", flat=True)), {"3", "S0004"})
        self.assertFalse(Student.objects.filter(identifier_class__isnull=False).exists())

    def test_colliding_candidates_are_not_merged(self):
        group = StudentClass.objects.create(class_number="4/1", academic_year="2569")
        for number in ["3", "03"]:
            student = Student.objects.create(student_number=number, full_name="Legacy Example")
            ClassMembership.objects.create(student=student, student_class=group)
        self.convert()
        self.assertEqual(set(Student.objects.values_list("student_number", flat=True)), {"3", "03"})
