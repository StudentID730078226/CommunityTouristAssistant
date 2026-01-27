"""Tests for places views."""

from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from accounts.models import Contribution
from places.models import ActivityPlace, BeachPlace, FoodPlace, HeritagePlace, Place, PlaceImage, PlaceLike
from reviews.models import Review


@pytest.mark.django_db
def test_search_basic(client, approved_place):
    """Test search basic.

    :param client: Django test client.
    :param approved_place: Approved place fixture.
    :return: None
    :rtype: None
    """
    assert client.get(reverse("places:search_places")).status_code == 200
    assert client.get(reverse("places:search_places"), {"q": "Harbor"}).status_code == 200
    assert client.get(reverse("places:search_places"), {"category": Place.Category.OTHER}).status_code == 200


@pytest.mark.django_db
def test_search_filters_sort_and_cards(client, approved_place, user):
    """Test search filters sort and cards.

    :param client: Django test client.
    :param approved_place: Approved place fixture.
    :param user: User fixture.
    :return: None
    :rtype: None
    """
    other = Place.objects.create(
        name="No Image Place",
        description="Plain",
        category=Place.Category.OTHER,
        location_text="TR2",
        created_by=user,
        moderation_status=Place.ModerationStatus.APPROVED,
    )
    Review.objects.create(place=approved_place, user=user, rating=5, text="Great")
    PlaceImage.objects.create(place=approved_place, image=SimpleUploadedFile("img.jpg", b"img", content_type="image/jpeg"))

    response = client.get(
        reverse("places:search_places"),
        {
            "q": "Harbor",
            "category": Place.Category.OTHER,
            "min_rating": "4",
            "has_images": "1",
            "sort": "top_rated",
            "per_page": "6",
        },
    )
    assert response.status_code == 200
    content = response.content.decode()
    assert "Harbor Walk" in content
    assert other.name not in content


@pytest.mark.django_db
def test_detail_type_resolves_for_all_polymorphic_models(client, user):
    """Test detail type resolves for all polymorphic models.

    :param client: Django test client.
    :param user: User fixture.
    :return: None
    :rtype: None
    """
    base_kwargs = dict(description="Desc", category=Place.Category.OTHER, location_text="TR1", created_by=user)
    heritage = HeritagePlace.objects.create(name="H", moderation_status=Place.ModerationStatus.APPROVED, **base_kwargs)
    food = FoodPlace.objects.create(name="F", cuisine="Italian", moderation_status=Place.ModerationStatus.APPROVED, **base_kwargs)
    activity = ActivityPlace.objects.create(
        name="A",
        activity_type="Hiking",
        moderation_status=Place.ModerationStatus.APPROVED,
        **base_kwargs,
    )
    beach = BeachPlace.objects.create(name="B", moderation_status=Place.ModerationStatus.APPROVED, **base_kwargs)

    for place in [heritage, food, activity, beach]:
        assert client.get(reverse("places:place_detail", kwargs={"pk": place.pk})).status_code == 200


@pytest.mark.django_db
def test_place_detail_filter_sort_and_pagination_branches(client, approved_place, user):
    """Test place detail filter sort and pagination branches.

    :param client: Django test client.
    :param approved_place: Approved place fixture.
    :param user: User fixture.
    :return: None
    :rtype: None
    """
    Review.objects.create(place=approved_place, user=user, rating=5, text="Great")
    guest_review = Review.objects.create(place=approved_place, user=None, rating=2, text="Low")
    guest_review.is_approved = True
    guest_review.save(update_fields=["is_approved"])

    urls = [
        {"rating": "bad", "sort": "oldest", "per_page": "bad"},
        {"rating": "9", "sort": "highest", "per_page": "99"},
        {"rating": "2", "sort": "lowest", "per_page": "10"},
        {"sort": "unknown", "per_page": "20"},
    ]
    for params in urls:
        response = client.get(reverse("places:place_detail", kwargs={"pk": approved_place.pk}), params)
        assert response.status_code == 200


@pytest.mark.django_db
def test_place_detail_review_integrityerror_branch(client, approved_place, user, monkeypatch):
    """Test place detail review integrityerror branch.

    :param client: Django test client.
    :param approved_place: Approved place fixture.
    :param user: User fixture.
    :param monkeypatch: Pytest monkeypatch fixture.
    :return: None
    :rtype: None
    """
    client.force_login(user)

    original_save = Review.save

    def raising_save(self, *args, **kwargs):
        """Raising save.

        :param self: Fixture parameter.
        :return: None
        :rtype: None
        """
        raise IntegrityError("forced")

    monkeypatch.setattr(Review, "save", raising_save)
    response = client.post(
        reverse("places:place_detail", kwargs={"pk": approved_place.pk}),
        data={"rating": "4", "text": "Will fail"},
        follow=True,
    )
    assert response.status_code == 200
    monkeypatch.setattr(Review, "save", original_save)


@pytest.mark.django_db
def test_add_place_error_branches(client, user, monkeypatch):
    """Test add place error branches.

    :param client: Django test client.
    :param user: User fixture.
    :param monkeypatch: Pytest monkeypatch fixture.
    :return: None
    :rtype: None
    """
    client.force_login(user)
    url = reverse("places:add_place")

    # Invalid place type
    invalid_type = client.post(
        url,
        data={"name": "X", "description": "D", "category": Place.Category.OTHER, "location_text": "TR1", "place_type": "x"},
    )
    assert invalid_type.status_code == 200

    # Invalid forms
    invalid_form = client.post(url, data={"place_type": "other"})
    assert invalid_form.status_code == 200

    # Geocode failure
    monkeypatch.setattr("places.views.geocode_location", lambda _loc: (None, None))
    geocode_fail = client.post(
        url,
        data={
            "name": "GeoFail",
            "description": "D",
            "category": Place.Category.OTHER,
            "location_text": "TR1",
            "place_type": "other",
        },
    )
    assert geocode_fail.status_code == 200

    # Too many images
    monkeypatch.setattr("places.views.geocode_location", lambda _loc: (50.0, -5.0))
    many_files = [
        SimpleUploadedFile(f"img{i}.jpg", b"filecontent", content_type="image/jpeg")
        for i in range(31)
    ]
    too_many = client.post(
        url,
        data={
            "name": "Many Images",
            "description": "D",
            "category": Place.Category.OTHER,
            "location_text": "TR1",
            "place_type": "other",
            "images": many_files,
        },
    )
    assert too_many.status_code == 200


@pytest.mark.django_db
def test_toggle_like_add_and_remove(client, approved_place, user):
    """Test toggle like add and remove.

    :param client: Django test client.
    :param approved_place: Approved place fixture.
    :param user: User fixture.
    :return: None
    :rtype: None
    """
    client.force_login(user)
    url = reverse("places:toggle_like", kwargs={"pk": approved_place.pk})
    assert client.post(url).status_code == 302
    assert PlaceLike.objects.filter(place=approved_place, user=user).exists()
    assert client.post(url).status_code == 302
    assert not PlaceLike.objects.filter(place=approved_place, user=user).exists()


@pytest.mark.django_db
def test_edit_opening_hours_flow(client, approved_place, user, another_user):
    # Guest must log in.
    """Test edit opening hours flow.

    :param client: Django test client.
    :param approved_place: Approved place fixture.
    :param user: User fixture.
    :param another_user: Secondary user fixture.
    :return: None
    :rtype: None
    """
    edit_url = reverse("places:edit_opening_hours", kwargs={"pk": approved_place.pk})
    assert client.get(edit_url).status_code == 302

    # Any authenticated user can add when missing.
    client.force_login(another_user)
    response = client.post(
        edit_url,
        data={"opening_days_list": ["mon", "tue", "wed", "thu", "fri", "sat", "sun"], "opening_time": "09:00", "closing_time": "18:00"},
        follow=True,
    )
    assert response.status_code == 200
    approved_place.refresh_from_db()
    assert approved_place.opening_time is not None
    assert approved_place.closing_time is not None

    # Unrelated user cannot edit once hours already exist.
    denied = client.post(
        edit_url,
        data={"opening_days_list": ["mon", "tue", "wed", "thu", "fri"], "opening_time": "08:00", "closing_time": "17:00"},
        follow=True,
    )
    assert denied.status_code == 200
    approved_place.refresh_from_db()
    assert approved_place.opening_days == "mon,tue,wed,thu,fri,sat,sun"

    # Place creator can edit existing hours.
    client.force_login(user)
    creator_update = client.post(
        edit_url,
        data={"opening_days_list": ["mon", "tue", "wed", "thu", "fri"], "opening_time": "08:00", "closing_time": "17:00"},
        follow=True,
    )
    assert creator_update.status_code == 200
    approved_place.refresh_from_db()
    assert approved_place.opening_days == "mon,tue,wed,thu,fri"


@pytest.mark.django_db
def test_edit_opening_hours_invalid_submission_stays_on_page(client, approved_place, another_user):
    """Test edit opening hours invalid submission stays on page.

    :param client: Django test client.
    :param approved_place: Approved place fixture.
    :param another_user: Secondary user fixture.
    :return: None
    :rtype: None
    """
    client.force_login(another_user)
    edit_url = reverse("places:edit_opening_hours", kwargs={"pk": approved_place.pk})
    response = client.post(
        edit_url,
        data={"opening_days_list": ["mon", "tue"], "opening_time": "09:00", "closing_time": ""},
        follow=True,
    )
    assert response.status_code == 200
