from django.urls import path
from config import deletion_views
from . import views
from . import rubric_presets_views, marking_library_views

app_name = "assessments"
urlpatterns = [
    path("<int:pk>/delete/", deletion_views.module, name="delete"),
    path("", views.index, name="index"),
    path("add/", views.create, name="add"),
    path("marking-library/", marking_library_views.index, name="marking-library"),
    path("marking-library/add/", marking_library_views.editor, name="marking-library-add"),
    path("marking-library/<int:pk>/copy/", marking_library_views.copy_category, name="marking-library-copy"),
    path("marking-library/<int:pk>/edit/", marking_library_views.editor, name="marking-library-edit"),
    path("marking-library/<int:pk>/delete/", marking_library_views.delete, name="marking-library-delete"),
    path("rubric-presets/", rubric_presets_views.index, name="rubric-presets"),
    path("rubric-presets/add/", rubric_presets_views.editor, name="rubric-preset-add"),
    path("rubric-presets/save-copy/", rubric_presets_views.save_copy, name="rubric-preset-save-copy"),
    path("rubric-presets/<int:pk>/edit/", rubric_presets_views.editor, name="rubric-preset-edit"),
    path("rubric-presets/<int:pk>/delete/", rubric_presets_views.delete, name="rubric-preset-delete"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/copy/", views.copy_module, name="copy"),
    path("<int:pk>/edit/", views.edit, name="edit"),
    path("<int:pk>/classrooms/<int:classroom_pk>/scores/", views.classroom_scores, name="scores"),
    path("<int:pk>/classrooms/<int:classroom_pk>/scores/save/", views.save_scores_view, name="save-scores"),
]
