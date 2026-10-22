from django.utils.translation import gettext_lazy
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.db.models.functions import Lower
from config.identifiers import assignment_identifier
from .services.evaluation import default_evaluation_rubric


class RubricPreset(models.Model):
    name = models.CharField(max_length=120)
    levels = models.JSONField(default=default_evaluation_rubric)
    revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name", "pk"]
        constraints = [models.UniqueConstraint(Lower("name"), name="unique_rubric_preset_name")]

    def __str__(self):
        return self.name


class MarkingSchemeCategory(models.Model):
    name_th = models.CharField(max_length=150, blank=True)
    name_en = models.CharField(max_length=150, blank=True)
    subcategories = models.JSONField(default=list)
    revision = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["pk"]

    def __str__(self):
        return self.name_th or self.name_en


class Assignment(models.Model):
    class Calculation(models.TextChoices):
        POINTS = "points", gettext_lazy("Add category scores")
        WEIGHTED = "weighted", gettext_lazy("Weight categories by percentage")

    assignment_id = models.CharField(gettext_lazy("Module ID"), max_length=86, unique=True)
    assignment_number = models.PositiveSmallIntegerField(gettext_lazy("Module number"), null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(99)])
    name = models.CharField(gettext_lazy("Module name"), max_length=200)
    offering = models.ForeignKey("academics.CourseOffering", on_delete=models.PROTECT, related_name="assignments")
    unit = models.ForeignKey("academics.CourseUnit", on_delete=models.PROTECT, related_name="modules", null=True, blank=True)
    information = models.TextField(blank=True, max_length=5000)
    calculation_mode = models.CharField(max_length=10, choices=Calculation.choices, default=Calculation.POINTS)
    evaluation_rubric = models.JSONField(default=default_evaluation_rubric)
    scheme_locked = models.BooleanField(default=False)
    scheme_revision = models.PositiveIntegerField(default=1)
    score_revision = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["assignment_id"]

    def __str__(self):
        return f"{self.assignment_id} — {self.name}"

    def clean(self):
        if self.unit_id and self.offering_id and self.unit.course_id != self.offering.course_id:
            raise ValidationError({"unit": gettext_lazy("Choose a unit belonging to this module's course.")})
        if self.assignment_number is not None and self.offering_id:
            self.assignment_id = assignment_identifier(self.offering.academic_year, self.offering.course.course_id, self.assignment_number)
        if self.pk:
            original = Assignment.objects.filter(pk=self.pk).first()
            if original and original.scheme_locked:
                if self.offering_id != original.offering_id:
                    raise ValidationError({"offering": gettext_lazy("The course cannot change after marking has started.")})
                if self.calculation_mode != original.calculation_mode:
                    raise ValidationError({"calculation_mode": gettext_lazy("The calculation method cannot change after marking has started.")})

    def save(self, *args, **kwargs):
        if self.assignment_number is not None and self.offering_id:
            self.assignment_id = assignment_identifier(self.offering.academic_year, self.offering.course.course_id, self.assignment_number)
            if kwargs.get("update_fields") is not None:
                kwargs["update_fields"] = set(kwargs["update_fields"]) | {"assignment_id"}
        super().save(*args, **kwargs)


class MarkingCategory(models.Model):
    class Aggregation(models.TextChoices):
        SUM = "sum", gettext_lazy("Sum")
        AVERAGE = "average", gettext_lazy("Average")
        WEIGHTED_AVERAGE = "weighted_average", gettext_lazy("Weighted average")

    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name="categories")
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=150)
    learning_objective = models.TextField(blank=True, max_length=5000)
    aggregation = models.CharField(max_length=20, choices=Aggregation.choices, default=Aggregation.SUM)
    evaluation_rubric = models.JSONField(default=default_evaluation_rubric)
    weight = models.DecimalField(max_digits=5, decimal_places=2, default=0, validators=[MinValueValidator(0), MaxValueValidator(100)])
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "pk"]
        constraints = [models.UniqueConstraint(fields=["assignment", "code"], name="unique_assignment_category")]

    def __str__(self):
        return f"{self.assignment.assignment_id}: {self.name}"


class Criterion(models.Model):
    category = models.ForeignKey(MarkingCategory, on_delete=models.CASCADE, related_name="criteria")
    code = models.CharField(max_length=20)
    name = models.CharField(max_length=150)
    maximum = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    weight = models.DecimalField(max_digits=6, decimal_places=2, default=1, validators=[MinValueValidator(Decimal("0.01")), MaxValueValidator(Decimal("9999.99"))])
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "pk"]
        constraints = [models.UniqueConstraint(fields=["category", "code"], name="unique_category_criterion")]

    def __str__(self):
        return f"{self.category.name} — {self.name}"


class Score(models.Model):
    enrollment = models.ForeignKey("academics.Enrollment", on_delete=models.PROTECT, related_name="scores")
    criterion = models.ForeignKey(Criterion, on_delete=models.PROTECT, related_name="scores")
    value = models.DecimalField(max_digits=8, decimal_places=2, validators=[MinValueValidator(0)])
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["enrollment", "criterion"], name="unique_enrollment_criterion_score"),
            models.CheckConstraint(condition=models.Q(value__gte=0), name="nonnegative_student_score"),
        ]

    def clean(self):
        if self.criterion_id and self.enrollment_id:
            if self.enrollment.offering_id != self.criterion.category.assignment.offering_id:
                raise ValidationError(gettext_lazy("The student and module must belong to the same course teaching period."))
            if self.value is not None and self.value > self.criterion.maximum:
                raise ValidationError({"value": gettext_lazy("The score exceeds this subcategory's maximum mark.")})


class Attendance(models.Model):
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name="attendance_records")
    classroom = models.ForeignKey("students.StudentClass", on_delete=models.PROTECT, related_name="assignment_attendance")
    enrollment = models.ForeignKey("academics.Enrollment", on_delete=models.PROTECT, related_name="assignment_attendance")
    present = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["assignment", "classroom", "enrollment"], name="unique_assignment_attendance")]


class ClassroomAssignmentRecord(models.Model):
    learning_date = models.DateField(null=True, blank=True)
    class Completion(models.TextChoices):
        COMPLETED = "completed", gettext_lazy("Module completed")
        UNCOMPLETED = "uncompleted", gettext_lazy("Module uncompleted")

    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name="classroom_records")
    classroom = models.ForeignKey("students.StudentClass", on_delete=models.PROTECT, related_name="assignment_records")
    problem = models.TextField(blank=True, max_length=5000)
    suggestion = models.TextField(blank=True, max_length=5000)
    problem_choices = models.JSONField(default=list, blank=True)
    suggestion_choices = models.JSONField(default=list, blank=True)
    suggestion_details = models.JSONField(default=dict, blank=True)
    module_status = models.CharField(max_length=12, choices=Completion.choices, blank=True, default="")
    revision = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["assignment", "classroom"], name="unique_assignment_class_record")]
