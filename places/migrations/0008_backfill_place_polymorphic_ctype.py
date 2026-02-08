from django.db import migrations


def set_polymorphic_ctype(apps, schema_editor):
    ContentType = apps.get_model("contenttypes", "ContentType")
    Place = apps.get_model("places", "Place")
    HeritagePlace = apps.get_model("places", "HeritagePlace")
    FoodPlace = apps.get_model("places", "FoodPlace")
    ActivityPlace = apps.get_model("places", "ActivityPlace")
    BeachPlace = apps.get_model("places", "BeachPlace")

    ct_place, _ = ContentType.objects.get_or_create(app_label="places", model="place")
    ct_heritage, _ = ContentType.objects.get_or_create(app_label="places", model="heritageplace")
    ct_food, _ = ContentType.objects.get_or_create(app_label="places", model="foodplace")
    ct_activity, _ = ContentType.objects.get_or_create(app_label="places", model="activityplace")
    ct_beach, _ = ContentType.objects.get_or_create(app_label="places", model="beachplace")

    place_ids = Place.objects.filter(polymorphic_ctype__isnull=True).values_list("pk", flat=True).iterator()
    for place_id in place_ids:
        if HeritagePlace.objects.filter(pk=place_id).exists():
            ctype_id = ct_heritage.id
        elif FoodPlace.objects.filter(pk=place_id).exists():
            ctype_id = ct_food.id
        elif ActivityPlace.objects.filter(pk=place_id).exists():
            ctype_id = ct_activity.id
        elif BeachPlace.objects.filter(pk=place_id).exists():
            ctype_id = ct_beach.id
        else:
            ctype_id = ct_place.id

        Place.objects.filter(pk=place_id).update(polymorphic_ctype_id=ctype_id)


class Migration(migrations.Migration):
    dependencies = [
        ("places", "0007_activityplace_beachplace_foodplace_heritageplace_and_more"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [
        migrations.RunPython(set_polymorphic_ctype, migrations.RunPython.noop),
    ]
