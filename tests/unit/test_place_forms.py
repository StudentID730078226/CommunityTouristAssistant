"""Tests for place forms."""

from __future__ import annotations

from places.forms import PlaceForm, PlaceOpeningHoursForm


def test_place_form_requires_both_opening_and_closing_times():
    """Test place form requires both opening and closing times.

    :return: None
    :rtype: None
    """
    form = PlaceForm(
        data={
            "name": "A",
            "description": "D",
            "category": "other",
            "location_text": "TR1",
            "opening_days_list": ["mon", "tue"],
            "place_type": "food",
            "opening_time": "09:00",
            "closing_time": "",
        }
    )
    assert form.is_valid() is False


def test_opening_hours_form_requires_both_opening_and_closing_times():
    """Test opening hours form requires both opening and closing times.

    :return: None
    :rtype: None
    """
    form = PlaceOpeningHoursForm(
        data={
            "opening_days_list": ["mon"],
            "opening_time": "",
            "closing_time": "17:00",
        }
    )
    assert form.is_valid() is False


def test_place_form_ignores_hours_for_beach_type():
    """Test place form ignores hours for beach type.

    :return: None
    :rtype: None
    """
    form = PlaceForm(
        data={
            "name": "Beach",
            "description": "D",
            "category": "beach",
            "location_text": "TR1",
            "place_type": "beach",
            "opening_days_list": ["mon"],
            "opening_time": "09:00",
            "closing_time": "17:00",
        }
    )
    assert form.is_valid() is True
    assert form.cleaned_data["opening_time"] is None
