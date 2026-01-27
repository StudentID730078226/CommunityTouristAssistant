"""Tests for reviews models."""

from __future__ import annotations

import pytest

from reviews.models import Review, ReviewReport


@pytest.mark.django_db
def test_review_and_report_str_methods(approved_place, user, another_user):
    """Test review and report str methods.

    :param approved_place: Approved place fixture.
    :param user: User fixture.
    :param another_user: Secondary user fixture.
    :return: None
    :rtype: None
    """
    review = Review.objects.create(place=approved_place, user=user, rating=4, text="Good")
    report = ReviewReport.objects.create(review=review, reporter=another_user, reason="Reason")
    assert str(review).startswith("Review by")
    assert "Report on review" in str(report)
