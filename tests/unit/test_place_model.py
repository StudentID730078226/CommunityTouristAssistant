"""Tests for place model."""

from __future__ import annotations

from datetime import datetime, time

import pytest
from django.utils import timezone

from reviews.models import Review


@pytest.mark.django_db
def test_place_save_syncs_is_approved_with_moderation_status(user):
    """Test place save syncs is approved with moderation status.

    :param user: User fixture.
    :return: None
    :rtype: None
    """
    from places.models import Place

    place = Place.objects.create(
        name="Test Place",
        description="Desc",
        category=Place.Category.OTHER,
        location_text="TR1",
        created_by=user,
        moderation_status=Place.ModerationStatus.PENDING,
    )
    assert place.is_approved is False

    place.moderation_status = Place.ModerationStatus.APPROVED
    place.save()
    place.refresh_from_db()
    assert place.is_approved is True


@pytest.mark.django_db
def test_place_average_rating_and_likes_count(approved_place, user, another_user):
    """Test place average rating and likes count.

    :param approved_place: Approved place fixture.
    :param user: User fixture.
    :param another_user: Secondary user fixture.
    :return: None
    :rtype: None
    """
    from places.models import PlaceLike

    assert approved_place.likes_count == 0
    PlaceLike.objects.create(place=approved_place, user=user)
    PlaceLike.objects.create(place=approved_place, user=another_user)
    assert approved_place.likes_count == 2
    assert str(approved_place) == approved_place.name

    Review.objects.create(place=approved_place, user=user, rating=4, text="Great!")
    Review.objects.create(place=approved_place, user=another_user, rating=2, text="Okay")
    assert approved_place.average_rating == 3.0


@pytest.mark.django_db
def test_place_opening_hours_open_now_logic(user, monkeypatch):
    """Test place opening hours open now logic.

    :param user: User fixture.
    :param monkeypatch: Pytest monkeypatch fixture.
    :return: None
    :rtype: None
    """
    from places.models import Place

    place = Place.objects.create(
        name="Hours Place",
        description="Desc",
        category=Place.Category.OTHER,
        location_text="TR1",
        created_by=user,
        moderation_status=Place.ModerationStatus.APPROVED,
        opening_days="Mon-Fri",
        opening_time=time(9, 0),
        closing_time=time(17, 0),
    )
    assert place.has_opening_hours is True

    monday_midday = timezone.make_aware(datetime(2026, 2, 2, 12, 0, 0))
    monkeypatch.setattr("places.models.timezone.localtime", lambda: monday_midday)
    assert place.is_open_now is True

    sunday_midday = timezone.make_aware(datetime(2026, 2, 1, 12, 0, 0))
    monkeypatch.setattr("places.models.timezone.localtime", lambda: sunday_midday)
    assert place.is_open_now is False


@pytest.mark.django_db
def test_place_opening_hours_additional_branches(user, monkeypatch):
    """Test place opening hours additional branches.

    :param user: User fixture.
    :param monkeypatch: Pytest monkeypatch fixture.
    :return: None
    :rtype: None
    """
    from places.models import Place

    no_hours = Place.objects.create(
        name="No Hours",
        description="Desc",
        category=Place.Category.OTHER,
        location_text="TR1",
        created_by=user,
        moderation_status=Place.ModerationStatus.APPROVED,
    )
    assert no_hours.is_open_now is None
    assert no_hours._is_open_today_by_days(3) is True

    place = Place.objects.create(
        name="Night Hours",
        description="Desc",
        category=Place.Category.OTHER,
        location_text="TR1",
        created_by=user,
        moderation_status=Place.ModerationStatus.APPROVED,
        opening_days="BadToken, Sun-Tue",
        opening_time=time(22, 0),
        closing_time=time(2, 0),
    )
    assert place._parse_day_token("xxx") is None
    assert place._is_open_today_by_days(0) is True
    assert place._is_open_today_by_days(3) is False

    just_listed_days = Place(
        name="Listed Days",
        description="Desc",
        category=Place.Category.OTHER,
        location_text="TR1",
        opening_days="Mon,Wed,Fri",
        opening_time=time(9, 0),
        closing_time=time(17, 0),
    )
    assert just_listed_days._is_open_today_by_days(2) is True

    unknown_days = Place(
        name="Unknown Days",
        description="Desc",
        category=Place.Category.OTHER,
        location_text="TR1",
        opening_days="???",
        opening_time=time(9, 0),
        closing_time=time(17, 0),
    )
    assert unknown_days._is_open_today_by_days(4) is True

    unknown_range_days = Place(
        name="Unknown Range",
        description="Desc",
        category=Place.Category.OTHER,
        location_text="TR1",
        opening_days="foo-bar",
        opening_time=time(9, 0),
        closing_time=time(17, 0),
    )
    assert unknown_range_days._is_open_today_by_days(1) is True

    monday_late = timezone.make_aware(datetime(2026, 2, 2, 23, 30, 0))
    monkeypatch.setattr("places.models.timezone.localtime", lambda: monday_late)
    assert place.is_open_now is True
