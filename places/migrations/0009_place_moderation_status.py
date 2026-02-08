from django.db import migrations, models


def backfill_moderation_status(apps, schema_editor):
    Place = apps.get_model("places", "Place")
    Place.objects.filter(is_approved=True).update(moderation_status="approved")
    Place.objects.filter(is_approved=False).update(moderation_status="pending")


class Migration(migrations.Migration):
    dependencies = [
        ("places", "0008_backfill_place_polymorphic_ctype"),
    ]

    operations = [
        migrations.AddField(
            model_name="place",
            name="moderation_status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending Review"),
                    ("approved", "Approved"),
                    ("rejected", "Rejected"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
        migrations.RunPython(backfill_moderation_status, migrations.RunPython.noop),
    ]
