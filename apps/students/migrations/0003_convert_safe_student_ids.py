"""Convert only single-class, numeric legacy identities; never merge records."""
import re
from collections import Counter, defaultdict
from django.db import migrations


def convert_safe_ids(apps, schema_editor):
    Student = apps.get_model("students", "Student")
    Classroom = apps.get_model("students", "StudentClass")
    Membership = apps.get_model("students", "ClassMembership")
    groups, namespaces = {}, Counter()
    for group in Classroom.objects.all():
        match = re.fullmatch(r"([1-9])\s*/\s*([0-9]{1,2})", group.class_number.strip())
        if re.fullmatch(r"[1-9][0-9]{3}", group.academic_year) and match and 1 <= int(match[2]) <= 99:
            prefix = group.academic_year + match[1] + f"{int(match[2]):02d}"
            groups[group.pk] = (prefix, f"{match[1]}/{int(match[2])}")
            namespaces[prefix] += 1
    members = defaultdict(list)
    for student_id, class_id in Membership.objects.values_list("student_id", "student_class_id"):
        members[student_id].append(class_id)
    all_students = list(Student.objects.all())
    occupied = {student.student_number: student.pk for student in all_students}
    candidates = []
    for student in all_students:
        if student.identifier_class_id or student.roll_number is not None or len(members[student.pk]) != 1:
            continue
        class_id = members[student.pk][0]
        if class_id not in groups:
            continue
        prefix, _ = groups[class_id]
        if namespaces[prefix] != 1:
            continue
        old = student.student_number
        if re.fullmatch(r"[0-9]+", old) and len(old) <= 80 and 1 <= int(old) <= 99:
            roll = int(old)
        elif re.fullmatch(re.escape(prefix) + r"[0-9]{2}", old) and 1 <= int(old[-2:]) <= 99:
            roll = int(old[-2:])
        else:
            continue
        candidates.append((student.pk, class_id, roll, prefix + f"{roll:02d}"))
    targets = Counter(key for _, _, _, key in candidates)
    for student_pk, class_id, roll, key in candidates:
        if targets[key] != 1 or occupied.get(key, student_pk) != student_pk:
            continue
        Classroom.objects.filter(pk=class_id).update(class_number=groups[class_id][1])
        Student.objects.filter(pk=student_pk).update(student_number=key, identifier_class_id=class_id, roll_number=roll)


class Migration(migrations.Migration):
    dependencies = [("students", "0002_student_identifier_class_student_roll_number_and_more")]
    operations = [migrations.RunPython(convert_safe_ids, migrations.RunPython.noop)]
