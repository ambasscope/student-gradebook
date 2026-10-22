from django.utils.translation import gettext
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction, IntegrityError
from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404, redirect, render

from apps.students.models import ClassMembership, Student
from .forms import CourseForm, OfferingForm, CourseUnitForm
from .models import Course, CourseOffering, CourseUnit
from .services.enrollment import roster_plan, sync_roster



def page(request, template, **context):
    return render(request, "academics/" + template, {"active_page": "courses", **context})


def index(request):
    query = request.GET.get("q", "").strip()
    courses = Course.objects.annotate(period_count=Count("offerings", distinct=True), classroom_count=Count("offerings__classrooms", distinct=True)).order_by("course_id")
    if query:
        courses = courses.filter(Q(course_id__icontains=query) | Q(name__icontains=query))
    return page(request, "index.html", courses=Paginator(courses, 24).get_page(request.GET.get("page")), query=query)


def detail(request, pk):
    course = get_object_or_404(Course, pk=pk)
    from apps.assessments.models import Assignment
    modules = Assignment.objects.select_related("unit").order_by("unit__unit_id", "assignment_number", "assignment_id")
    periods = course.offerings.prefetch_related("classrooms", Prefetch("assignments", queryset=modules)).annotate(student_count=Count("enrollments", filter=Q(enrollments__is_active=True)))
    return page(request, "detail.html", course=course, periods=periods, units=course.units.annotate(module_count=Count("modules")))


def unit_detail(request, course_pk, pk):
    unit = get_object_or_404(CourseUnit.objects.select_related("course"), pk=pk, course_id=course_pk)
    modules = unit.modules.select_related("offering__course").order_by("-offering__academic_year", "offering__semester", "assignment_number")
    return page(request, "unit_detail.html", course=unit.course, unit=unit, modules=modules, periods=unit.course.offerings.all())


def unit_edit(request, course_pk, pk=None):
    course = get_object_or_404(Course, pk=course_pk)
    unit = get_object_or_404(CourseUnit, pk=pk, course=course) if pk else None
    form = CourseUnitForm(request.POST if request.method == "POST" else None, instance=unit, course=course)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                saved = form.save()
        except IntegrityError:
            form.add_error("unit_id", gettext("This unit ID is already used in this course."))
        else:
            messages.success(request, gettext("Unit saved."))
            return redirect("academics:unit-detail", course_pk=course.pk, pk=saved.pk)
    return page(request, "unit_edit.html", course=course, unit=unit, form=form, title=gettext("Edit unit") if unit else gettext("Add unit"))


def create(request):
    course_form = CourseForm(request.POST or None, prefix="course")
    offering_form = OfferingForm(request.POST or None, prefix="period")
    if request.method == "POST":
        valid_course, valid_period = course_form.is_valid(), offering_form.is_valid()
        if valid_course and valid_period:
            with transaction.atomic():
                course = course_form.save()
                period = offering_form.save(commit=False)
                period.course = course
                period.save()
                offering_form.save_m2m()
                sync_roster(period)
            messages.success(request, gettext("Course created and the selected classrooms enrolled."))
            return redirect("academics:detail", pk=course.pk)
    return page(request, "create.html", course_form=course_form, offering_form=offering_form)


def edit(request, pk):
    course = get_object_or_404(Course, pk=pk)
    form = CourseForm(request.POST or None, instance=course)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, gettext("Course details saved."))
        return redirect("academics:detail", pk=course.pk)
    return page(request, "edit.html", course=course, form=form)


def offering_edit(request, course_pk, pk=None):
    course = get_object_or_404(Course, pk=course_pk)
    period = get_object_or_404(CourseOffering, pk=pk, course=course) if pk else None
    form = OfferingForm(request.POST or None, instance=period, course=course)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            saved = form.save()
            sync_roster(saved)
        messages.success(request, gettext("Teaching period and classroom enrolment saved."))
        return redirect("academics:detail", pk=course.pk)
    return page(request, "offering_edit.html", course=course, form=form, title=gettext("Edit teaching period") if period else gettext("Add teaching period"))


def roster(request, course_pk, pk):
    period = get_object_or_404(CourseOffering.objects.select_related("course"), pk=pk, course_id=course_pk)
    classrooms = list(period.classrooms.all())
    query = request.GET.get("q", "").strip()
    students = Student.objects.filter(course_enrollments__offering=period, course_enrollments__is_active=True).prefetch_related(Prefetch("memberships", queryset=ClassMembership.objects.filter(student_class__in=classrooms).select_related("student_class")))
    if query:
        students = students.filter(Q(student_id__icontains=query) | Q(full_name__icontains=query))
    return page(request, "roster.html", course=period.course, period=period, classrooms=classrooms, students=Paginator(students, 50).get_page(request.GET.get("page")), query=query)


def roster_refresh(request, course_pk, pk):
    period = get_object_or_404(CourseOffering.objects.select_related("course"), pk=pk, course_id=course_pk)
    if request.method == "POST":
        try:
            plan = sync_roster(period, request.POST.get("fingerprint", ""))
        except ValidationError as error:
            messages.error(request, " ".join(error.messages))
        else:
            messages.success(request, gettext("Roster updated. Added: %(len_plan_added_ids)s. No longer enrolled: %(len_plan_removed_ids)s.") % {"len_plan_added_ids": len(plan['added_ids']), "len_plan_removed_ids": len(plan['removed_ids'])})
            return redirect("academics:roster", course_pk=course_pk, pk=pk)
    plan = roster_plan(period)
    return page(request, "roster_refresh.html", course=period.course, period=period, plan=plan, added=Student.objects.filter(pk__in=plan["added_ids"]), removed=Student.objects.filter(pk__in=plan["removed_ids"]))
