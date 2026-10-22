import json
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db import transaction, OperationalError
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from .models import MarkingSchemeCategory
from .marking_library_forms import MarkingLibraryForm
from .services.marking_library import category_catalog


def index(request):
    return render(request, 'assessments/marking_library.html', {
        'active_page': 'marking-library', 'categories': category_catalog()})


def editor(request, pk=None, copy_source=None):
    category = get_object_or_404(MarkingSchemeCategory, pk=pk) if pk is not None else None
    form = MarkingLibraryForm(request.POST if request.method == 'POST' else None, instance=category)
    if copy_source is not None and request.method != 'POST':
        form.initial.update(name_th=(copy_source.name_th[:141] + ' (สำเนา)') if copy_source.name_th else '',
                            name_en=(copy_source.name_en[:143] + ' (copy)') if copy_source.name_en else '',
                            subcategories_json=json.dumps(copy_source.subcategories,ensure_ascii=False))
    if request.method == 'POST' and form.is_valid():
        values = {field: form.cleaned_data[field] for field in ['name_th', 'name_en']}
        values['subcategories'] = form.cleaned_data['subcategories_json']
        try:
            with transaction.atomic():
                if category:
                    changed = MarkingSchemeCategory.objects.filter(pk=category.pk, revision=form.cleaned_data['revision']).update(
                        **values, revision=F('revision') + 1, updated_at=timezone.now())
                    if not changed:
                        raise ValidationError(_("This library category changed in another window. Reload before saving."))
                else:
                    MarkingSchemeCategory.objects.create(**values)
        except ValidationError as error:
            form.add_error(None, error)
        except OperationalError:
            form.add_error(None, _("Another save is in progress. Try again."))
        else:
            messages.success(request, _("Marking library saved. Existing modules keep their current marking schemes."))
            return redirect('assessments:marking-library')
    try:
        items = json.loads(form['subcategories_json'].value() or '[]')
        if not isinstance(items, list):
            items = []
    except (ValueError, TypeError):
        items = []
    return render(request, 'assessments/marking_library_edit.html', {
        'active_page': 'marking-library', 'form': form, 'category': category, 'initial_items': items})


def copy_category(request, pk):
    return editor(request, copy_source=get_object_or_404(MarkingSchemeCategory,pk=pk))


def delete(request, pk):
    category = get_object_or_404(MarkingSchemeCategory, pk=pk)
    error = ''
    if request.method == 'POST':
        try:
            revision = int(request.POST.get('revision', ''))
        except (TypeError, ValueError):
            revision = None
        try:
            with transaction.atomic():
                deleted, _details = MarkingSchemeCategory.objects.filter(pk=category.pk, revision=revision).delete()
                if not deleted:
                    error = _("This library category changed in another window. Reload before deleting.")
        except OperationalError:
            error = _("Another save is in progress. Try again.")
        if not error:
            messages.success(request, _("Library category deleted. Existing modules and scores are unchanged."))
            return redirect('assessments:marking-library')
    return render(request, 'assessments/marking_library_delete.html', {
        'active_page': 'marking-library', 'category': category, 'error': error})
