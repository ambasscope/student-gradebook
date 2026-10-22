from django.contrib import admin
from .models import Assignment, Criterion, MarkingCategory, Score


class ReadOnlyAssessmentAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Assignment)
class AssignmentAdmin(ReadOnlyAssessmentAdmin):
    list_display = ["assignment_id", "name", "offering", "scheme_locked"]
    search_fields = ["assignment_id", "name"]


admin.site.register(MarkingCategory, ReadOnlyAssessmentAdmin)
admin.site.register(Criterion, ReadOnlyAssessmentAdmin)


@admin.register(Score)
class ScoreAdmin(ReadOnlyAssessmentAdmin):
    list_display = ["enrollment", "criterion", "value", "updated_at"]
