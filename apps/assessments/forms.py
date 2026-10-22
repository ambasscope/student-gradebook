from django.utils.translation import gettext_lazy
import json
from django import forms
from django.core.exceptions import ValidationError
from apps.academics.models import CourseOffering, CourseUnit
from .models import Assignment, RubricPreset
from .services.schemes import export_scheme, validate_scheme, validate_locked_scheme
from .services.presets import default_scheme
from .services.evaluation import default_evaluation_rubric, validate_evaluation_rubric
from config.identifiers import assignment_identifier


class RubricPresetForm(forms.Form):
    name = forms.CharField(label=gettext_lazy("Preset name"), max_length=120)
    rubric_json = forms.CharField(widget=forms.HiddenInput, max_length=20000)
    revision = forms.IntegerField(widget=forms.HiddenInput, required=False)

    def __init__(self, *args, instance=None, **kwargs):
        self.instance = instance
        super().__init__(*args, **kwargs)
        self.initial.update({"name": instance.name if instance else "",
                             "rubric_json": json.dumps(instance.levels if instance else default_evaluation_rubric(), ensure_ascii=False),
                             "revision": instance.revision if instance else None})

    def clean_name(self):
        name = self.cleaned_data["name"]
        existing = RubricPreset.objects.filter(name__iexact=name)
        if self.instance:
            existing = existing.exclude(pk=self.instance.pk)
        if existing.exists():
            raise ValidationError(gettext_lazy("A saved rubric preset already uses this name. Choose another name."))
        return name

    def clean_rubric_json(self):
        return validate_evaluation_rubric(self.cleaned_data["rubric_json"])

    def clean(self):
        data = super().clean()
        if self.instance and data.get("revision") != self.instance.revision:
            self.add_error(None, gettext_lazy("This preset changed in another window. Reload before saving."))
        return data


class OfferingChoice(forms.ModelChoiceField):
    def label_from_instance(self, period):
        return f"{period.course} · {period.academic_year} · {period.semester_display}"


class AssignmentForm(forms.ModelForm):
    offering = OfferingChoice(label=gettext_lazy("Course and teaching period"), queryset=CourseOffering.objects.select_related("course").order_by("course__course_id", "-academic_year", "semester"))
    unit = forms.ModelChoiceField(label=gettext_lazy("Unit"), queryset=CourseUnit.objects.none(), help_text=gettext_lazy("Choose a unit from the selected course. Create its units on the course page first."))
    scheme_json = forms.CharField(widget=forms.HiddenInput, max_length=400000)
    scheme_revision = forms.IntegerField(widget=forms.HiddenInput, required=False)
    evaluation_json = forms.CharField(widget=forms.HiddenInput, max_length=20000, required=False)
    evaluation_revision = forms.IntegerField(widget=forms.HiddenInput, required=False)
    objectives_json = forms.CharField(widget=forms.HiddenInput, max_length=320000, required=False)

    class Meta:
        model = Assignment
        fields = ["assignment_number", "name", "offering", "unit", "information", "calculation_mode"]
        widgets = {"information": forms.Textarea(attrs={"rows": 3})}
        labels = {"calculation_mode": gettext_lazy("Combine category scores"), "information": gettext_lazy("Information")}
        help_texts = {"assignment_number": gettext_lazy("A number from 1 to 99, unique for this course across the academic year. The module ID is generated automatically.")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk and self.instance.scheme_locked:
            offering_id = self.instance.offering_id
        else:
            offering_id = self.data.get("offering") if self.is_bound else self.initial.get("offering", self.instance.offering_id)
        try:
            period = CourseOffering.objects.get(pk=offering_id)
        except (CourseOffering.DoesNotExist, ValueError, TypeError, OverflowError):
            period = None
        if period:
            self.fields["unit"].queryset = CourseUnit.objects.filter(course=period.course)
        self.initial.setdefault("evaluation_json", json.dumps(self.instance.evaluation_rubric if self.instance.pk else default_evaluation_rubric(), ensure_ascii=False))
        if self.instance.pk:
            self.initial["objectives_json"] = json.dumps({str(category.pk): category.learning_objective for category in self.instance.categories.all()}, ensure_ascii=False)
            self.initial["evaluation_revision"] = self.instance.scheme_revision
        if not self.instance.pk and not self.is_bound:
            self.initial.setdefault("scheme_json", json.dumps(default_scheme(), ensure_ascii=False))
        self.fields["assignment_number"].required = not self.instance.pk or self.instance.assignment_number is not None
        if self.instance.pk and self.instance.assignment_number is None:
            self.fields["assignment_number"].help_text = gettext_lazy("Legacy module: leave blank to retain its current ID, or enter a number to convert it.")
        if self.instance.pk:
            self.initial["scheme_json"] = json.dumps(export_scheme(self.instance), ensure_ascii=False)
            self.initial["scheme_revision"] = self.instance.scheme_revision
            if self.instance.scheme_locked:
                for field in ["offering", "calculation_mode"]:
                    self.fields[field].disabled = True

    def clean(self):
        data = super().clean()
        # Older submissions without this field retain their saved/default rubric.
        self.evaluation_submitted = "evaluation_json" in self.data
        raw = data.get("evaluation_json") if self.evaluation_submitted else self.instance.evaluation_rubric
        try:
            self.evaluation = validate_evaluation_rubric(raw)
        except ValidationError as error:
            self.add_error("evaluation_json", error)
        if self.instance.pk and self.evaluation_submitted and data.get("evaluation_revision") != self.instance.scheme_revision:
            self.add_error(None, gettext_lazy("The evaluation rubric changed in another window. Reload the page before editing it."))
        number, offering = data.get("assignment_number"), data.get("offering")
        if number is not None and offering is not None:
            try:
                key = assignment_identifier(offering.academic_year, offering.course.course_id, number)
            except ValidationError as error:
                self.add_error("assignment_number", error)
            else:
                if Assignment.objects.filter(assignment_id=key).exclude(pk=self.instance.pk).exists():
                    self.add_error("assignment_number", gettext_lazy("This module number is already used for this course and academic year, possibly in another semester."))
                self.instance.assignment_id = key
        if self.instance.pk and data.get("scheme_revision") != self.instance.scheme_revision:
            self.add_error(None, gettext_lazy("This module changed in another window. Reload the page before editing it."))
        if "scheme_json" in data and "calculation_mode" in data:
            try:
                self.scheme = validate_locked_scheme(data["scheme_json"], self.instance) if self.instance.pk and self.instance.scheme_locked else validate_scheme(data["scheme_json"], data["calculation_mode"])
            except ValidationError as error:
                self.add_error("scheme_json", error)
        return data
