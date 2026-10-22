# Classrooms and courses

## Classrooms

The main navigation now uses Classrooms. Each classroom appears as a card with
its class/section, academic year, and student count. Opening a card shows the
classroom's students, notes, and enrolled courses. Import/add actions started
there preselect that classroom. All students remains available as a secondary
view for searching across classrooms.

The students module, models, identifiers, and existing records are retained.
Canonical links start with `/classrooms/`; the earlier `/students/` routes remain
available for compatibility.

## Courses

Choose Courses → Add course. Enter:

- Course ID: a unique, text identifier, preserving leading zeros.
- Course name.
- Information: a free-text description or notes.
- Academic year and a numeric semester (usually 1 or 2) for the first teaching period.
- Any number of classrooms from that academic year.

A reusable Course record holds its ID, name, and information. A CourseOffering
holds the academic year, semester, and selected classrooms. This keeps future
modules and scores separated between teaching periods. Duplicate course IDs
and duplicate teaching periods are rejected. An empty classroom selection is
allowed so a course can be prepared before students are available.

The course detail page lists its teaching periods and classrooms. Edit course
details changes the reusable metadata; Edit period and classrooms changes the
selected classroom enrolments. Add teaching period reuses the course for another
semester or academic year without creating a duplicate course ID.

Use the Units section to create course units with an ID and name, then create
modules inside those units. Unit IDs are unique within a course. See
[units and semesters](units-and-semesters.md) for hierarchy and report fields.

## Student roster

Saving a teaching period enrols the current students of its selected classrooms.
Students shared by two classrooms are enrolled only once. The course roster is
stored explicitly rather than changing silently whenever a class list changes.

After importing or adding more classroom students, use Review roster updates in
the course page to see additions/removals before applying them. A stale preview
is rejected if classroom membership changed after review. Removed students become
inactive; their enrollment records remain available for future score history.
Saving changed classroom selections also refreshes the roster.

An enrolled classroom cannot be reassigned to another academic year; create a new
classroom for the new year. Course and student IDs remain unique external keys;
stable internal primary keys preserve relationships if those labels are edited.

## Startup and validation

Restart the usual Windows/Mac launcher. It applies the included academics
migration and refreshes local static files. Existing student data remains in
the same app-data database. No new packages are needed for this change.

```sh
python manage.py test apps.students apps.academics
```

Modules, score categories, and the Tabulator marking grid are the next phase
and are not implemented by this update. Future modules should reference a
CourseOffering and scores should reference its Enrollment records.

## Classroom-local student numbers

New student records use classroom/year/roll-generated IDs. The same roll number
in different classrooms or years represents different records. Roster
deduplication applies when the same internal student record is linked more than
once (such as a preserved legacy record); the app cannot identify one person
across classroom/year changes from roll numbers alone. See generated-identifiers.md.
