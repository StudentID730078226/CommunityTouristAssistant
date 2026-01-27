"""Tests for admin actions."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.contrib import admin
from django.contrib.auth.models import User
from django.test import RequestFactory

from accounts.models import Contribution
from places.admin import PlaceAdmin, PlaceImageInline, approve_places, reject_places
from places.models import Place, PlaceImage
from reviews.admin import ReviewAdmin
from reviews.models import ModerationLog, Review, ReviewReport


@pytest.mark.django_db
def test_place_admin_actions_and_inline_preview(user):
    """Test place admin actions and inline preview.

    :param user: User fixture.
    :return: None
    :rtype: None
    """
    place = Place.objects.create(
        name="Moderate Me",
        description="desc",
        category=Place.Category.OTHER,
        location_text="TR1",
        created_by=user,
        moderation_status=Place.ModerationStatus.PENDING,
    )

    rf = RequestFactory()
    request = rf.post("/admin/places/place/")
    request.user = User.objects.create_superuser("su1", "su1@example.com", "StrongPass123!")

    approve_places(None, request, Place.objects.filter(pk=place.pk))
    place.refresh_from_db()
    assert place.moderation_status == Place.ModerationStatus.APPROVED

    reject_places(None, request, Place.objects.filter(pk=place.pk))
    place.refresh_from_db()
    assert place.moderation_status == Place.ModerationStatus.REJECTED
    assert ModerationLog.objects.filter(object_id=place.pk, action=ModerationLog.Action.PLACE_APPROVED).exists()
    assert ModerationLog.objects.filter(object_id=place.pk, action=ModerationLog.Action.PLACE_REJECTED).exists()

    contribution = Contribution.objects.get(user=user)
    assert contribution.points >= 20

    inline = PlaceImageInline(PlaceImage, admin.site)
    assert inline.image_preview(PlaceImage(place=place)) == "No image"
    assert "img" in inline.image_preview(SimpleNamespace(image=SimpleNamespace(url="/media/test.jpg")))


@pytest.mark.django_db
def test_review_admin_dismiss_action(approved_place, user, another_user):
    """Test review admin dismiss action.

    :param approved_place: Approved place fixture.
    :param user: User fixture.
    :param another_user: Secondary user fixture.
    :return: None
    :rtype: None
    """
    review = Review.objects.create(place=approved_place, user=user, rating=1, text="bad")
    ReviewReport.objects.create(review=review, reporter=another_user, reason="r1")
    review.reported = True
    review.save(update_fields=["reported"])

    review_admin = ReviewAdmin(Review, admin.site)
    request = RequestFactory().get("/admin/reviews/review/")
    request.user = User.objects.create_superuser("su2", "su2@example.com", "StrongPass123!")
    review_admin.dismiss_reported_reviews(request, Review.objects.filter(pk=review.pk))

    review.refresh_from_db()
    assert review.reported is False
    assert review.reports.first().status == ReviewReport.Status.DISMISSED
    assert ModerationLog.objects.filter(object_id=review.pk, action=ModerationLog.Action.REVIEW_DISMISSED).exists()


@pytest.mark.django_db
def test_review_admin_uphold_enables_restriction_after_threshold(approved_place, user, another_user):
    """Test review admin uphold enables restriction after threshold.

    :param approved_place: Approved place fixture.
    :param user: User fixture.
    :param another_user: Secondary user fixture.
    :return: None
    :rtype: None
    """
    contribution = Contribution.objects.get(user=user)
    contribution.upheld_reports_count = 2
    contribution.points = 100
    contribution.save(update_fields=["upheld_reports_count", "points"])

    review = Review.objects.create(place=approved_place, user=user, rating=1, text="bad text")
    ReviewReport.objects.create(review=review, reporter=another_user, reason="r1")
    review.reported = True
    review.save(update_fields=["reported"])

    review_admin = ReviewAdmin(Review, admin.site)
    request = RequestFactory().get("/admin/reviews/review/")
    request.user = User.objects.create_superuser("su3", "su3@example.com", "StrongPass123!")
    review_admin.uphold_reported_reviews(request, Review.objects.filter(pk=review.pk))

    contribution.refresh_from_db()
    assert contribution.upheld_reports_count == 3
    assert contribution.review_restriction_active is True
    assert ModerationLog.objects.filter(object_id=review.pk, action=ModerationLog.Action.REVIEW_UPHELD).exists()


@pytest.mark.django_db
def test_review_admin_soft_archive_and_restore(approved_place, user):
    """Test review admin soft archive and restore.

    :param approved_place: Approved place fixture.
    :param user: User fixture.
    :return: None
    :rtype: None
    """
    review = Review.objects.create(place=approved_place, user=user, rating=3, text="archive me")
    admin_obj = ReviewAdmin(Review, admin.site)
    request = RequestFactory().get("/admin/reviews/review/")
    request.user = User.objects.create_superuser("su4", "su4@example.com", "StrongPass123!")

    admin_obj.archive_reviews(request, Review.objects.filter(pk=review.pk))
    review.refresh_from_db()
    assert review.is_archived is True
    assert ModerationLog.objects.filter(object_id=review.pk, action=ModerationLog.Action.REVIEW_ARCHIVED).exists()

    admin_obj.restore_reviews(request, Review.objects.filter(pk=review.pk))
    review.refresh_from_db()
    assert review.is_archived is False
    assert ModerationLog.objects.filter(object_id=review.pk, action=ModerationLog.Action.REVIEW_RESTORED).exists()
