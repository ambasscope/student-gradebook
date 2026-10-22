from django.utils.translation import gettext_lazy
from django import forms
from django.db.models import Count
from apps.students.models import StudentClass
from .models import Course, CourseOffering, CourseUnit
from config.identifiers import academic_year
from config.semesters import semester_number, legacy_semester_number


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ["course_id", "name", "information"]
        labels = {"information": gettext_lazy("Information")}
        widgets = {"information": forms.Textarea(attrs={"rows": 4})}
        help_texts = {"course_id": gettext_lazy("A unique identifier, for example MATH101 or 00123.")}


class ClassroomChoiceField(forms.ModelMultipleChoiceField):
    def label_from_instance(self, classroom):
        return gettext_lazy("%(classroom)s · %(year)s (%(count)s students)") % {"classroom": classroom.class_number, "year": classroom.academic_year, "count": classroom.student_count}


class CourseUnitForm(forms.ModelForm):
    class Meta:
        model = CourseUnit
        fields = ["unit_id", "name"]
        help_texts = {"unit_id": gettext_lazy("Unique within this course, for example 1 or 2. The report prints this ID only.")}

    def __init__(self, *args, course, **kwargs):
        super().__init__(*args, **kwargs)
        self.instance.course = course

    def clean_unit_id(self):
        value = self.cleaned_data["unit_id"]
        if CourseUnit.objects.filter(course=self.instance.course, unit_id=value).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError(gettext_lazy("This unit ID is already used in this course."))
        return value


class OfferingForm(forms.ModelForm):
    classrooms = ClassroomChoiceField(queryset=StudentClass.objects.none(), required=False, widget=forms.CheckboxSelectMultiple, help_text=gettext_lazy("Choose any number of classrooms from this academic year. Their students will be enrolled together."))

    class Meta:
        model = CourseOffering
        fields = ["academic_year", "semester", "classrooms"]
        labels = {"academic_year": gettext_lazy("Academic year"), "semester": gettext_lazy("Semester"), "classrooms": gettext_lazy("Classrooms")}
        help_texts = {"academic_year": gettext_lazy("Must match the selected classrooms' academic year."), "semester": gettext_lazy("Enter only a positive whole number, usually 1 or 2.")}
        widgets = {"semester": forms.NumberInput(attrs={"min": "1", "step": "1", "inputmode": "numeric"})}

    def __init__(self, *args, course=None, **kwargs):
        super().__init__(*args, **kwargs)
        if course is not None:
            self.instance.course = course
        if self.instance.pk:
            self.initial["semester"] = legacy_semester_number(self.instance.semester) or self.instance.semester
        self.fields["classrooms"].queryset = StudentClass.objects.annotate(student_count=Count("memberships")).order_by("-academic_year", "class_number")
        if not self.instance.pk:
            years = list(StudentClass.objects.values_list("academic_year", flat=True).distinct())
            if len(years) == 1:
                self.initial.setdefault("academic_year", years[0])

    def clean(self):
        data = super().clean()
        year = data.get("academic_year")
        selected = data.get("classrooms")
        if selected is not None and any(classroom.academic_year != year for classroom in selected):
            self.add_error("classrooms", gettext_lazy("Choose classrooms from the same academic year as this teaching period."))
        course = getattr(self.instance, "course", None)
        if course and course.pk and year and data.get("semester"):
            existing = CourseOffering.objects.filter(course=course, academic_year=year)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            if any(legacy_semester_number(value) == data["semester"] for value in existing.values_list("semester", flat=True)):
                self.add_error(None, gettext_lazy("This course already has a teaching period for that academic year and semester."))
        return data

    def clean_semester(self):
        return semester_number(self.cleaned_data["semester"])

    def clean_academic_year(self):
        year = self.cleaned_data["academic_year"]
        if self.instance.pk and year == self.instance.academic_year:
            return year
        return academic_year(year)
