from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("places", "0009_place_moderation_status"),
    ]

    operations = [
        migrations.AddField(
            model_name="place",
            name="closing_time",
            field=models.TimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="place",
            name="opening_days",
            field=models.CharField(
                blank=True,
                help_text="Optional. Example: Mon-Sun, Mon-Fri, Sat-Sun, or Mon,Wed,Fri",
                max_length=120,
            ),
        ),
        migrations.AddField(
            model_name="place",
            name="opening_time",
            field=models.TimeField(blank=True, null=True),
        ),
    ]
