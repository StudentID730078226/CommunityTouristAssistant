"""Tests for template tags."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from accounts.templatetags.profile_tags import user_badge, user_status


def test_user_status_and_badge_for_user_without_contribution():
    """Test user status and badge for user without contribution.

    :return: None
    :rtype: None
    """
    anon_like = SimpleNamespace()
    text = user_status(anon_like)
    badge = user_badge(anon_like)
    assert isinstance(text, str)
    assert "Explorer" in text
    assert "badge" in str(badge)


@pytest.mark.django_db
def test_user_status_and_badge_for_high_level_user(user):
    """Test user status and badge for high level user.

    :param user: User fixture.
    :return: None
    :rtype: None
    """
    contribution = user.contribution
    contribution.points = 300
    contribution.save(update_fields=["points"])

    assert user_status(user) == "Community Champion"
    assert "Community Champion" in str(user_badge(user))
