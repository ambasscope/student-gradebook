"""Shared classroom comments and stable IDs for selectable common sentences."""
from django.core.exceptions import ValidationError
from django.utils.translation import gettext
from apps.assessments.models import ClassroomAssignmentRecord
from datetime import date


PROBLEM_PHRASES = [
    ("activity_time", "กิจกรรมการจัดการเรียนรู้ ไม่เหมาะสมกับเวลา"),
    ("unfinished_work", "มีนักเรียนทำใบงาน/ใบกิจกรรมไม่ทันตามกำหนดเวลา"),
    ("disengaged", "มีนักเรียนที่ไม่สนใจเรียน"),
    ("other", "อื่น ๆ"),
]
SUGGESTION_PHRASES = [
    ("plan_topic", "ควรนำแผนไปปรับปรุง เรื่อง"),
    ("below_standard", "แนวทางแก้ไขนักเรียนที่ไม่ผ่านการประเมิน"),
    ("absent_students", "แนวทางแก้ไขนักเรียนที่ไม่มาเรียน"),
    ("none", "ไม่มีข้อเสนอแนะ"),
]
SUGGESTION_DETAIL_KEYS = ["plan_topic", "below_standard", "absent_students"]


def classroom_notes_data(assignment, classroom):
    record = ClassroomAssignmentRecord.objects.filter(assignment=assignment, classroom=classroom).first()
    return {
        "learning_date": record.learning_date.isoformat() if record and record.learning_date else "",
        "problem": record.problem if record else "",
        "suggestion": record.suggestion if record else "",
        "problem_choices": record.problem_choices if record else [],
        "suggestion_choices": record.suggestion_choices if record else [],
        "suggestion_details": {key: (record.suggestion_details.get(key, "") if record else "") for key in SUGGESTION_DETAIL_KEYS},
        "revision": record.revision if record else 0,
        "module_status": record.module_status if record else "",
    }


def comment_phrase_groups(notes):
    return {
        field: [{"id": key, "text": text, "checked": key in notes[field + "_choices"], "needs_details": field == "suggestion" and key in SUGGESTION_DETAIL_KEYS, "details": notes["suggestion_details"].get(key, "")} for key, text in phrases]
        for field, phrases in [("problem", PROBLEM_PHRASES), ("suggestion", SUGGESTION_PHRASES)]
    }


def validate_classroom_notes(data):
    if not isinstance(data, dict) or type(data.get("revision")) is not int or data["revision"] < 0:
        raise ValidationError(gettext("The classroom comments could not be read. Reload the page before saving."))
    result = {"revision": data["revision"]}
    if data.get("module_status") not in ClassroomAssignmentRecord.Completion.values:
        raise ValidationError(gettext("Choose Module completed or Module uncompleted before saving."))
    result["module_status"] = data["module_status"]
    for field in ["problem", "suggestion"]:
        value = data.get(field)
        if not isinstance(value, str) or len(value) > 5000:
            raise ValidationError(gettext("Each classroom comment must be text of at most 5,000 characters."))
        result[field] = value.replace("\r\n", "\n").replace("\r", "\n")
    for field, phrases in [("problem_choices", PROBLEM_PHRASES), ("suggestion_choices", SUGGESTION_PHRASES)]:
        keys = [key for key, _ in phrases]
        choices = data.get(field)
        if not isinstance(choices, list) or len(choices) > len(keys) or any(not isinstance(key, str) or key not in keys for key in choices):
            raise ValidationError(gettext("Select only the listed common sentences for classroom comments."))
        if len(set(choices)) != len(choices):
            raise ValidationError(gettext("A common sentence appears more than once in the classroom comments."))
        result[field] = [key for key in keys if key in choices]
    if "none" in result["suggestion_choices"] and len(result["suggestion_choices"]) > 1:
        raise ValidationError(gettext("No suggestions cannot be selected together with another suggestion."))
    details = data.get("suggestion_details")
    if not isinstance(details, dict) or set(details) - set(SUGGESTION_DETAIL_KEYS):
        raise ValidationError(gettext("The suggestion details could not be read. Review the text fields before saving."))
    result["suggestion_details"] = {}
    for key in SUGGESTION_DETAIL_KEYS:
        value = details.get(key, "")
        if not isinstance(value, str) or len(value) > 5000:
            raise ValidationError(gettext("Each suggestion detail must be text of at most 5,000 characters."))
        result["suggestion_details"][key] = value.replace("\r\n", "\n").replace("\r", "\n") if key in result["suggestion_choices"] else ""
    if "other" not in result["problem_choices"]:
        result["problem"] = ""
    if "none" in result["suggestion_choices"]:
        result["suggestion"] = ""
    raw = data.get("learning_date")
    try:
        if not isinstance(raw, str): raise ValueError
        parsed = date.fromisoformat(raw) if raw else None
        if parsed and parsed.isoformat() != raw: raise ValueError
    except ValueError:
        raise ValidationError(gettext("Enter the valid learning date."))
    result["learning_date"] = parsed
    return result
