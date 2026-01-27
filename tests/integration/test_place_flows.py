"""Tests for place flows."""

from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from accounts.models import Contribution
from places.models import Place, PlaceImage
from reviews.models import Review


@pytest.mark.django_db
def test_add_place_requires_login(client):
    """Test add place requires login.

    :param client: Django test client.
    :return: None
    :rtype: None
    """
    response = client.get(reverse("places:add_place"))
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


@pytest.mark.django_db
def test_authenticated_user_can_submit_generic_place(client, user, monkeypatch):
    """Test authenticated user can submit generic place.

    :param client: Django test client.
    :param user: User fixture.
    :param monkeypatch: Pytest monkeypatch fixture.
    :return: None
    :rtype: None
    """
    client.force_login(user)

    monkeypatch.setattr("places.views.geocode_location", lambda _loc: (50.0, -5.0))
    response = client.post(
        reverse("places:add_place"),
        data={
            "name": "Hidden Cove",
            "description": "Quiet and peaceful",
            "category": Place.Category.OTHER,
            "location_text": "TR1 1AA",
            "place_type": "other",
        },
    )

    assert response.status_code == 302
    place = Place.objects.get(name="Hidden Cove")
    assert place.created_by == user
    assert place.moderation_status == Place.ModerationStatus.PENDING
    assert place.is_approved is False


@pytest.mark.django_db
def test_add_place_get_and_image_upload(client, user, monkeypatch):
    """Test add place get and image upload.

    :param client: Django test client.
    :param user: User fixture.
    :param monkeypatch: Pytest monkeypatch fixture.
    :return: None
    :rtype: None
    """
    client.force_login(user)
    assert client.get(reverse("places:add_place")).status_code == 200

    monkeypatch.setattr("places.views.geocode_location", lambda _loc: (50.0, -5.0))
    response = client.post(
        reverse("places:add_place"),
        data={
            "name": "Image Place",
            "description": "Has photo",
            "category": Place.Category.OTHER,
            "location_text": "TR1 1AA",
            "place_type": "other",
            "images": [SimpleUploadedFile("thumb.jpg", b"img", content_type="image/jpeg")],
        },
    )
    assert response.status_code == 302
    place = Place.objects.get(name="Image Place")
    assert PlaceImage.objects.filter(place=place).count() == 1


@pytest.mark.django_db
def test_place_detail_review_submission_and_duplicate_prevention(client, approved_place, user):
    """Test place detail review submission and duplicate prevention.

    :param client: Django test client.
    :param approved_place: Approved place fixture.
    :param user: User fixture.
    :return: None
    :rtype: None
    """
    client.force_login(user)
    url = reverse("places:place_detail", kwargs={"pk": approved_place.pk})

    first = client.post(url, data={"rating": "5", "text": "Excellent trip!"}, follow=True)
    assert first.status_code == 200
    assert Review.objects.filter(place=approved_place, user=user).count() == 1

    duplicate = client.post(url, data={"rating": "4", "text": "Second attempt"}, follow=True)
    assert duplicate.status_code == 200
    assert Review.objects.filter(place=approved_place, user=user).count() == 1


@pytest.mark.django_db
def test_guest_duplicate_review_blocked_via_place_detail(client, approved_place):
    """Test guest duplicate review blocked via place detail.

    :param client: Django test client.
    :param approved_place: Approved place fixture.
    :return: None
    :rtype: None
    """
    url = reverse("places:place_detail", kwargs={"pk": approved_place.pk})
    first = client.post(url, data={"rating": "5", "text": "Guest first"}, follow=True)
    assert first.status_code == 200
    assert Review.objects.filter(place=approved_place, user=None).count() == 1

    second = client.post(url, data={"rating": "3", "text": "Guest second"}, follow=True)
    assert second.status_code == 200
    assert Review.objects.filter(place=approved_place, user=None).count() == 1
    assert (
        b"Guest users can only submit one review per place in this session."
        in second.content
    )


@pytest.mark.django_db
def test_restricted_user_cannot_add_review_via_place_detail(client, approved_place, user):
    """Test restricted user cannot add review via place detail.

    :param client: Django test client.
    :param approved_place: Approved place fixture.
    :param user: User fixture.
    :return: None
    :rtype: None
    """
    contribution = Contribution.objects.get(user=user)
    contribution.review_restriction_active = True
    contribution.save(update_fields=["review_restriction_active"])

    client.force_login(user)
    response = client.post(
        reverse("places:place_detail", kwargs={"pk": approved_place.pk}),
        data={"rating": "3", "text": "Blocked review"},
        follow=True,
    )
    assert response.status_code == 200
    assert Review.objects.filter(place=approved_place, user=user).count() == 0


@pytest.mark.django_db
def test_toggle_like_returns_json_for_ajax(client, approved_place, user):
    """Test toggle like returns json for ajax.

    :param client: Django test client.
    :param approved_place: Approved place fixture.
    :param user: User fixture.
    :return: None
    :rtype: None
    """
    client.force_login(user)
    response = client.post(
        reverse("places:toggle_like", kwargs={"pk": approved_place.pk}),
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["liked"] is True
    assert payload["likes_count"] == 1
