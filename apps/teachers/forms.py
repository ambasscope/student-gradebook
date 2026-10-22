from django import forms
from django.utils.translation import gettext_lazy
from .models import TeacherProfile


class TeacherForm(forms.ModelForm):
    revision = forms.IntegerField(widget=forms.HiddenInput, min_value=0)

    class Meta:
        model = TeacherProfile
        fields = ["name", "academic_status"]
        labels = {"name": gettext_lazy("Name"), "academic_status": gettext_lazy("Academic status")}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.initial["revision"] = self.instance.revision
