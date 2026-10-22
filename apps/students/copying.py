from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _
from config.identifiers import student_identifier
from .forms import StudentClassForm
from .models import Student, ClassMembership


class ClassroomCopyForm(StudentClassForm):
    include_students = forms.BooleanField(label=_("Copy student names and roll numbers"), required=False,
        help_text=_("Leave unchecked for an empty classroom. Copied students receive new IDs for the destination classroom and year; no scores or course enrolments are copied."))


@transaction.atomic
def copy_classroom(form, source):
    classroom = form.save()
    if form.cleaned_data['include_students']:
        students = list(Student.objects.filter(memberships__student_class=source).order_by('roll_number','pk'))
        rolls=[student.roll_number for student in students]
        if any(roll is None or not 1 <= roll <= 99 for roll in rolls) or len(rolls) != len(set(rolls)):
            raise ValidationError(_("The source classroom has missing or duplicate roll numbers. Fix the student list or copy an empty classroom."))
        for source_student in students:
            key=student_identifier(classroom.academic_year,classroom.class_number,source_student.roll_number)
            if Student.objects.filter(student_number=key).exists():
                raise ValidationError(_("A generated student ID already exists for this destination. Choose another classroom or year."))
            student=Student.objects.create(identifier_class=classroom,roll_number=source_student.roll_number,
                student_id=source_student.student_id,status=source_student.status,resignation_date=source_student.resignation_date,
                full_name=source_student.full_name,email=source_student.email,notes=source_student.notes)
            ClassMembership.objects.create(student=student,student_class=classroom)
    return classroom
