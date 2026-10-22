"""Category-specific qualitative bands, independent of overall category weights."""
import json
from decimal import Decimal, InvalidOperation
from django.core.exceptions import ValidationError
from django.utils.translation import gettext


def default_evaluation_rubric():
    # Return fresh data: editing one assignment must not alter another.
    return [
        {"minimum": "80", "label": "Excellent", "is_fail": False},
        {"minimum": "60", "label": "Good", "is_fail": False},
        {"minimum": "50", "label": "Pass", "is_fail": False},
        {"minimum": "0", "label": "Fail", "is_fail": True},
    ]


def validate_evaluation_rubric(raw):
    try:
        bands = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, ValueError):
        raise ValidationError(gettext("The evaluation rubric could not be read. Review the levels and try again."))
    if not isinstance(bands, list) or not 1 <= len(bands) <= 20:
        raise ValidationError(gettext("Add between 1 and 20 evaluation levels."))
    result, minimums, labels = [], set(), set()
    for band in bands:
        if not isinstance(band, dict):
            raise ValidationError(gettext("Each evaluation level needs a minimum percentage and a label."))
        value, label = band.get("minimum"), band.get("label")
        try:
            if isinstance(value, (bool, list, dict)) or value is None:
                raise InvalidOperation
            minimum = Decimal(str(value).strip())
            if not minimum.is_finite() or not Decimal("0") <= minimum <= Decimal("100"):
                raise InvalidOperation
            if minimum.quantize(Decimal("0.01")) != minimum:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            raise ValidationError(gettext("Minimum percentages must be between 0 and 100, with at most two decimal places."))
        if not isinstance(label, str) or not label.strip() or len(label.strip()) > 80:
            raise ValidationError(gettext("Each evaluation label must contain 1 to 80 characters."))
        label = label.strip()
        if minimum in minimums:
            raise ValidationError(gettext("Each evaluation level must have a different minimum percentage."))
        if label.casefold() in labels:
            raise ValidationError(gettext("Each evaluation level must have a different label."))
        minimums.add(minimum)
        labels.add(label.casefold())
        is_fail = band.get("is_fail", legacy_failure_label(label))
        if type(is_fail) is not bool:
            raise ValidationError(gettext("Select whether each evaluation level counts as failed."))
        result.append({"minimum": str(minimum.quantize(Decimal("0.01"))), "label": label, "is_fail": is_fail})
    if Decimal("0") not in minimums:
        raise ValidationError(gettext("Include a level with minimum 0% so every score has an evaluation."))
    return sorted(result, key=lambda band: Decimal(band["minimum"]), reverse=True)


def category_evaluation(total, maximum, rubric):
    if maximum <= 0:
        return None
    # Compare exact marks, rather than a rounded display percentage.
    for band in rubric:
        if total * Decimal("100") >= maximum * Decimal(band["minimum"]):
            return band["label"]
    return None


def evaluation_ranges(rubric):
    upper, result = None, []
    for band in rubric:
        result.append({**band, "upper": upper})
        upper = band["minimum"]
    return result


def legacy_failure_label(label):
    return str(label).strip().casefold() in {"fail", "failed", "ไม่ผ่าน", "ไม่ผ่านเกณฑ์"}


def evaluation_failed(total, maximum, rubric):
    if maximum <= 0:
        return True
    for band in rubric:
        if total * Decimal("100") >= maximum * Decimal(band["minimum"]):
            return band.get("is_fail", legacy_failure_label(band["label"]))
    return True
