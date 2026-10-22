from django.db import migrations


def classify_levels(apps, schema_editor):
    Assignment = apps.get_model("assessments", "Assignment")
    for module in Assignment.objects.using(schema_editor.connection.alias).all().iterator():
        bands = module.evaluation_rubric
        if not isinstance(bands, list):
            continue
        changed = False
        for band in bands:
            if isinstance(band, dict) and "is_fail" not in band:
                band["is_fail"] = str(band.get("label", "")).strip().casefold() in {"fail", "failed", "ไม่ผ่าน", "ไม่ผ่านเกณฑ์"}
                changed = True
        if changed:
            module.evaluation_rubric = bands
            module.scheme_revision += 1
            module.save(update_fields=["evaluation_rubric", "scheme_revision"])


class Migration(migrations.Migration):
    dependencies = [("assessments", "0007_learning_date")]
    operations = [migrations.RunPython(classify_levels, migrations.RunPython.noop)]
