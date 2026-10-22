import json
from importlib import import_module
from django.apps import apps
from django.test import TestCase
from django.urls import reverse
from apps.students.models import Student, StudentClass, ClassMembership
from apps.academics.models import Course, CourseOffering, Enrollment
from apps.academics.forms import CourseForm, OfferingForm
from apps.assessments.models import Assignment, Criterion, Score
from apps.assessments.forms import AssignmentForm
from apps.assessments.services.schemes import replace_scheme


SCHEME = [{"code": "A", "name": "Content", "items": [{"code": "Ai", "name": "Understanding", "maximum": "10"}]}]


class GeneratedAssignmentTests(TestCase):
    def setUp(self):
        self.course = Course.objects.create(course_id="MATH101", name="Mathematics")
        self.period = CourseOffering.objects.create(course=self.course, academic_year="2569", semester="Semester 1")

    def data(self, **changes):
        return {"assignment_number": 3, "name": "Homework", "offering": self.period.pk, "calculation_mode": "points", "scheme_json": json.dumps(SCHEME), **changes}

    def test_form_generates_key_and_ignores_submitted_key(self):
        response = self.client.post(reverse("assessments:add"), self.data(assignment_id="tampered"))
        self.assertEqual(response.status_code, 302)
        assignment = Assignment.objects.get()
        self.assertEqual((assignment.assignment_id, assignment.assignment_number), ("2569MATH10103", 3))

    def test_numbers_are_unique_across_semesters_but_not_years_or_courses(self):
        self.client.post(reverse("assessments:add"), self.data())
        second = CourseOffering.objects.create(course=self.course, academic_year="2569", semester="Semester 2")
        self.assertFalse(AssignmentForm(self.data(offering=second.pk)).is_valid())
        next_year = CourseOffering.objects.create(course=self.course, academic_year="2570", semester="Semester 1")
        self.assertTrue(AssignmentForm(self.data(offering=next_year.pk)).is_valid())
        other = Course.objects.create(course_id="ENG101", name="English")
        other_period = CourseOffering.objects.create(course=other, academic_year="2569", semester="Semester 1")
        self.assertTrue(AssignmentForm(self.data(offering=other_period.pk)).is_valid())

    def test_number_limits_and_four_digit_year(self):
        for number in ["", 0, 100, "3.5", "HW03"]:
            with self.subTest(number=number):
                self.assertFalse(AssignmentForm(self.data(assignment_number=number)).is_valid())
        self.period.academic_year = "2569/2570"; self.period.save()
        self.assertFalse(AssignmentForm(self.data()).is_valid())

    def test_long_course_id_is_supported(self):
        self.course.course_id = "X" * 80; self.course.save()
        self.client.post(reverse("assessments:add"), self.data())
        self.assertEqual(len(Assignment.objects.get().assignment_id), 86)

    def test_course_and_year_cannot_invalidate_generated_keys(self):
        self.client.post(reverse("assessments:add"), self.data())
        self.assertFalse(CourseForm({"course_id": "CHANGED", "name": "Mathematics"}, instance=self.course).is_valid())
        self.assertFalse(OfferingForm({"academic_year": "2570", "semester": "Semester 1", "classrooms": []}, instance=self.period, course=self.course).is_valid())

    def test_conversion_preserves_scores_and_internal_keys(self):
        group = StudentClass.objects.create(class_number="4/1", academic_year="2569")
        student = Student.objects.create(student_number="3", full_name="Legacy Example")
        ClassMembership.objects.create(student=student, student_class=group)
        enrollment = Enrollment.objects.create(student=student, offering=self.period)
        assignment = Assignment.objects.create(assignment_id="3", name="Legacy homework", offering=self.period)
        replace_scheme(assignment, SCHEME)
        item = Criterion.objects.get(category__assignment=assignment)
        score = Score.objects.create(enrollment=enrollment, criterion=item, value="8")
        import_module("apps.students.migrations.0003_convert_safe_student_ids").convert_safe_ids(apps, None)
        import_module("apps.assessments.migrations.0003_convert_safe_assignment_ids").convert_safe_ids(apps, None)
        student.refresh_from_db(); assignment.refresh_from_db(); score.refresh_from_db()
        self.assertEqual(student.student_number, "256940103")
        self.assertEqual(assignment.assignment_id, "2569MATH10103")
        self.assertEqual((score.enrollment_id, score.criterion_id), (enrollment.pk, item.pk))
        self.assertEqual(Score.objects.count(), 1)

    def test_ambiguous_assignment_numbers_and_arbitrary_keys_are_preserved(self):
        second = CourseOffering.objects.create(course=self.course, academic_year="2569", semester="Semester 2")
        for key, period in [("3", self.period), ("03", second), ("HW04", self.period)]:
            Assignment.objects.create(assignment_id=key, name="Legacy", offering=period)
        import_module("apps.assessments.migrations.0003_convert_safe_assignment_ids").convert_safe_ids(apps, None)
        self.assertEqual(set(Assignment.objects.values_list("assignment_id", flat=True)), {"3", "03", "HW04"})
        self.assertFalse(Assignment.objects.filter(assignment_number__isnull=False).exists())
