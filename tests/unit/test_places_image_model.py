"""Tests for places image model."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from django.core.exceptions import ValidationError

from places.models import PlaceImage, validate_image_size


@pytest.mark.django_db
def test_validate_image_size_blocks_large_file():
    """Test validate image size blocks large file.

    :return: None
    :rtype: None
    """
    large = SimpleNamespace(size=6 * 1024 * 1024)
    with pytest.raises(ValidationError):
        validate_image_size(large)


@pytest.mark.django_db
def test_placeimage_str(approved_place):
    """Test placeimage str.

    :param approved_place: Approved place fixture.
    :return: None
    :rtype: None
    """
    image = PlaceImage(place=approved_place)
    assert "Image for" in str(image)
