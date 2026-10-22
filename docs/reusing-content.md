# Reusing courses and modules

For another academic year, open the course and select **Copy teaching period**.
The course ID and name can be reused across years. Choose the destination course,
academic year, semester, and classrooms, then select the modules to copy. You can
instead choose an existing teaching period; its classroom enrolments stay as they
are. Creating a new period enrols only the students in the selected destination
classrooms.

Module numbers are preserved across years. If a destination course and year
already uses a number, the copy stops and creates nothing. Select **Use available
module numbers when a number is already used** to permit automatic renumbering,
or copy an individual module and choose its number yourself. Numbers remain
unique across both semesters of a course's academic year. Legacy modules without
numbers receive available numbers during a bulk copy.

Copying modules preserves their names, information, learning objectives, category
aggregation methods, weights, maximum marks, and category evaluation rubrics.
The copies get new database identities and generated public IDs, are unlocked,
and contain no scores, attendance, teaching dates, completion status, or classroom
comments. Changing the copies leaves their originals unchanged.

Other copy actions:

- **Course:** enter a new course ID; optionally include all units and a source
  teaching period with its modules. Use this when you need a separate course.
- **Unit:** choose a destination course, unit ID, and name. Optionally copy the
  modules from one source period into a destination period.
- **Module:** opens the usual editor with a copy of its settings. Select its
  destination period and unit and review the module number. Within its original
  year, the form suggests the next available number. Changing to another year
  lets you reuse the original number.
- **Classroom:** choose its class/section and year. By default the classroom is
  empty. Optionally copy names, roll numbers, email addresses and student notes;
  students receive newly generated IDs, without any course enrolments or scores.
- **Student:** choose a new classroom and roll number to copy the student's
  details with a new generated ID. Historical records are retained.
- **Marking library category:** edit a copy of its bilingual names and
  subcategory defaults, then save it as a new category.
- **Rubric preset:** copy its evaluation levels and enter a new preset name.

Bulk copies reuse destination units only when both their unit IDs and names
match. A conflicting unit name stops the copy; copy modules individually to
choose another unit. Unassigned legacy modules also need a unit before bulk
copying, or can be copied individually and assigned a unit in the editor.

Opening a copy page never creates records. **Create copy** or **Save** commits
the reviewed form. Each bulk copy is one transaction: failures leave no partial
course, unit, teaching period, student roster, or module copies behind.
