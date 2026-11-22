from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("assessments", "0012_marking_scheme_library")]

    operations = [
        migrations.CreateModel(
            name="RubricSettings",
            fields=[
                ("id", models.PositiveSmallIntegerField(default=1, editable=False, primary_key=True, serialize=False)),
                ("preset_key", models.CharField(default="builtin:default", max_length=80)),
            ],
            options={"constraints": [models.CheckConstraint(condition=models.Q(id=1), name="single_rubric_settings")]},
        ),
    ]
