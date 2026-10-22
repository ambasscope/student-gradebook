# Student system

The Students page supports file imports, manual add/edit, search, class/year
filters, and class metadata editing. The local application opens directly
without accounts or login.

## Student identity and class membership

`Student.student_number` is now generated as year (4 digits), classroom code
(3 digits), and roll number (2 digits). Example: 2569, 4/1, 3 → 256940103.
`Student.roll_number` stores the number local to the classroom, and
`Student.identifier_class` records the classroom/year used for the identifier.
SQLite's internal primary key remains stable for enrolments and scores.
The generated identifier is hidden from user-facing pages, including imports,
scoring and delete previews. `Student.student_id` is a separate, optional
school-issued identifier, stored as text to retain leading zeros. It may repeat
across classrooms or years; imports always match classroom/year/roll. Existing
generated identifiers and related scores are preserved; the new optional ID
starts blank for existing records.

Each classroom/year has separate student identities. Existing ambiguous legacy
identities retain their IDs and memberships. See generated-identifiers.md.

## File workflow

1. Choose .xlsx, .xls, .csv, or .tsv and enter the class/section and academic year.
2. Match columns to roll number (1–99) and name. Use one full-name column, or separate
   first/last name columns. Optional columns: school-issued Student ID, email and student notes.
3. Review the preview and row errors, then save the complete import.

Only a classroom roll number and name are required in the file. An example
UTF-8 CSV is available from the import page. Repeating the import of the same
class/year does not duplicate students or memberships. The same roll number in
another class/year has a different generated ID. Duplicate roll numbers inside
one file, including 3 and 03, are rejected. Existing conflicting details require
the explicit update option; blank optional values never clear Student ID, email or notes.

The first nonblank row is interpreted as the header. The first Excel sheet is
used unless a sheet name is entered. Supported CSV separators: comma, semicolon,
tab. UTF-8 is the default; UTF-16, Thai Windows, and Western Windows are selectable.
Files are limited to 5 MB, 5,000 data rows, and 100 columns. Save identifiers as
Text in Excel; zero-only number formats such as 00000 are also preserved, but
digits already lost by Excel's numeric precision cannot be recovered. Formulas
use values cached by Excel; save as values if their cached results are missing.

Uploads are parsed and stored temporarily in the user's database-backed session;
the source file is not retained. Previews expire after 30 minutes and are removed
from the active session after successful import. Imports are validated again at
save time and committed as one database transaction. A preview contains only
the first 100 students, but validation covers every row.

## Run this version

Restart the platform launcher. The updated requirements install openpyxl/xlrd
and the launcher applies the included students migration. The database remains
in the existing app-data folder. For manual development:

```sh
python -m pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
```

Then open Classrooms → Import student list. Tests:

```sh
python manage.py test apps.students
```

The .xls fixture in the tests contains fictional sample data and does not
require xlwt at runtime. Additional Word report forms remain
outside this student-system change.

## Studying and resignation

Students default to Studying (กำลังศึกษา). Edit a student to choose Resigned
(ลาออก) and a calendar resignation date. The date is required for Resigned and
must be cleared to return to Studying. Imports do not reset status. Copying a
student or classroom preserves the optional ID and status; edit them if needed.

The resignation date is the first day excluded from score entry. The saved
classroom/module teaching date decides who appears; without a date, the local
computer date is used. Modules before resignation retain their scores and remain
editable. Saving a teaching-date change refreshes the roster. If unsaved score
edits would become ineligible on the new date, they are rejected atomically;
undo those cell edits and save the date first. No stored marks or attendance
are deleted by a status/date change. Reopening an old page after a status change
requires reloading before saving.

Word module reports use **current** Studying status, even for older modules,
and still include studying students who were absent or unassessed. Excel
exports keep all active course-enrolled students, but resigned students have
grey rows with only roll number/name and no marks or evaluation formulas,
even for modules taught before resignation. Original marks remain in SQLite.
