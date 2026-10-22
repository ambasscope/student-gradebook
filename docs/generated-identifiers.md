# Generated student and module IDs

Student lists now contain roll numbers local to one classroom, rather than
institution-wide student IDs. The application generates the public student ID;
the internal SQLite primary key remains unchanged and continues to link courses
and scores.

## Students

Format: four-digit academic year + three-digit classroom code + two-digit roll number.

- Academic year: exactly four digits, such as 2569. No Buddhist/Gregorian conversion is performed.
- Classroom: grade/section, grade 1–9 and section 1–99. For 4/1, the code is 401; for 4/12 it is 412.
- Roll number: 1–99. Numbers 3 and 03 represent the same roll number and become 03 in the generated ID.
- Example: year 2569, classroom 4/1, roll number 3 → 256940103.

The Excel/CSV/TSV file needs a roll-number column and a name column. The import
form supplies the classroom and academic year. Column matching, preview, and
confirmation work as before; the preview now shows both the roll number and
generated ID. Download the updated CSV template for an example.

Repeating the same classroom/year import reuses the same generated IDs.
The same roll number in another classroom or another year creates a separate
student record. The system does not assume these are the same person; tracking
one person across years would require a separate permanent personal identifier.
Duplicate numbers such as 3 and 03 in one list are rejected. Maximum roll number
is 99, regardless of the file-size limits.

For manual entry, choose a classroom and enter the roll number. The app generates
the ID on save. Generated student identities retain their classroom/year and
roll number; names, email, and notes remain editable. Classroom names and years
that determine generated IDs are protected from changes. Create another
classroom for a different year or section. Classroom lists and the scoring grid
show the roll number alongside the generated ID.

## Modules

Format: four-digit academic year + course ID + two-digit module number.

For year 2569, course MATH101, module number 3, the key is 2569MATH10103.
Enter only the module number (1–99); select the course teaching period and
the app derives the key. Course IDs remain text and may contain leading zeros.

The format does not include the semester, so module numbers must be unique
across all semesters for the same course and academic year. Use the next unused
number when another semester already used that number. Numbers may repeat for
another course or academic year. A course ID or teaching-period year used by
generated modules cannot change, to preserve these keys.

## Existing records

The upgrade changes public IDs only where the number can be identified safely.
Student conversion requires exactly one classroom membership, a valid classroom
and year, and either a numeric legacy number from 1–99 (leading zeroes allowed)
or an already correctly composed ID. Module conversion accepts a plain
one/two-digit number, or a key already matching its course/year and two-digit
number. Arbitrary text such as HW03 is preserved rather than guessed.

Multiple classroom memberships, invalid classroom/year formats, duplicate
classroom namespaces, or colliding generated keys leave the original records
unchanged. Records are never merged or deleted. Internal student, enrolment,
module, criterion, and score keys remain unchanged, preserving scores.

A preserved legacy record can still have its details edited. Its form lets you
leave the number blank to retain its ID. Explicit conversion requires a valid
classroom/number and no conflicting records; students with several classroom
memberships need their identity resolved first.

Back up app-data before upgrading. The automatic conversion does not retain the
previous public ID in a separate field; restoring the pre-upgrade database
backup is the recovery path if conversion needs to be reversed. This update
backs up the installed database and replaces no student data with sample data.

Restart the launcher after updating. It applies the included migrations and
refreshes the web assets. No account setup or login is required.
