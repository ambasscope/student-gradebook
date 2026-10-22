# Architecture

One Django project, five internal business modules, and one shared browser
interface. The top navigation contains Classrooms, Courses, Modules, and
Reports; internal module names need not match the user-facing page labels.

## Module responsibilities

| Module | Responsibility |
| --- | --- |
| config | Shared settings, overview, portable data location |
| students | Student records |
| academics | Courses, semesters, course offerings, enrolments |
| assessments | Modules, marking criteria, marks, grading rules |
| reports | Report context, Word rendering, local downloads |

Dependencies point from academics to students, assessments to academics, and
reports to the preceding modules. Assessments must not depend on reports.
The local interface does not use accounts or login. Django auth tables remain
for migration compatibility and historical score author references; account and
admin routes are not exposed. New score entries have no account author.

## Request flow

```text
Teacher → shared Django interface → validated form/service → models → SQLite
Report → shared grading service → context → Word template → private download
```

Keep grade calculations in `apps/assessments/services/grading.py`; both result
pages and generated documents call it. Templates control presentation only.
App HTML may live under `apps/<module>/templates/<module>/`; common layouts live
under `templates/`. Word source templates live under reports/document_templates.

## Launch and storage

The platform launcher calls launcher.py. It prepares a machine-local virtual
environment and delegates runtime startup to that environment's Python.
Waitress serves the WSGI app only on 127.0.0.1; WhiteNoise serves collected
static assets. The local interface opens directly. CSRF protection, form
validation, and import-preview sessions remain active. Report files
stay private; never expose the app-data directory as a public static folder.

The same source folder moves between Windows and Mac. Local data moves in
app-data; dependencies and collected assets are recreated. See portability.md
and the README for the folder tree and distribution process.

## Current implementation boundary

Navigation, local startup, and storage configuration are in
place. Student models, class membership, imports, and editing are implemented. Course, CourseOffering, ClassroomEnrollment, and Enrollment are also implemented.
Modules, marking categories, criteria, and scores are implemented. Tabulator
6.6.0 runs locally with grouped scoring columns, validated block paste, repeat
autofill, and undo/redo. The server validates every submitted batch atomically
and compares previous cell values, scheme revision, and classroom roster.
The grading service supports raw points and normalized weighted categories.
Module Record reports use the shared grading service, a validated preview,
and an editable Thai Word template. A report registry supports further forms. No background worker,
separate JavaScript frontend, or external database server is required initially.

## References

- [Django app structure](https://docs.djangoproject.com/en/5.2/intro/reusable-apps/)
- [docxtpl templates](https://docxtpl.readthedocs.io/en/latest/)
- [SQLite usage guidance](https://www.sqlite.org/whentouse.html)
