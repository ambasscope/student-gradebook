"""Developer-only gettext tools; normal app users use the bundled .mo files."""
import os
import shutil
from contextlib import contextmanager
from pathlib import Path
from django.conf import settings
from django.core.management.base import CommandError


@contextmanager
def gettext_tools(required):
    original = os.environ.get("PATH", "")
    candidates = [Path("/opt/homebrew/opt/gettext/bin"), Path("/usr/local/opt/gettext/bin")]
    extras = [str(path) for path in candidates if path.is_dir()]
    os.environ["PATH"] = os.pathsep.join(extras + [original])
    try:
        missing = [name for name in required if shutil.which(name) is None]
        if missing:
            raise CommandError("GNU gettext is required for editing translations. Install its developer tools, then retry. Missing: " + ", ".join(missing))
        yield
    finally:
        os.environ["PATH"] = original


@contextmanager
def project_directory():
    original = Path.cwd()
    os.chdir(settings.BASE_DIR)
    try:
        yield
    finally:
        os.chdir(original)


IGNORE = ["runtime", "app-data", "static/vendor/*", "*/tests/*", "*/migrations/*"]
