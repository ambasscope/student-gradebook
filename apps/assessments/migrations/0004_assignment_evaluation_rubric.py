import apps.assessments.services.evaluation
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("assessments", "0003_convert_safe_assignment_ids")]
    operations = [
        migrations.AddField(
            model_name="assignment",
            name="evaluation_rubric",
            field=models.JSONField(default=apps.assessments.services.evaluation.default_evaluation_rubric),
        ),
    ]
