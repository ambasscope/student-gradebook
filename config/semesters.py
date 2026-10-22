"""Store semester numbers independently of their translated display label."""
import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext, gettext_lazy

THAI_DIGITS = str.maketrans("๐๑๒๓๔๕๖๗๘๙", "0123456789")


def semester_number(value):
    text = str(value).strip()
    if not re.fullmatch(r"[0-9]{1,50}", text) or int(text) < 1:
        raise ValidationError(gettext_lazy("Enter a positive whole semester number, such as 1 or 2. Do not include words."))
    return str(int(text))


def validate_semester(value):
    semester_number(value)


def legacy_semester_number(value):
    """Read recognized old labels without inventing numbers for ambiguous text."""
    text = str(value).strip().translate(THAI_DIGITS)
    match = re.fullmatch(r"(?:semester\s*|ภาค(?:เรียน|การศึกษา)(?:ที่)?\s*)?([0-9]{1,50})", text, re.IGNORECASE)
    if not match:
        return None
    try:
        return semester_number(match.group(1))
    except ValidationError:
        return None


def semester_label(value):
    number = legacy_semester_number(value) or str(value).strip()
    return gettext("Semester %(number)s") % {"number": number}
