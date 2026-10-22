# Module Record export

The template's `{{ unit_id }}`, `{{ semester }}`, and `{{ academic_year }}` slots
are supported. Create units on the course page and assign each module to a unit.
Only the unit ID is printed. Semester is numeric; academic year comes from the
course teaching period and can differ from the teaching/signature date's year.
See [units and semesters](units-and-semesters.md).

1. Save the teacher's **Name** and **Academic status (วิทยฐานะ)** on Teacher.
   Previous Position values are retained in the renamed Academic status field.
2. On each module's classroom scoring page, save a learning date, one completion
   choice, attendance, scores, and shared problems/suggestions.
3. Open **Reports → Module Record**, choose a course teaching period, and click
   **Load classrooms and modules**.
4. Select a classroom and the modules to include, then **Prepare preview**.
5. Review the four category mappings, objectives, comments, attendance and counts.
   The standard Thai category names map automatically; custom names need an
   explicit choice. Select a different scoring category for each form section.
   Only those four selected categories appear in this fixed form.
6. Shorten report wording if prompted, then **Update preview** and
   **Export Word (.docx)**. These wording edits apply to this download only.

The download combines one A4 page per module for the selected classroom, ordered
by module number (then module ID). Up to 50 modules can be exported together.
Repeat for another classroom. All pages share the Thai template, regardless of
interface language. The learning date also fills the signature date, with the
Thai month name and Buddhist year. The signature line remains blank for signing.

## Counts and evaluation

The base is every active course enrollment whose student belongs to the selected
classroom **and currently marked Studying**, including absent students. Resigned
students are excluded from counts and every percentage, even for older modules.
This current-status report roster can differ from historical score entry.
Absence does not remove students from any percentage. A missing attendance row
means present, matching the default checked attendance box.

For each selected category, an assessment is complete only when every
subcategory has a mark. Incomplete/unassessed categories count as failed in this
report; their marks remain unchanged and the scoring page still shows Pending.
A complete category passes unless its matching qualitative level has **Count as
failed** checked. Excellent, Good and Pass all pass in the default rubric; Fail
fails. The flag can be edited even after marking starts, so custom names in
English or Thai do not have to match a hard-coded word. Existing Fail/Failed,
ไม่ผ่าน and ไม่ผ่านเกณฑ์ labels are flagged during the upgrade; review other
custom failure labels yourself on the module editor.

Passed + failed equals the full roster size in every section. Percentages use
that same denominator and round to two decimal places. Category weights affect
assignment totals, not category pass/fail thresholds. A student with complete
marks can still pass while marked absent; missing marks always fail in the
report, as requested.

## Preview and layout

The preview requires a saved teacher profile, learning date, completion choice,
and a nonempty course roster. It verifies selected modules belong to the chosen
teaching period and the classroom is enrolled in it. Preview tokens expire after
one hour. Changed wording, scores, attendance, rosters or source details require
a refreshed preview before export.

Report objectives are limited to 160 characters, module titles to 90, and each
comment to 240. A conservative line budget also blocks text that exceeds the
one-page layout. Saved objectives and comments can remain longer. For this
fixed form, course names (60), course IDs (25), classroom labels (10), teacher
names (80) and academic status (70) must fit; edit unusually long source labels
if prompted. Use TH Sarabun New to keep the intended appearance. Different
fonts or Word layout engines may alter wrapping, so inspect the exported file
before printing.

## Adding another report form

Add a dedicated selection/context service, Word template, and view/URL, then
register its title, description and URL in
`apps/reports/services/registry.py`. Keep each report's counting rules and
renderer separate where its structure differs. Assessments never depend on
reports. The first implemented type is Module Record; other forms can be added
without changing scoring models.
