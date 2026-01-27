"""Tests for home and urls."""

from __future__ import annotations

import importlib

import pytest
from django.test.utils import override_settings
from django.urls import reverse


@pytest.mark.django_db
def test_home_for_guest_and_authenticated(client, approved_place, user):
    """Test home for guest and authenticated.

    :param client: Django test client.
    :param approved_place: Approved place fixture.
    :param user: User fixture.
    :return: None
    :rtype: None
    """
    assert client.get(reverse("home")).status_code == 200
    client.force_login(user)
    assert client.get(reverse("home")).status_code == 200


def test_policy_pages_render(client):
    """Test policy pages render.

    :param client: Django test client.
    :return: None
    :rtype: None
    """
    assert client.get(reverse("contribution_guidelines")).status_code == 200
    assert client.get(reverse("moderation_policy")).status_code == 200
    assert client.get(reverse("acceptable_use_policy")).status_code == 200


def test_community_urls_debug_static_branch():
    """Test community urls debug static branch.

    :return: None
    :rtype: None
    """
    with override_settings(DEBUG=True):
        mod = importlib.import_module("community_tourism.urls")
        importlib.reload(mod)
        assert len(mod.urlpatterns) >= 1


def test_asgi_module_loads_application():
    """Test asgi module loads application.

    :return: None
    :rtype: None
    """
    mod = importlib.import_module("community_tourism.asgi")
    importlib.reload(mod)
    assert mod.application is not None


def test_wsgi_module_loads_application():
    """Test wsgi module loads application.

    :return: None
    :rtype: None
    """
    mod = importlib.import_module("community_tourism.wsgi")
    importlib.reload(mod)
    assert mod.application is not None
