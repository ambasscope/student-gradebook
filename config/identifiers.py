"""The public identifiers use fixed-width year, classroom, and local numbers."""
from django.utils.translation import gettext
import re
from django.core.exceptions import ValidationError


def academic_year(value):
    text = str(value).strip()
    if not re.fullmatch(r"[1-9][0-9]{3}", text):
        raise ValidationError(gettext("Enter a four-digit academic year, for example 2569."))
    return text


def classroom_parts(value):
    match = re.fullmatch(r"([1-9])\s*/\s*([0-9]{1,2})", str(value).strip())
    if not match or not 1 <= int(match[2]) <= 99:
        raise ValidationError(gettext("Use grade/section, for example 4/1 or 4/12. Grade must be 1–9 and section 1–99."))
    grade, section = int(match[1]), int(match[2])
    return f"{grade}/{section}", f"{grade}{section:02d}"


def local_number(value, label=None):
    label = gettext("Number") if label is None else label
    text = str(value).strip()
    if isinstance(value, bool) or not re.fullmatch(r"[0-9]{1,2}", text) or not 1 <= int(text) <= 99:
        raise ValidationError(gettext("%(label)s: enter a whole number from 1 to 99.") % {"label": label})
    return int(text)


def student_identifier(year, classroom, roll):
    number = local_number(roll, gettext("Roll number"))
    return academic_year(year) + classroom_parts(classroom)[1] + f"{number:02d}"


def assignment_identifier(year, course_id, number):
    course = str(course_id).strip()
    if not course or len(course) > 80:
        raise ValidationError(gettext("A course ID of at most 80 characters is required."))
    number = local_number(number, gettext("Module number"))
    return academic_year(year) + course + f"{number:02d}"
