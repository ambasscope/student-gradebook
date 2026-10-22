"""Parse roster files, validate mapped rows, and commit one atomic import."""
from django.utils.translation import gettext
import csv
import io
import re
import zipfile
from pathlib import Path

from django.core.exceptions import ValidationError
from django.db import transaction
from apps.students.models import ClassMembership, Student, StudentClass
from config.identifiers import academic_year, classroom_parts, local_number, student_identifier

MAX_ROWS = 5000
MAX_COLUMNS = 100


class ImportProblem(ValueError):
    pass


def cell_text(value, number_format=""):
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, int) and not isinstance(value, bool) and re.fullmatch(r"0+", number_format):
        return str(value).zfill(len(number_format))
    return str(value).strip()


def parse_file(file, *, encoding="utf-8-sig", sheet_name=""):
    suffix = Path(file.name).suffix.lower()
    raw = file.read(5 * 1024 * 1024 + 1)
    if len(raw) > 5 * 1024 * 1024:
        raise ImportProblem(gettext("Choose a file smaller than 5 MB."))
    if not raw:
        raise ImportProblem(gettext("The file is empty."))
    if suffix in {".csv", ".tsv"}:
        try:
            text = raw.decode(encoding)
        except UnicodeError as error:
            raise ImportProblem(gettext("The text encoding did not match the file. Choose another encoding or save as UTF-8 CSV.")) from error
        try:
            dialect = csv.Sniffer().sniff(text[:8192], delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel_tab if suffix == ".tsv" else csv.excel
        if suffix == ".tsv":
            dialect = csv.excel_tab
        rows = csv.reader(io.StringIO(text), dialect, strict=True)
        try:
            return collect_rows(rows)
        except csv.Error as error:
            raise ImportProblem(gettext("The file could not be read as a complete CSV/TSV table.")) from error
    if suffix == ".xlsx":
        from openpyxl import load_workbook
        workbook = None
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                if sum(entry.file_size for entry in archive.infolist()) > 40 * 1024 * 1024:
                    raise ImportProblem(gettext("This Excel workbook is too large when expanded. Save the student sheet as CSV."))
            workbook = load_workbook(io.BytesIO(raw), read_only=True, data_only=True)
            if sheet_name and sheet_name not in workbook.sheetnames:
                raise ImportProblem(gettext("That worksheet was not found. Available sheets: ") + ", ".join(workbook.sheetnames))
            sheet = workbook[sheet_name] if sheet_name else workbook.worksheets[0]
            if sheet.max_column and sheet.max_column > MAX_COLUMNS:
                raise ImportProblem(gettext("Use a student sheet with at most 100 columns."))
            # Ignore stale Excel dimensions; enforce our own streaming limits.
            sheet.reset_dimensions()
            return collect_rows(([cell_text(cell.value, getattr(cell, "number_format", "")) for cell in row] for row in sheet.iter_rows()))
        except ImportProblem:
            raise
        except Exception as error:
            raise ImportProblem(gettext("The Excel workbook could not be read. Save it as .xlsx or UTF-8 CSV and try again.")) from error
        finally:
            if workbook is not None:
                workbook.close()
    if suffix == ".xls":
        import xlrd
        workbook = None
        try:
            workbook = xlrd.open_workbook(file_contents=raw, formatting_info=True)
            if sheet_name and sheet_name not in workbook.sheet_names():
                raise ImportProblem(gettext("That worksheet was not found. Available sheets: ") + ", ".join(workbook.sheet_names()))
            sheet = workbook.sheet_by_name(sheet_name) if sheet_name else workbook.sheet_by_index(0)
            def rows():
                for row in range(sheet.nrows):
                    values = []
                    for col in range(sheet.ncols):
                        cell = sheet.cell(row, col)
                        format_string = workbook.format_map[workbook.xf_list[cell.xf_index].format_key].format_str
                        values.append(cell_text(cell.value, format_string))
                    yield values
            return collect_rows(rows())
        except ImportProblem:
            raise
        except Exception as error:
            raise ImportProblem(gettext("The older Excel file could not be read. Save it as .xlsx or UTF-8 CSV and try again.")) from error
        finally:
            if workbook is not None:
                workbook.release_resources()
    raise ImportProblem(gettext("Choose an .xlsx, .xls, .csv, or .tsv file."))


def collect_rows(rows):
    headers = None
    data = []
    for row_number, row in enumerate(rows, start=1):
        if row_number > MAX_ROWS + 100:
            raise ImportProblem(gettext("The sheet contains too many rows. Keep one header row and at most 5,000 students."))
        if len(row) > MAX_COLUMNS:
            raise ImportProblem(gettext("Use a file with at most 100 columns."))
        values = [cell_text(value) for value in row]
        if any(len(value) > 10000 for value in values):
            raise ImportProblem(gettext("Row %(row_number)s contains an unusually long cell.") % {"row_number": row_number})
        if not any(values):
            continue
        if headers is None:
            headers = [name or gettext("Column %(number)s") % {"number": index + 1} for index, name in enumerate(values)]
            continue
        if len(data) >= MAX_ROWS:
            raise ImportProblem(gettext("Import at most 5,000 students at a time."))
        if len(values) > len(headers) and any(values[len(headers):]):
            raise ImportProblem(gettext("Row %(row_number)s has more columns than the header row.") % {"row_number": row_number})
        values = (values + [""] * len(headers))[:len(headers)]
        data.append({"row": row_number, "values": values})
    if headers is None or not data:
        raise ImportProblem(gettext("Include column headings and at least one student row."))
    return {"headers": headers, "rows": data}


ALIASES = {
    "roll_number": {"rollnumber", "rollno", "studentno", "no", "number", "เลขที่"},
    "student_id": {"studentid", "studentnumber", "schoolid", "รหัสนักศึกษา", "รหัสนักเรียน", "เลขประจำตัวนักเรียน"},
    "full_name": {"fullname", "studentname", "name", "ชื่อสกุล", "ชื่อและนามสกุล"},
    "first_name": {"firstname", "givenname", "ชื่อ"},
    "last_name": {"lastname", "surname", "familyname", "นามสกุล"},
    "email": {"email", "emailaddress", "อีเมล"},
    "notes": {"notes", "note", "remarks", "หมายเหตุ"},
}


def suggest_mapping(headers):
    result = {}
    for field, aliases in ALIASES.items():
        for index, header in enumerate(headers):
            if re.sub(r"[\W_]", "", header.lower()) in {re.sub(r"[\W_]", "", alias) for alias in aliases}:
                result[field] = str(index)
                break
    if result.get("full_name"):
        result.pop("first_name", None)
        result.pop("last_name", None)
    return result


def map_records(table, mapping):
    records = []
    for source in table["rows"]:
        def value(key):
            column = mapping.get(key)
            return source["values"][int(column)] if column not in (None, "") else ""
        name = value("full_name") or " ".join(part for part in [value("first_name"), value("last_name")] if part)
        records.append({"row": source["row"], "roll_number": value("roll_number"), "student_id": value("student_id"), "full_name": name, "email": value("email"), "notes": value("notes")})
    return records


def build_plan(records, metadata):
    """Derive IDs before matching; roll numbers are local to one classroom/year."""
    counts = {"new": 0, "updated": 0, "linked": 0, "unchanged": 0}
    try:
        normalized = {**metadata, "academic_year": academic_year(metadata.get("academic_year", "")), "class_number": classroom_parts(metadata.get("class_number", ""))[0]}
    except ValidationError as error:
        return {"rows": [], "errors": [{"row": "class", "messages": error.messages}], "counts": counts, "total": len(records)}
    matches = []
    for candidate in StudentClass.objects.filter(academic_year=normalized["academic_year"]):
        try:
            if classroom_parts(candidate.class_number)[0] == normalized["class_number"]:
                matches.append(candidate)
        except ValidationError:
            pass
    if len(matches) > 1:
        return {"rows": [], "errors": [{"row": "class", "messages": [gettext("More than one legacy classroom has this class code and year. Resolve the duplicate classrooms before importing.")]}], "counts": counts, "total": len(records)}
    group = matches[0] if matches else None
    prepared = []
    for record in records:
        errors = []
        number = ""
        roll = record.get("roll_number", "")
        try:
            roll = local_number(roll, gettext("Roll number"))
            number = student_identifier(normalized["academic_year"], normalized["class_number"], roll)
        except ValidationError as error:
            errors.extend(error.messages)
        prepared.append({"student_id": "", **record, "roll_number": roll, "student_number": number, "errors": errors})
    existing = {student.student_number: student for student in Student.objects.filter(student_number__in=[row["student_number"] for row in prepared]).prefetch_related("memberships")}
    members = set(group.memberships.values_list("student__student_number", flat=True)) if group else set()
    seen, rows, errors = set(), [], []
    for record in prepared:
        row_errors = record["errors"]
        number = record["student_number"]
        student = Student(**{key: record[key] for key in ["student_number", "student_id", "full_name", "email", "notes"]})
        try:
            student.full_clean(validate_unique=False, validate_constraints=False)
        except ValidationError as error:
            for field, messages in error.message_dict.items():
                if field != "student_number" or number:
                    row_errors.extend(gettext("%(field)s: %(message)s") % {"field": {"student_number": gettext("Roll number"), "student_id": gettext("Student ID"), "full_name": gettext("Student name"), "email": gettext("Email"), "notes": gettext("Notes")}.get(field, field), "message": message} for message in messages)
        if number and number in seen:
            row_errors.append(gettext("This roll number appears more than once in the classroom list (for example 3 and 03 are the same number)."))
        seen.add(number)
        old = existing.get(number)
        if old:
            if old.identifier_class_id and (not group or old.identifier_class_id != group.pk or old.roll_number != record["roll_number"]):
                row_errors.append(gettext("This generated ID conflicts with another classroom identity. Review the classroom records."))
            elif not old.identifier_class_id and (not group or {membership.student_class_id for membership in old.memberships.all()} != {group.pk}):
                row_errors.append(gettext("This generated ID matches an ambiguous legacy record. Resolve that record before importing."))
        changes = old and any(record[key] and record[key] != getattr(old, key) for key in ["student_id", "full_name", "email", "notes"])
        if changes and not normalized["update_existing"]:
            row_errors.append(gettext("This classroom roll number already exists with different details. Correct the file or select the update-existing option."))
        action = "new" if old is None else "updated" if changes and normalized["update_existing"] else "linked" if number not in members else "unchanged"
        if row_errors:
            errors.append({"row": record["row"], "messages": row_errors})
        else:
            counts[action] += 1
        rows.append({**record, "action": action, "action_label": {"new": gettext("New"), "updated": gettext("Updated"), "linked": gettext("Linked"), "unchanged": gettext("Unchanged")}[action], "errors": row_errors})
    return {"rows": rows, "errors": errors, "counts": counts, "total": len(records), "metadata": normalized, "classroom_pk": group.pk if group else None}


@transaction.atomic
def commit_import(records, metadata):
    plan = build_plan(records, metadata)
    if plan["errors"]:
        raise ImportProblem(gettext("The import has row errors. Review the preview before saving."))
    metadata = plan["metadata"]
    if plan["classroom_pk"]:
        group = StudentClass.objects.get(pk=plan["classroom_pk"])
    else:
        group, _ = StudentClass.objects.get_or_create(class_number=metadata["class_number"], academic_year=metadata["academic_year"], defaults={"notes": metadata["class_notes"]})
    if metadata["class_notes"] and group.notes != metadata["class_notes"]:
        group.notes = metadata["class_notes"]
        group.save(update_fields=["notes"])
    for record in plan["rows"]:
        fields = {key: record[key] for key in ["student_id", "full_name", "email", "notes"]}
        student, created = Student.objects.get_or_create(student_number=record["student_number"], defaults={**fields, "identifier_class": group, "roll_number": record["roll_number"]})
        if not created:
            if student.identifier_class_id is None:
                student.identifier_class = group
                student.roll_number = record["roll_number"]
                student.save()
            if metadata["update_existing"]:
                for key, value in fields.items():
                    if value:
                        setattr(student, key, value)
                student.save()
        ClassMembership.objects.get_or_create(student=student, student_class=group)
    return group, plan["counts"]
