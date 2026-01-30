"""Views for account authentication, activation, profile, and account management."""

from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db.models import Avg, Count
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from django.views import View

from places.models import Place

from .models import Contribution


class LoginView(View):
    """Sign in an existing user account."""

    template_name = "accounts/login.html"

    @staticmethod
    def _build_context() -> dict[str, dict[str, str]]:
        """Return initial form data and error containers.

        :return: Context dictionary with form defaults and errors.
        :rtype: dict[str, dict[str, str]]
        """
        return {
            "form_data": {"username": ""},
            "form_errors": {},
        }

    def get(self, request: HttpRequest) -> HttpResponse:
        """Render the login page."""
        return render(request, self.template_name, self._build_context())

    def post(self, request: HttpRequest) -> HttpResponse:
        """Authenticate a user and redirect on success."""
        context = self._build_context()
        username = request.POST.get("username", "")
        password = request.POST.get("password", "")
        context["form_data"]["username"] = username

        user = authenticate(request, username=username, password=password)
        if user:
            if not user.is_active:
                context["form_errors"]["non_field"] = "Please activate your account via email."
                return render(request, self.template_name, context)
            login(request, user)
            messages.success(request, "You are now logged in.")
            return redirect("home")

        context["form_errors"]["non_field"] = "Invalid username or password."
        return render(request, self.template_name, context)


class SignupView(View):
    """Create an inactive account and email an activation link."""

    template_name = "accounts/signup.html"

    @staticmethod
    def _build_context() -> dict[str, dict[str, str]]:
        """Return initial form data and error containers.

        :return: Context dictionary with form defaults and errors.
        :rtype: dict[str, dict[str, str]]
        """
        return {
            "form_data": {"username": "", "email": ""},
            "form_errors": {},
        }

    def get(self, request: HttpRequest) -> HttpResponse:
        """Render the signup page."""
        return render(request, self.template_name, self._build_context())

    def post(self, request: HttpRequest) -> HttpResponse:
        """Validate signup details, create user, and send activation email."""
        context = self._build_context()
        username = request.POST.get("username", "")
        email = request.POST.get("email", "")
        password1 = request.POST.get("password1", "")
        password2 = request.POST.get("password2", "")
        context["form_data"]["username"] = username
        context["form_data"]["email"] = email

        form_errors = context["form_errors"]

        if password1 != password2:
            form_errors["password2"] = "Passwords do not match."

        try:
            validate_password(password1)
        except ValidationError as exc:
            form_errors["password1"] = " ".join(exc.messages)

        if User.objects.filter(username=username).exists():
            form_errors["username"] = "Username already exists."

        if User.objects.filter(email=email).exists():
            form_errors["email"] = "Email address already in use."

        if form_errors:
            return render(request, self.template_name, context)

        user = User.objects.create_user(
            username=username,
            email=email,
            password=password1,
            is_active=False,
        )

        token = default_token_generator.make_token(user)
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        activation_link = request.build_absolute_uri(reverse("accounts:activate", args=[uid, token]))

        send_mail(
            subject="Activate your account",
            message=f"Click the link to activate your account:\n{activation_link}",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )

        messages.success(request, "Account created! Check your email to activate your account.")
        return redirect("accounts:login")


class ActivateAccountView(View):
    """Activate a newly created account using a time-limited token link."""

    def get(self, request: HttpRequest, uidb64: str, token: str) -> HttpResponse:
        """Activate a user account or show a failure message."""
        try:
            uid = urlsafe_base64_decode(uidb64).decode()
            user = User.objects.get(pk=uid)
        except (TypeError, ValueError, User.DoesNotExist):
            user = None

        if user and default_token_generator.check_token(user, token):
            user.is_active = True
            user.save(update_fields=["is_active"])
            messages.success(request, "Your account has been activated! You can now log in.")
        else:
            messages.error(request, "Activation link is invalid or expired.")

        return redirect("accounts:login")


class LogoutView(LoginRequiredMixin, View):
    """Log out the current user."""

    def get(self, request: HttpRequest) -> HttpResponse:
        """Log out and redirect to the home page."""
        logout(request)
        messages.info(request, "You have been logged out.")
        return redirect("home")


class ProfileView(LoginRequiredMixin, View):
    """Show profile details, contribution stats, and moderation outcomes."""

    def get(self, request: HttpRequest) -> HttpResponse:
        """Render the profile page for the authenticated user."""
        contribution, _ = Contribution.objects.get_or_create(user=request.user)

        submitted_places = Place.objects.filter(created_by=request.user).order_by("-created_at")
        pending_places = submitted_places.filter(moderation_status=Place.ModerationStatus.PENDING)
        approved_places = submitted_places.filter(moderation_status=Place.ModerationStatus.APPROVED)
        rejected_places = submitted_places.filter(moderation_status=Place.ModerationStatus.REJECTED)
        liked_places = (
            Place.objects.filter(likes__user=request.user, is_approved=True, is_archived=False)
            .annotate(avg_rating=Avg("reviews__rating"), likes_total=Count("likes", distinct=True))
            .prefetch_related("images")
            .distinct()
        )

        context = {
            "user": request.user,
            "contribution": contribution,
            "submitted_places": submitted_places,
            "pending_places": pending_places,
            "approved_places": approved_places,
            "rejected_places": rejected_places,
            "liked_places": liked_places,
        }
        return render(request, "accounts/profile.html", context)


class ContributionsView(LoginRequiredMixin, View):
    """Render detailed contribution stats page."""

    def get(self, request: HttpRequest) -> HttpResponse:
        """Render the contribution summary page."""
        contribution, _ = Contribution.objects.get_or_create(user=request.user)
        return render(request, "accounts/contributions.html", {"contribution": contribution})


class DeleteAccountView(LoginRequiredMixin, View):
    """Allow users to permanently delete their own account."""

    def get(self, request: HttpRequest) -> HttpResponse:
        """Render the delete account confirmation page."""
        return render(request, "accounts/delete_account.html")

    def post(self, request: HttpRequest) -> HttpResponse:
        """Delete the account and redirect to the place list."""
        user = request.user
        logout(request)
        user.delete()
        messages.success(request, "Your account has been deleted.")
        return redirect("places:search_places")
