"""Reusable rubric copies; applying a preset never links category results to it."""
from copy import deepcopy
from django.utils.translation import gettext, gettext_noop
from django.core.exceptions import ValidationError
from apps.assessments.models import RubricPreset, RubricSettings
from .evaluation import default_evaluation_rubric, validate_evaluation_rubric


def bands(minima, labels):
    return [{"minimum": str(minimum), "label": label, "is_fail": index == len(minima) - 1}
            for index, (minimum, label) in enumerate(zip(minima, labels))]


# Fixed rubric content: interface language switches do not change grading labels.
# Add another entry here to ship an additional built-in preset.
BUILTIN_PRESETS = [
    {"id": "builtin:default", "name": gettext_noop("Default four levels (80 / 60 / 50)"),
     "levels": default_evaluation_rubric()},
    {"id": "builtin:thai-four", "name": gettext_noop("Thai four levels (80 / 60 / 50)"),
     "levels": bands([80, 60, 50, 0], ["ดีเยี่ยม", "ดี", "ผ่าน", "ไม่ผ่าน"])},
    {"id": "builtin:thai-three", "name": gettext_noop("Thai three levels (80 / 50)"),
     "levels": bands([80, 50, 0], ["ดี", "ผ่าน", "ไม่ผ่าน"])},
    {"id": "builtin:pass-50", "name": gettext_noop("Pass / Fail (pass at 50%)"),
     "levels": bands([50, 0], ["ผ่าน", "ไม่ผ่าน"])},
    {"id": "builtin:pass-60", "name": gettext_noop("Pass / Fail (pass at 60%)"),
     "levels": bands([60, 0], ["ผ่าน", "ไม่ผ่าน"])},
]


def builtin_catalog():
    return [{**deepcopy(preset), "name": gettext(preset["name"]), "builtin": True,
             "levels": validate_evaluation_rubric(preset["levels"])} for preset in BUILTIN_PRESETS]


def saved_preset_data(preset):
    return {"id": f"saved:{preset.pk}", "name": preset.name, "builtin": False,
            "levels": validate_evaluation_rubric(preset.levels)}


def rubric_preset_catalog():
    return builtin_catalog() + [saved_preset_data(preset) for preset in RubricPreset.objects.all()]


def default_rubric_preset():
    """Resolve the local preference without changing any saved module rubric."""
    key = RubricSettings.objects.filter(pk=1).values_list("preset_key", flat=True).first() or "builtin:default"
    builtins = builtin_catalog()
    for preset in builtins:
        if preset["id"] == key:
            return preset
    if key.startswith("saved:"):
        try:
            pk = int(key.split(":", 1)[1])
        except ValueError:
            pk = 0
        preset = RubricPreset.objects.filter(pk=pk).first()
        if preset:
            try:
                return saved_preset_data(preset)
            except ValidationError:
                pass
    # Missing/deleted presets never prevent teachers from opening a module.
    return builtins[0]


def current_default_evaluation_rubric():
    return deepcopy(default_rubric_preset()["levels"])
