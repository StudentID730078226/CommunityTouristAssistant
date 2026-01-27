"""Tests for reviews views."""

from __future__ import annotations

import pytest
from django.db import IntegrityError
from django.urls import reverse

from accounts.models import Contribution
from reviews.models import Review
from reviews.spam import CAPTCHA_ANSWER_KEY, CAPTCHA_REQUIRED_KEY


@pytest.mark.django_db
def test_place_reviews_page_renders(client, approved_place):
    """Test place reviews page renders.

    :param client: Django test client.
    :param approved_place: Approved place fixture.
    :return: None
    :rtype: None
    """
    response = client.get(reverse("reviews:place_reviews", kwargs={"place_id": approved_place.id}))
    assert response.status_code == 200


@pytest.mark.django_db
def test_add_review_get_and_post_as_guest(client, approved_place):
    """Test add review get and post as guest.

    :param client: Django test client.
    :param approved_place: Approved place fixture.
    :return: None
    :rtype: None
    """
    assert client.get(reverse("reviews:add_review", kwargs={"place_id": approved_place.id})).status_code == 200
    response = client.post(
        reverse("reviews:add_review", kwargs={"place_id": approved_place.id}),
        data={"rating": "4", "text": "Guest review"},
    )
    assert response.status_code == 302
    assert Review.objects.filter(place=approved_place, user=None).exists()


@pytest.mark.django_db
def test_guest_duplicate_review_blocked_on_add_review(client, approved_place):
    """Test guest duplicate review blocked on add review page.

    :param client: Django test client.
    :param approved_place: Approved place fixture.
    :return: None
    :rtype: None
    """
    url = reverse("reviews:add_review", kwargs={"place_id": approved_place.id})
    first = client.post(url, data={"rating": "4", "text": "Guest review first"}, follow=True)
    assert first.status_code == 200
    assert Review.objects.filter(place=approved_place, user=None).count() == 1

    second = client.post(url, data={"rating": "5", "text": "Guest review second"}, follow=True)
    assert second.status_code == 200
    assert Review.objects.filter(place=approved_place, user=None).count() == 1
    assert (
        b"Guest users can only submit one review per place in this session."
        in second.content
    )


@pytest.mark.django_db
def test_add_review_restricted_and_integrity_error(client, approved_place, user, monkeypatch):
    """Test add review restricted and integrity error.

    :param client: Django test client.
    :param approved_place: Approved place fixture.
    :param user: User fixture.
    :param monkeypatch: Pytest monkeypatch fixture.
    :return: None
    :rtype: None
    """
    contribution = Contribution.objects.get(user=user)
    contribution.review_restriction_active = True
    contribution.save(update_fields=["review_restriction_active"])
    client.force_login(user)

    restricted = client.post(
        reverse("reviews:add_review", kwargs={"place_id": approved_place.id}),
        data={"rating": "4", "text": "Blocked"},
        follow=True,
    )
    assert restricted.status_code == 200

    contribution.review_restriction_active = False
    contribution.save(update_fields=["review_restriction_active"])

    original_save = Review.save

    def raise_integrity(*args, **kwargs):
        """Raise integrity.

        :return: None
        :rtype: None
        """
        raise IntegrityError("forced")

    monkeypatch.setattr(Review, "save", raise_integrity)
    failed = client.post(
        reverse("reviews:add_review", kwargs={"place_id": approved_place.id}),
        data={"rating": "5", "text": "forced fail"},
        follow=True,
    )
    assert failed.status_code == 200
    monkeypatch.setattr(Review, "save", original_save)


@pytest.mark.django_db
def test_add_review_authenticated_success_and_duplicate_blocked(client, approved_place, user):
    """Test add review authenticated success and duplicate blocked.

    :param client: Django test client.
    :param approved_place: Approved place fixture.
    :param user: User fixture.
    :return: None
    :rtype: None
    """
    client.force_login(user)
    url = reverse("reviews:add_review", kwargs={"place_id": approved_place.id})

    first = client.post(url, data={"rating": "4", "text": "Great place"})
    assert first.status_code == 302

    duplicate = client.post(url, data={"rating": "5", "text": "Second try"}, follow=True)
    assert duplicate.status_code == 200
    assert Review.objects.filter(place=approved_place, user=user).count() == 1


@pytest.mark.django_db
def test_add_review_honeypot_and_similarity_block(client, approved_place, user):
    """Test add review honeypot and similarity block.

    :param client: Django test client.
    :param approved_place: Approved place fixture.
    :param user: User fixture.
    :return: None
    :rtype: None
    """
    Review.objects.create(
        place=approved_place,
        user=user,
        rating=4,
        text="The beach walk was beautiful and peaceful with excellent views all around.",
    )

    honeypot = client.post(
        reverse("reviews:add_review", kwargs={"place_id": approved_place.id}),
        data={"rating": "4", "text": "spam", "honeypot": "bot"},
        follow=True,
    )
    assert honeypot.status_code == 200
    assert Review.objects.filter(place=approved_place, text="spam").count() == 0

    similar = client.post(
        reverse("reviews:add_review", kwargs={"place_id": approved_place.id}),
        data={"rating": "5", "text": "The beach walk was beautiful and peaceful, with excellent views all around."},
        follow=True,
    )
    assert similar.status_code == 200
    assert Review.objects.filter(place=approved_place).count() == 1


@pytest.mark.django_db
def test_add_review_requires_and_validates_captcha_when_flagged(client, approved_place):
    """Test add review requires and validates captcha when flagged.

    :param client: Django test client.
    :param approved_place: Approved place fixture.
    :return: None
    :rtype: None
    """
    session = client.session
    session[CAPTCHA_REQUIRED_KEY] = True
    session.save()

    # Generate challenge.
    assert client.get(reverse("reviews:add_review", kwargs={"place_id": approved_place.id})).status_code == 200
    session = client.session
    answer = session.get(CAPTCHA_ANSWER_KEY)

    wrong = client.post(
        reverse("reviews:add_review", kwargs={"place_id": approved_place.id}),
        data={"rating": "4", "text": "Guest review", "captcha_answer": "999"},
        follow=True,
    )
    assert wrong.status_code == 200
    assert Review.objects.filter(place=approved_place, text="Guest review").count() == 0

    correct = client.post(
        reverse("reviews:add_review", kwargs={"place_id": approved_place.id}),
        data={"rating": "4", "text": "Guest review", "captcha_answer": answer},
        follow=True,
    )
    assert correct.status_code == 200
    assert Review.objects.filter(place=approved_place, text="Guest review").count() == 1
