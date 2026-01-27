"""Tests for accounts auth."""

from __future__ import annotations

import pytest
from django.contrib.auth.models import User
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.test.utils import override_settings
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


@pytest.mark.django_db
@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
def test_signup_creates_inactive_user_and_sends_activation_email(client):
    """Test signup creates inactive user and sends activation email.

    :param client: Django test client.
    :return: None
    :rtype: None
    """
    response = client.post(
        reverse("accounts:signup"),
        data={
            "username": "newuser",
            "email": "newuser@example.com",
            "password1": "StrongPass123!",
            "password2": "StrongPass123!",
        },
    )
    assert response.status_code == 302

    user = User.objects.get(username="newuser")
    assert user.is_active is False
    assert len(mail.outbox) == 1
    assert "Activate your account" in mail.outbox[0].subject


@pytest.mark.django_db
def test_activate_account_marks_user_active(client):
    """Test activate account marks user active.

    :param client: Django test client.
    :return: None
    :rtype: None
    """
    user = User.objects.create_user(
        username="inactive_user",
        email="inactive@example.com",
        password="StrongPass123!",
        is_active=False,
    )
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)

    response = client.get(reverse("accounts:activate", args=[uid, token]))
    assert response.status_code == 302
    user.refresh_from_db()
    assert user.is_active is True


@pytest.mark.django_db
def test_inactive_user_cannot_log_in(client):
    """Test inactive user cannot log in.

    :param client: Django test client.
    :return: None
    :rtype: None
    """
    User.objects.create_user(
        username="inactive_login",
        email="inactive_login@example.com",
        password="StrongPass123!",
        is_active=False,
    )
    response = client.post(
        reverse("accounts:login"),
        data={"username": "inactive_login", "password": "StrongPass123!"},
        follow=True,
    )
    assert response.status_code == 200
    assert "_auth_user_id" not in client.session
