"""Verify the schema upgrade retains IDs and score foreign keys."""
from decimal import Decimal
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class StudentStatusMigrationTests(TransactionTestCase):
    def test_existing_students_scores_and_memberships_survive_upgrade(self):
        executor=MigrationExecutor(connection)
        latest=executor.loader.graph.leaf_nodes()
        previous=[target for target in latest if target[0]!='students']+[('students','0003_convert_safe_student_ids')]
        executor.migrate(previous)
        try:
            state=executor.loader.project_state(previous).apps
            Group=state.get_model('students','StudentClass')
            Student=state.get_model('students','Student')
            Membership=state.get_model('students','ClassMembership')
            Course=state.get_model('academics','Course')
            Offering=state.get_model('academics','CourseOffering')
            Enrollment=state.get_model('academics','Enrollment')
            Module=state.get_model('assessments','Assignment')
            Category=state.get_model('assessments','MarkingCategory')
            Criterion=state.get_model('assessments','Criterion')
            Score=state.get_model('assessments','Score')
            group=Group.objects.create(class_number='4/1',academic_year='2569')
            student=Student.objects.create(student_number='256940103',identifier_class=group,roll_number=3,full_name='Existing Example')
            legacy=Student.objects.create(student_number='S0099',full_name='Ambiguous Legacy')
            membership=Membership.objects.create(student=student,student_class=group)
            course=Course.objects.create(course_id='SCI',name='Science')
            offering=Offering.objects.create(course=course,academic_year='2569',semester='1')
            enrollment=Enrollment.objects.create(offering=offering,student=student)
            module=Module.objects.create(offering=offering,assignment_id='2569SCI01',assignment_number=1,name='Existing module')
            category=Category.objects.create(assignment=module,code='K',name='Knowledge')
            criterion=Criterion.objects.create(category=category,code='K1',name='Task',maximum=10)
            score=Score.objects.create(enrollment=enrollment,criterion=criterion,value=Decimal('8.5'))
            executor=MigrationExecutor(connection);executor.migrate(latest)
            from apps.students.models import Student as NewStudent, ClassMembership
            from apps.assessments.models import Score as NewScore
            updated=NewStudent.objects.get(pk=student.pk)
            self.assertEqual((updated.student_number,updated.student_id,updated.status,updated.resignation_date),('256940103','','studying',None))
            self.assertEqual(NewStudent.objects.get(pk=legacy.pk).student_number,'S0099')
            self.assertEqual(ClassMembership.objects.get(pk=membership.pk).student_id,student.pk)
            self.assertEqual(NewScore.objects.get(pk=score.pk).enrollment_id,enrollment.pk)
            self.assertEqual(NewScore.objects.get(pk=score.pk).value,Decimal('8.5'))
            self.assertEqual(NewScore.objects.count(),1)
        finally:
            MigrationExecutor(connection).migrate(latest)
