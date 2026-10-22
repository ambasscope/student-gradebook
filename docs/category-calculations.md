# Category calculations and assessment levels

Open **Modules → Edit module**. Each category has its own **Combine subcategory
scores** setting and an expandable **Category evaluation rubric** editor.

- **Sum:** add the raw marks; maximum = sum of all subcategory maxima.
- **Average:** sum of raw marks divided by the total number of subcategories.
- **Weighted average:** sum(mark × relative weight) divided by sum(weights).
  Positive weights from 0.01 to 9999.99 are supported; they need not total 100.

Average and Weighted average require the **same maximum mark** for every
subcategory in that category. A shared maximum field enforces this when editing
an unmarked scheme. For example, marks 8, 6, 4 out of 10 become 18/30 under Sum,
6/10 under Average, or 5.33/10 with weights 1, 2, 3 under Weighted average.
Evaluation uses the exact, unrounded ratio (32/60 in that last example).

The existing module option **Combine category scores** controls the separate
step of combining category results into a module total. It either adds category
scores or applies the module's category percentage weights. Subcategory weights
only affect the Weighted average calculation inside their own category.

Each category's rubric has independent minimum percentages, labels, and
**Count as failed** flags. Include a 0% level. Every complete result without a
failure flag counts as passed in Module Record reports. Existing categories
start with Sum and a copy of their module's former rubric, preserving results.

Use the rubric preset selector to load starter levels, or **Save as preset**
to reuse your own levels in other categories and modules. Presets are editable
copies. See [rubric preset guide](rubric-presets.md).

Blank marks remain unmarked; evaluation stays Pending until every subcategory
is marked. Partial means use the full planned denominator (all subcategories
or all weights). The entered marks are never replaced by zeros. On the scoring
page and Excel exports, category scores display two decimal places. Assessment
bands use unrounded calculations, so a displayed rounded score does not change
the assessment threshold.

After marking starts, you can change the aggregation, subcategory weights,
objectives, and category rubrics. Existing raw marks and record IDs are retained.
Names, maxima, and the structure stay fixed. A marked category with unequal
maxima must keep Sum. Scoring pages opened before a settings change must reload
before saving, to prevent submitting stale calculations.

Both Module Record Word reports and Student score Excel workbooks use these
category settings. Excel summary cells recalculate from the category sheets;
each category sheet contains its own assessment levels and, when applicable,
relative weights below the student table and outside the printed area.
