"""Tests for places utils."""

from __future__ import annotations

from types import SimpleNamespace

from places.utils import geocode_location


def test_geocode_location_non_200_response(monkeypatch):
    """Test geocode location non 200 response.

    :param monkeypatch: Pytest monkeypatch fixture.
    :return: None
    :rtype: None
    """
    monkeypatch.setattr("places.utils.requests.get", lambda *args, **kwargs: SimpleNamespace(status_code=500, json=lambda: {}))
    assert geocode_location("TR1") == (None, None)


def test_geocode_location_missing_result(monkeypatch):
    """Test geocode location missing result.

    :param monkeypatch: Pytest monkeypatch fixture.
    :return: None
    :rtype: None
    """
    monkeypatch.setattr(
        "places.utils.requests.get",
        lambda *args, **kwargs: SimpleNamespace(status_code=200, json=lambda: {"status": 200, "result": None}),
    )
    assert geocode_location("TR1") == (None, None)


def test_geocode_location_api_status_failure(monkeypatch):
    """Test geocode location api status failure.

    :param monkeypatch: Pytest monkeypatch fixture.
    :return: None
    :rtype: None
    """
    monkeypatch.setattr(
        "places.utils.requests.get",
        lambda *args, **kwargs: SimpleNamespace(status_code=200, json=lambda: {"status": 404, "result": {}}),
    )
    assert geocode_location("TR1") == (None, None)


def test_geocode_location_success(monkeypatch):
    """Test geocode location success.

    :param monkeypatch: Pytest monkeypatch fixture.
    :return: None
    :rtype: None
    """
    monkeypatch.setattr(
        "places.utils.requests.get",
        lambda *args, **kwargs: SimpleNamespace(
            status_code=200,
            json=lambda: {"status": 200, "result": {"latitude": 50.2, "longitude": -5.2}},
        ),
    )
    assert geocode_location("TR1") == (50.2, -5.2)
