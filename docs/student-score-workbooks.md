# Student score workbook

Open **Reports → Student score workbook** (สมุดบันทึกคะแนนผู้เรียน).
Choose a course teaching period and click **Load classrooms and modules**.
Select one enrolled classroom and the modules to include, then use
**Preview workbook sheets** or **Export Excel (.xlsx)**.

The download contains, in module-number order:

1. One module summary sheet: roll number, name, and each category's calculated
   score and qualitative assessment. No total across categories is included.
2. One sheet for each category, in marking-scheme order: roll number, name,
   every raw subcategory score and one qualitative assessment column. There is
   no additional subtotal column on these category sheets.

Three modules with four categories each produce 15 sheets. No cover, extra
summary or instruction sheet is added. Sheet names include the module number
and category; long names are shortened only for Excel's 31-character tab limit.
Full category and subcategory names remain in the sheet headings. Duplicate
or invalid tab names are handled automatically.

## Titles and printing

Each sheet starts with these centered Thai lines:

```text
แบบบันทึกคะแนนประกอบรายวิชา {course_name} ปีการศึกษา {academic_year}
แผนการเรียนรู้ที่ {module_number} ชื่อแผน {module_name}
ชั้นมัธยมศึกษาปีที่ {classroom}
```

The module number is the number entered in the app, rather than the generated
database identifier; legacy modules without a number use their retained ID.
The selected classroom label, such as 4/1, appears as saved. A fourth line
identifies the category or the category summary.

All sheets are set to A4 portrait, one page wide, unlimited pages tall, with a
bounded print area, centered horizontally and page numbers in the footer.
Rows 1–8 (titles and table headings) repeat on every printed page. Category and
subcategory headings rotate upward by 90 degrees. Maximum scores are printed
below their headings. The first two columns and eight header rows are frozen
for scrolling. Row heights account for long names and assessment labels.

In Excel, choose **Print Entire Workbook** to print all selected modules, or
print individual sheets. The font is TH Sarabun New, matching the app's Thai
Word report. Install that font for the intended appearance and inspect Print
Preview before printing; substitutions and printer settings can change page
breaks. Extremely wide custom schemes still scale down to fit the page width.

## Data and calculations

The workbook roster includes active course enrollments whose students
belong to the selected classroom, including absent and resigned students.
Resigned students appear as grey rows with roll number and name only, on every
summary and category sheet. Their score and evaluation cells contain no values
or formulas, even for older modules; their original marks remain in SQLite. Saved roll numbers
are retained and sorted; exporting never renumbers or changes students. Missing
or duplicate roll numbers must be corrected before export. Teacher profile,
teaching date, completion choice and shared comments are not prerequisites for
a score workbook.

Raw marks are numeric Excel cells. Missing marks stay blank, recorded zeroes
remain zero, and a wholly unmarked category has a blank subtotal. A partially
marked category shows its entered subtotal and รอการประเมิน. Complete categories
use that category's saved qualitative rubric, including custom labels. Category
scores use its selected Sum, Average, or Weighted average method, independently
of the module's overall category percentage weights. Average modes require the
same maximum for every subcategory. Partial averages keep the full planned
denominator, and qualitative assessment uses unrounded values.
The module-record form's aggregate count-as-failed rule does not replace a
student's pending assessment in this score export.

Each category sheet owns its assessment formula. Its saved rubric is visible
below the student table, outside the print area, without creating an extra
sheet. Relative weights for Weighted average are also stored below that table.
Summary scores calculate from the category's raw cells and weights using its
saved aggregation method, and summary assessment
cells link to that category sheet. Formulas include cached grading-service
results for immediate viewing and recalculate in Excel after downloaded marks
are edited. Editing the workbook does not update the application's database.

Only selected modules from the chosen teaching period and classroom are
accepted. Up to 50 modules are selectable; very large exports are bounded to
500 sheets / 500,000 table cells. Export smaller groups if prompted.

## Implementation

`apps/reports/services/score_context.py` reads the roster and shared grading
results within the report view's database transaction.
`score_workbooks.py` generates native XLSX worksheets, formulas, caches, print
settings and safe literal text using the standard library and a versioned style
workbook in `apps/reports/spreadsheet_templates/`. No extra runtime or package
installation is required. See [category calculations](category-calculations.md)
for settings, formulas, and migration behavior.
