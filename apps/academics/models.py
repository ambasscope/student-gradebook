from django.utils.translation import gettext_lazy
from django.core.exceptions import ValidationError
from django.db import models
from config.semesters import semester_number, semester_label, legacy_semester_number, validate_semester


class Course(models.Model):
    course_id = models.CharField(gettext_lazy("Course ID"), max_length=80, unique=True)
    name = models.CharField(gettext_lazy("Course name"), max_length=200)
    information = models.TextField(blank=True, max_length=5000)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["course_id"]

    def __str__(self):
        return f"{self.course_id} — {self.name}"

    def clean(self):
        if self.pk and self.offerings.filter(assignments__assignment_number__isnull=False).exists():
            if Course.objects.get(pk=self.pk).course_id != self.course_id:
                raise ValidationError({"course_id": gettext_lazy("This course has generated module IDs. Keep its course ID, or create a new course.")})


class CourseUnit(models.Model):
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="units")
    unit_id = models.CharField(gettext_lazy("Unit ID"), max_length=40)
    name = models.CharField(gettext_lazy("Unit name"), max_length=200)

    class Meta:
        ordering = ["unit_id", "pk"]
        constraints = [models.UniqueConstraint(fields=["course", "unit_id"], name="unique_course_unit_id")]

    def __str__(self):
        return f"{self.unit_id} — {self.name}"


class CourseOffering(models.Model):
    course = models.ForeignKey(Course, on_delete=models.PROTECT, related_name="offerings")
    academic_year = models.CharField(max_length=30)
    semester = models.CharField(max_length=50, default="1", validators=[validate_semester])
    classrooms = models.ManyToManyField("students.StudentClass", through="ClassroomEnrollment", related_name="course_offerings", blank=True)

    class Meta:
        ordering = ["-academic_year", "semester"]
        constraints = [models.UniqueConstraint(fields=["course", "academic_year", "semester"], name="unique_course_teaching_period")]

    def __str__(self):
        return f"{self.course.course_id} · {self.academic_year} · {self.semester_display}"

    @property
    def semester_display(self):
        return semester_label(self.semester)

    def clean(self):
        self.semester = semester_number(self.semester)
        if self.pk and self.assignments.filter(assignment_number__isnull=False).exists():
            original = CourseOffering.objects.get(pk=self.pk)
            if (self.course_id, self.academic_year) != (original.course_id, original.academic_year):
                raise ValidationError(gettext_lazy("This teaching period has generated module IDs. Its course and academic year are fixed."))
        if self.pk and self.assignments.filter(scheme_locked=True).exists():
            original = CourseOffering.objects.get(pk=self.pk)
            original_semester = legacy_semester_number(original.semester) or original.semester
            if (self.course_id, self.academic_year, self.semester) != (original.course_id, original.academic_year, original_semester):
                raise ValidationError(gettext_lazy("This teaching period has marked modules. Its course, academic year, and semester cannot change."))


class ClassroomEnrollment(models.Model):
    offering = models.ForeignKey(CourseOffering, on_delete=models.CASCADE)
    classroom = models.ForeignKey("students.StudentClass", on_delete=models.PROTECT)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["offering", "classroom"], name="unique_course_classroom")]

    def clean(self):
        if self.offering_id and self.classroom_id and self.offering.academic_year != self.classroom.academic_year:
            raise ValidationError(gettext_lazy("The classroom and course teaching period must use the same academic year."))


class Enrollment(models.Model):
    offering = models.ForeignKey(CourseOffering, on_delete=models.PROTECT, related_name="enrollments")
    student = models.ForeignKey("students.Student", on_delete=models.PROTECT, related_name="course_enrollments")
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["offering", "student"], name="unique_course_student")]
