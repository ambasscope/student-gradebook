from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction, IntegrityError, OperationalError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.translation import gettext as _
from .copy_forms import CourseCopyForm, PeriodCopyForm, UnitCopyForm
from .models import Course, CourseOffering, CourseUnit
from .services.copying import create_period, copy_modules


def attempt(form, operation):
    try:
        with transaction.atomic():
            return operation()
    except ValidationError as error:
        form.add_error(None, error)
    except (IntegrityError, OperationalError):
        form.add_error(None, _("The copy conflicts with existing data or another save. Nothing was copied. Review the destination and try again."))
    return None


def page(request, form, source, title, explanation):
    return render(request,'copy_form.html',{'active_page':'courses','form':form,'source':source,'title':title,'explanation':explanation})


def course(request, pk):
    source=get_object_or_404(Course,pk=pk)
    form=CourseCopyForm(request.POST if request.method=='POST' else None,source=source)
    if request.method=='POST' and form.is_valid():
        def save():
            saved=form.save()
            if form.cleaned_data['copy_units']:
                CourseUnit.objects.bulk_create([CourseUnit(course=saved,unit_id=unit.unit_id,name=unit.name) for unit in source.units.all()])
            period=form.cleaned_data.get('source_period')
            if period:
                destination=create_period(saved,form.cleaned_data['academic_year'],form.cleaned_data['semester'],form.cleaned_data['classrooms'])
                copy_modules(period.assignments.all(),destination)
            return saved
        saved=attempt(form,save)
        if saved:
            messages.success(request,_("Course copied. The original course and all student results are unchanged."))
            return redirect('academics:detail',pk=saved.pk)
    return page(request,form,source,_("Copy course"),_("Enter a new course ID and review its details. Optionally copy its units and one teaching period with all its modules. Choose the destination year, semester, and classrooms if copying a period."))


def period(request,course_pk,pk):
    source=get_object_or_404(CourseOffering.objects.select_related('course'),pk=pk,course_id=course_pk)
    form=PeriodCopyForm(request.POST if request.method=='POST' else None,source=source)
    if request.method=='POST' and form.is_valid():
        def save():
            destination=form.cleaned_data.get('existing_period')
            if destination is None:
                destination=create_period(form.cleaned_data['destination_course'],form.cleaned_data['academic_year'],form.cleaned_data['semester'],form.cleaned_data['classrooms'])
            copy_modules(form.cleaned_data['modules'],destination,renumber=form.cleaned_data['renumber'])
            return destination
        saved=attempt(form,save)
        if saved:
            messages.success(request,_("Teaching period copied. The copied modules are ready to edit and have no student results."))
            return redirect('academics:detail',pk=saved.course_id)
    return page(request,form,source,_("Copy teaching period"),_("Choose an existing destination period, or create a new one below. Select the modules to copy. Their units, objectives, marking schemes, and rubrics are copied; student scores, attendance, dates, and classroom comments start empty."))


def unit(request,course_pk,pk):
    source=get_object_or_404(CourseUnit.objects.select_related('course'),pk=pk,course_id=course_pk)
    form=UnitCopyForm(request.POST if request.method=='POST' else None,source=source)
    if request.method=='POST' and form.is_valid():
        def save():
            saved=form.save()
            source_period=form.cleaned_data.get('source_period')
            if source_period:
                copy_modules(source_period.assignments.filter(unit=source),form.cleaned_data['destination_period'],
                             unit_override=saved,renumber=form.cleaned_data['renumber'])
            return saved
        saved=attempt(form,save)
        if saved:
            messages.success(request,_("Unit copied. Its original modules and student results are unchanged."))
            return redirect('academics:unit-detail',course_pk=saved.course_id,pk=saved.pk)
    return page(request,form,source,_("Copy unit"),_("Choose a destination course and an unused unit ID. Optionally select a source teaching period and a destination period to copy this unit's modules too."))
