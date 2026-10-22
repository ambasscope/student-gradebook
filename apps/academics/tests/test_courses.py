from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from apps.students.forms import StudentClassForm
from apps.students.models import ClassMembership, Student, StudentClass
from apps.academics.forms import OfferingForm
from apps.academics.models import Course, CourseOffering, Enrollment
from apps.academics.services.enrollment import roster_plan, sync_roster


class CourseTests(TestCase):
    def setUp(self):
        self.first = StudentClass.objects.create(class_number="3A", academic_year="2026")
        self.second = StudentClass.objects.create(class_number="3B", academic_year="2026")
        self.next_year = StudentClass.objects.create(class_number="4A", academic_year="2027")
        self.alice = Student.objects.create(student_number="00017", full_name="Example Alice")
        self.bob = Student.objects.create(student_number="00018", full_name="Example Bob")
        ClassMembership.objects.create(student=self.alice, student_class=self.first)
        ClassMembership.objects.create(student=self.alice, student_class=self.second)
        ClassMembership.objects.create(student=self.bob, student_class=self.second)

    def create_course(self, **changes):
        data = {"course-course_id": "00123", "course-name": "Mathematics", "course-information": "Example information", "period-academic_year": "2026", "period-semester": "1", "period-classrooms": [self.first.pk, self.second.pk], **changes}
        return self.client.post(reverse("academics:add"), data)

    def test_create_course_enrolls_two_classrooms_without_duplicate_students(self):
        response = self.create_course()
        course = Course.objects.get()
        self.assertRedirects(response, reverse("academics:detail", args=[course.pk]))
        self.assertEqual(course.course_id, "00123")
        period = course.offerings.get()
        self.assertEqual(period.classrooms.count(), 2)
        self.assertEqual(period.enrollments.count(), 2)
        self.assertEqual(period.enrollments.filter(student=self.alice).count(), 1)

    def test_course_id_is_unique_and_existing_course_is_not_overwritten(self):
        self.create_course()
        response = self.create_course(**{"course-name": "Different Course"})
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["course_form"].errors["course_id"])
        self.assertEqual(Course.objects.count(), 1)
        self.assertEqual(Course.objects.get().name, "Mathematics")

    def test_mixed_academic_years_rejected_before_any_course_is_saved(self):
        response = self.create_course(**{"period-classrooms": [self.first.pk, self.next_year.pk]})
        self.assertContains(response, "same academic year")
        self.assertEqual(Course.objects.count(), 0)

    def test_invalid_course_or_period_does_not_leave_partial_record(self):
        for changes in [{"course-name": ""}, {"period-academic_year": ""}, {"period-classrooms": [999999]}]:
            with self.subTest(changes=changes):
                self.assertEqual(self.create_course(**changes).status_code, 200)
                self.assertEqual(Course.objects.count(), 0)

    def test_same_course_can_have_separate_period_rosters(self):
        self.create_course()
        course = Course.objects.get()
        ClassMembership.objects.create(student=self.alice, student_class=self.next_year)
        response = self.client.post(reverse("academics:offering-add", args=[course.pk]), {"academic_year": "2027", "semester": "1", "classrooms": [self.next_year.pk]})
        self.assertRedirects(response, reverse("academics:detail", args=[course.pk]))
        self.assertEqual(course.offerings.count(), 2)
        self.assertEqual(course.offerings.get(academic_year="2026").enrollments.count(), 2)
        self.assertEqual(course.offerings.get(academic_year="2027").enrollments.count(), 1)

    def test_duplicate_teaching_period_shows_form_error(self):
        self.create_course()
        course = Course.objects.get()
        response = self.client.post(reverse("academics:offering-add", args=[course.pk]), {"academic_year": "2026", "semester": "1", "classrooms": [self.first.pk]})
        self.assertContains(response, "already has a teaching period")
        self.assertEqual(course.offerings.count(), 1)

    def test_roster_refresh_requires_explicit_review_and_rejects_stale_preview(self):
        self.create_course()
        period = CourseOffering.objects.get()
        old = roster_plan(period)["fingerprint"]
        added = Student.objects.create(student_number="00019", full_name="Example New")
        ClassMembership.objects.create(student=added, student_class=self.first)
        self.assertFalse(period.enrollments.filter(student=added).exists())
        with self.assertRaisesMessage(ValidationError, "changed after your preview"):
            sync_roster(period, old)
        self.assertFalse(period.enrollments.filter(student=added).exists())
        preview = roster_plan(period)
        self.assertEqual(preview["added_ids"], {added.pk})
        sync_roster(period, preview["fingerprint"])
        self.assertTrue(period.enrollments.filter(student=added, is_active=True).exists())

    def test_removing_classroom_retains_inactive_enrollment_and_can_reactivate_it(self):
        self.create_course()
        period = CourseOffering.objects.get()
        original_pk = period.enrollments.get(student=self.bob).pk
        period.classrooms.set([self.first])
        sync_roster(period)
        self.assertFalse(period.enrollments.get(student=self.bob).is_active)
        period.classrooms.add(self.second)
        sync_roster(period)
        self.assertTrue(period.enrollments.get(student=self.bob).is_active)
        self.assertEqual(period.enrollments.get(student=self.bob).pk, original_pk)

    def test_enrolled_classroom_year_cannot_be_changed_in_form(self):
        self.create_course()
        form = StudentClassForm({"class_number": "3A", "academic_year": "2027", "notes": ""}, instance=self.first)
        self.assertFalse(form.is_valid())
        self.assertIn("academic_year", form.errors)

    def test_course_metadata_edit_keeps_enrollment_references(self):
        self.create_course()
        course = Course.objects.get()
        period = CourseOffering.objects.get()
        self.client.post(reverse("academics:edit", args=[course.pk]), {"course_id": "00124", "name": "Updated mathematics", "information": "New information"})
        course.refresh_from_db()
        self.assertEqual(course.course_id, "00124")
        self.assertEqual(period.enrollments.count(), 2)
        self.assertEqual(period.course_id, course.pk)

    def test_course_roster_is_scoped_to_correct_course(self):
        self.create_course()
        period = CourseOffering.objects.get()
        other = Course.objects.create(course_id="ENG101", name="English")
        self.assertEqual(self.client.get(reverse("academics:roster", args=[other.pk, period.pk])).status_code, 404)

    def test_database_rejects_duplicate_student_enrollment(self):
        self.create_course()
        period = CourseOffering.objects.get()
        with self.assertRaises(IntegrityError), transaction.atomic():
            Enrollment.objects.create(offering=period, student=self.alice)

    def test_classroom_cards_and_detail_show_only_their_students(self):
        response = self.client.get(reverse("students:index"))
        self.assertContains(response, "Classrooms")
        self.assertContains(response, reverse("students:classroom-detail", args=[self.first.pk]))
        detail = self.client.get(reverse("students:classroom-detail", args=[self.first.pk]))
        self.assertContains(detail, self.alice.full_name)
        self.assertNotContains(detail, self.bob.full_name)
        self.assertNotContains(detail, self.alice.student_number)

    def test_import_from_classroom_prefills_year_and_class(self):
        response = self.client.get(reverse("students:import-upload"), {"class": self.first.pk})
        self.assertEqual(response.context["form"].initial["class_number"], "3A")
        self.assertEqual(response.context["form"].initial["academic_year"], "2026")
