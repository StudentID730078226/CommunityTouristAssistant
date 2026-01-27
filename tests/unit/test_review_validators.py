"""Tests for review validators."""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError

from reviews.validators import validate_review_language


def test_review_language_validator_blocks_banned_word():
    """Test review language validator blocks banned word.

    :return: None
    :rtype: None
    """
    with pytest.raises(ValidationError):
        validate_review_language("This contains badword1 in text")


def test_review_language_validator_blocks_excessive_links():
    """Test review language validator blocks excessive links.

    :return: None
    :rtype: None
    """
    with pytest.raises(ValidationError):
        validate_review_language("http://a.com http://b.com http://c.com")


def test_review_language_validator_accepts_clean_text():
    """Test review language validator accepts clean text.

    :return: None
    :rtype: None
    """
    validate_review_language("Lovely place with friendly staff and clean paths.")


def test_review_language_validator_blocks_too_long_text():
    """Test review language validator blocks too long text.

    :return: None
    :rtype: None
    """
    with pytest.raises(ValidationError):
        validate_review_language("a" * 1201)
