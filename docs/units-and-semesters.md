# Course units and semester numbers

The hierarchy is **Course → Unit → Module**. A course can have many units, and
a unit can have many modules. Units belong to the course and can be reused
across its academic years and semesters. Every module still belongs to one
specific course teaching period as well.

Open **Courses → a course → Units → Add unit** and enter its ID and name. Unit
IDs are unique within that course; another course can use the same unit ID.
Select a unit to see its modules or edit its ID/name. Use a teaching-period link
on the unit page to add a module with that unit preselected. On **Add/Edit
module**, choosing the teaching period filters units to its course. The server
also rejects a unit from any other course.

Existing modules are retained with their scores and initially have no unit.
Assign their units using Edit module before exporting Module Record reports.
Unit assignment can be changed after marking starts without replacing raw
scores or their criteria. Open score editors must reload after saving module
settings, as before. Module numbers and generated IDs retain their existing
course/year numbering; numbering does not restart for each unit.

The semester input accepts a positive whole number only, normally **1** or **2**.
Other positive semester numbers are supported. Words, fractions, zero, and
negative values are rejected. Leading zeros are removed, so `01` and `1` refer
to the same semester. New teaching periods default to 1. Display text adds the
translated label: **Semester 1** / **ภาคเรียนที่ 1**.

The update converts recognized old semester labels such as `Semester 1` and
`ภาคเรียนที่ ๒` to numeric strings while retaining the teaching-period IDs and
their enrollments. Ambiguous labels and conversions that would create duplicate
course/year/semester identities are preserved for manual review. They are not
merged or assigned invented semester numbers. New input is validated as numeric.

## Word template fields

The user's source template remains the design authority. These tokens are now
filled from saved course/module data:

- `{{ unit_id }}`: the chosen unit's public ID, including leading zeros if used.
  The report does not print its name or internal database key.
- `{{ semester }}`: the numeric semester only. Keep `ภาคเรียนที่` in the template.
- `{{ academic_year }}`: the course teaching period's academic year.

The teaching/signature date still comes from the classroom module record.
Its Buddhist calendar `date_year` is independent of the academic year: a lesson
taught in January 2570 can belong to academic year 2569. The same teaching date
is used in both date locations.

Example metadata text:

```text
หน่วยที่ {{ unit_id }} แผนการเรียนรู้ที่ {{ module_number }} เรื่อง {{ module_title }}
รายวิชา {{ course_name }} รหัสวิชา {{ course_id }} ภาคเรียนที่ {{ semester }} ปีการศึกษา {{ academic_year }} ชั้น ม. {{ classroom }}
```

Do not put the word Semester into the stored semester value; the app/template
provides the label. The report preview still checks that wording fits one page
per module, and combined Word exports still start every module on a new page.
