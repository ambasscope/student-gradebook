from django import forms
from django.utils.translation import gettext_lazy as _
from apps.academics.models import CourseOffering
from apps.students.models import StudentClass
from apps.assessments.models import Assignment
from apps.assessments.forms import OfferingChoice
from .services.context import REPORT_SECTIONS, infer_category


class ModuleChoice(forms.ModelMultipleChoiceField):
    def label_from_instance(self, module):
        label = f"{module.assignment_number or module.assignment_id} — {module.name}"
        if module.unit_id:
            return _("Unit %(unit)s · %(module)s") % {"unit": module.unit.unit_id, "module": label}
        return label


class ModuleRecordSelectionForm(forms.Form):
    offering = OfferingChoice(label=_("Course and teaching period"), queryset=CourseOffering.objects.select_related("course").all())
    classroom = forms.ModelChoiceField(label=_("Classroom"), queryset=StudentClass.objects.none())
    modules = ModuleChoice(label=_("Modules to export"), queryset=Assignment.objects.none(), widget=forms.CheckboxSelectMultiple)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        raw = (self.data if self.is_bound else self.initial).get("offering")
        try:
            period = CourseOffering.objects.get(pk=raw)
        except (CourseOffering.DoesNotExist, ValueError, TypeError, OverflowError):
            return
        self.fields["classroom"].queryset = period.classrooms.all()
        self.fields["modules"].queryset = period.assignments.select_related("unit").order_by("assignment_number", "assignment_id")

    def clean_modules(self):
        modules = self.cleaned_data["modules"]
        if len(modules) > 50:
            raise forms.ValidationError(_("Export at most 50 modules at a time."))
        return modules


class ModuleRecordWordingForm(forms.Form):
    module_title = forms.CharField(label=_("Module title in report"), max_length=90)
    problem = forms.CharField(label=_("Problems in report"), required=False, max_length=240, widget=forms.Textarea(attrs={"rows": 3}))
    suggestion = forms.CharField(label=_("Suggestions in report"), required=False, max_length=240, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, source, **kwargs):
        self.source = source
        categories = source["categories"]
        initial = {"module_title": source["module_title"], "problem": source["problem"], "suggestion": source["suggestion"]}
        for section in REPORT_SECTIONS:
            match = infer_category(categories, section["key"])
            initial[section["key"] + "_category"] = str(match["id"]) if match else ""
            initial[section["key"] + "_objective"] = match["objective"] if match else ""
        super().__init__(*args, initial=initial, **kwargs)
        self.fields["module_title"].widget.attrs["maxlength"] = 90
        for section in REPORT_SECTIONS:
            key = section["key"]
            self.fields[key + "_category"] = forms.ChoiceField(label=section["title"], choices=[("", _("Choose marking category"))] + [(str(c["id"]), c["name"]) for c in categories])
            self.fields[key + "_objective"] = forms.CharField(label=_("Learning objective in report"), max_length=160, widget=forms.Textarea(attrs={"rows": 2}))
        # Put categories/objectives before the final comments.
        order = ["module_title"]
        for section in REPORT_SECTIONS:
            order.extend([section["key"] + "_category", section["key"] + "_objective"])
        self.order_fields(order + ["problem", "suggestion"])

    def clean(self):
        data = super().clean()
        chosen = [data.get(s["key"] + "_category") for s in REPORT_SECTIONS]
        if all(chosen) and len(set(chosen)) != len(chosen):
            raise forms.ValidationError(_("Choose a different marking category for each report section."))
        return data
