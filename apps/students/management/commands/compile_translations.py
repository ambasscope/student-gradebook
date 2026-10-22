from django.core.management import call_command
from django.core.management.base import BaseCommand
from config.translation_tools import IGNORE, gettext_tools, project_directory


class Command(BaseCommand):
    help = "Compile the manually edited Thai .po files; restart the app afterward."

    def handle(self, *args, **options):
        with gettext_tools(["msgfmt"]), project_directory():
            call_command("compilemessages", locale=["th"], ignore_patterns=IGNORE,
                         stdout=self.stdout, stderr=self.stderr, verbosity=options["verbosity"])
        self.stdout.write(self.style.SUCCESS("Thai translations compiled. Restart the app and refresh its pages."))
