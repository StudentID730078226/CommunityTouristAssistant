"""Tests for contribution levels."""

from __future__ import annotations

import pytest

from accounts.models import Contribution


@pytest.mark.django_db
def test_contribution_level_and_progress(user):
    """Test contribution level and progress.

    :param user: User fixture.
    :return: None
    :rtype: None
    """
    contribution = Contribution.objects.get(user=user)
    assert contribution.level_name == "New Explorer"
    assert contribution.points_to_next_level == 50

    contribution.points = 130
    contribution.save(update_fields=["points"])
    contribution.refresh_from_db()

    assert contribution.level_name == "Trusted Guide"
    assert contribution.is_trusted() is True
    assert contribution.next_level_name == "Community Champion"
    assert contribution.points_to_next_level == 120
    assert 0 <= contribution.level_progress_percent <= 100


@pytest.mark.django_db
def test_contribution_top_level_and_edge_progress(user):
    """Test contribution top level and edge progress.

    :param user: User fixture.
    :return: None
    :rtype: None
    """
    contribution = Contribution.objects.get(user=user)
    contribution.points = 1000
    contribution.save(update_fields=["points"])
    contribution.refresh_from_db()

    assert contribution.next_level_name is None
    assert contribution.points_to_next_level == 0
    assert contribution.level_progress_percent == 100

    # Force zero-span thresholds to hit defensive branch.
    old_levels = Contribution.LEVELS
    Contribution.LEVELS = [(0, "Start", "secondary"), (0, "Next", "info")]
    try:
        assert contribution.level_progress_percent == 100
    finally:
        Contribution.LEVELS = old_levels


@pytest.mark.django_db
def test_contribution_str_and_defensive_zero_span_branch(user):
    """Test contribution str and defensive zero span branch.

    :param user: User fixture.
    :return: None
    :rtype: None
    """
    contribution = Contribution.objects.get(user=user)
    contribution.points = -20
    contribution.save(update_fields=["points"])

    old_levels = Contribution.LEVELS
    Contribution.LEVELS = [(0, "Start", "secondary"), (-10, "Next", "info")]
    try:
        assert contribution.level_progress_percent == 100
        assert str(contribution) == f"{user.username} ({contribution.points} pts)"
    finally:
        Contribution.LEVELS = old_levels
