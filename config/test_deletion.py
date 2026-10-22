from decimal import Decimal
import time
from unittest.mock import patch

from django.core import signing
from django.db import IntegrityError
from django.db.models.query import QuerySet
from django.test import TestCase, Client
from django.urls import reverse

from apps.students.models import StudentClass, Student, ClassMembership
from apps.academics.models import Course, CourseUnit, CourseOffering, ClassroomEnrollment, Enrollment
from apps.assessments.models import Assignment, MarkingCategory, Criterion, Score, Attendance, ClassroomAssignmentRecord
from config.deletion import build_plan, DELETE_ORDER
from config.deletion_views import SALT


class DeleteRecordTests(TestCase):
    def setUp(self):
        self.first = StudentClass.objects.create(class_number='4/1', academic_year='2569')
        self.other = StudentClass.objects.create(class_number='4/2', academic_year='2569')
        self.ada = self.student(self.first, 1, 'Ada Example')
        self.ben = self.student(self.first, 2, 'Ben Example')
        self.cara = self.student(self.other, 1, 'Cara Example')
        self.course = Course.objects.create(course_id='SCI', name='Science')
        self.other_course = Course.objects.create(course_id='ART', name='Art')
        self.period = CourseOffering.objects.create(course=self.course, academic_year='2569', semester='1')
        self.later = CourseOffering.objects.create(course=self.course, academic_year='2570', semester='1')
        self.other_period = CourseOffering.objects.create(course=self.other_course, academic_year='2569', semester='1')
        for period, group in [(self.period,self.first),(self.other_period,self.first),(self.other_period,self.other)]:
            ClassroomEnrollment.objects.create(offering=period,classroom=group)
        self.unit = CourseUnit.objects.create(course=self.course,unit_id='1',name='First unit')
        self.second_unit = CourseUnit.objects.create(course=self.course,unit_id='2',name='Second unit')
        self.other_unit = CourseUnit.objects.create(course=self.other_course,unit_id='1',name='Other course unit')
        self.module = self.module_record(self.period,self.unit,1)
        self.sibling = self.module_record(self.period,self.unit,2)
        self.next_year = self.module_record(self.later,self.unit,1)
        self.other_module = self.module_record(self.other_period,self.other_unit,1)
        self.other_unit_module = self.module_record(self.period,self.second_unit,3)
        self.enrollment = Enrollment.objects.create(offering=self.period,student=self.ada)
        self.ben_enrollment = Enrollment.objects.create(offering=self.period,student=self.ben)
        self.ada_art = Enrollment.objects.create(offering=self.other_period,student=self.ada)
        self.cara_art = Enrollment.objects.create(offering=self.other_period,student=self.cara)
        self.score(self.module,self.enrollment,5,self.first)
        self.score(self.module,self.ben_enrollment,6,self.first)
        self.score(self.sibling,self.enrollment,7,self.first)
        self.score(self.other_module,self.ada_art,8,self.first)
        self.score(self.other_module,self.cara_art,9,self.other)
        self.score(self.other_unit_module,self.enrollment,4,self.first)
        for module, group in [(self.module,self.first),(self.sibling,self.first),(self.other_module,self.first),(self.other_module,self.other)]:
            ClassroomAssignmentRecord.objects.create(assignment=module,classroom=group,problem='Example problem',module_status='completed')

    def student(self, group, roll, name):
        student=Student.objects.create(identifier_class=group,roll_number=roll,full_name=name)
        ClassMembership.objects.create(student=student,student_class=group)
        return student

    def module_record(self, period, unit, number):
        module=Assignment.objects.create(offering=period,unit=unit,assignment_number=number,name=f'Module {number}')
        category=MarkingCategory.objects.create(assignment=module,code='K',name='Knowledge')
        Criterion.objects.create(category=category,code='K1',name='Raw mark',maximum=10)
        return module

    def score(self,module,enrollment,value,group):
        Score.objects.create(criterion=module.categories.get().criteria.get(),enrollment=enrollment,value=value)
        Attendance.objects.create(assignment=module,classroom=group,enrollment=enrollment)

    def url(self, kind):
        return {
            'classroom':reverse('students:classroom-delete',args=[self.first.pk]),
            'student':reverse('students:student-delete',args=[self.ada.pk]),
            'course':reverse('academics:delete',args=[self.course.pk]),
            'unit':reverse('academics:unit-delete',args=[self.course.pk,self.unit.pk]),
            'module':reverse('assessments:delete',args=[self.module.pk]),
        }[kind]

    def token(self, kind):
        response=self.client.get(self.url(kind))
        self.assertEqual(response.status_code,200)
        return response.context['form']['snapshot'].value()

    def delete(self, kind):
        return self.client.post(self.url(kind),{'snapshot':self.token(kind),'confirmed':'on'})

    def counts(self):
        return {model._meta.label:model.objects.count() for model in DELETE_ORDER}

    def test_preview_never_deletes_and_all_five_buttons_are_available(self):
        before=self.counts()
        for kind in ['classroom','student','course','unit','module']:
            with self.subTest(kind=kind):
                response=self.client.get(self.url(kind))
                self.assertEqual(response.status_code,200)
                self.assertContains(response,'Records to delete')
                self.assertContains(response,'Saved scores')
                self.assertContains(response,'csrfmiddlewaretoken')
                self.assertEqual(self.counts(),before)
        for page, route in [('students:index','classroom'),('students:all','student'),('academics:index','course'),('assessments:index','module')]:
            self.assertContains(self.client.get(reverse(page)),self.url(route))
        self.assertContains(self.client.get(reverse('academics:detail',args=[self.course.pk])),self.url('unit'))

    def test_missing_confirmation_or_snapshot_does_not_delete(self):
        before=self.counts()
        token=self.token('course')
        for payload in [{'snapshot':token},{'confirmed':'on'},{}]:
            self.assertEqual(self.client.post(self.url('course'),payload).status_code,400)
            self.assertEqual(self.counts(),before)

    def test_confirmation_requires_csrf(self):
        before=self.counts()
        client=Client(enforce_csrf_checks=True)
        self.assertEqual(client.post(self.url('student'),{'snapshot':self.token('student'),'confirmed':'on'}).status_code,403)
        self.assertEqual(self.counts(),before)

    def test_other_http_methods_do_not_delete(self):
        before=self.counts()
        self.assertEqual(self.client.delete(self.url('module')).status_code,405)
        self.assertEqual(self.client.patch(self.url('module')).status_code,405)
        self.assertEqual(self.counts(),before)

    def test_module_deletes_marks_and_class_records_but_preserves_siblings(self):
        self.assertEqual(self.delete('module').status_code,302)
        self.assertFalse(Assignment.objects.filter(pk=self.module.pk).exists())
        self.assertEqual(Score.objects.count(),4)
        self.assertEqual(Assignment.objects.count(),4)
        self.assertEqual(Student.objects.count(),3)
        self.assertTrue(ClassroomAssignmentRecord.objects.filter(assignment=self.sibling).exists())
        self.assertTrue(Enrollment.objects.filter(pk=self.enrollment.pk).exists())

    def test_unit_deletes_modules_across_years_but_preserves_other_units(self):
        self.assertEqual(self.delete('unit').status_code,302)
        self.assertFalse(CourseUnit.objects.filter(pk=self.unit.pk).exists())
        self.assertFalse(Assignment.objects.filter(pk__in=[self.module.pk,self.sibling.pk,self.next_year.pk]).exists())
        self.assertTrue(Assignment.objects.filter(pk=self.other_unit_module.pk).exists())
        self.assertEqual(Score.objects.count(),3)
        self.assertEqual(CourseOffering.objects.count(),3)

    def test_course_deletes_only_its_hierarchy_and_keeps_students_and_classes(self):
        self.assertEqual(self.delete('course').status_code,302)
        self.assertFalse(Course.objects.filter(pk=self.course.pk).exists())
        self.assertEqual(CourseOffering.objects.count(),1)
        self.assertEqual(CourseUnit.objects.count(),1)
        self.assertEqual(Assignment.objects.count(),1)
        self.assertEqual(Enrollment.objects.count(),2)
        self.assertEqual(Score.objects.count(),2)
        self.assertEqual(Student.objects.count(),3)
        self.assertEqual(StudentClass.objects.count(),2)
        self.assertTrue(ClassroomAssignmentRecord.objects.filter(assignment=self.other_module,classroom=self.first).exists())

    def test_student_deletes_all_course_marks_and_memberships_without_deleting_class_comments(self):
        self.assertEqual(self.delete('student').status_code,302)
        self.assertFalse(Student.objects.filter(pk=self.ada.pk).exists())
        self.assertEqual(Score.objects.count(),2)
        self.assertEqual(Attendance.objects.count(),2)
        self.assertEqual(ClassroomAssignmentRecord.objects.count(),4)
        self.assertEqual(Assignment.objects.count(),5)
        self.assertEqual(StudentClass.objects.count(),2)

    def test_classroom_deletes_students_and_class_records_but_keeps_courses_and_other_class(self):
        # The preview explicitly identifies the legacy student's other membership.
        ClassMembership.objects.create(student=self.ada,student_class=self.other)
        preview=self.client.get(self.url('classroom'))
        self.assertContains(preview,'shared with other classrooms')
        self.assertContains(preview,str(self.other))
        token=preview.context['form']['snapshot'].value()
        self.assertEqual(self.client.post(self.url('classroom'),{'snapshot':token,'confirmed':'on'}).status_code,302)
        self.assertEqual(Student.objects.count(),1)
        self.assertTrue(Student.objects.filter(pk=self.cara.pk).exists())
        self.assertFalse(StudentClass.objects.filter(pk=self.first.pk).exists())
        self.assertEqual(Course.objects.count(),2)
        self.assertEqual(Assignment.objects.count(),5)
        self.assertEqual(Score.objects.get().value,Decimal('9'))
        self.assertEqual(ClassroomAssignmentRecord.objects.count(),1)
        self.assertTrue(ClassroomEnrollment.objects.filter(classroom=self.other).exists())

    def test_generated_student_without_membership_is_included(self):
        detached=Student.objects.create(identifier_class=self.first,roll_number=9,full_name='Detached student')
        self.assertContains(self.client.get(self.url('classroom')),detached.full_name)
        self.assertEqual(self.delete('classroom').status_code,302)
        self.assertFalse(Student.objects.filter(pk=detached.pk).exists())

    def test_updated_score_invalidates_previous_confirmation(self):
        token=self.token('module')
        Score.objects.filter(criterion__category__assignment=self.module).update(value=3)
        before=self.counts()
        response=self.client.post(self.url('module'),{'snapshot':token,'confirmed':'on'})
        self.assertEqual(response.status_code,409)
        self.assertContains(response,'changed after the preview',status_code=409)
        self.assertFalse(response.context['form'].is_bound)
        self.assertEqual(self.counts(),before)

    def test_new_module_invalidates_course_confirmation(self):
        token=self.token('course')
        self.module_record(self.period,self.unit,4)
        before=self.counts()
        self.assertEqual(self.client.post(self.url('course'),{'snapshot':token,'confirmed':'on'}).status_code,409)
        self.assertEqual(self.counts(),before)

    def test_expired_tampered_and_wrong_record_tokens_cannot_delete(self):
        before=self.counts()
        with patch('django.core.signing.time.time',return_value=time.time()-1900):
            old=signing.dumps(build_plan('student',self.ada).fingerprint,salt=SALT)
        for token in [old,'tampered',self.token('course')]:
            self.assertEqual(self.client.post(self.url('student'),{'snapshot':token,'confirmed':'on'}).status_code,409)
            self.assertEqual(self.counts(),before)

    def test_deletion_is_rolled_back_if_a_protected_or_busy_record_prevents_completion(self):
        before=self.counts();token=self.token('student')
        original=QuerySet.delete
        def fail_on_enrollment(query):
            if query.model is Enrollment:
                raise IntegrityError('Simulated new protected relation')
            return original(query)
        with patch.object(QuerySet,'delete',fail_on_enrollment):
            response=self.client.post(self.url('student'),{'snapshot':token,'confirmed':'on'})
        self.assertEqual(response.status_code,409)
        self.assertEqual(self.counts(),before)
        self.assertEqual(Score.objects.filter(enrollment=self.enrollment).count(),3)

    def test_unit_cannot_be_deleted_through_another_courses_url(self):
        url=reverse('academics:unit-delete',args=[self.other_course.pk,self.unit.pk])
        self.assertEqual(self.client.get(url).status_code,404)
        self.assertEqual(self.client.post(url,{'snapshot':self.token('unit'),'confirmed':'on'}).status_code,404)
        self.assertTrue(CourseUnit.objects.filter(pk=self.unit.pk).exists())

    def test_thai_confirmation_and_buttons_are_translated(self):
        response=self.client.get(self.url('student'),HTTP_ACCEPT_LANGUAGE='th')
        self.assertContains(response,'ลบนักเรียน')
        self.assertContains(response,'ลบอย่างถาวร')
        self.assertContains(response,'ข้อมูลที่จะลบ')
        self.assertNotContains(response,'I understand that all listed records')

    def test_large_scorebook_deletes_with_sqlite_parameter_limit(self):
        import sqlite3
        from django.db import connection
        category=self.module.categories.get()
        criteria=Criterion.objects.bulk_create([
            Criterion(category=category,code=f'bulk-{i}',name=f'Criterion {i}',maximum=10)
            for i in range(1100)])
        Score.objects.bulk_create([Score(criterion=item,enrollment=self.enrollment,value=5) for item in criteria])
        raw=connection.connection
        previous=raw.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER,999)
        try:
            preview=self.client.get(self.url('module'))
            self.assertEqual(preview.status_code,200)
            self.assertContains(preview,'1102')
            self.assertEqual(self.delete('module').status_code,302)
            self.assertEqual(Score.objects.count(),4)
            self.assertTrue(Assignment.objects.filter(pk=self.sibling.pk).exists())
        finally:
            raw.setlimit(sqlite3.SQLITE_LIMIT_VARIABLE_NUMBER,previous)
