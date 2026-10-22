"""Module-record context. Reporting never fills or changes a student's marks."""
from decimal import Decimal, ROUND_HALF_UP
import re
from config.numbers import compact_number
from django.utils.translation import gettext_lazy as _
from apps.assessments.models import Attendance, ClassroomAssignmentRecord, Score
from apps.assessments.services.scoring import classroom_enrollments
from apps.assessments.services.grading import assignment_result
from apps.assessments.services.classroom_records import PROBLEM_PHRASES, SUGGESTION_PHRASES
from apps.teachers.models import TeacherProfile
from config.semesters import legacy_semester_number

REPORT_SECTIONS = [
    {"key": "knowledge", "title": "ด้านความรู้ (K)", "aliases": {"ด้านความรู้", "ความรู้", "ด้านความรู้ (K)", "Knowledge (K)"}},
    {"key": "skills", "title": "ด้านทักษะและการปฏิบัติ (P)", "aliases": {"ด้านทักษะและการปฏิบัติ", "ด้านทักษะและการปฏิบัติ (P)", "Practices (P)"}},
    {"key": "attitudes", "title": "ด้านเจตคติ/คุณลักษณะ (A)", "aliases": {"ด้านเจตคติและคุณลักษณะ", "ด้านเจตคติและคุณลักษณะ (A)", "ด้านเจตคติ/คุณลักษณะ (A)", "ด้านเจตคติ/คุณลักษณะ", "Attitudes and Attributes (A)"}},
    {"key": "competencies", "title": "สมรรถนะ", "aliases": {"สมรรถนะ", "ด้านสมรรถนะ", "ด้านสมรรถนะของผู้เรียน (C)", "Competencies (C)"}},
]
THAI_MONTHS = ["มกราคม", "กุมภาพันธ์", "มีนาคม", "เมษายน", "พฤษภาคม", "มิถุนายน", "กรกฎาคม", "สิงหาคม", "กันยายน", "ตุลาคม", "พฤศจิกายน", "ธันวาคม"]


def compact(text):
    return re.sub(r"\s+", " ", str(text or "")).strip()


def infer_category(categories, key):
    aliases = next(s["aliases"] for s in REPORT_SECTIONS if s["key"] == key)
    matches = [c for c in categories if compact(c["name"]) in aliases]
    return matches[0] if len(matches) == 1 else None


def percentage(count, total):
    return compact_number(Decimal(count) * 100 / total if total else Decimal(0))


def combined_comments(record):
    if not record:
        return "", ""
    problems = [text for key, text in PROBLEM_PHRASES if key != "other" and key in record.problem_choices]
    if compact(record.problem):
        problems.append(record.problem)
    suggestions = []
    for key, text in SUGGESTION_PHRASES:
        if key in record.suggestion_choices:
            detail = record.suggestion_details.get(key, "") if isinstance(record.suggestion_details, dict) else ""
            suggestions.append(text + (": " + compact(detail) if compact(detail) else ""))
    if compact(record.suggestion):
        suggestions.append(record.suggestion)
    return compact("; ".join(problems)), compact("; ".join(suggestions))


def module_source(module, classroom, teacher):
    categories = list(module.categories.prefetch_related("criteria"))
    roster = list(classroom_enrollments(module, classroom).filter(student__status="studying"))
    criteria = [criterion for category in categories for criterion in category.criteria.all()]
    values = {(e, c): v for e, c, v in Score.objects.filter(enrollment__in=roster, criterion__in=criteria).values_list("enrollment_id", "criterion_id", "value")}
    attendance = dict(Attendance.objects.filter(assignment=module, classroom=classroom, enrollment__in=roster).values_list("enrollment_id", "present"))
    record = ClassroomAssignmentRecord.objects.filter(assignment=module, classroom=classroom).first()
    counts = {c.pk: {"passed": 0, "unassessed": 0} for c in categories}
    for enrollment in roster:
        result = assignment_result(module, categories, {c.pk: values.get((enrollment.pk, c.pk)) for c in criteria})
        for category in categories:
            evaluation = result["categories"][category.pk]
            if not evaluation["complete"]:
                counts[category.pk]["unassessed"] += 1
            elif not evaluation["failed"]:
                counts[category.pk]["passed"] += 1
    total = len(roster)
    present = sum(attendance.get(enrollment.pk, True) for enrollment in roster)
    problem, suggestion = combined_comments(record)
    learning_date = record.learning_date if record else None
    issues = []
    semester = legacy_semester_number(module.offering.semester)
    if semester is None:
        issues.append(_("Save a numeric semester on the course teaching-period page before exporting."))
    if not module.unit_id:
        issues.append(_("Choose a unit for this module on the Edit module page before exporting."))
    elif module.unit.course_id != module.offering.course_id:
        issues.append(_("Choose a unit belonging to this module's course."))
    if not teacher or not compact(teacher.name) or not compact(teacher.academic_status):
        issues.append(_("Save the teacher's name and academic status on the Teacher page."))
    if not learning_date:
        issues.append(_("Save a learning date on this module's classroom scoring page."))
    if not record or record.module_status not in ClassroomAssignmentRecord.Completion.values:
        issues.append(_("Save Module completed or Module uncompleted on the scoring page."))
    if not total:
        issues.append(_("This classroom has no students currently marked Studying enrolled in the course."))
    course = module.offering.course
    limits = [(course.name, 60, _("Course name")), (course.course_id, 25, _("Course ID")), (classroom.class_number, 10, _("Classroom")), (teacher.name if teacher else "", 80, _("Teacher name")), (teacher.academic_status if teacher else "", 70, _("Academic status"))]
    for value, maximum, label in limits:
        if len(compact(value)) > maximum:
            issues.append(_("%(field)s is too long for this one-page form (maximum %(maximum)s characters). Shorten it in its source page.") % {"field": label, "maximum": maximum})
    result = {
        "module_pk": module.pk, "module_title": module.name,
        "module_number": str(module.assignment_number) if module.assignment_number else module.assignment_id,
        "module_id": module.assignment_id, "classroom": compact(classroom.class_number),
        "course_name": compact(course.name), "course_id": compact(course.course_id),
        "semester": semester or "", "semester_display": module.offering.semester_display,
        "academic_year": module.offering.academic_year,
        "unit_id": module.unit.unit_id if module.unit_id else "",
        "teacher_name": compact(teacher.name) if teacher else "",
        "academic_status": compact(teacher.academic_status) if teacher else "",
        "date_day": str(learning_date.day) if learning_date else "",
        "date_month": THAI_MONTHS[learning_date.month - 1] if learning_date else "",
        "date_year": str(learning_date.year + 543) if learning_date else "",
        "total": total, "present": present, "absent": total - present,
        "present_percent": percentage(present, total), "absent_percent": percentage(total - present, total),
        "completed": bool(record and record.module_status == ClassroomAssignmentRecord.Completion.COMPLETED),
        "problem": problem, "suggestion": suggestion, "issues": issues,
        "categories": [],
        # Preview invalidation covers all source edits relevant to the report.
        "revisions": [module.scheme_revision, module.score_revision, record.revision if record else 0, teacher.revision if teacher else 0],
    }
    for category in categories:
        count = counts[category.pk]
        result["categories"].append({"id": category.pk, "name": category.name, "objective": compact(category.learning_objective), "passed": count["passed"], "failed": total - count["passed"], "unassessed": count["unassessed"], "pass_percent": percentage(count["passed"], total), "fail_percent": percentage(total - count["passed"], total)})
    return result


def report_sources(modules, classroom):
    teacher = TeacherProfile.objects.filter(pk=1).first()
    return [module_source(module, classroom, teacher) for module in modules]


def filled_context(source, wording):
    result = {key: value for key, value in source.items() if key not in {"categories", "issues", "revisions"}}
    result["module_title"] = compact(wording["module_title"])
    result["problem"] = compact(wording["problem"]) or "........................................................................................................................"
    result["suggestion"] = compact(wording["suggestion"]) or "........................................................................................................................"
    result["completed_box"] = "☑︎" if source["completed"] else "☐︎"
    result["uncompleted_box"] = "☐︎" if source["completed"] else "☑︎"
    sections = []
    for section in REPORT_SECTIONS:
        key = section["key"]
        category = next(c for c in source["categories"] if str(c["id"]) == wording[key + "_category"])
        item = {**category, "title": section["title"], "objective": compact(wording[key + "_objective"])}
        sections.append(item)
        for field in ["objective", "passed", "failed", "pass_percent", "fail_percent"]:
            result[key + "_" + field] = item[field]
    result["sections"] = sections
    return result
