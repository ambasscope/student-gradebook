"""Report types have separate views, contexts and document renderers."""
from django.utils.translation import gettext_lazy as _

REPORT_TYPES = [
    {"name": _("Module Record"), "description": _("Export the Thai teaching record: one page per module and classroom, combined in one Word document."), "url_name": "reports:module-record"},
    {"name": _("Student score workbook"), "description": _("Export a portrait A4 Excel workbook with one summary sheet and one sheet per marking category for each selected module."), "url_name": "reports:student-scores"},
]
