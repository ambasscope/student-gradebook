import time

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from apps.students.models import ClassMembership, Student, StudentClass


class StudentViewsTests(TestCase):
    def upload(self, content=b"roll_number,student_name\n17,Example Student\n"):
        return self.client.post(reverse("students:import-upload"), {"student_file": SimpleUploadedFile("students.csv", content), "class_number": "4/1", "academic_year": "2569", "encoding": "utf-8-sig"})

    def mapping(self):
        token = self.client.session["student_import"]["token"]
        return self.client.post(reverse("students:import-map"), {"token": token, "roll_number": "0", "full_name": "1"})

    def test_upload_map_preview_confirm_workflow(self):
        self.assertRedirects(self.upload(), reverse("students:import-map"))
        self.assertEqual(Student.objects.count(), 0)
        self.assertRedirects(self.mapping(), reverse("students:import-preview"))
        preview = self.client.get(reverse("students:import-preview"))
        self.assertContains(preview, "Example Student")
        self.assertNotContains(preview, "256940117")
        self.assertContains(preview, "Import 1 student")
        token = self.client.session["student_import"]["token"]
        response = self.client.post(reverse("students:import-confirm"), {"token": token})
        self.assertRedirects(response, reverse("students:classroom-detail", args=[StudentClass.objects.get().pk]))
        self.assertEqual(Student.objects.get().student_number, "256940117")
        self.assertEqual(StudentClass.objects.get().class_number, "4/1")
        self.assertNotIn("student_import", self.client.session)

    def test_confirmation_is_post_only(self):
        self.assertEqual(self.client.get(reverse("students:import-confirm")).status_code, 405)

    def test_old_tab_token_cannot_import_a_new_upload(self):
        self.upload()
        old_token = self.client.session["student_import"]["token"]
        self.upload(b"roll_number,student_name\n18,Other Student\n")
        self.mapping()
        self.client.post(reverse("students:import-confirm"), {"token": old_token})
        self.assertEqual(Student.objects.count(), 0)

    def test_preview_expiry_requires_new_upload(self):
        self.upload()
        session = self.client.session
        pending = session["student_import"]
        pending["created"] = time.time() - 1801
        session["student_import"] = pending
        session.save()
        self.assertRedirects(self.client.get(reverse("students:import-map")), reverse("students:import-upload"))

    def test_invalid_file_shows_useful_error_without_writing(self):
        response = self.client.post(reverse("students:import-upload"), {"student_file": SimpleUploadedFile("list.xlsx", b"invalid"), "class_number": "4/1", "academic_year": "2569", "encoding": "utf-8-sig"})
        self.assertContains(response, "could not be read")
        self.assertEqual(Student.objects.count(), 0)

    def test_existing_details_rechecked_at_confirmation(self):
        self.upload()
        self.mapping()
        token = self.client.session["student_import"]["token"]
        group = StudentClass.objects.create(class_number="4/1", academic_year="2569")
        Student.objects.create(identifier_class=group, roll_number=17, full_name="Different Person")
        self.client.post(reverse("students:import-confirm"), {"token": token})
        self.assertEqual(ClassMembership.objects.count(), 0)
        self.assertEqual(Student.objects.get().full_name, "Different Person")

    def test_manual_add_edit_and_class_membership(self):
        group = StudentClass.objects.create(class_number="4/1", academic_year="2569")
        self.client.post(reverse("students:add"), {"roll_number": "17", "full_name": "Example", "student_class": group.pk})
        student = Student.objects.get()
        self.assertEqual(student.memberships.count(), 1)
        self.client.post(reverse("students:edit", args=[student.pk]), {"student_number": "00017", "full_name": "Updated", "notes": "Example notes"})
        student.refresh_from_db()
        self.assertEqual(student.full_name, "Updated")
        self.assertEqual(student.memberships.count(), 1)

    def test_class_and_year_filters_use_same_membership(self):
        student = Student.objects.create(student_number="00017", full_name="Example")
        first = StudentClass.objects.create(class_number="3A", academic_year="2026")
        second = StudentClass.objects.create(class_number="4A", academic_year="2027")
        ClassMembership.objects.create(student=student, student_class=first)
        ClassMembership.objects.create(student=student, student_class=second)
        response = self.client.get(reverse("students:all"), {"class": first.pk, "year": "2027"})
        self.assertNotContains(response, "00017")

    def test_duplicate_column_mapping_rejected(self):
        self.upload()
        token = self.client.session["student_import"]["token"]
        response = self.client.post(reverse("students:import-map"), {"token": token, "roll_number": "0", "full_name": "0"})
        self.assertContains(response, "Use each file column")
        self.assertEqual(Student.objects.count(), 0)
