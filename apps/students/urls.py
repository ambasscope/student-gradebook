from django.urls import path
from config import deletion_views
from . import views

app_name = "students"
urlpatterns = [
    path("classes/<int:pk>/delete/", deletion_views.classroom, name="classroom-delete"),
    path("students/<int:pk>/delete/", deletion_views.student, name="student-delete"),
    path("", views.index, name="index"),
    path("classes/<int:pk>/copy/", views.classroom_copy, name="classroom-copy"),
    path("students/<int:pk>/copy/", views.student_copy, name="student-copy"),
    path("all/", views.all_students, name="all"),
    path("<int:pk>/", views.classroom_detail, name="classroom-detail"),
    path("add/", views.student_edit, name="add"),
    path("students/<int:pk>/edit/", views.student_edit, name="edit"),
    path("<int:pk>/edit/", views.student_edit, name="legacy-edit"),
    path("classes/", views.classes, name="classes"),
    path("classes/<int:pk>/edit/", views.classes, name="class-edit"),
    path("import/", views.import_upload, name="import-upload"),
    path("import/map/", views.import_map, name="import-map"),
    path("import/preview/", views.import_preview, name="import-preview"),
    path("import/confirm/", views.import_confirm, name="import-confirm"),
    path("import/template/", views.import_template, name="import-template"),
]
