import json
from pathlib import Path
from django.db import migrations, models


def seed_kpac(apps, schema_editor):
    Category = apps.get_model("assessments", "MarkingSchemeCategory")
    data = json.loads((Path(__file__).resolve().parents[1] / "data" / "marking-scheme_kpac.json").read_text(encoding="utf-8"))
    Category.objects.using(schema_editor.connection.alias).bulk_create([
        Category(name_th=item["name_th"], name_en=item["name_en"], subcategories=item["subcategories"])
        for item in data["categories"]])


class Migration(migrations.Migration):
    dependencies = [("assessments", "0011_course_units")]
    operations = [
        migrations.CreateModel(name="MarkingSchemeCategory", fields=[
            ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
            ("name_th", models.CharField(blank=True, max_length=150)),
            ("name_en", models.CharField(blank=True, max_length=150)),
            ("subcategories", models.JSONField(default=list)),
            ("revision", models.PositiveIntegerField(default=1)),
            ("created_at", models.DateTimeField(auto_now_add=True)),
            ("updated_at", models.DateTimeField(auto_now=True)),
        ], options={"ordering": ["pk"]}),
        migrations.RunPython(seed_kpac, migrations.RunPython.noop),
    ]
