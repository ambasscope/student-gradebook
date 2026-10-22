import io
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from openpyxl import Workbook

from apps.students.models import ClassMembership, Student, StudentClass
from apps.students.services.imports import ImportProblem, build_plan, commit_import, map_records, parse_file


def metadata(**changes):
    return {"class_number": "4/1", "academic_year": "2569", "class_notes": "Morning class", "update_existing": False, **changes}


def record(number="17", name="Example Student", **changes):
    return {"row": 2, "roll_number": number, "full_name": name, "email": "", "notes": "", **changes}


class ImportTests(TestCase):
    def test_utf8_csv_preserves_ids_and_non_latin_names(self):
        file = SimpleUploadedFile("list.csv", "\ufeffstudent_id,student_name\n00017,สมชาย ใจดี\n".encode("utf-8"))
        parsed = parse_file(file)
        rows = map_records(parsed, {"roll_number": "0", "full_name": "1"})
        self.assertEqual(rows[0]["roll_number"], "00017")
        self.assertEqual(rows[0]["full_name"], "สมชาย ใจดี")

    def test_tsv_and_semicolon_csv(self):
        for name, text in [("list.tsv", "id\tname\n00017\tExample\n"), ("list.csv", "id;name\n00017;Example\n")]:
            with self.subTest(name=name):
                self.assertEqual(parse_file(SimpleUploadedFile(name, text.encode()))["rows"][0]["values"], ["00017", "Example"])

    def test_xlsx_text_and_zero_number_format_preserved(self):
        workbook = Workbook()
        workbook.active.append(["id", "name"])
        workbook.active.append(["00017", "Example One"])
        workbook.active.append([18, "Example Two"])
        workbook.active["A3"].number_format = "00000"
        stream = io.BytesIO()
        workbook.save(stream)
        parsed = parse_file(SimpleUploadedFile("students.xlsx", stream.getvalue()))
        self.assertEqual([row["values"][0] for row in parsed["rows"]], ["00017", "00018"])

    def test_xls_fixture_preserves_zero_number_format(self):
        fixture = Path(__file__).parent / "fixtures/student-list.xls"
        parsed = parse_file(SimpleUploadedFile("list.xls", fixture.read_bytes()))
        self.assertEqual(parsed["rows"][0]["values"][0], "00017")

    def test_named_sheet_and_missing_sheet(self):
        workbook = Workbook()
        workbook.active.title = "Students"
        workbook.active.append(["id", "name"])
        workbook.active.append(["00017", "Example"])
        stream = io.BytesIO()
        workbook.save(stream)
        with self.assertRaisesMessage(ImportProblem, "worksheet was not found"):
            parse_file(SimpleUploadedFile("list.xlsx", stream.getvalue()), sheet_name="Wrong")

    def test_bad_files_do_not_escape_as_server_errors(self):
        for name, value in [("list.xlsx", b"not excel"), ("list.xls", b"not excel"), ("list.csv", b""), ("list.csv", b"\xff\xff")]:
            with self.subTest(name=name):
                with self.assertRaises(ImportProblem):
                    parse_file(SimpleUploadedFile(name, value))

    def test_import_is_idempotent(self):
        commit_import([record()], metadata())
        _, counts = commit_import([record()], metadata())
        self.assertEqual(Student.objects.count(), 1)
        self.assertEqual(ClassMembership.objects.count(), 1)
        self.assertEqual(counts["unchanged"], 1)

    def test_same_roll_number_in_two_academic_years_has_separate_identity(self):
        commit_import([record()], metadata())
        commit_import([record()], metadata(academic_year="2570"))
        self.assertEqual(Student.objects.count(), 2)
        self.assertEqual(ClassMembership.objects.count(), 2)

    def test_duplicate_or_invalid_rows_save_nothing(self):
        for rows in [[record(), record(row=3)], [record(), record("18", "", row=3)], [record(email="not-email")]]:
            with self.subTest(rows=rows):
                with self.assertRaises(ImportProblem):
                    commit_import(rows, metadata())
                self.assertEqual(Student.objects.count(), 0)
                self.assertEqual(StudentClass.objects.count(), 0)

    def test_existing_conflict_requires_explicit_update(self):
        commit_import([record()], metadata())
        self.assertTrue(build_plan([record(name="Changed Name")], metadata())["errors"])
        with self.assertRaises(ImportProblem):
            commit_import([record(name="Changed Name")], metadata())
        commit_import([record(name="Changed Name")], metadata(update_existing=True))
        self.assertEqual(Student.objects.get().full_name, "Changed Name")

    def test_blank_optional_cells_do_not_erase_existing_email(self):
        commit_import([record(email="student@example.invalid")], metadata())
        commit_import([record(name="Changed Name")], metadata(update_existing=True))
        self.assertEqual(Student.objects.get().email, "student@example.invalid")

    def test_late_failure_rolls_back_entire_class_import(self):
        with patch.object(ClassMembership.objects, "get_or_create", side_effect=RuntimeError("unexpected failure")):
            with self.assertRaises(RuntimeError):
                commit_import([record()], metadata())
        self.assertEqual(Student.objects.count(), 0)
        self.assertEqual(StudentClass.objects.count(), 0)
