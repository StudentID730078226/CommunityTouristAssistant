"""Tests for accounts views."""

from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test.utils import override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from places.models import Place


@pytest.mark.django_db
def test_login_invalid_credentials(client):
    """Test login invalid credentials.

    :param client: Django test client.
    :return: None
    :rtype: None
    """
    assert client.get(reverse("accounts:login")).status_code == 200
    response = client.post(reverse("accounts:login"), data={"username": "x", "password": "y"}, follow=True)
    assert response.status_code == 200
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_login_success_redirects_home(client):
    """Test login success redirects home.

    :param client: Django test client.
    :return: None
    :rtype: None
    """
    user = User.objects.create_user("activeuser", "a@a.com", "StrongPass123!", is_active=True)
    response = client.post(
        reverse("accounts:login"),
        data={"username": user.username, "password": "StrongPass123!"},
    )
    assert response.status_code == 302


@pytest.mark.django_db
def test_activate_account_invalid_token_path(client, user):
    """Test activate account invalid token path.

    :param client: Django test client.
    :param user: User fixture.
    :return: None
    :rtype: None
    """
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    response = client.get(reverse("accounts:activate", args=[uid, "bad-token"]))
    assert response.status_code == 302


@pytest.mark.django_db
def test_activate_account_invalid_uid_path(client):
    """Test activate account invalid uid path.

    :param client: Django test client.
    :return: None
    :rtype: None
    """
    response = client.get(reverse("accounts:activate", args=["not-base64", "bad-token"]))
    assert response.status_code == 302


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_signup_password_mismatch_and_existing_username(client, user):
    """Test signup password mismatch and existing username.

    :param client: Django test client.
    :param user: User fixture.
    :return: None
    :rtype: None
    """
    assert client.get(reverse("accounts:signup")).status_code == 200
    mismatch = client.post(
        reverse("accounts:signup"),
        data={
            "username": "newx",
            "email": "newx@example.com",
            "password1": "StrongPass123!",
            "password2": "DifferentPass123!",
        },
    )
    assert mismatch.status_code == 302

    existing = client.post(
        reverse("accounts:signup"),
        data={
            "username": user.username,
            "email": "dup@example.com",
            "password1": "StrongPass123!",
            "password2": "StrongPass123!",
        },
    )
    assert existing.status_code == 302
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_signup_weak_password_rejected(client):
    """Test signup weak password rejected.

    :param client: Django test client.
    :return: None
    :rtype: None
    """
    response = client.post(
        reverse("accounts:signup"),
        data={
            "username": "weakuser",
            "email": "weak@example.com",
            "password1": "123",
            "password2": "123",
        },
    )
    assert response.status_code == 302
    assert not User.objects.filter(username="weakuser").exists()


@pytest.mark.django_db
def test_login_inactive_user_branch_with_authenticate_returning_user(client, monkeypatch):
    """Test login inactive user branch with authenticate returning user.

    :param client: Django test client.
    :param monkeypatch: Pytest monkeypatch fixture.
    :return: None
    :rtype: None
    """
    inactive = User.objects.create_user(
        username="inactive-branch",
        email="inactive-branch@example.com",
        password="StrongPass123!",
        is_active=False,
    )
    monkeypatch.setattr("accounts.views.authenticate", lambda *args, **kwargs: inactive)
    response = client.post(
        reverse("accounts:login"),
        data={"username": "inactive-branch", "password": "StrongPass123!"},
    )
    assert response.status_code == 302


@pytest.mark.django_db
def test_logout_profile_contributions_and_delete_account_views(client, user):
    # Profile/contributions require login and should render.
    """Test logout profile contributions and delete account views.

    :param client: Django test client.
    :param user: User fixture.
    :return: None
    :rtype: None
    """
    Place.objects.create(
        name="Pending Place",
        description="Desc",
        category=Place.Category.OTHER,
        location_text="TR1",
        created_by=user,
        moderation_status=Place.ModerationStatus.PENDING,
    )
    Place.objects.create(
        name="Approved Place",
        description="Desc",
        category=Place.Category.OTHER,
        location_text="TR1",
        created_by=user,
        moderation_status=Place.ModerationStatus.APPROVED,
    )
    Place.objects.create(
        name="Rejected Place",
        description="Desc",
        category=Place.Category.OTHER,
        location_text="TR1",
        created_by=user,
        moderation_status=Place.ModerationStatus.REJECTED,
    )

    client.force_login(user)
    assert client.get(reverse("accounts:profile")).status_code == 200
    assert client.get(reverse("accounts:contributions")).status_code == 200
    assert client.get(reverse("accounts:delete_account")).status_code == 200

    logout_response = client.get(reverse("accounts:logout"))
    assert logout_response.status_code == 302

    client.force_login(user)
    delete_response = client.post(reverse("accounts:delete_account"))
    assert delete_response.status_code == 302
    assert not User.objects.filter(pk=user.pk).exists()
