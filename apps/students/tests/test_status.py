from datetime import date
from decimal import Decimal
from io import BytesIO
from unittest.mock import patch
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils.translation import override

from apps.academics.models import Course, CourseOffering, CourseUnit, Enrollment
from apps.assessments.models import Assignment, Attendance, ClassroomAssignmentRecord, Score
from apps.assessments.services.scoring import grid_data, save_scores, ScoreProblem
from apps.assessments.services.schemes import replace_scheme
from apps.reports.services.context import module_source
from apps.reports.services.score_context import score_workbook_context
from apps.reports.services.score_workbooks import render_score_workbook, S
from apps.students.forms import StudentForm, ColumnMappingForm
from apps.students.models import Student, StudentClass, ClassMembership
from apps.students.services.imports import commit_import, build_plan, map_records, suggest_mapping


class StudentStatusTests(TestCase):
    def setUp(self):
        self.enterContext(override("en"))
        self.group = StudentClass.objects.create(class_number='4/1', academic_year='2569')
        self.course = Course.objects.create(course_id='SCI', name='Science')
        self.period = CourseOffering.objects.create(course=self.course, academic_year='2569', semester='1')
        self.period.classrooms.add(self.group)
        self.unit = CourseUnit.objects.create(course=self.course, unit_id='1', name='Unit one')
        self.students = []
        self.enrollments = []
        for roll, name in enumerate(['Studying Example', 'Resigned Example', 'Unassessed Example'], 1):
            student = Student.objects.create(identifier_class=self.group, roll_number=roll, full_name=name,
                                             student_id='001234' if roll < 3 else '')
            ClassMembership.objects.create(student=student, student_class=self.group)
            self.students.append(student)
            self.enrollments.append(Enrollment.objects.create(student=student, offering=self.period))
        self.modules = []
        for number, day in enumerate([date(2026,10,1), date(2026,10,15), date(2026,10,20)], 1):
            module = Assignment.objects.create(offering=self.period, unit=self.unit, assignment_number=number, name=f'Module {number}')
            replace_scheme(module, [{'name':'Knowledge', 'items':[{'name':'Task', 'maximum':'10'}]}])
            ClassroomAssignmentRecord.objects.create(assignment=module, classroom=self.group, learning_date=day, module_status='completed')
            criterion = module.categories.get().criteria.get()
            for enrollment, value in zip(self.enrollments[:2], [8,10]):
                Score.objects.create(enrollment=enrollment, criterion=criterion, value=value)
            Attendance.objects.create(assignment=module, classroom=self.group, enrollment=self.enrollments[0], present=False)
            self.modules.append(module)
        self.resign()

    def resign(self):
        student = self.students[1]
        student.status = Student.Status.RESIGNED
        student.resignation_date = date(2026,10,15)
        student.full_clean()
        student.save()

    def payload(self, module=None, changes=None):
        module = module or self.modules[0]
        data = grid_data(module, self.group)
        return {'scheme_revision':data['scheme_revision'], 'roster_signature':data['roster_signature'], 'changes':changes or []}

    def test_optional_ids_keep_leading_zeros_and_do_not_replace_generated_identity(self):
        student = self.students[0]
        key, pk = student.student_number, student.pk
        form = StudentForm({'student_class':self.group.pk,'roll_number':1,'full_name':student.full_name,
                            'student_id':'000099','status':'studying','student_number':'malicious'}, instance=student)
        self.assertTrue(form.is_valid(), form.errors)
        form.save();student.refresh_from_db()
        self.assertEqual((student.pk,student.student_number,student.student_id),(pk,key,'000099'))
        self.assertEqual(self.enrollments[0].scores.count(),3)
        self.assertEqual(str(student),'000099 — Studying Example')

    def test_ids_may_repeat_across_years_and_can_be_blank(self):
        group=StudentClass.objects.create(class_number='4/1',academic_year='2570')
        student=Student.objects.create(identifier_class=group,roll_number=1,full_name='Next year',student_id='001234')
        self.assertNotEqual(student.student_number,self.students[0].student_number)
        student.student_id='';student.full_clean();student.save()

    def test_status_requires_date_and_clear_date_when_returning_to_studying(self):
        for status,day in [('resigned',''),('studying','2026-10-15')]:
            form=StudentForm({'student_class':self.group.pk,'roll_number':1,'full_name':'Example','status':status,'resignation_date':day},instance=self.students[0])
            self.assertFalse(form.is_valid())
            self.assertIn('resignation_date',form.errors)
        form=StudentForm({'student_class':self.group.pk,'roll_number':1,'full_name':'Example','status':'resigned','resignation_date':'2026-02-30'},instance=self.students[0])
        self.assertFalse(form.is_valid())
        self.assertEqual(form.fields['resignation_date'].widget.input_type,'date')
        with self.assertRaises(IntegrityError),transaction.atomic():
            Student.objects.filter(pk=self.students[0].pk).update(status='resigned',resignation_date=None)

    def test_grid_keeps_earlier_modules_but_excludes_on_and_after_resignation(self):
        first=grid_data(self.modules[0],self.group)
        self.assertEqual([r['roll_number'] for r in first['rows']],[1,2,3])
        self.assertEqual(first['rows'][1][f'c_{self.modules[0].categories.get().criteria.get().pk}'],'10.00')
        for module in self.modules[1:]:
            self.assertEqual([r['roll_number'] for r in grid_data(module,self.group)['rows']],[1,3])
        self.assertEqual(Score.objects.count(),6)

    def test_undated_module_uses_today(self):
        ClassroomAssignmentRecord.objects.filter(assignment=self.modules[0]).update(learning_date=None)
        with patch('apps.assessments.services.scoring.date') as clock:
            clock.today.return_value=date(2026,10,22)
            self.assertEqual([r['roll_number'] for r in grid_data(self.modules[0],self.group)['rows']],[1,3])

    def test_historical_scores_can_be_edited_without_modifying_later_scores(self):
        module=self.modules[0];criterion=module.categories.get().criteria.get()
        change={'enrollment_id':self.enrollments[1].pk,'criterion_id':criterion.pk,'previous':'10','value':'9'}
        result=save_scores(module.pk,self.group.pk,self.payload(module,[change]))
        self.assertEqual(result['saved'],1)
        self.assertEqual(Score.objects.get(enrollment=self.enrollments[1],criterion=criterion).value,Decimal('9'))
        self.assertEqual(self.enrollments[1].scores.count(),3)

    def test_forged_post_cannot_edit_resigned_students_later_scores_or_attendance(self):
        module=self.modules[-1];criterion=module.categories.get().criteria.get()
        for field,change in [('changes',{'enrollment_id':self.enrollments[1].pk,'criterion_id':criterion.pk,'previous':'10','value':'1'}),
                             ('attendance_changes',{'enrollment_id':self.enrollments[1].pk,'previous':True,'value':False})]:
            payload=self.payload(module);payload[field]=[change]
            with self.assertRaises(ScoreProblem):save_scores(module.pk,self.group.pk,payload)
        self.assertEqual(Score.objects.get(enrollment=self.enrollments[1],criterion=criterion).value,Decimal('10'))
        self.assertFalse(Attendance.objects.filter(assignment=module,enrollment=self.enrollments[1]).exists())

    def test_resigning_after_page_open_invalidates_unsaved_score_batch(self):
        self.students[1].status='studying';self.students[1].resignation_date=None;self.students[1].save()
        payload=self.payload(self.modules[-1])
        self.resign()
        with self.assertRaisesMessage(ScoreProblem,'roster changed'):
            save_scores(self.modules[-1].pk,self.group.pk,payload)

    def test_date_change_refreshes_roster_and_rejects_ineligible_cell_edits_atomically(self):
        module=self.modules[0];data=grid_data(module,self.group)
        payload=self.payload(module);payload['classroom_notes']={**data['classroom_notes'],'learning_date':'2026-10-20'}
        criterion=module.categories.get().criteria.get()
        payload['changes']=[{'enrollment_id':self.enrollments[1].pk,'criterion_id':criterion.pk,'previous':'10','value':'2'}]
        with self.assertRaises(ScoreProblem):save_scores(module.pk,self.group.pk,payload)
        self.assertEqual(module.classroom_records.get().learning_date,date(2026,10,1))
        payload['changes']=[]
        result=save_scores(module.pk,self.group.pk,payload)
        self.assertTrue(result['reload_required'])
        self.assertEqual([r['roll_number'] for r in grid_data(module,self.group)['rows']],[1,3])
        self.assertEqual(Score.objects.get(criterion=criterion,enrollment=self.enrollments[1]).value,Decimal('10'))

    def test_word_report_uses_current_studying_roster_including_absent_and_unassessed(self):
        source=module_source(self.modules[0],self.group,None)
        self.assertEqual((source['total'],source['present'],source['absent']),(2,1,1))
        category=source['categories'][0]
        self.assertEqual((category['passed'],category['failed'],category['unassessed']),(1,1,1))
        self.assertEqual((category['pass_percent'],category['fail_percent']),('50','50'))
        self.assertEqual(Score.objects.count(),6)

    def test_zero_studying_students_is_safe_for_word_report(self):
        Student.objects.update(status='resigned',resignation_date=date(2026,10,15))
        source=module_source(self.modules[0],self.group,None)
        self.assertEqual(source['total'],0)
        self.assertEqual(source['categories'][0]['pass_percent'],'0')
        self.assertTrue(source['issues'])

    def test_excel_all_sheets_keep_grey_names_but_no_scores_or_formulas_for_resigned(self):
        context=score_workbook_context(self.period,self.group,self.modules)
        self.assertEqual(context['sheet_count'],6)
        for module in context['modules']:
            self.assertTrue(module['rows'][1]['resigned'])
            self.assertTrue(all(value is None for value in module['rows'][1]['values'].values()))
        content=render_score_workbook(context)
        with ZipFile(BytesIO(content)) as archive:
            styles=ET.fromstring(archive.read('xl/styles.xml'))
            formats=styles.find('{'+S+'}cellXfs');fills=styles.find('{'+S+'}fills')
            sheets=[name for name in archive.namelist() if name.startswith('xl/worksheets/sheet') and name.endswith('.xml')]
            self.assertEqual(len(sheets),6)
            for name in sheets:
                root=ET.fromstring(archive.read(name))
                row=root.find('.//{'+S+'}row[@r="10"]')
                self.assertIn('Resigned Example',''.join(row.itertext()))
                for cell in row:
                    self.assertIsNone(cell.find('{'+S+'}f'))
                    fill=fills[int(formats[int(cell.get('s'))].get('fillId'))]
                    self.assertEqual(fill.find('.//{'+S+'}fgColor').get('rgb'),'FFD9D9D9')
                    if cell.get('r')[0] not in ('A','B'):
                        self.assertIsNone(cell.find('{'+S+'}v'))
                        self.assertIsNone(cell.find('{'+S+'}is'))
                self.assertEqual(root.find('{'+S+'}pageSetup').get('orientation'),'portrait')
        self.assertEqual(Score.objects.count(),6)

    def test_student_ids_and_status_visible_but_internal_key_never_in_pages_or_grid(self):
        for url in [reverse('students:all'),reverse('students:classroom-detail',args=[self.group.pk]),
                    reverse('students:edit',args=[self.students[1].pk]), reverse('students:student-delete',args=[self.students[1].pk]),
                    reverse('assessments:scores',args=[self.modules[0].pk,self.group.pk])]:
            response=self.client.get(url)
            self.assertEqual(response.status_code,200)
            self.assertNotContains(response,self.students[1].student_number)
        response=self.client.get(reverse('students:classroom-detail',args=[self.group.pk]),HTTP_ACCEPT_LANGUAGE='th')
        self.assertContains(response,'001234')
        self.assertContains(response,'ลาออก')
        self.assertContains(response,'กำลังศึกษา')
        self.assertContains(response,'2026-10-15')
        self.assertEqual(grid_data(self.modules[0],self.group)['rows'][0]['student_id'],'001234')

    def test_import_optional_student_id_matches_roll_and_preserves_resignation(self):
        mapping=suggest_mapping(['เลขที่','ชื่อ-นามสกุล','รหัสนักเรียน'])
        self.assertEqual(mapping['roll_number'],'0');self.assertEqual(mapping['student_id'],'2')
        form=ColumnMappingForm(['roll','name','id'],{'token':'x','roll_number':'0','full_name':'1','student_id':'2'})
        self.assertTrue(form.is_valid(),form.errors)
        records=map_records({'rows':[{'row':2,'values':['2','Resigned Example','000077']}]},form.cleaned_data)
        meta={'class_number':'4/1','academic_year':'2569','class_notes':'','update_existing':True}
        key=self.students[1].student_number
        commit_import(records,meta)
        self.students[1].refresh_from_db()
        self.assertEqual((self.students[1].student_number,self.students[1].student_id,self.students[1].status),(key,'000077','resigned'))
        self.assertEqual(Student.objects.count(),3)
        self.assertEqual(Score.objects.count(),6)
        records[0]['student_id']='';commit_import(records,meta)
        self.students[1].refresh_from_db();self.assertEqual(self.students[1].student_id,'000077')

    def test_returning_to_studying_restores_score_grid_without_losing_marks(self):
        student=self.students[1]
        student.status='studying';student.resignation_date=None;student.full_clean();student.save()
        data=grid_data(self.modules[-1],self.group)
        self.assertEqual([row['roll_number'] for row in data['rows']],[1,2,3])
        self.assertEqual(Score.objects.count(),6)

    def test_copy_student_and_classroom_preserve_optional_id_and_status(self):
        response=self.client.get(reverse('students:student-copy',args=[self.students[1].pk]))
        form=response.context['form']
        self.assertEqual(form.initial['student_id'],'001234')
        self.assertEqual(form.initial['status'],'resigned')
        self.assertEqual(form.initial['resignation_date'],date(2026,10,15))
        response=self.client.post(reverse('students:classroom-copy',args=[self.group.pk]),{
            'class_number':'4/3','academic_year':'2570','include_students':'on'})
        self.assertEqual(response.status_code,302)
        copied=Student.objects.get(identifier_class__class_number='4/3',roll_number=2)
        self.assertEqual((copied.student_id,copied.status,copied.resignation_date),('001234','resigned',date(2026,10,15)))
        self.assertFalse(Enrollment.objects.filter(student=copied).exists())

    def test_all_resigned_roster_can_still_export_excel(self):
        Student.objects.update(status='resigned',resignation_date=date(2026,10,15))
        context=score_workbook_context(self.period,self.group,self.modules)
        self.assertEqual(context['student_count'],3)
        self.assertTrue(all(row['resigned'] for module in context['modules'] for row in module['rows']))
        self.assertTrue(render_score_workbook(context).startswith(b'PK'))
