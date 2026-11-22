"""Validate a two-level marking scheme before replacing any database records."""
from django.utils.translation import gettext
import json
from config.numbers import compact_number
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from apps.assessments.models import Assignment, Criterion, MarkingCategory
from .evaluation import default_evaluation_rubric, validate_evaluation_rubric, evaluation_ranges


def decimal_value(value, label, minimum=Decimal("0"), maximum=Decimal("999999.99")):
    if isinstance(value, (bool, list, dict)) or value is None:
        raise ValidationError(gettext("%(label)s: enter a number.") % {"label": label})
    try:
        result = Decimal(str(value).strip())
        if not result.is_finite() or result < minimum or result > maximum:
            raise InvalidOperation
        rounded = result.quantize(Decimal("0.01"))
        if rounded != result:
            raise ValidationError(gettext("%(label)s: use at most two decimal places.") % {"label": label})
    except (InvalidOperation, ValueError):
        raise ValidationError(gettext("%(label)s: enter a number between %(minimum)s and %(maximum)s.") % {"label": label, "minimum": compact_number(minimum), "maximum": compact_number(maximum)})
    return rounded


def text_value(value, label, maximum):
    if not isinstance(value, str) or not value.strip() or len(value.strip()) > maximum:
        raise ValidationError(gettext("%(label)s: enter text of at most %(maximum)s characters.") % {"label": label, "maximum": maximum})
    return value.strip()


def validate_scheme(raw, mode, default_rubric=None):
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (ValueError, TypeError):
        raise ValidationError(gettext("The marking scheme could not be read. Review the categories and try again."))
    if not isinstance(data, list) or not 1 <= len(data) <= 30:
        raise ValidationError(gettext("Add between 1 and 30 categories."))
    result, total_items = [], 0
    for category_index, category in enumerate(data, 1):
        if not isinstance(category, dict):
            raise ValidationError(gettext("Each category needs a name, learning objective, and subcategory list."))
        name = text_value(category.get("name"), gettext("Category name"), 150)
        objective = category.get("learning_objective", "")
        if not isinstance(objective, str) or len(objective) > 5000:
            raise ValidationError(gettext("Each learning objective must be text of at most 5,000 characters."))
        weight = decimal_value(category.get("weight") or 0, gettext("Category weight"), maximum=Decimal("100")) if mode == Assignment.Calculation.WEIGHTED else Decimal("0")
        aggregation = category.get("aggregation", MarkingCategory.Aggregation.SUM)
        if aggregation not in MarkingCategory.Aggregation.values:
            raise ValidationError(gettext("Choose Sum, Average, or Weighted average for each category."))
        rubric = validate_evaluation_rubric(category.get("evaluation_rubric", default_rubric if default_rubric is not None else default_evaluation_rubric()))
        items = category.get("items")
        if not isinstance(items, list):
            raise ValidationError(gettext("Each category needs a subcategory list, which may be empty in a draft."))
        criteria = []
        for item_index, item in enumerate(items, 1):
            if not isinstance(item, dict):
                raise ValidationError(gettext("Each subcategory needs a name and maximum mark."))
            criteria.append({"code": f"S{item_index}", "name": text_value(item.get("name"), gettext("Subcategory name"), 150), "maximum": decimal_value(item.get("maximum"), gettext("Subcategory maximum"), minimum=Decimal("0.01")), "weight": decimal_value(item.get("weight", 1), gettext("Subcategory weight"), minimum=Decimal("0.01"), maximum=Decimal("9999.99"))})
        total_items += len(criteria)
        if aggregation != MarkingCategory.Aggregation.SUM and len({item["maximum"] for item in criteria}) > 1:
            raise ValidationError(gettext("Average and Weighted average require the same maximum mark for every subcategory in that category. Existing categories with unequal maxima must keep Sum after marking starts."))
        if total_items > 100:
            raise ValidationError(gettext("Use at most 100 scoring subcategories per module."))
        # Private keys keep legacy uniqueness constraints without asking users for codes.
        result.append({"code": f"C{category_index}", "name": name, "learning_objective": objective.strip(), "weight": weight, "aggregation": aggregation, "evaluation_rubric": rubric, "items": criteria})
    if mode == Assignment.Calculation.WEIGHTED and sum(category["weight"] for category in result) != Decimal("100"):
        raise ValidationError(gettext("Category weights must add up to 100%."))
    return result


def export_scheme(assignment):
    return [{"id": category.pk, "name": category.name, "learning_objective": category.learning_objective, "weight": compact_number(category.weight), "aggregation": category.aggregation, "aggregation_label": category.get_aggregation_display(), "evaluation_rubric": category.evaluation_rubric, "evaluation_levels": evaluation_ranges(category.evaluation_rubric), "items": [{"id": item.pk, "name": item.name, "maximum": compact_number(item.maximum), "weight": compact_number(item.weight)} for item in category.criteria.all()]} for category in assignment.categories.prefetch_related("criteria")]


def validate_locked_scheme(raw, assignment):
    """Keep identities and raw-score structure fixed while editing calculations."""
    normalized = validate_scheme(raw, assignment.calculation_mode)
    data = json.loads(raw) if isinstance(raw, str) else raw
    existing = list(assignment.categories.prefetch_related("criteria"))
    message = gettext("Category names, subcategories, and maximum marks cannot change after marking starts. Reload the page.")
    if len(data) != len(existing):
        raise ValidationError(message)
    for source, category, clean in zip(data, existing, normalized):
        items = list(category.criteria.all())
        if (type(source.get("id")) is not int or source["id"] != category.pk or clean["name"] != category.name
                or clean["weight"] != category.weight or len(clean["items"]) != len(items)):
            raise ValidationError(message)
        clean["id"] = category.pk
        for item_source, item, item_clean in zip(source["items"], items, clean["items"]):
            if type(item_source.get("id")) is not int or item_source["id"] != item.pk or item_clean["name"] != item.name or item_clean["maximum"] != item.maximum:
                raise ValidationError(message)
            item_clean["id"] = item.pk
    return normalized


@transaction.atomic
def update_locked_scheme(assignment, scheme, expected_revision):
    current = Assignment.objects.select_for_update().get(pk=assignment.pk)
    if current.scheme_revision != expected_revision:
        raise ValidationError(gettext("The marking scheme changed in another window. Reload before editing it."))
    scheme = validate_locked_scheme(scheme, current)
    changed = Assignment.objects.filter(pk=current.pk, scheme_revision=expected_revision).update(scheme_revision=F("scheme_revision") + 1)
    if not changed:
        raise ValidationError(gettext("The module changed. Reload before editing the scheme."))
    for settings in scheme:
        MarkingCategory.objects.filter(pk=settings["id"], assignment=current).update(
            learning_objective=settings["learning_objective"], aggregation=settings["aggregation"], evaluation_rubric=settings["evaluation_rubric"])
        for item in settings["items"]:
            Criterion.objects.filter(pk=item["id"], category_id=settings["id"]).update(weight=item["weight"])
    assignment.refresh_from_db()


def scheme_ready(categories):
    return bool(categories) and all(list(category.criteria.all()) for category in categories)


def validate_objectives(raw, assignment):
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        raise ValidationError(gettext("The learning objectives could not be read. Reload before editing."))
    ids = {str(pk) for pk in assignment.categories.values_list("pk", flat=True)}
    if not isinstance(data, dict) or set(data) != ids:
        raise ValidationError(gettext("The marking categories changed. Reload before editing their learning objectives."))
    if any(not isinstance(value, str) or len(value) > 5000 for value in data.values()):
        raise ValidationError(gettext("Each learning objective must be text of at most 5,000 characters."))
    return {int(pk): value.strip() for pk, value in data.items()}


@transaction.atomic
def replace_scheme(assignment, scheme, expected_revision=None):
    current = Assignment.objects.select_for_update().get(pk=assignment.pk)
    if current.scheme_locked:
        raise ValidationError(gettext("The marking scheme is locked because marking has started."))
    if expected_revision is not None and current.scheme_revision != expected_revision:
        raise ValidationError(gettext("The marking scheme changed in another window. Reload before editing it."))
    scheme = validate_scheme(scheme, assignment.calculation_mode)
    # On SQLite this write also acquires the database write lock before replacement.
    changed = Assignment.objects.filter(pk=current.pk, scheme_locked=False, scheme_revision=current.scheme_revision).update(scheme_revision=F("scheme_revision") + 1)
    if not changed:
        raise ValidationError(gettext("The module changed. Reload before editing the scheme."))
    current.categories.all().delete()
    for position, category in enumerate(scheme):
        group = MarkingCategory.objects.create(assignment=current, code=category["code"], name=category["name"], learning_objective=category["learning_objective"], weight=category["weight"], aggregation=category["aggregation"], evaluation_rubric=category["evaluation_rubric"], position=position)
        Criterion.objects.bulk_create([Criterion(category=group, code=item["code"], name=item["name"], maximum=item["maximum"], weight=item["weight"], position=index) for index, item in enumerate(category["items"])])
    assignment.refresh_from_db()
