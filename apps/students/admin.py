from django.contrib import admin
from .models import ClassMembership, Student, StudentClass


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ["student_id", "full_name", "status", "resignation_date", "email"]
    search_fields = ["student_id", "full_name", "status", "resignation_date", "email"]


@admin.register(StudentClass)
class StudentClassAdmin(admin.ModelAdmin):
    list_display = ["class_number", "academic_year"]
    list_filter = ["academic_year"]
    search_fields = ["class_number", "academic_year"]


@admin.register(ClassMembership)
class ClassMembershipAdmin(admin.ModelAdmin):
    list_display = ["student", "student_class"]
    autocomplete_fields = ["student", "student_class"]
