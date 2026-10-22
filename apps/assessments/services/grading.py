"""Shared assignment totals; blank scores remain unmarked rather than zero."""
from decimal import Decimal, ROUND_HALF_UP
from apps.assessments.models import Assignment
from .evaluation import category_evaluation, evaluation_failed


def category_result(category, values):
    items = list(category.criteria.all())
    numerator, maximum_numerator, divisor, marked = Decimal(0), Decimal(0), Decimal(0), 0
    for item in items:
        weight = item.weight if category.aggregation == "weighted_average" else Decimal(1)
        maximum_numerator += item.maximum * weight
        divisor += weight
        value = values.get(item.pk)
        if value is not None:
            numerator += value * weight
            marked += 1
    if category.aggregation == "sum":
        divisor = Decimal(1)
    subtotal = numerator / divisor if divisor else Decimal(0)
    maximum = maximum_numerator / divisor if divisor else Decimal(0)
    complete = bool(items) and marked == len(items)
    # The common divisor cancels: compare exact numerators before any rounding.
    return {"subtotal": subtotal, "maximum": maximum, "marked": marked,
            "item_count": len(items), "complete": complete,
            "numerator": numerator, "maximum_numerator": maximum_numerator,
            "evaluation": category_evaluation(numerator, maximum_numerator, category.evaluation_rubric) if complete else None,
            "failed": evaluation_failed(numerator, maximum_numerator, category.evaluation_rubric) if complete else True}


def assignment_result(assignment, categories, values):
    total, marked, item_count = Decimal("0"), 0, 0
    subtotals, category_results = {}, {}
    for category in categories:
        result = category_result(category, values)
        subtotal, maximum = result["subtotal"], result["maximum"]
        marked += result["marked"]
        item_count += result["item_count"]
        subtotals[category.pk] = subtotal.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        category_results[category.pk] = {**result, "subtotal": subtotals[category.pk]}
        total += subtotal / maximum * category.weight if assignment.calculation_mode == Assignment.Calculation.WEIGHTED and maximum else subtotal
    return {"total": total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "subtotals": subtotals, "categories": category_results, "marked": marked, "item_count": item_count, "complete": item_count > 0 and all(result["complete"] for result in category_results.values())}
