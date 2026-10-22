# Modules and scores

1. Create a course teaching period and enrol its classrooms on Courses.
2. Open Modules → Add module (also available within a course period).
3. Enter a module number (1–99), name, course teaching period, and optional information. The ID is generated from year + course ID + two-digit number.
4. Choose Add category scores or Weight categories by percentage for the module total.
5. New modules start with four categories and no subcategories. Enter learning
   objectives and add named subcategories with positive maximum marks. You can
   save a draft before adding subcategories, or start with your own categories.
6. For each category, choose Sum, Average, or Weighted average, then keep or edit
   its independent evaluation rubric. Average modes use one common maximum.
7. Save, open the module, and select an enrolled classroom.
8. Double-click a scoring cell to enter a mark, then select Save changes.

Module numbers are unique within a course/year across all semesters.
The generated key includes the course ID, including its letters and leading zeroes. An
module belongs to one specific course teaching period. Creating a new
period does not reuse or change the previous period's marks.

## Teacher and modules

The Teacher tab comes immediately before Classrooms and stores one teacher
profile for this local app: name (ชื่อ) and academic status (วิทยฐานะ). Save the form to
record or update the profile. It does not create a login account.

The user interface now calls assignments Modules (แผนการเรียนรู้). Existing
module IDs, course references, scores, and attendance are retained. The main
module URLs use `/modules/`; old `/assignments/` links still work.

## Default marking scheme and objectives

New modules start with four categories:

- ด้านความรู้
- ด้านทักษะและการปฏิบัติ
- ด้านเจตคติและคุณลักษณะ
- สมรรถนะ

There are no default subcategories, maximum scores, or category weights.
For each category, enter its name and learning objective (จุดประสงค์), and
add named subcategories with their maximum marks. Category/subcategory codes
are no longer entered or displayed. You may edit category names and the scheme
before marking starts.

Modules can be saved as drafts with empty categories. Every category needs at
least one subcategory before score entry is enabled. Attendance, completion
status, and classroom comments can still be saved while the scheme is a draft.
For weighted scoring, the category weights must total 100%.

Load preset replaces the displayed scheme with the new four-category draft
and selects raw points. Restore previous scheme reverses the most recent
load/start-blank action until the form is saved. Existing modules keep their
saved categories and marks unless you explicitly replace an unmarked scheme.

Learning objectives remain editable after marking starts, alongside the module
name, number, information, and evaluation rubric. Updating an objective preserves
existing subcategories and score records; open scoring pages must reload afterward.

## Calculations

Sum adds entered subcategory marks. For example, 8/10 + 12/20 + 4/5 gives 24
points out of a possible 35. Average divides by the number of subcategories;
Weighted average uses positive relative subcategory weights. Both average modes
require equal maxima. The module total then adds category scores or applies
category percentage weights. See [category calculations](category-calculations.md).

Weighted categories first divides each category's subtotal by its combined
maximum, then multiplies by its percentage weight. Category weights must total
exactly 100%. For A weighted 70% and B weighted 30%, marks A = 20/30 and
B = 4/5 give (20/30 × 70) + (4/5 × 30) = 70.67 out of 100.

Marks and weights accept at most two decimal places. No negative marks or
marks above the subcategory maximum are accepted. Blank cells remain unmarked;
zero counts as an entered mark. Totals reflect entered marks so far, and the
Marked column shows completion. An incomplete total is not a finalized grade.

## Category evaluation

The Summary section has a qualitative evaluation column beside each category's
subtotal. Evaluations update immediately when valid scores are edited, pasted,
filled, cleared, or undone. They are derived from scores, rather than stored as
separate marks.

Category percentage = unrounded category score / category maximum × 100,
using that category's selected aggregation method for both score and maximum.
Category weights affect the overall weighted total, but do not affect this
percentage. Classification uses exact values before display rounding.

| Percentage | Default evaluation |
| --- | --- |
| 80% to 100% | Excellent |
| 60% up to, but excluding, 80% | Good |
| 50% up to, but excluding, 60% | Pass |
| Below 50% | Fail |

For example, a category subtotal of 24/30 is Excellent, 4/6 is Good, and
4/9 is Fail.
Each category stays Pending until every one of its subcategories has a recorded
score. Zero is a recorded score; a blank is unmarked. Invalid entries also leave
the affected category Pending.

Open Modules → a module → Edit module → Category evaluation rubric.
You can rename labels (including Thai labels), change thresholds, add or remove
levels, and load the default again. Changes are saved with Save module.
Provide 1–20 levels, distinct labels and minimum percentages, and a 0% level
to cover the lowest scores. Thresholds accept at most two decimal places and
must be between 0 and 100. Levels are saved in descending threshold order;
the highest matching minimum applies.

Each module has its own rubric. Editing it does not change another
module, subcategory maxima, or any stored marks. Existing modules get
the default rubric when this migration is applied. The rubric remains editable
after marking starts. Open score pages must reload after a rubric change before
saving more marks, to ensure they use the current rubric.

Evaluation labels are user-editable data and do not change with the interface
language toggle. New interface strings are collected in the Thai translation
catalogs with blank translations for you to complete.

## Spreadsheet controls

- Select a score cell and paste a rectangular numeric block copied from Excel.
  Score columns are consecutive; omit headings, IDs, names, and totals.
- Paste into one cell to expand to the pasted block. Paste into a selected
  rectangle to repeat the pasted values over that selection.
- Select cells and drag the small corner handle to repeat their values. This
  autofill repeats a pattern; it does not generate Excel sequences or formulas.
- Fill selection applies one number; Empty cells only preserves entered marks.
- Clear selection makes scoring cells unmarked. Student details and summary
  columns are read-only.
- Undo/Redo applies to changes since the last save, including block paste and
  autofill. Saving clears the undo history.
- Find student filters the displayed students without losing unsaved marks.

Save changes is explicit. Unsaved cells are highlighted, and leaving the page
with unsaved changes prompts a browser warning. Internet access and Microsoft
Excel are not required for this grid.

## Module completion

On each classroom scoring page, select exactly one checkbox before saving:

- Module completed — การจัดการเรียนรู้เป็นไปตามแผน
- Module uncompleted — การจัดการเรียนรู้ไม่เป็นไปตามแผน

Selecting one unchecks the other. The choice is stored for this specific module
and classroom. It describes delivery according to the learning plan, separately
from attendance and how many scores have been entered. Existing records start
without a completion choice; choose one when next saving. Completion can be saved
by itself, with comments or attendance, or together with scores.

## Attendance and classroom comments

The Attendance column beside student details contains a checkbox for each
student. Checked means present; unchecked means absent. Existing and new
students start checked unless an absence has already been saved for that
module and classroom. Attendance is separate from marks: recording an
absence does not set a score to zero or change an evaluation.

Below the grid, Classroom comments provides two panels shared by the entire
class for this module. They are not comments attached to individual
students. Choose any of the supplied Thai sentences:

**ปัญหาและอุปสรรค**

- กิจกรรมการจัดการเรียนรู้ ไม่เหมาะสมกับเวลา
- มีนักเรียนทำใบงาน/ใบกิจกรรมไม่ทันตามกำหนดเวลา
- มีนักเรียนที่ไม่สนใจเรียน
- อื่น ๆ — select this to enable the other-problems text box.

**ข้อเสนอแนะ/แนวทางแก้ไข**

- ควรนำแผนไปปรับปรุง เรื่อง — with a topic field.
- แนวทางแก้ไขนักเรียนที่ไม่ผ่านการประเมิน — with a solution field.
- แนวทางแก้ไขนักเรียนที่ไม่มาเรียน — with a solution field.
- ไม่มีข้อเสนอแนะ — exclusive of the other suggestions.

Selected suggestions enable their respective detail fields. Additional
suggestion details can be entered in the larger text box, except while
ไม่มีข้อเสนอแนะ is selected. Each text field accepts up to 5,000 characters.
Unchecked detail fields are inactive and are not saved; their text remains in
the current page in case you reselect the option before leaving.

Use either Save changes button to save scores, attendance, selected sentences,
and classroom comments together. You can save attendance or comments without
entering any marks. The whole batch is validated before anything is written;
invalid or conflicting changes reject the batch. Unsaved attendance/comments
also block language switching and prompt when leaving the page.

Attendance and comments are separate for every module/classroom pair.
Changing one classroom's attendance or notes does not change another's, even
when a student shares the same course score in two classroom views. Text and
selections are retained across reopening the page. A new module starts with
checked attendance and empty classroom comments.

The supplied common sentences and default category names remain Thai in both
interface languages. New interface labels and messages have blank entries in the
Thai catalogs for manual translation. To revise the supplied sentences later,
edit `apps/assessments/services/classroom_records.py`; keep their stable IDs so
existing saved selections continue to work.

## Preserving records

Only active course enrolments that are still members of the selected classroom
appear. If the classroom list changes after course enrolment, review roster
updates in Courses before marking new students. A student shared by two
classrooms uses the same course enrolment and therefore the same module
scores in both classroom views.

Saving checks the roster, scheme revision, each edited score/attendance cell's
previous value, and the classroom comment revision. A stale or invalid batch is rejected in full; the unsaved entries remain
on the page. Reload to review current data before retrying a conflicting edit.

After the first nonblank score is saved, category names, subcategory structure,
maximum marks, overall category weights, and course teaching period are locked,
even if marks are later cleared. Module number, name, information, learning
objectives, category aggregation, subcategory weights, and each category's rubric
remain editable; the public ID follows the number. The course/year/semester identity
of a marked teaching period is also protected. Create a new module for a
different scheme. Historical marks remain stored when enrolments become inactive.

## Storage and distribution

Scores use the existing local SQLite database at `app-data/db.sqlite3` by
default (or the configured `GRADEBOOK_DATA_DIR`). No account or login is required. Restart the launcher to apply
the new migration and refresh bundled assets. Updating the source keeps the
existing database. A fresh source ZIP excludes app-data, credentials, runtime
assets, backups, and Python environments, so recipients create their own data.

Excel file export/import for marks, resit attempts, late penalties, exemptions,
final letter grades, semester-level module weights, and further Word report forms are
future work. The current weights apply to categories within one module.

See [generated ID guide](generated-identifiers.md) for identity rules and legacy
record conversion. Classroom scoring now displays local roll numbers too.
