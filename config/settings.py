"""Settings for a local, portable application bound to this computer."""
import os
import sys
from pathlib import Path
from config.storage import DATA_DIR, load_secret_key

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or load_secret_key()
DEBUG = os.environ.get("DJANGO_DEBUG") == "1"
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "[::1]"]
INSTALLED_APPS = [
    "django.contrib.auth",  # Preserve legacy score authors and existing migrations.
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "apps.teachers.apps.TeachersConfig",
    "apps.students.apps.StudentsConfig",
    "apps.academics.apps.AcademicsConfig",
    "apps.assessments.apps.AssessmentsConfig",
    "apps.reports.apps.ReportsConfig",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
TEMPLATES = [{
    "BACKEND": "django.template.backends.django.DjangoTemplates",
    "DIRS": [BASE_DIR / "templates"],
    "APP_DIRS": True,
    "OPTIONS": {"context_processors": [
        "django.template.context_processors.request",
        "django.contrib.messages.context_processors.messages",
    ]},
}]
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"
DATABASES = {"default": {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": DATA_DIR / "db.sqlite3",
}}
LANGUAGE_CODE = "en"
LANGUAGES = [("en", "English"), ("th", "ไทย")]
LOCALE_PATHS = [BASE_DIR / "locale"]
TIME_ZONE = "UTC"  # Choose the institution's timezone before recording timestamps.
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATICFILES_DIRS = [] if getattr(sys, "frozen", False) else [BASE_DIR / "static"]
STATIC_ROOT = Path(os.environ.get("GRADEBOOK_STATIC_ROOT") or BASE_DIR / "runtime" / "staticfiles")
# Generated reports stay outside public static assets.
MEDIA_ROOT = DATA_DIR / "reports"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
