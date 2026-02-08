from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def backfill_place_likes(apps, schema_editor):
    Place = apps.get_model("places", "Place")
    PlaceLike = apps.get_model("places", "PlaceLike")
    through_model = Place.liked_by.through

    now = timezone.now()
    like_rows = through_model.objects.all().values_list("place_id", "user_id")
    to_create = [PlaceLike(place_id=place_id, user_id=user_id, created_at=now) for place_id, user_id in like_rows]
    PlaceLike.objects.bulk_create(to_create, ignore_conflicts=True)


class Migration(migrations.Migration):
    dependencies = [
        ("places", "0010_place_opening_hours"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PlaceLike",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "place",
                    models.ForeignKey(on_delete=models.deletion.CASCADE, related_name="likes", to="places.place"),
                ),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="place_likes",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(fields=("user", "place"), name="unique_place_like"),
                ],
            },
        ),
        migrations.RunPython(backfill_place_likes, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="place",
            name="liked_by",
        ),
    ]
