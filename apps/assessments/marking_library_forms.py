import json
from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from .services.schemes import decimal_value
from config.numbers import compact_number


class MarkingLibraryForm(forms.Form):
    name_th = forms.CharField(label=_("Category name (Thai)"), max_length=150, required=False)
    name_en = forms.CharField(label=_("Category name (English)"), max_length=150, required=False)
    subcategories_json = forms.CharField(widget=forms.HiddenInput, max_length=250000)
    revision = forms.IntegerField(widget=forms.HiddenInput, required=False)

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        super().__init__(*args, **kwargs)
        if instance:
            self.initial.update(name_th=instance.name_th, name_en=instance.name_en,
                                subcategories_json=json.dumps(instance.subcategories, ensure_ascii=False), revision=instance.revision)
        else:
            self.initial['subcategories_json'] = '[]'

    def clean_subcategories_json(self):
        try:
            items = json.loads(self.cleaned_data['subcategories_json'])
        except (ValueError, TypeError):
            raise ValidationError(_("The subcategory list could not be read. Review it and try again."))
        if not isinstance(items, list) or len(items) > 100:
            raise ValidationError(_("Use at most 100 subcategories per library category."))
        result, seen = [], set()
        for item in items:
            if not isinstance(item, dict):
                raise ValidationError(_("Each subcategory needs a name in Thai or English."))
            names = {}
            for field in ['name_th', 'name_en']:
                name = item.get(field, '')
                if not isinstance(name, str) or len(name.strip()) > 150:
                    raise ValidationError(_("Names must contain at most 150 characters."))
                names[field] = name.strip()
            if not any(names.values()):
                raise ValidationError(_("Each subcategory needs a name in Thai or English."))
            keys = {(field, value.casefold()) for field, value in names.items() if value}
            if keys & seen:
                raise ValidationError(_("Each subcategory in this category must have a different name."))
            seen.update(keys)
            maximum = item.get('maximum', '')
            if maximum not in ('', None):
                maximum = compact_number(decimal_value(maximum, _("Maximum mark"), minimum=Decimal('0.01')))
            else:
                maximum = ''
            weight = compact_number(decimal_value(item.get('weight', 1), _("Subcategory weight"),
                                                   minimum=Decimal('0.01'), maximum=Decimal('9999.99')))
            result.append({**names, 'maximum': maximum, 'weight': weight})
        return result

    def clean(self):
        data = super().clean()
        if not data.get('name_th') and not data.get('name_en'):
            self.add_error(None, _("Enter the category name in Thai or English. The other language is optional."))
        if self.instance and data.get('revision') != self.instance.revision:
            self.add_error(None, _("This library category changed in another window. Reload before saving."))
        return data
