from django.urls import path
from config import deletion_views
from . import views, copy_views

app_name = "academics"
urlpatterns = [
    path("<int:pk>/delete/", deletion_views.course, name="delete"),
    path("<int:course_pk>/units/<int:pk>/delete/", deletion_views.unit, name="unit-delete"),
    path("", views.index, name="index"),
    path("add/", views.create, name="add"),
    path("<int:pk>/", views.detail, name="detail"),
    path("<int:pk>/copy/", copy_views.course, name="copy"),
    path("<int:pk>/edit/", views.edit, name="edit"),
    path("<int:course_pk>/units/<int:pk>/copy/", copy_views.unit, name="unit-copy"),
    path("<int:course_pk>/periods/<int:pk>/copy/", copy_views.period, name="offering-copy"),
    path("<int:course_pk>/units/add/", views.unit_edit, name="unit-add"),
    path("<int:course_pk>/units/<int:pk>/", views.unit_detail, name="unit-detail"),
    path("<int:course_pk>/units/<int:pk>/edit/", views.unit_edit, name="unit-edit"),
    path("<int:course_pk>/periods/add/", views.offering_edit, name="offering-add"),
    path("<int:course_pk>/periods/<int:pk>/edit/", views.offering_edit, name="offering-edit"),
    path("<int:course_pk>/periods/<int:pk>/students/", views.roster, name="roster"),
    path("<int:course_pk>/periods/<int:pk>/refresh/", views.roster_refresh, name="roster-refresh"),
]
