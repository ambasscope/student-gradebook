from django.urls import path
from . import views

app_name = "reports"
urlpatterns = [
    path("", views.index, name="index"),
    path("module-record/", views.module_record, name="module-record"),
    path("student-scores/", views.student_scores, name="student-scores"),
]
