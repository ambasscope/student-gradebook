from django.urls import include, path
from config.views import home
from django.views.i18n import JavaScriptCatalog

urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    path("jsi18n/", JavaScriptCatalog.as_view(), name="javascript-catalog"),
    path("", home, name="home"),
    path("teacher/", include("apps.teachers.urls")),
    path("classrooms/", include("apps.students.urls")),
    path("students/", include("apps.students.urls", namespace="legacy_students")),
    path("courses/", include("apps.academics.urls")),
    path("modules/", include("apps.assessments.urls")),
    path("assignments/", include("apps.assessments.urls", namespace="legacy_assessments")),
    path("reports/", include("apps.reports.urls")),
]
