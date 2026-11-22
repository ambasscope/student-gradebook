"""Built-in rubric browsing and local, reusable user presets."""
import json
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import IntegrityError, OperationalError, transaction
from django.db.models import F
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
from .forms import DefaultRubricForm, RubricPresetForm
from .models import RubricPreset, RubricSettings
from .services.rubric_presets import builtin_catalog, rubric_preset_catalog, saved_preset_data, current_default_evaluation_rubric, default_rubric_preset


def index(request):
    form = DefaultRubricForm(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                RubricSettings.objects.update_or_create(pk=1, defaults={"preset_key": form.cleaned_data["preset_key"]})
        except (IntegrityError, OperationalError):
            form.add_error(None, _("The default rubric could not be saved. Try again."))
        else:
            messages.success(request, _("Default evaluation rubric saved. Existing modules and scores are unchanged."))
            return redirect("assessments:rubric-presets")
    return render(request, "assessments/rubric_presets.html", {
        "active_page": "assignments", "builtin_presets": builtin_catalog(),
        "saved_presets": RubricPreset.objects.all(), "default_form": form})


def editor(request, pk=None):
    instance = get_object_or_404(RubricPreset, pk=pk) if pk is not None else None
    form = RubricPresetForm(request.POST if request.method == "POST" else None, instance=instance)
    if request.method == "POST" and form.is_valid():
        try:
            with transaction.atomic():
                if instance:
                    changed = RubricPreset.objects.filter(pk=instance.pk, revision=form.cleaned_data["revision"]).update(
                        name=form.cleaned_data["name"], levels=form.cleaned_data["rubric_json"],
                        revision=F("revision") + 1, updated_at=timezone.now())
                    if not changed:
                        raise ValidationError(_("This preset changed in another window. Reload before saving."))
                else:
                    RubricPreset.objects.create(name=form.cleaned_data["name"], levels=form.cleaned_data["rubric_json"])
        except ValidationError as error:
            form.add_error(None, error)
        except (IntegrityError, OperationalError):
            form.add_error(None, _("The preset could not be saved. Its name may already be used, or another save is in progress. Reload and try again."))
        else:
            messages.success(request, _("Rubric preset saved. Existing module categories keep their current levels."))
            return redirect("assessments:rubric-presets")
    try:
        levels = json.loads(form["rubric_json"].value() or "[]")
        if not isinstance(levels, list):
            levels = current_default_evaluation_rubric()
    except (ValueError, TypeError):
        levels = current_default_evaluation_rubric()
    if not instance and request.method != "POST":
        source = next((item for item in rubric_preset_catalog() if item["id"] == request.GET.get("from")), None)
        if source:
            levels = source["levels"]
    return render(request, "assessments/rubric_preset_edit.html", {
        "active_page": "assignments", "form": form, "preset": instance,
        "initial_rubric": levels, "rubric_presets": rubric_preset_catalog(),
        "default_evaluation": current_default_evaluation_rubric()})


def delete(request, pk):
    preset = get_object_or_404(RubricPreset, pk=pk)
    error = ""
    if request.method == "POST":
        try:
            revision = int(request.POST.get("revision", ""))
        except (ValueError, TypeError):
            revision = None
        try:
            with transaction.atomic():
                deleted, _details = RubricPreset.objects.filter(pk=preset.pk, revision=revision).delete()
                if not deleted:
                    error = _("This preset changed in another window. Reload before deleting.")
                else:
                    RubricSettings.objects.filter(pk=1, preset_key=f"saved:{preset.pk}").update(preset_key="builtin:default")
        except OperationalError:
            error = _("Another save is in progress. Try again.")
        if not error:
            messages.success(request, _("Rubric preset deleted. Existing module categories are unchanged."))
            return redirect("assessments:rubric-presets")
    return render(request, "assessments/rubric_preset_delete.html", {
        "active_page": "assignments", "preset": preset, "error": error,
        "is_default": default_rubric_preset()["id"] == f"saved:{preset.pk}"})


@require_POST
def save_copy(request):
    """Save the current category rubric without saving the module form."""
    try:
        payload = json.loads(request.body)
        if not isinstance(payload, dict) or not isinstance(payload.get("name"), str):
            raise ValueError
    except (ValueError, UnicodeError):
        return JsonResponse({"error": _("The rubric preset could not be read. Review it and try again.")}, status=400)
    form = RubricPresetForm({"name": payload["name"], "rubric_json": json.dumps(payload.get("levels"), ensure_ascii=False)})
    if not form.is_valid():
        return JsonResponse({"error": " ".join(message for errors in form.errors.values() for message in errors)}, status=400)
    try:
        with transaction.atomic():
            preset = RubricPreset.objects.create(name=form.cleaned_data["name"], levels=form.cleaned_data["rubric_json"])
    except (IntegrityError, OperationalError):
        return JsonResponse({"error": _("The preset could not be saved. Its name may already be used, or another save is in progress. Reload and try again.")}, status=409)
    return JsonResponse({"preset": saved_preset_data(preset)}, status=201)
