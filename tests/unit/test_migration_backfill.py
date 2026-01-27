"""Tests for migration backfill."""

from __future__ import annotations

import importlib

import pytest
from django.apps import apps as global_apps

from places.models import ActivityPlace, BeachPlace, FoodPlace, HeritagePlace, Place


@pytest.mark.django_db
def test_backfill_polymorphic_ctype_handles_all_place_types(user):
    """Test backfill polymorphic ctype handles all place types.

    :param user: User fixture.
    :return: None
    :rtype: None
    """
    migration_mod = importlib.import_module("places.migrations.0008_backfill_place_polymorphic_ctype")
    set_polymorphic_ctype = migration_mod.set_polymorphic_ctype
    base_kwargs = dict(description="desc", category=Place.Category.OTHER, location_text="TR1", created_by=user)

    generic = Place.objects.create(name="Generic", moderation_status=Place.ModerationStatus.PENDING, **base_kwargs)
    heritage = HeritagePlace.objects.create(name="Heritage", moderation_status=Place.ModerationStatus.PENDING, **base_kwargs)
    food = FoodPlace.objects.create(name="Food", cuisine="Italian", moderation_status=Place.ModerationStatus.PENDING, **base_kwargs)
    activity = ActivityPlace.objects.create(name="Act", activity_type="Kayaking", moderation_status=Place.ModerationStatus.PENDING, **base_kwargs)
    beach = BeachPlace.objects.create(name="Beach", moderation_status=Place.ModerationStatus.PENDING, **base_kwargs)

    Place.objects.filter(pk__in=[generic.pk, heritage.pk, food.pk, activity.pk, beach.pk]).update(polymorphic_ctype=None)
    set_polymorphic_ctype(global_apps, None)

    for pk in [generic.pk, heritage.pk, food.pk, activity.pk, beach.pk]:
        assert Place.objects.get(pk=pk).polymorphic_ctype_id is not None
