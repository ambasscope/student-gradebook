from django.utils.translation import gettext
import json
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import Prefetch, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_POST
from apps.academics.models import CourseOffering, CourseUnit
from apps.students.models import StudentClass
from .forms import AssignmentForm
from .models import Assignment, Score
from .services.schemes import export_scheme, replace_scheme, update_locked_scheme
from .services.scoring import ScoreProblem, grid_data, save_scores
from .services.presets import preset_catalog
from .services.marking_library import category_catalog
from .services.rubric_presets import rubric_preset_catalog, current_default_evaluation_rubric
from .services.classroom_records import comment_phrase_groups



def page(request, template, **context):
    return render(request, "assessments/" + template, {"active_page": "assignments", **context})


def index(request):
    query = request.GET.get("q", "").strip()
    assignments = Assignment.objects.select_related("offering__course", "unit").prefetch_related("categories__criteria")
    if query:
        assignments = assignments.filter(Q(assignment_id__icontains=query) | Q(name__icontains=query) | Q(offering__course__name__icontains=query) | Q(offering__course__course_id__icontains=query))
    return page(request, "index.html", assignments=Paginator(assignments, 24).get_page(request.GET.get("page")), query=query)


def detail(request, pk):
    assignment = get_object_or_404(Assignment.objects.select_related("offering__course", "unit"), pk=pk)
    classrooms = assignment.offering.classrooms.all()
    return page(request, "detail.html", assignment=assignment, classrooms=classrooms, scheme=export_scheme(assignment), category_rubrics=export_scheme(assignment))


def editor(request, instance=None, copy_source=None):
    initial = {}
    period_id = request.GET.get("period", "")
    if period_id.isdigit() and CourseOffering.objects.filter(pk=period_id).exists():
        initial["offering"] = period_id
    unit_id = request.GET.get("unit", "")
    if unit_id.isdigit() and CourseUnit.objects.filter(pk=unit_id).exists():
        initial["unit"] = unit_id
    if copy_source is not None:
        used = set(Assignment.objects.filter(offering__course=copy_source.offering.course, offering__academic_year=copy_source.offering.academic_year).values_list("assignment_number", flat=True))
        number = next((n for n in range(1, 100) if n not in used), None)
        initial = {"offering": copy_source.offering_id, "unit": copy_source.unit_id,
                   "assignment_number": number, "name": copy_source.name, "information": copy_source.information,
                   "calculation_mode": copy_source.calculation_mode, "scheme_json": json.dumps(export_scheme(copy_source), ensure_ascii=False),
                   "evaluation_json": json.dumps(copy_source.evaluation_rubric, ensure_ascii=False), **initial}
        if str(initial["offering"]) != str(copy_source.offering_id):
            initial["assignment_number"] = copy_source.assignment_number
    form = AssignmentForm(request.POST if request.method == "POST" else None, instance=instance, initial=initial)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                if instance is None:
                    saved = form.save(commit=False)
                    saved.evaluation_rubric = form.evaluation
                    saved.save()
                    replace_scheme(saved, form.scheme)
                else:
                    saved = Assignment.objects.select_for_update().get(pk=instance.pk)
                    if form.evaluation_submitted and form.cleaned_data["evaluation_revision"] != saved.scheme_revision:
                        raise ValidationError(gettext("The evaluation rubric changed in another window. Reload before editing it."))
                    if form.scheme is not None and saved.scheme_locked and not instance.scheme_locked:
                        raise ValidationError(gettext("Marking started in another window. Reload the page before changing the module."))
                    if form.scheme is not None and form.cleaned_data["scheme_revision"] != saved.scheme_revision:
                        raise ValidationError(gettext("The scheme changed in another window. Reload before editing it."))
                    saved.assignment_number = form.cleaned_data["assignment_number"]
                    saved.assignment_id = form.instance.assignment_id
                    saved.name = form.cleaned_data["name"]
                    saved.information = form.cleaned_data["information"]
                    saved.unit = form.cleaned_data["unit"]
                    saved.evaluation_rubric = form.evaluation
                    fields = ["assignment_number", "assignment_id", "name", "information", "unit", "evaluation_rubric", "updated_at"]
                    if not saved.scheme_locked:
                        saved.offering = form.cleaned_data["offering"]
                        saved.calculation_mode = form.cleaned_data["calculation_mode"]
                        fields.extend(["offering", "calculation_mode"])
                    saved.save(update_fields=fields)
                    if saved.scheme_locked:
                        update_locked_scheme(saved, form.scheme, form.cleaned_data["scheme_revision"])
                    else:
                        replace_scheme(saved, form.scheme, form.cleaned_data["scheme_revision"])
        except ValidationError as error:
            form.add_error(None, error)
        except (IntegrityError, OperationalError):
            form.add_error(None, gettext("The module changed while saving. No changes were saved; reload and try again."))
        else:
            messages.success(request, gettext("Module saved."))
            return redirect("assessments:detail", pk=saved.pk)
    try:
        initial_scheme = json.loads(form["scheme_json"].value() or "[]")
        if not isinstance(initial_scheme, list):
            initial_scheme = []
    except (ValueError, TypeError):
        initial_scheme = []
    try:
        initial_evaluation = json.loads(form["evaluation_json"].value() or "[]")
        if not isinstance(initial_evaluation, list):
            initial_evaluation = []
    except (ValueError, TypeError):
        initial_evaluation = []
    unit_options = [{"id": unit.pk, "course": unit.course_id, "label": str(unit)} for unit in CourseUnit.objects.all()]
    offering_courses = {str(pk): course for pk, course in CourseOffering.objects.values_list("pk", "course_id")}
    return page(request, "edit.html", form=form, assignment=instance, copy_source=copy_source, initial_scheme=initial_scheme, initial_evaluation=initial_evaluation, default_evaluation=current_default_evaluation_rubric(), rubric_presets=rubric_preset_catalog(), presets=preset_catalog(), marking_library=category_catalog(), unit_options=unit_options, offering_courses=offering_courses, locked=bool(instance and instance.scheme_locked), title=gettext("Copy module") if copy_source else gettext("Edit module") if instance else gettext("Add module"))


def create(request):
    return editor(request)


def edit(request, pk):
    return editor(request, get_object_or_404(Assignment, pk=pk))


def copy_module(request, pk):
    source = get_object_or_404(Assignment.objects.select_related("offering__course", "unit"), pk=pk)
    return editor(request, copy_source=source)


def classroom_scores(request, pk, classroom_pk):
    assignment = get_object_or_404(Assignment.objects.select_related("offering__course", "unit"), pk=pk)
    classroom = get_object_or_404(assignment.offering.classrooms, pk=classroom_pk)
    config = grid_data(assignment, classroom)
    config["save_url"] = reverse("assessments:save-scores", args=[pk, classroom_pk])
    missing = classroom.memberships.exclude(student_id__in=assignment.offering.enrollments.filter(is_active=True).values_list("student_id", flat=True)).count()
    return page(request, "scores.html", assignment=assignment, classroom=classroom, grid=config, missing_students=missing, category_rubrics=export_scheme(assignment), classroom_notes=config["classroom_notes"], comment_phrases=comment_phrase_groups(config["classroom_notes"]))


@require_POST
def save_scores_view(request, pk, classroom_pk):
    get_object_or_404(Assignment, pk=pk)
    try:
        payload = json.loads(request.body)
    except (ValueError, UnicodeError):
        return JsonResponse({"error": gettext("The score batch could not be read.")}, status=400)
    try:
        result = save_scores(pk, classroom_pk, payload)
    except ScoreProblem as error:
        return JsonResponse({"error": str(error)}, status=error.status)
    except (IntegrityError, OperationalError):
        return JsonResponse({"error": gettext("Another save is in progress or the roster changed. No changes were saved; try again or reload.")}, status=409)
    return JsonResponse(result)
