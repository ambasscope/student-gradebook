from django.utils.translation import gettext_lazy
from django import forms
from .models import Student, StudentClass
from config.identifiers import academic_year, classroom_parts, student_identifier


class ImportUploadForm(forms.Form):
    student_file = forms.FileField(
        label=gettext_lazy("Student list"),
        help_text=gettext_lazy("Excel (.xlsx or .xls), CSV, or TSV. Maximum 5 MB and 5,000 students."),
        widget=forms.FileInput(attrs={"accept": ".xlsx,.xls,.csv,.tsv"}),
    )
    class_number = forms.CharField(label=gettext_lazy("Class/section"), max_length=80, help_text=gettext_lazy("Applies to this whole list. Use grade/section, for example 4/1 or 4/12."))
    academic_year = forms.CharField(label=gettext_lazy("Academic year"), max_length=4, help_text=gettext_lazy("Four digits, for example 2569. This is used in the generated student ID."))
    class_notes = forms.CharField(label=gettext_lazy("Class notes"), required=False, max_length=2000, help_text=gettext_lazy("Nonblank notes replace the notes on an existing class. Leave blank to keep its notes."), widget=forms.Textarea(attrs={"rows": 2}))
    encoding = forms.ChoiceField(
        label=gettext_lazy("CSV/TSV text encoding"),
        choices=[("utf-8-sig", gettext_lazy("UTF-8 (recommended)")), ("utf-16", gettext_lazy("UTF-16")), ("cp874", gettext_lazy("Thai Windows")), ("cp1252", gettext_lazy("Western Windows"))],
        help_text=gettext_lazy("Used only for CSV and TSV files."),
    )
    sheet_name = forms.CharField(label=gettext_lazy("Excel sheet name"), required=False, max_length=100, help_text=gettext_lazy("Leave blank to use the first worksheet."))
    update_existing = forms.BooleanField(
        label=gettext_lazy("Update existing students using the values in this file"),
        required=False,
        help_text=gettext_lazy("Updates names and nonblank email/notes. Blank optional cells never erase existing details."),
    )

    def clean_student_file(self):
        file = self.cleaned_data["student_file"]
        if file.size > 5 * 1024 * 1024:
            raise forms.ValidationError(gettext_lazy("Choose a file smaller than 5 MB."))
        if file.name.rsplit(".", 1)[-1].lower() not in {"xlsx", "xls", "csv", "tsv"}:
            raise forms.ValidationError(gettext_lazy("Choose an .xlsx, .xls, .csv, or .tsv file."))
        return file

    def clean_class_number(self):
        return classroom_parts(self.cleaned_data["class_number"])[0]

    def clean_academic_year(self):
        return academic_year(self.cleaned_data["academic_year"])


class ColumnMappingForm(forms.Form):
    token = forms.CharField(widget=forms.HiddenInput)
    roll_number = forms.ChoiceField(label=gettext_lazy("Roll number column (1–99)"))
    student_id = forms.ChoiceField(label=gettext_lazy("Student ID column (optional)"), required=False)
    full_name = forms.ChoiceField(label=gettext_lazy("Full name column"), required=False)
    first_name = forms.ChoiceField(label=gettext_lazy("First name column"), required=False)
    last_name = forms.ChoiceField(label=gettext_lazy("Last name column"), required=False)
    email = forms.ChoiceField(label=gettext_lazy("Email column"), required=False)
    notes = forms.ChoiceField(label=gettext_lazy("Student notes column"), required=False)

    def __init__(self, headers, *args, **kwargs):
        super().__init__(*args, **kwargs)
        columns = [(str(i), f"{i + 1}. {name}") for i, name in enumerate(headers)]
        self.fields["roll_number"].choices = [("", gettext_lazy("Choose a column"))] + columns
        for name in ["student_id", "full_name", "first_name", "last_name", "email", "notes"]:
            self.fields[name].choices = [("", gettext_lazy("Not used"))] + columns

    def clean(self):
        data = super().clean()
        if not data.get("full_name") and not (data.get("first_name") and data.get("last_name")):
            raise forms.ValidationError(gettext_lazy("Choose a full name column, or both first and last name columns."))
        if data.get("full_name") and (data.get("first_name") or data.get("last_name")):
            raise forms.ValidationError(gettext_lazy("Use either full name or first/last name columns."))
        selected = [data.get(key) for key in ("roll_number", "student_id", "full_name", "first_name", "last_name", "email", "notes") if data.get(key)]
        if len(selected) != len(set(selected)):
            raise forms.ValidationError(gettext_lazy("Use each file column for only one student field."))
        return data


class StudentForm(forms.ModelForm):
    student_class = forms.ModelChoiceField(label=gettext_lazy("Class/section and academic year"), queryset=StudentClass.objects.all())

    class Meta:
        model = Student
        fields = ["student_class", "roll_number", "student_id", "full_name", "status", "resignation_date", "email", "notes"]
        labels = {"email": gettext_lazy("Email"), "notes": gettext_lazy("Notes")}
        widgets = {"notes": forms.Textarea(attrs={"rows": 3}), "resignation_date": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["roll_number"].required = not self.instance.pk
        self.fields["roll_number"].help_text = gettext_lazy("Number within this classroom, from 1 to 99.")
        self.fields["student_id"].help_text = gettext_lazy("Optional school-issued ID. Leading zeros are preserved.")
        self.fields["resignation_date"].help_text = gettext_lazy("Required for resigned students. Earlier module scores are preserved. Clear this date when changing back to Studying.")
        # Older clients may omit status; preserve it instead of resetting it.
        if self.is_bound and "status" not in self.data:
            self.data = self.data.copy()
            self.data["status"] = self.instance.status
            self.data["resignation_date"] = self.instance.resignation_date.isoformat() if self.instance.resignation_date else ""
        if self.is_bound and self.instance.pk and "student_id" not in self.data:
            self.data = self.data.copy()
            self.data["student_id"] = self.instance.student_id
        if self.instance.identifier_class_id:
            self.initial["student_class"] = self.instance.identifier_class_id
            for name in ["student_class", "roll_number"]:
                self.fields[name].disabled = True
            self.fields["student_class"].help_text = gettext_lazy("The classroom and roll number are fixed after creation. Edit the name or other details below.")
        elif self.instance.pk:
            self.fields["student_class"].required = False
            self.fields["roll_number"].help_text = gettext_lazy("Legacy record: leave blank to preserve its current ID. Choose a classroom and number to convert it.")

    def clean(self):
        data = super().clean()
        group, roll = data.get("student_class"), data.get("roll_number")
        if roll is not None and group is None:
            self.add_error("student_class", gettext_lazy("Choose the classroom for this roll number."))
        if group is not None and roll is not None:
            try:
                number = student_identifier(group.academic_year, group.class_number, roll)
            except forms.ValidationError as error:
                self.add_error("student_class", error)
            else:
                if Student.objects.filter(student_number=number).exclude(pk=self.instance.pk).exists():
                    self.add_error("roll_number", gettext_lazy("This roll number already exists in the selected classroom and academic year."))
                elif self.instance.pk and self.instance.memberships.exclude(student_class=group).exists():
                    self.add_error("student_class", gettext_lazy("This legacy student belongs to other classrooms. Keep its current ID until its classroom identity is resolved."))
                else:
                    self.instance.identifier_class = group
                    self.instance.roll_number = roll
                    self.instance.student_number = number
        return data


class StudentClassForm(forms.ModelForm):
    class Meta:
        model = StudentClass
        fields = ["class_number", "academic_year", "notes"]
        labels = {"academic_year": gettext_lazy("Academic year"), "notes": gettext_lazy("Notes")}
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def clean_class_number(self):
        value = self.cleaned_data["class_number"]
        if self.instance.pk and value == self.instance.class_number:
            return value
        return classroom_parts(value)[0]

    def clean_academic_year(self):
        year = self.cleaned_data["academic_year"]
        if self.instance.pk and self.instance.course_offerings.exclude(academic_year=year).exists():
            raise forms.ValidationError(gettext_lazy("This classroom is enrolled in a course for its existing academic year. Create a new classroom for another year instead."))
        if self.instance.pk and year == self.instance.academic_year:
            return year
        return academic_year(year)

    def clean(self):
        data = super().clean()
        if "class_number" in data and "academic_year" in data:
            try:
                code = classroom_parts(data["class_number"])[1]
            except forms.ValidationError:
                return data
            for group in StudentClass.objects.filter(academic_year=data["academic_year"]).exclude(pk=self.instance.pk):
                try:
                    matches = classroom_parts(group.class_number)[1] == code
                except forms.ValidationError:
                    continue
                if matches:
                    self.add_error("class_number", gettext_lazy("This classroom already exists in that academic year, including an equivalent slash or zero-padded spelling."))
                    break
        return data
