# Score workbook styles

`score-styles.xlsx` is the internal style source. `style-cells.json` maps style
names to sample cells in its single Styles worksheet. It contains no student
data. The exporter reads its styles and theme, adds native 90-degree rotation,
and creates the selected modules' worksheets. The Styles worksheet is never
included in downloaded reports.

Report text, formulas, column widths, page setup and the three-line Thai title
are defined in `apps/reports/services/score_workbooks.py`. Data and qualitative
results originate in `score_context.py` and the shared assessment service.
The line-width estimates in `document_templates/line-widths.json` are reused
for Thai row-height estimates; no font files are distributed.
