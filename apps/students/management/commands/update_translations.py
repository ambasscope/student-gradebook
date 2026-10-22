from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand
from config.translation_tools import IGNORE, gettext_tools, project_directory


class Command(BaseCommand):
    help = "Extract new interface text into the Thai .po files without translating it."

    def handle(self, *args, **options):
        (settings.BASE_DIR / "locale").mkdir(exist_ok=True)
        with gettext_tools(["xgettext", "msgmerge", "msguniq"]), project_directory():
            for domain in ["django", "djangojs"]:
                call_command("makemessages", locale=["th"], domain=domain, ignore_patterns=IGNORE,
                             stdout=self.stdout, stderr=self.stderr, verbosity=options["verbosity"])
        self.stdout.write(self.style.SUCCESS("Thai catalogs updated. Edit msgstr in django.po and djangojs.po, then run compile_translations."))
