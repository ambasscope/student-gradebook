from django import forms
from django.db.models import Count
from django.utils.translation import gettext_lazy as _
from config.semesters import legacy_semester_number
from apps.students.models import StudentClass
from apps.assessments.models import Assignment
from .models import Course, CourseOffering
from .forms import CourseForm, OfferingForm, CourseUnitForm, ClassroomChoiceField
from .services.copying import next_year


class PeriodCopyForm(forms.Form):
    existing_period = forms.ModelChoiceField(label=_("Existing destination teaching period (optional)"), queryset=CourseOffering.objects.select_related('course'), required=False,
        help_text=_("Choose an existing period, or leave blank and enter the new period below. Existing classroom enrolments are kept."))
    destination_course = forms.ModelChoiceField(label=_("Destination course"), queryset=Course.objects.all(), required=False)
    academic_year = forms.CharField(label=_("Academic year"), max_length=4, required=False)
    semester = forms.CharField(label=_("Semester"), required=False, widget=forms.NumberInput(attrs={'min':1,'step':1}))
    classrooms = ClassroomChoiceField(label=_("Classrooms"), queryset=StudentClass.objects.annotate(student_count=Count('memberships')), required=False, widget=forms.CheckboxSelectMultiple,
        help_text=_("For a new period, choose classrooms belonging to the destination academic year."))
    modules = forms.ModelMultipleChoiceField(label=_("Modules to copy"), queryset=Assignment.objects.none(), required=False, widget=forms.CheckboxSelectMultiple)
    renumber = forms.BooleanField(label=_("Use available module numbers when a number is already used"), required=False,
        help_text=_("Otherwise existing module numbers are preserved and conflicts stop the whole copy. Legacy modules without numbers receive available numbers."))

    def __init__(self, *args, source, **kwargs):
        self.source = source
        super().__init__(*args, **kwargs)
        self.fields['modules'].queryset = source.assignments.order_by('assignment_number','pk')
        self.initial.update(destination_course=source.course_id, academic_year=next_year(source.academic_year), semester=legacy_semester_number(source.semester) or '',
                            modules=list(source.assignments.values_list('pk',flat=True)))

    def clean(self):
        data = super().clean()
        if data.get('existing_period'):
            return data
        if not data.get('destination_course'):
            self.add_error('destination_course', _("Choose a destination course."))
            return data
        form = OfferingForm({'academic_year':data.get('academic_year',''), 'semester':data.get('semester',''),
                             'classrooms':[group.pk for group in data.get('classrooms',[])]}, course=data['destination_course'])
        if not form.is_valid():
            for field, errors in form.errors.items():
                for error in errors:
                    self.add_error(field if field in self.fields else None, error)
        else:
            data.update({field:form.cleaned_data[field] for field in ['academic_year','semester','classrooms']})
        return data


class CourseCopyForm(CourseForm):
    copy_units = forms.BooleanField(label=_("Copy all units"), required=False, initial=True,
        help_text=_("Units needed by copied modules are always included."))
    source_period = forms.ModelChoiceField(label=_("Copy a teaching period and its modules (optional)"), queryset=CourseOffering.objects.none(), required=False)
    academic_year = forms.CharField(label=_("Destination academic year"), max_length=4, required=False)
    semester = forms.CharField(label=_("Semester"), required=False, widget=forms.NumberInput(attrs={'min':1,'step':1}))
    classrooms = ClassroomChoiceField(label=_("Destination classrooms"), queryset=StudentClass.objects.annotate(student_count=Count('memberships')), required=False, widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, source, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['source_period'].queryset = source.offerings.all()
        self.initial.update(course_id='', name=source.name, information=source.information, copy_units=True)
        latest=source.offerings.first()
        if latest:self.initial.update(academic_year=next_year(latest.academic_year), semester=legacy_semester_number(latest.semester) or '')

    def clean(self):
        data=super().clean()
        if data.get('source_period'):
            period = OfferingForm({'academic_year':data.get('academic_year',''), 'semester':data.get('semester',''),
                                   'classrooms':[group.pk for group in data.get('classrooms',[])]})
            if not period.is_valid():
                for field,errors in period.errors.items():
                    for error in errors:self.add_error(field if field in self.fields else None,error)
            else:
                data.update({field:period.cleaned_data[field] for field in ['academic_year','semester','classrooms']})
        return data


class UnitCopyForm(CourseUnitForm):
    destination_course = forms.ModelChoiceField(label=_("Destination course"), queryset=Course.objects.all())
    source_period = forms.ModelChoiceField(label=_("Copy modules from teaching period (optional)"), queryset=CourseOffering.objects.none(), required=False)
    destination_period = forms.ModelChoiceField(label=_("Destination teaching period"), queryset=CourseOffering.objects.select_related('course'), required=False)
    renumber = forms.BooleanField(label=_("Use available module numbers when a number is already used"), required=False)

    def __init__(self, *args, source, **kwargs):
        data=args[0] if args else kwargs.get('data')
        course=source.course
        if data:
            try:course=Course.objects.get(pk=data.get('destination_course'))
            except (Course.DoesNotExist,ValueError,TypeError):pass
        super().__init__(*args, course=course, **kwargs)
        self.fields['source_period'].queryset = source.course.offerings.filter(assignments__unit=source).distinct()
        self.initial.update(destination_course=source.course_id, unit_id=source.unit_id, name=source.name)
        self.order_fields(['destination_course','unit_id','name','source_period','destination_period','renumber'])

    def clean(self):
        data=super().clean()
        if data.get('source_period'):
            if not data.get('destination_period'):
                self.add_error('destination_period', _("Choose a destination teaching period to copy these modules."))
            elif data.get('destination_course') and data['destination_period'].course_id != data['destination_course'].pk:
                self.add_error('destination_period', _("Choose a teaching period belonging to the destination course."))
        return data
