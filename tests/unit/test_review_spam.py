"""Tests for review spam."""

from __future__ import annotations

import pytest

from reviews.models import Review
from reviews.spam import is_duplicate_or_similar_review, normalize_text


def test_normalize_text_basic():
    """Test normalize text basic.

    :return: None
    :rtype: None
    """
    assert normalize_text(" Hello,  WORLD!! ") == "hello world"


@pytest.mark.django_db
def test_duplicate_or_similarity_detection(approved_place, user):
    """Test duplicate or similarity detection.

    :param approved_place: Approved place fixture.
    :param user: User fixture.
    :return: None
    :rtype: None
    """
    Review.objects.create(
        place=approved_place,
        user=user,
        rating=4,
        text="This was an amazing location with scenic views and great facilities.",
    )
    assert is_duplicate_or_similar_review(
        approved_place,
        "This was an amazing location with scenic views and great facilities.",
    )
    assert is_duplicate_or_similar_review(
        approved_place,
        "This was an amazing location with scenic views and great facilities plus lovely atmosphere.",
    )
    assert is_duplicate_or_similar_review(
        approved_place,
        "Completely different short text",
    ) is False
