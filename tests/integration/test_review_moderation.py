"""Tests for review moderation."""

from __future__ import annotations

import pytest
from django.contrib import admin
from django.test import RequestFactory
from django.urls import reverse

from accounts.models import Contribution
from reviews.admin import ReviewAdmin
from reviews.models import Review, ReviewReport


@pytest.mark.django_db
def test_report_review_creates_report_and_flags_review(client, approved_place, user, another_user):
    """Test report review creates report and flags review.

    :param client: Django test client.
    :param approved_place: Approved place fixture.
    :param user: User fixture.
    :param another_user: Secondary user fixture.
    :return: None
    :rtype: None
    """
    review = Review.objects.create(place=approved_place, user=user, rating=4, text="Nice walk")
    client.force_login(another_user)

    response = client.post(reverse("reviews:report_review", kwargs={"review_id": review.id}), data={"reason": "Abusive"})
    assert response.status_code == 302

    review.refresh_from_db()
    assert review.reported is True
    assert ReviewReport.objects.filter(review=review, reporter=another_user).count() == 1


@pytest.mark.django_db
def test_duplicate_report_is_blocked(client, approved_place, user, another_user):
    """Test duplicate report is blocked.

    :param client: Django test client.
    :param approved_place: Approved place fixture.
    :param user: User fixture.
    :param another_user: Secondary user fixture.
    :return: None
    :rtype: None
    """
    review = Review.objects.create(place=approved_place, user=user, rating=4, text="Nice walk")
    ReviewReport.objects.create(review=review, reporter=another_user, reason="Spam")

    client.force_login(another_user)
    response = client.post(reverse("reviews:report_review", kwargs={"review_id": review.id}), data={"reason": "Spam again"})
    assert response.status_code == 302
    assert ReviewReport.objects.filter(review=review, reporter=another_user).count() == 1


@pytest.mark.django_db
def test_self_report_is_blocked(client, approved_place, user):
    """Test self report is blocked.

    :param client: Django test client.
    :param approved_place: Approved place fixture.
    :param user: User fixture.
    :return: None
    :rtype: None
    """
    review = Review.objects.create(place=approved_place, user=user, rating=4, text="Own review")
    client.force_login(user)
    response = client.post(reverse("reviews:report_review", kwargs={"review_id": review.id}))
    assert response.status_code == 302
    assert ReviewReport.objects.filter(review=review).count() == 0


@pytest.mark.django_db
def test_admin_uphold_report_applies_penalty(approved_place, user, another_user):
    """Test admin uphold report applies penalty.

    :param approved_place: Approved place fixture.
    :param user: User fixture.
    :param another_user: Secondary user fixture.
    :return: None
    :rtype: None
    """
    review = Review.objects.create(place=approved_place, user=user, rating=2, text="Rude text")
    ReviewReport.objects.create(review=review, reporter=another_user, reason="Abuse")
    review.reported = True
    review.save(update_fields=["reported"])

    superuser = user.__class__.objects.create_superuser("admin_mod", "admin@example.com", "pass123456")
    request = RequestFactory().get("/admin/reviews/review/")
    request.user = superuser

    review_admin = ReviewAdmin(Review, admin.site)
    review_admin.uphold_reported_reviews(request, Review.objects.filter(pk=review.pk))

    review.refresh_from_db()
    contribution = Contribution.objects.get(user=user)
    assert review.is_approved is False
    assert review.reported is False
    assert review.moderation_penalty_applied is True
    assert contribution.upheld_reports_count == 1
    assert contribution.points >= 0
