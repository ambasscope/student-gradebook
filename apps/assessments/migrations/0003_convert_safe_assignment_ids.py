"""Only plain local numbers or already well-formed keys can be inferred safely."""
import re
from collections import Counter
from django.db import migrations


def convert_safe_ids(apps, schema_editor):
    Assignment = apps.get_model("assessments", "Assignment")
    assignments = list(Assignment.objects.select_related("offering__course"))
    occupied = {item.assignment_id: item.pk for item in assignments}
    candidates = []
    for item in assignments:
        if item.assignment_number is not None:
            continue
        year, course = item.offering.academic_year, item.offering.course.course_id
        if not re.fullmatch(r"[1-9][0-9]{3}", year) or not course or course != course.strip():
            continue
        prefix = year + course
        old = item.assignment_id
        if re.fullmatch(r"[0-9]{1,2}", old) and 1 <= int(old) <= 99:
            number = int(old)
        elif re.fullmatch(re.escape(prefix) + r"[0-9]{2}", old) and 1 <= int(old[-2:]) <= 99:
            number = int(old[-2:])
        else:
            continue
        candidates.append((item.pk, number, prefix + f"{number:02d}"))
    targets = Counter(key for _, _, key in candidates)
    for pk, number, key in candidates:
        if targets[key] == 1 and occupied.get(key, pk) == pk:
            Assignment.objects.filter(pk=pk).update(assignment_id=key, assignment_number=number)


class Migration(migrations.Migration):
    dependencies = [("assessments", "0002_assignment_assignment_number_and_more")]
    operations = [migrations.RunPython(convert_safe_ids, migrations.RunPython.noop)]
