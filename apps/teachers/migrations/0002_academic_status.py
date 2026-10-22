from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [("teachers", "0001_teacher_modules_objectives")]
    operations = [migrations.RenameField(model_name="teacherprofile", old_name="position", new_name="academic_status")]
