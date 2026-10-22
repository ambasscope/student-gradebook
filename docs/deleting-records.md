# Delete classrooms, students, courses, units, and modules

Red Delete actions appear on the list and detail pages. The first click opens
a preview; it does not delete anything. Review the target and linked records,
check the acknowledgement, then choose Delete permanently. Cancel returns to
the existing record. English and Thai labels are included.

- Classroom: removes its student records (including generated IDs without a
  membership), their memberships in all classrooms, course enrolments, scores,
  and attendance, plus that classroom's enrolments and module records. If a
  legacy student is shared with another classroom, that student's records are
  removed everywhere; those memberships and courses appear in the preview.
  Course/module definitions and other students/classrooms are kept.
- Student: removes the student everywhere, with memberships, course enrolments,
  scores, and attendance. Whole-class comments and module records remain.
- Course: removes all its teaching periods, units, modules, schemes, enrolments,
  scores, attendance, and classroom module records across all years/semesters.
  Students and classrooms remain.
- Unit: removes its modules across all teaching periods, with schemes, scores,
  attendance, and classroom records. The course, other units, students, and
  classrooms remain.
- Module: removes its scheme, scores, attendance, and module records in all
  classrooms. The course, unit, students, and classrooms remain.

The preview shows exact counts for each record type and up to 50 entries per
type; larger groups show the remaining count. No previously exported files,
backups, or application presets are deleted. Deletion cannot be undone in the UI.

A signed preview expires after 30 minutes. Changes to the affected records
invalidate it, even when record counts have not changed. Review the refreshed
list and confirm again. Confirmations use POST with CSRF protection; deletion
runs in one database transaction so a protected relation or save conflict does
not leave partially deleted data. Model-level PROTECT relationships are retained.

No schema migration is required. Source/browser/pywebview modes use the same
buttons. A previously distributed executable must be rebuilt to include them.
