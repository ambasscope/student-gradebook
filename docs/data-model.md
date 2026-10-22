# Current data model

| App | Model | Main fields and relationships |
| --- | --- | --- |
| students | Student | Generated student_number, roll_number 1–99, identifier_class, name |
| students | StudentClass | Class/section number, academic year |
| students | ClassMembership | Student and classroom; unique pair |
| academics | Course | Unique textual course_id, name, information |
| academics | CourseUnit | Course, public unit_id unique within the course, name |
| academics | CourseOffering | Course, academic year, semester; unique combination |
| academics | ClassroomEnrollment | Classroom enrolled in a course offering |
| academics | Enrollment | Student and course offering; unique pair, active flag |
| assessments | Module | Generated assignment_id, assignment_number 1–99, name, offering, course unit, information, calculation mode, scheme lock/revision, score revision |
| assessments | MarkingCategory | Module, private category code, name, objective, percentage weight, aggregation, independent evaluation_rubric, display order |
| assessments | Criterion | Category, private subcategory code, name, maximum mark, relative weight, display order |
| assessments | Score | Enrollment, criterion, decimal mark, updated_by, timestamp; unique pair |

Student → Enrollment ← CourseOffering → Module → MarkingCategory → Criterion.
Course → CourseUnit → Module is the curriculum hierarchy. New module forms
require a unit belonging to the offering's course; legacy module rows keep a
nullable unit until explicitly assigned. Semester inputs store positive whole
number strings; translated Semester labels are added only for display.
Score links Enrollment and Criterion. The service validates that the marked
criterion belongs to the same course offering as the enrolment.

Categories have exactly one level of subcategories. Marks are stored against
subcategories; category scores use Sum, Average, or Weighted average. Average
modes require equal subcategory maxima. Each category owns its assessment bands.
The module's points mode adds the resulting category scores.
Weighted mode normalizes each category subtotal by its combined maximum and
multiplies by its percentage weight; weights must total 100%.

A blank is the absence of a Score row; zero is a recorded mark. Decimal marks
and weights allow two decimal places. Database uniqueness/nonnegative checks
complement service validation of maxima, classroom membership, and course identity.
The entire score batch is atomic. Previous-cell comparisons prevent stale edits,
and scheme/roster revisions protect structure and classroom changes.

Schemes lock after marking starts and remain locked after scores are cleared.
Names/information and the external module ID remain editable. A legacy shared
student in two classrooms has one enrolment and one mark per criterion. Newly
generated students have separate identities for each classroom/year.
Inactive enrolments retain historical scores.

Module Record Word and student-score Excel reports use these shared calculations.
Semester-level module
weights, resits, exemptions, late penalties, grade boundaries, and finalization
policies are not part of the implemented module calculation.

Generated public IDs are derived from year/class/roll or year/course/module
number. Integer primary keys remain stable. See generated-identifiers.md for
formats, cross-semester module numbering, and safe legacy conversion.
