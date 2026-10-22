import hashlib
import json
from django.core import signing
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import render
from django.utils.translation import gettext as _
from django.utils.http import content_disposition_header
from .forms import ModuleRecordSelectionForm, ModuleRecordWordingForm
from .services.context import filled_context, report_sources
from .services.documents import render_module_records, check_page_fit, LayoutError
from .services.registry import REPORT_TYPES
from .services.score_context import score_workbook_context
from .services.score_workbooks import render_score_workbook


def index(request):
    return render(request, "reports/index.html", {"active_page": "reports", "report_types": REPORT_TYPES})


@transaction.atomic
def student_scores(request):
    selection = ModuleRecordSelectionForm(request.POST if request.method == "POST" else None, initial=request.GET)
    preview = None
    if request.method == "POST" and selection.is_valid():
        data = selection.cleaned_data
        modules = data["modules"].select_related("offering__course", "unit").prefetch_related("categories__criteria")
        try:
            preview = score_workbook_context(data["offering"], data["classroom"], modules)
        except ValidationError as error:
            selection.add_error(None, error)
        else:
            if request.POST.get("action") == "export":
                try:
                    workbook = render_score_workbook(preview)
                except (OSError, ValueError):
                    selection.add_error(None, _("The score workbook could not be generated. Check the workbook style template and try again."))
                else:
                    response = HttpResponse(workbook, content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                    response["Content-Disposition"] = content_disposition_header(True, "student-scores.xlsx")
                    response["Cache-Control"] = "no-store"
                    return response
    return render(request, "reports/student_scores.html", {"active_page": "reports", "selection": selection, "preview": preview})


def preview_digest(sources, contexts):
    # Localized validation messages are excluded from the snapshot.
    stable = [{k: v for k, v in source.items() if k != "issues"} for source in sources]
    payload = json.dumps({"sources": stable, "contexts": contexts}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()


@transaction.atomic
def module_record(request):
    selection = ModuleRecordSelectionForm(request.POST if request.method == "POST" else None, initial=request.GET)
    entries, contexts, issues, token = [], [], [], ""
    selected = request.method == "POST" and selection.is_valid()
    if selected:
        data = selection.cleaned_data
        sources = report_sources(data["modules"].select_related("offering__course", "unit"), data["classroom"])
        detail_submitted = request.POST.get("wording_present") == "1"
        for source in sources:
            prefix = f"module-{source['module_pk']}"
            form = ModuleRecordWordingForm(request.POST if detail_submitted else None, prefix=prefix, source=source)
            if not detail_submitted:
                # Validate defaults too: no export until every report field fits.
                defaults = {}
                for field, value in form.initial.items():
                    defaults[f"{prefix}-{field}"] = value
                form = ModuleRecordWordingForm(defaults, prefix=prefix, source=source)
            valid = form.is_valid()
            context = filled_context(source, form.cleaned_data) if valid else None
            entries.append({"source": source, "form": form, "context": context})
            issues.extend(source["issues"])
            if context:
                try:
                    check_page_fit(context)
                except LayoutError:
                    issues.append(_("Module %(number)s has too much text for one page. Shorten its report wording below and update the preview.") % {"number": source["module_number"]})
                except (OSError, ValueError):
                    issues.append(_("The module-record template could not be read. Restore the supplied template before exporting."))
                contexts.append(context)
        ready = not issues and len(contexts) == len(sources) and bool(sources)
        if ready:
            digest = preview_digest(sources, contexts)
            token = signing.dumps(digest, salt="module-record-preview")
            if request.POST.get("action") == "export":
                try:
                    previous = signing.loads(request.POST.get("preview_token", ""), salt="module-record-preview", max_age=3600)
                except signing.BadSignature:
                    previous = None
                if previous != digest:
                    issues.append(_("The report wording or source data changed, or the preview expired. Review this refreshed preview and export again."))
                else:
                    try:
                        output = render_module_records(contexts)
                    except (OSError, ValueError, ValidationError):
                        issues.append(_("The Word report could not be generated. Check the module-record template and try again."))
                    else:
                        response = HttpResponse(output, content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
                        response["Content-Disposition"] = 'attachment; filename="module-records.docx"'
                        response["Cache-Control"] = "no-store"
                        return response
    return render(request, "reports/module_record.html", {"active_page": "reports", "selection": selection, "selected": selected, "entries": entries, "report_issues": issues, "preview_token": token})
