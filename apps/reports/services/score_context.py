"""Read a consistent score snapshot without changing student or score records."""
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _
from apps.assessments.models import Score
from apps.assessments.services.scoring import classroom_enrollments
from apps.assessments.services.grading import assignment_result
from apps.assessments.services.evaluation import validate_evaluation_rubric


def score_workbook_context(offering, classroom, modules):
    modules = list(modules)
    if not modules or any(module.offering_id != offering.pk for module in modules):
        raise ValidationError(_("Select modules from the chosen course and teaching period."))
    if not offering.classrooms.filter(pk=classroom.pk).exists():
        raise ValidationError(_("This classroom is not enrolled in the selected course."))
    enrollments = list(classroom_enrollments(modules[0], classroom))
    if not enrollments:
        raise ValidationError(_("This classroom has no active students enrolled in the course."))
    rolls = [item.student.roll_number for item in enrollments]
    if any(roll is None for roll in rolls) or len(set(rolls)) != len(rolls):
        raise ValidationError(_("Some enrolled students have missing or duplicate roll numbers. Check the selected classroom's student list before exporting."))
    prepared, sheet_count, cell_count = [], 0, 0
    for module in modules:
        categories = list(module.categories.all())
        if not categories:
            raise ValidationError(_("Module %(module)s has no marking categories. Add its marking scheme before exporting.") % {"module": module.name})
        criteria = [criterion for category in categories for criterion in category.criteria.all()]
        values = {(enrollment, criterion): value for enrollment, criterion, value in Score.objects.filter(enrollment__in=enrollments, criterion__in=criteria).values_list("enrollment_id", "criterion_id", "value")}
        groups = [{"id": category.pk, "name": category.name, "aggregation": category.aggregation, "rubric": validate_evaluation_rubric(category.evaluation_rubric),
                   "criteria": [{"id": criterion.pk, "name": criterion.name, "maximum": str(criterion.maximum), "weight": str(criterion.weight)} for criterion in category.criteria.all()]}
                  for category in categories]
        rows = []
        for enrollment in enrollments:
            resigned = enrollment.student.status == "resigned"
            marks = {criterion.pk: None if resigned else values.get((enrollment.pk, criterion.pk)) for criterion in criteria}
            result = assignment_result(module, categories, marks)
            rows.append({"roll": enrollment.student.roll_number, "name": enrollment.student.full_name, "resigned": resigned,
                         "values": {str(pk): str(value) if value is not None else None for pk, value in marks.items()},
                         "categories": {str(pk): {"subtotal": str(item["subtotal"]) if item["marked"] else None,
                                                 "evaluation": "" if resigned else item["evaluation"] or "รอการประเมิน"}
                                        for pk, item in result["categories"].items()}})
        prepared.append({"number": str(module.assignment_number) if module.assignment_number else module.assignment_id,
                         "id": module.assignment_id, "name": module.name, "categories": groups,
                         "rows": rows})
        sheet_count += 1 + len(groups)
        cell_count += len(rows) * (2 + 2 * len(groups) + sum(3 + len(group["criteria"]) for group in groups))
    if sheet_count > 500 or cell_count > 500000:
        raise ValidationError(_("This workbook is too large. Select fewer modules and export again."))
    return {"course_name": offering.course.name, "academic_year": offering.academic_year,
            "classroom": classroom.class_number, "modules": prepared,
            "student_count": len(enrollments), "sheet_count": sheet_count}
