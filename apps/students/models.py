from django.utils.translation import gettext_lazy
from django.db import models
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from config.identifiers import student_identifier


class Student(models.Model):
    class Status(models.TextChoices):
        STUDYING = "studying", gettext_lazy("Studying")
        RESIGNED = "resigned", gettext_lazy("Resigned")

    # Preserve the existing unique identifier and all foreign-key relationships.
    # This field is internal; school-issued IDs may repeat across academic years.
    student_number = models.CharField(gettext_lazy("Generated student ID"), max_length=80, unique=True, editable=False)
    student_id = models.CharField(gettext_lazy("Student ID"), max_length=80, blank=True, default="")
    status = models.CharField(gettext_lazy("Student status"), max_length=10, choices=Status.choices, default=Status.STUDYING)
    resignation_date = models.DateField(gettext_lazy("Resignation date"), blank=True, null=True)
    roll_number = models.PositiveSmallIntegerField(gettext_lazy("Roll number"), null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(99)])
    identifier_class = models.ForeignKey("StudentClass", on_delete=models.PROTECT, null=True, blank=True, related_name="identified_students")
    full_name = models.CharField(gettext_lazy("Student name"), max_length=200)
    email = models.EmailField(blank=True)
    notes = models.TextField(blank=True, max_length=2000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["student_number"]
        constraints = [
            models.CheckConstraint(condition=(models.Q(status="studying", resignation_date__isnull=True) | models.Q(status="resigned", resignation_date__isnull=False)), name="valid_student_resignation"),
            models.UniqueConstraint(fields=["identifier_class", "roll_number"], name="unique_class_roll_number"),
            models.CheckConstraint(condition=(models.Q(identifier_class__isnull=True, roll_number__isnull=True) | models.Q(identifier_class__isnull=False, roll_number__isnull=False, roll_number__gte=1, roll_number__lte=99)), name="valid_student_identifier_parts"),
        ]

    def clean(self):
        if self.status == self.Status.RESIGNED and not self.resignation_date:
            raise ValidationError({"resignation_date": gettext_lazy("Enter the resignation date for a resigned student.")})
        if self.status == self.Status.STUDYING and self.resignation_date:
            raise ValidationError({"resignation_date": gettext_lazy("Clear the resignation date when the student is studying.")})
        if self.identifier_class_id and self.roll_number is not None:
            self.student_number = student_identifier(self.identifier_class.academic_year, self.identifier_class.class_number, self.roll_number)
        elif self.identifier_class_id or self.roll_number is not None:
            raise ValidationError(gettext_lazy("Choose both a classroom and roll number to generate the student ID."))

    def save(self, *args, **kwargs):
        if self.identifier_class_id and self.roll_number is not None:
            self.student_number = student_identifier(self.identifier_class.academic_year, self.identifier_class.class_number, self.roll_number)
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"student_number"}
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.student_id} — {self.full_name}" if self.student_id else self.full_name

    def studying_on(self, day):
        """The resignation date is the first day the student is excluded."""
        return self.status == self.Status.STUDYING or bool(self.resignation_date and day < self.resignation_date)


class StudentClass(models.Model):
    """A whole class/section in one academic year, separate from a course."""

    class_number = models.CharField(gettext_lazy("Class/section"), max_length=80)
    academic_year = models.CharField(max_length=30)
    notes = models.TextField(blank=True, max_length=2000)

    class Meta:
        ordering = ["-academic_year", "class_number"]
        constraints = [
            models.UniqueConstraint(fields=["class_number", "academic_year"], name="unique_student_class_year")
        ]

    def __str__(self):
        return f"{self.class_number} · {self.academic_year}"

    def clean(self):
        if self.pk and self.identified_students.exists():
            original = StudentClass.objects.get(pk=self.pk)
            if (self.class_number, self.academic_year) != (original.class_number, original.academic_year):
                raise ValidationError(gettext_lazy("This classroom has generated student IDs. Its class number and academic year are fixed; create a new classroom for another class or year."))
        if self.pk and self.course_offerings.exclude(academic_year=self.academic_year).exists():
            raise ValidationError({"academic_year": gettext_lazy("This classroom is enrolled in a course for its existing academic year. Create a new classroom for another year instead.")})


class ClassMembership(models.Model):
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name="memberships")
    student_class = models.ForeignKey(StudentClass, on_delete=models.PROTECT, related_name="memberships")

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["student", "student_class"], name="unique_student_class_membership")
        ]
