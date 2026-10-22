import json
from datetime import date
from decimal import Decimal
from django.test import TestCase
from django.utils.translation import override
from apps.academics.models import Course, CourseOffering, CourseUnit, Enrollment
from apps.assessments.models import Assignment, Score, Attendance, ClassroomAssignmentRecord, MarkingSchemeCategory, RubricPreset
from apps.assessments.services.schemes import export_scheme, replace_scheme
from apps.assessments.services.evaluation import validate_evaluation_rubric
from apps.students.models import StudentClass, Student, ClassMembership


class ReusableCopyTests(TestCase):
    def setUp(self):
        self.course=Course.objects.create(course_id='COPY',name='Mathematics',information='Course information')
        self.period=CourseOffering.objects.create(course=self.course,academic_year='2569',semester='1')
        self.unit=CourseUnit.objects.create(course=self.course,unit_id='01',name='First unit')
        self.classroom=StudentClass.objects.create(class_number='4/1',academic_year='2569',notes='Class notes')
        self.period.classrooms.add(self.classroom)
        self.student=Student.objects.create(identifier_class=self.classroom,roll_number=1,full_name='Example Student',email='student@example.com',notes='Student notes')
        ClassMembership.objects.create(student=self.student,student_class=self.classroom)
        self.enrollment=Enrollment.objects.create(offering=self.period,student=self.student)
        self.rubric=[{'minimum':'75','label':'Achieved','is_fail':False},{'minimum':'0','label':'Revise','is_fail':True}]
        self.scheme=[{'name':'Knowledge','learning_objective':'Explain the concept','weight':'60','aggregation':'weighted_average','evaluation_rubric':self.rubric,
                      'items':[{'name':'Task A','maximum':'10','weight':'1'},{'name':'Task B','maximum':'10','weight':'3'}]},
                     {'name':'Skills','learning_objective':'Apply the concept','weight':'40','aggregation':'sum',
                      'items':[{'name':'Task C','maximum':'5','weight':'1'}]}]
        self.module=Assignment.objects.create(offering=self.period,unit=self.unit,assignment_number=1,name='Original module',information='Module information',calculation_mode='weighted',evaluation_rubric=self.rubric)
        replace_scheme(self.module,self.scheme)
        self.module.scheme_locked=True; self.module.score_revision=7;self.module.save(update_fields=['scheme_locked','score_revision'])
        for category in self.module.categories.all():
            for item in category.criteria.all():Score.objects.create(enrollment=self.enrollment,criterion=item,value=Decimal('3.5'))
        Attendance.objects.create(assignment=self.module,classroom=self.classroom,enrollment=self.enrollment,present=False)
        ClassroomAssignmentRecord.objects.create(assignment=self.module,classroom=self.classroom,learning_date=date(2026,10,19),module_status='completed',problem='Private problem',suggestion='Private suggestion',revision=3)
        self.source_marks=list(Score.objects.values_list('pk','enrollment_id','criterion_id','value'))

    def destination(self,course=None,year='2570',semester='1'):
        return CourseOffering.objects.create(course=course or self.course,academic_year=year,semester=semester)

    def assert_clean_copy(self,module):
        self.assertNotEqual(module.pk,self.module.pk)
        self.assertFalse(module.scheme_locked)
        self.assertEqual(module.score_revision,0)
        self.assertEqual(validate_evaluation_rubric(module.evaluation_rubric),validate_evaluation_rubric(self.module.evaluation_rubric))
        for original,copy in zip(export_scheme(self.module),export_scheme(module)):
            for field in ['name','learning_objective','aggregation','evaluation_rubric','weight']:
                self.assertEqual(copy[field],original[field],field)
            self.assertNotEqual(copy['id'],original['id'])
            for source_item,item in zip(original['items'],copy['items']):
                self.assertNotEqual(item['id'],source_item['id'])
                for field in ['name','maximum','weight']:self.assertEqual(item[field],source_item[field])
        self.assertFalse(Score.objects.filter(criterion__category__assignment=module).exists())
        self.assertFalse(module.attendance_records.exists())
        self.assertFalse(module.classroom_records.exists())
        self.assertEqual(list(Score.objects.values_list('pk','enrollment_id','criterion_id','value')),self.source_marks)
        self.module.refresh_from_db()
        self.assertTrue(self.module.scheme_locked)
        self.assertEqual(self.module.score_revision,7)
        self.assertFalse(self.module.attendance_records.get().present)
        self.assertEqual(self.module.classroom_records.get().problem,'Private problem')

    def test_individual_module_copy_can_change_year_number_and_name(self):
        destination=self.destination()
        url=f'/modules/{self.module.pk}/copy/'
        get=self.client.get(url)
        self.assertEqual(get.status_code,200)
        self.assertIsNone(get.context['form'].instance.pk)
        self.assertEqual(json.loads(get.context['form'].initial['evaluation_json']),self.rubric)
        data={'assignment_number':4,'name':'Copied module','offering':destination.pk,'unit':self.unit.pk,
              'information':'New information','calculation_mode':'weighted','scheme_json':json.dumps(export_scheme(self.module)),
              'evaluation_json':json.dumps(self.rubric)}
        response=self.client.post(url,data)
        self.assertEqual(response.status_code,302)
        copied=Assignment.objects.get(offering=destination)
        self.assertEqual(copied.assignment_id,'2570COPY04')
        self.assertEqual(copied.name,'Copied module')
        self.assert_clean_copy(copied)
        self.module.refresh_from_db();self.assertEqual(self.module.name,'Original module')
        copied.name='Independent';copied.save()
        self.module.refresh_from_db();self.assertEqual(self.module.name,'Original module')

    def test_period_copy_reuses_course_and_enrols_only_destination_students(self):
        classroom=StudentClass.objects.create(class_number='4/1',academic_year='2570')
        student=Student.objects.create(identifier_class=classroom,roll_number=1,full_name='Next year student')
        ClassMembership.objects.create(student=student,student_class=classroom)
        response=self.client.post(f'/courses/{self.course.pk}/periods/{self.period.pk}/copy/',{
            'destination_course':self.course.pk,'academic_year':'2570','semester':'2','classrooms':[classroom.pk],'modules':[self.module.pk]})
        self.assertEqual(response.status_code,302)
        destination=CourseOffering.objects.get(course=self.course,academic_year='2570')
        self.assertEqual(destination.semester,'2')
        self.assertEqual(list(destination.enrollments.values_list('student_id',flat=True)),[student.pk])
        self.assertEqual(Course.objects.count(),1)
        copied=destination.assignments.get();self.assertEqual(copied.assignment_id,'2570COPY01')
        self.assertEqual(copied.unit_id,self.unit.pk)
        self.assert_clean_copy(copied)

    def test_existing_period_keeps_roster_and_conflict_can_be_renumbered(self):
        url=f'/courses/{self.course.pk}/periods/{self.period.pk}/copy/'
        data={'existing_period':self.period.pk,'modules':[self.module.pk]}
        self.assertEqual(self.client.post(url,data).status_code,200)
        self.assertEqual(Assignment.objects.count(),1)
        self.assertEqual(self.client.post(url,{**data,'renumber':'on'}).status_code,302)
        copied=Assignment.objects.get(assignment_number=2)
        self.assert_clean_copy(copied)
        self.assertEqual(list(self.period.classrooms.values_list('pk',flat=True)),[self.classroom.pk])
        self.assertEqual(Enrollment.objects.count(),1)

    def test_course_copy_can_include_units_and_a_period(self):
        CourseUnit.objects.create(course=self.course,unit_id='02',name='Empty unit')
        response=self.client.post(f'/courses/{self.course.pk}/copy/',{'course_id':'NEW','name':'New course','information':'Info',
            'copy_units':'on','source_period':self.period.pk,'academic_year':'2571','semester':'1'})
        self.assertEqual(response.status_code,302)
        course=Course.objects.get(course_id='NEW')
        self.assertEqual(set(course.units.values_list('unit_id',flat=True)),{'01','02'})
        copied=course.offerings.get().assignments.get()
        self.assertEqual(copied.assignment_id,'2571NEW01')
        self.assertEqual(copied.unit.course_id,course.pk)
        self.assert_clean_copy(copied)

    def test_unit_copy_can_include_modules_with_independent_unit(self):
        response=self.client.post(f'/courses/{self.course.pk}/units/{self.unit.pk}/copy/',{
            'destination_course':self.course.pk,'unit_id':'02','name':'Copied unit','source_period':self.period.pk,
            'destination_period':self.period.pk,'renumber':'on'})
        self.assertEqual(response.status_code,302)
        copied=Assignment.objects.get(assignment_number=2)
        self.assertEqual(copied.unit.unit_id,'02')
        self.assertEqual(copied.unit.name,'Copied unit')
        self.assert_clean_copy(copied)

    def test_failed_bulk_copy_rolls_back_course_units_period_and_modules(self):
        broken=Assignment.objects.create(offering=self.period,assignment_number=2,name='No unit')
        replace_scheme(broken,self.scheme)
        counts=(Course.objects.count(),CourseUnit.objects.count(),CourseOffering.objects.count(),Assignment.objects.count())
        response=self.client.post(f'/courses/{self.course.pk}/copy/',{'course_id':'FAIL','name':'Do not create',
            'copy_units':'on','source_period':self.period.pk,'academic_year':'2571','semester':'1'})
        self.assertEqual(response.status_code,200)
        self.assertEqual((Course.objects.count(),CourseUnit.objects.count(),CourseOffering.objects.count(),Assignment.objects.count()),counts)
        self.assertFalse(Course.objects.filter(course_id='FAIL').exists())

    def test_destination_classroom_year_and_unit_course_are_validated(self):
        data={'destination_course':self.course.pk,'academic_year':'2570','semester':'1','classrooms':[self.classroom.pk],'modules':[self.module.pk]}
        response=self.client.post(f'/courses/{self.course.pk}/periods/{self.period.pk}/copy/',data)
        self.assertEqual(response.status_code,200)
        self.assertIn('classrooms',response.context['form'].errors)
        other=Course.objects.create(course_id='OTHER',name='Other')
        destination=self.destination(course=other)
        response=self.client.post(f'/courses/{self.course.pk}/units/{self.unit.pk}/copy/',{
            'destination_course':self.course.pk,'unit_id':'02','name':'Bad unit','source_period':self.period.pk,'destination_period':destination.pk})
        self.assertEqual(response.status_code,200)
        self.assertFalse(CourseUnit.objects.filter(course=self.course,unit_id='02').exists())

    def test_classroom_copy_can_start_empty_or_copy_new_student_ids(self):
        response=self.client.post(f'/classrooms/classes/{self.classroom.pk}/copy/',{'class_number':'4/1','academic_year':'2570','notes':'New','include_students':'on'})
        self.assertEqual(response.status_code,302)
        group=StudentClass.objects.get(academic_year='2570')
        student=Student.objects.get(identifier_class=group)
        self.assertEqual(student.student_number,'257040101')
        self.assertEqual(student.full_name,self.student.full_name)
        self.assertEqual(student.email,self.student.email)
        self.assertFalse(student.course_enrollments.exists())
        response=self.client.post(f'/classrooms/classes/{self.classroom.pk}/copy/',{'class_number':'4/2','academic_year':'2570','notes':'Empty'})
        self.assertEqual(response.status_code,302)
        self.assertFalse(StudentClass.objects.get(academic_year='2570',class_number='4/2').memberships.exists())

    def test_student_copy_requires_destination_and_generates_new_identity(self):
        group=StudentClass.objects.create(class_number='5/1',academic_year='2570')
        response=self.client.post(f'/classrooms/students/{self.student.pk}/copy/',{'student_class':group.pk,'roll_number':3,'full_name':'Copied student','email':'','notes':''})
        self.assertEqual(response.status_code,302)
        copied=Student.objects.get(identifier_class=group)
        self.assertEqual(copied.student_number,'257050103')
        self.assertFalse(copied.course_enrollments.exists())
        self.assertEqual(list(Score.objects.values_list('pk','enrollment_id','criterion_id','value')),self.source_marks)

    def test_all_copy_get_pages_are_read_only_and_render_in_both_languages(self):
        category=MarkingSchemeCategory.objects.first()
        preset=RubricPreset.objects.create(name='Original rubric',levels=self.rubric)
        urls=[f'/courses/{self.course.pk}/copy/',f'/courses/{self.course.pk}/periods/{self.period.pk}/copy/',
              f'/courses/{self.course.pk}/units/{self.unit.pk}/copy/',f'/modules/{self.module.pk}/copy/',
              f'/classrooms/classes/{self.classroom.pk}/copy/',f'/classrooms/students/{self.student.pk}/copy/',
              f'/modules/marking-library/{category.pk}/copy/',f'/modules/rubric-presets/add/?from=saved:{preset.pk}',
              '/courses/','/modules/','/classrooms/',f'/courses/{self.course.pk}/',f'/courses/{self.course.pk}/units/{self.unit.pk}/']
        models=[Course,CourseOffering,CourseUnit,Assignment,StudentClass,Student,MarkingSchemeCategory,RubricPreset]
        counts=[model.objects.count() for model in models]
        for lang in ['en','th']:
            self.client.cookies['django_language']=lang
            for url in urls:self.assertEqual(self.client.get(url).status_code,200,url)
        self.assertEqual([model.objects.count() for model in models],counts)

    def test_marking_library_copy_saves_an_independent_category(self):
        category=MarkingSchemeCategory.objects.first()
        response=self.client.get(f'/modules/marking-library/{category.pk}/copy/')
        form=response.context['form']
        data={key:form.initial[key] for key in ['name_th','name_en','subcategories_json']}
        count=MarkingSchemeCategory.objects.count()
        self.assertEqual(self.client.post(f'/modules/marking-library/{category.pk}/copy/',data).status_code,302)
        copied=MarkingSchemeCategory.objects.latest('pk')
        self.assertEqual(MarkingSchemeCategory.objects.count(),count+1)
        self.assertEqual(copied.subcategories[0]['name_th'],category.subcategories[0]['name_th'])

    def test_cross_course_period_copy_creates_needed_units(self):
        course=Course.objects.create(course_id='DEST',name='Destination')
        destination=self.destination(course=course)
        response=self.client.post(f'/courses/{self.course.pk}/periods/{self.period.pk}/copy/',{
            'existing_period':destination.pk,'modules':[self.module.pk]})
        self.assertEqual(response.status_code,302)
        copied=destination.assignments.get()
        self.assertEqual(copied.unit.unit_id,'01')
        self.assertEqual(copied.unit.course_id,course.pk)
        self.assertEqual(copied.assignment_id,'2570DEST01')
        self.assert_clean_copy(copied)

    def test_ambiguous_roll_numbers_roll_back_classroom_copy(self):
        legacy=Student.objects.create(student_number='legacy',full_name='Legacy student')
        ClassMembership.objects.create(student=legacy,student_class=self.classroom)
        response=self.client.post(f'/classrooms/classes/{self.classroom.pk}/copy/',{
            'class_number':'4/1','academic_year':'2570','notes':'','include_students':'on'})
        self.assertEqual(response.status_code,200)
        self.assertFalse(StudentClass.objects.filter(academic_year='2570').exists())
        self.assertEqual(Student.objects.count(),2)

    def test_csrf_is_required_to_commit_a_copy(self):
        from django.test import Client
        client=Client(enforce_csrf_checks=True)
        response=client.post(f'/courses/{self.course.pk}/copy/',{'course_id':'BLOCKED','name':'Not created'})
        self.assertEqual(response.status_code,403)
        self.assertFalse(Course.objects.filter(course_id='BLOCKED').exists())
