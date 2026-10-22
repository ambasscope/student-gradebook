from django.contrib import admin
from django.db import transaction
from .models import ClassroomEnrollment, Course, CourseOffering, Enrollment
from .services.enrollment import sync_roster


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ["course_id", "name"]
    search_fields = ["course_id", "name"]


class ClassroomEnrollmentInline(admin.TabularInline):
    model = ClassroomEnrollment
    extra = 0


@admin.register(CourseOffering)
class CourseOfferingAdmin(admin.ModelAdmin):
    list_display = ["course", "academic_year", "semester"]
    list_filter = ["academic_year", "semester"]
    search_fields = ["course__course_id", "course__name"]
    inlines = [ClassroomEnrollmentInline]

    @transaction.atomic
    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        sync_roster(form.instance)


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ["offering", "student", "is_active"]
    list_filter = ["is_active", "offering__academic_year"]
    search_fields = ["student__student_id", "student__full_name", "offering__course__course_id"]
    readonly_fields = ["offering", "student", "is_active"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
