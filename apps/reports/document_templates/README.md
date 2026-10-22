# Module Record Word template

`module-record.docx` is the editable source for the Thai **แบบบันทึกหลังการสอน**
form. It follows the supplied PDF's sections and signature block. The app fills
plain `{{ variable }}` placeholders using python-docx and repeats the page for
each selected module in the selected classroom. Word itself is not needed to
export. Use TH Sarabun New when opening/printing for the intended Thai layout;
font substitution can change pagination. No font files are distributed.

Keep one A4 section, paragraph text, and the supplied styles/margins. No images,
automatic numbered lists, hyperlinks, tables, or additional sections are supported
by this simple page-merging renderer. Bullet characters and checkbox symbols are
plain text. Preserve placeholder spelling; Word may split a placeholder across
runs and the renderer still reads it. Do not add new placeholder names without
adding them to the report context.

Fields: `module_number`, `module_title`, `course_name`, `course_id`, `classroom`,
`semester`, `academic_year`, `unit_id`,
`date_day`, `date_month`, `date_year`, `total`, `present`, `absent`,
`present_percent`, `absent_percent`, `completed_box`, `uncompleted_box`,
`problem`, `suggestion`, `teacher_name`, `academic_status`.

For each of `knowledge`, `skills`, `attitudes`, and `competencies`, append
`_objective`, `_passed`, `_failed`, `_pass_percent`, or `_fail_percent`.
The same date tokens appear at the top and in the signature block. Years are
Buddhist years; stored teaching dates remain normal calendar dates.
`academic_year` comes from the course teaching period, independently of the
teaching/signature date. `semester` contains the number only; put the label in
the template, for example `ภาคเรียนที่ {{ semester }} ปีการศึกษา {{ academic_year }}`.
`unit_id` is the selected unit's public ID, not its database key. The report does
not include the unit name. Assign each module to a course unit before exporting.

`line-widths.json` contains advance-width estimates only, used for a conservative
page budget. It contains no font outlines. The preview blocks excessive wording
and lets users shorten it without changing their saved records. Re-render and
inspect a normal and a long combined report after changing template formatting.

Generated reports are returned directly as private downloads, never stored as
public static files. This source contains no real student data.
