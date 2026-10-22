from django.utils.translation import gettext
import csv
import time
import uuid

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import Count, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from django.core.exceptions import ValidationError
from .copying import ClassroomCopyForm, copy_classroom
from apps.academics.services.copying import next_year
from .forms import ColumnMappingForm, ImportUploadForm, StudentClassForm, StudentForm
from .models import ClassMembership, Student, StudentClass
from .services.imports import ImportProblem, build_plan, commit_import, map_records, parse_file, suggest_mapping



def page(request, template, **context):
    return render(request, "students/" + template, {"active_page": "students", **context})


def pending_import(request):
    pending = request.session.get("student_import")
    if pending and time.time() - pending["created"] < 1800:
        return pending
    request.session.pop("student_import", None)
    messages.info(request, gettext("Upload a student list to start a new import. Previews expire after 30 minutes."))
    return None


def index(request):
    query = request.GET.get("q", "").strip()
    year = request.GET.get("year", "").strip()
    groups = StudentClass.objects.annotate(student_count=Count("memberships")).order_by("-academic_year", "class_number", "pk")
    if query:
        groups = groups.filter(Q(class_number__icontains=query) | Q(notes__icontains=query))
    if year:
        groups = groups.filter(academic_year=year)
    return page(request, "classrooms.html", groups=Paginator(groups, 24).get_page(request.GET.get("page")), years=StudentClass.objects.values_list("academic_year", flat=True).distinct().order_by("-academic_year"), query=query, selected_year=year)


def all_students(request):
    students = Student.objects.prefetch_related("memberships__student_class")
    query = request.GET.get("q", "").strip()
    group_id = request.GET.get("class", "")
    year = request.GET.get("year", "").strip()
    if query:
        students = students.filter(Q(student_id__icontains=query) | Q(full_name__icontains=query) | Q(roll_number__icontains=query))
    membership_filters = {}
    if group_id.isdigit():
        membership_filters["memberships__student_class_id"] = group_id
    if year:
        membership_filters["memberships__student_class__academic_year"] = year
    if membership_filters:
        students = students.filter(**membership_filters)
    students = students.distinct()
    parameters = request.GET.copy()
    parameters.pop("page", None)
    return page(request, "index.html", students=Paginator(students, 50).get_page(request.GET.get("page")), groups=StudentClass.objects.all(), years=StudentClass.objects.values_list("academic_year", flat=True).distinct().order_by("-academic_year"), query=query, selected_class=group_id, selected_year=year, filter_query=parameters.urlencode())


def classroom_detail(request, pk):
    group = get_object_or_404(StudentClass, pk=pk)
    query = request.GET.get("q", "").strip()
    students = Student.objects.filter(memberships__student_class=group)
    if query:
        students = students.filter(Q(student_id__icontains=query) | Q(full_name__icontains=query) | Q(roll_number__icontains=query))
    students = students.order_by("roll_number", "student_number")
    periods = group.course_offerings.select_related("course")
    return page(request, "classroom_detail.html", group=group, students=Paginator(students, 50).get_page(request.GET.get("page")), query=query, periods=periods)


def import_upload(request):
    initial = {}
    group_id = request.GET.get("class", "")
    if group_id.isdigit():
        group = StudentClass.objects.filter(pk=group_id).first()
        if group:
            initial = {"class_number": group.class_number, "academic_year": group.academic_year}
    form = ImportUploadForm(request.POST or None, request.FILES or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        data = form.cleaned_data
        try:
            table = parse_file(data["student_file"], encoding=data["encoding"], sheet_name=data["sheet_name"])
        except ImportProblem as error:
            form.add_error("student_file", str(error))
        else:
            request.session["student_import"] = {
                "token": uuid.uuid4().hex, "created": time.time(), "table": table,
                "metadata": {key: data[key] for key in ["class_number", "academic_year", "class_notes", "update_existing"]},
            }
            return redirect("students:import-map")
    return page(request, "import_upload.html", form=form)


def import_map(request):
    pending = pending_import(request)
    if pending is None:
        return redirect("students:import-upload")
    table = pending["table"]
    initial = {**suggest_mapping(table["headers"]), **pending.get("mapping", {}), "token": pending["token"]}
    form = ColumnMappingForm(table["headers"], request.POST or None, initial=initial)
    if request.method == "POST" and form.is_valid():
        if form.cleaned_data["token"] != pending["token"]:
            form.add_error(None, gettext("This preview belongs to an older upload. Reload this page and match the current file."))
        else:
            pending["mapping"] = form.cleaned_data
            pending["records"] = map_records(table, form.cleaned_data)
            request.session["student_import"] = pending
            return redirect("students:import-preview")
    return page(request, "import_map.html", form=form, headers=table["headers"], sample_rows=table["rows"][:5], metadata=pending["metadata"], total=len(table["rows"]))


def import_preview(request):
    pending = pending_import(request)
    if pending is None:
        return redirect("students:import-upload")
    if "records" not in pending:
        return redirect("students:import-map")
    plan = build_plan(pending["records"], pending["metadata"])
    return page(request, "import_preview.html", plan=plan, preview_rows=plan["rows"][:100], row_errors=plan["errors"][:100], metadata=pending["metadata"], token=pending["token"])


@require_POST
def import_confirm(request):
    pending = pending_import(request)
    if pending is None:
        return redirect("students:import-upload")
    if request.POST.get("token") != pending["token"] or "records" not in pending:
        messages.error(request, gettext("This preview is no longer current. Review the latest file before importing."))
        return redirect("students:import-map")
    try:
        group, counts = commit_import(pending["records"], pending["metadata"])
    except (ImportProblem, IntegrityError, OperationalError):
        messages.error(request, gettext("No changes were saved. Some student details changed or the file contains errors; review the preview."))
        return redirect("students:import-preview")
    request.session.pop("student_import", None)
    messages.success(request, gettext("Import complete. New students: %(counts_new)s. Updated: %(counts_updated)s. Existing students added to this class: %(counts_linked)s. Already present: %(counts_unchanged)s.") % {"counts_new": counts['new'], "counts_updated": counts['updated'], "counts_linked": counts['linked'], "counts_unchanged": counts['unchanged']})
    return redirect("students:classroom-detail", pk=group.pk)


def import_template(request):
    response = HttpResponse(content_type="text/csv; charset=utf-8")
    response["Content-Disposition"] = 'attachment; filename="student-list-template.csv"'
    response.write("\ufeff")
    csv.writer(response).writerows([["roll_number", "student_name", "student_id", "email", "notes"], ["3", "Example Student", "001234", "", ""]])
    return response


def student_edit(request, pk=None, copy_source=None):
    student = get_object_or_404(Student, pk=pk) if pk else None
    group_id = request.GET.get("class", "")
    initial = {"student_class": group_id} if group_id.isdigit() else {}
    if copy_source is not None:
        initial = {"status":copy_source.status,"resignation_date":copy_source.resignation_date,"student_id":copy_source.student_id,"full_name":copy_source.full_name,"email":copy_source.email,"notes":copy_source.notes,
                   "roll_number":copy_source.roll_number,**initial}
    form = StudentForm(request.POST if request.method == "POST" else None, instance=student, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                saved = form.save()
                if form.cleaned_data["student_class"]:
                    ClassMembership.objects.get_or_create(student=saved, student_class=form.cleaned_data["student_class"])
        except (IntegrityError, OperationalError):
            form.add_error(None, gettext("This classroom roll number was saved in another window. No changes were saved; reload and try again."))
        else:
            messages.success(request, gettext("Student saved."))
            selected = form.cleaned_data["student_class"]
            return redirect("students:classroom-detail", pk=selected.pk) if selected else redirect("students:all")
    return page(request, "edit.html", form=form, student=student, copy_source=copy_source, title=gettext("Copy student") if copy_source else gettext("Edit student") if student else gettext("Add student"))


def student_copy(request, pk):
    return student_edit(request, copy_source=get_object_or_404(Student, pk=pk))


def classroom_copy(request, pk):
    source = get_object_or_404(StudentClass, pk=pk)
    form = ClassroomCopyForm(request.POST if request.method == "POST" else None,
        initial={"class_number":source.class_number,"academic_year":next_year(source.academic_year),"notes":source.notes})
    if request.method == "POST" and form.is_valid():
        try:
            saved = copy_classroom(form, source)
        except ValidationError as error:
            form.add_error(None, error)
        except (IntegrityError, OperationalError):
            form.add_error(None, gettext("The copy conflicts with existing data or another save. Nothing was copied. Review the destination and try again."))
        else:
            messages.success(request, gettext("Classroom copied. Existing students, enrolments, and scores are unchanged."))
            return redirect("students:classroom-detail", pk=saved.pk)
    return render(request, "copy_form.html", {"active_page":"students","form":form,"source":source,
        "title":gettext("Copy classroom"),"explanation":gettext("Choose the destination classroom and academic year. You can start with an empty classroom or copy its student list with newly generated student IDs.")})


def classes(request, pk=None):
    group = get_object_or_404(StudentClass, pk=pk) if pk else None
    form = StudentClassForm(request.POST or None, instance=group)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, gettext("Class details saved."))
        return redirect("students:classes")
    return page(request, "classes.html", form=form, groups=StudentClass.objects.all(), title=gettext("Edit class") if group else gettext("Classes and academic years"))
