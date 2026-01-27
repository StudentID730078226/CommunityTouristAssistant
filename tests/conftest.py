"""Tests for conftest."""

from __future__ import annotations

import pytest
from django.contrib.auth.models import User

from places.models import Place


@pytest.fixture
def user(db) -> User:
    """Provide user fixture.

    :param db: Database access fixture.
    :return: None
    :rtype: None
    """
    return User.objects.create_user(username="alice", email="alice@example.com", password="test-pass-123")


@pytest.fixture
def another_user(db) -> User:
    """Provide another user fixture.

    :param db: Database access fixture.
    :return: None
    :rtype: None
    """
    return User.objects.create_user(username="bob", email="bob@example.com", password="test-pass-123")


@pytest.fixture
def approved_place(db, user: User) -> Place:
    """Provide approved place fixture.

    :param db: Database access fixture.
    :param user: User fixture.
    :return: None
    :rtype: None
    """
    return Place.objects.create(
        name="Harbor Walk",
        description="A scenic route",
        category=Place.Category.OTHER,
        location_text="TR1 1AA",
        latitude=50.1,
        longitude=-5.1,
        created_by=user,
        moderation_status=Place.ModerationStatus.APPROVED,
    )
