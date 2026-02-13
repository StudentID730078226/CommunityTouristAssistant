from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("reviews", "0008_moderationlog_modlog_action_created_idx_and_more"),
    ]

    operations = [
        migrations.DeleteModel(name="Rating"),
    ]
