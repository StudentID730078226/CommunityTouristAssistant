"""Views for listing reviews, creating reviews, and reporting abusive reviews."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.http import require_POST
from django_ratelimit.decorators import ratelimit

from accounts.models import Contribution
from places.models import Place

from .forms import ReviewForm
from .models import Review, ReviewReport
from .spam import get_or_create_captcha, is_duplicate_or_similar_review, require_captcha, validate_captcha


class PlaceReviewsView(View):
    """Render approved reviews for a specific place."""

    def get(self, request: HttpRequest, place_id: int) -> HttpResponse:
        """Render the reviews list for a place."""
        place = get_object_or_404(Place, id=place_id, is_archived=False)
        reviews = place.reviews.filter(is_approved=True, is_archived=False)
        return render(request, "reviews/place_reviews.html", {"place": place, "reviews": reviews})


def _rate_limit_requires_captcha(request: HttpRequest) -> bool:
    """Return True when a rate limit has been hit for a POST request."""
    return bool(getattr(request, "limited", False) and request.method == "POST")


def _build_review_form(
    request: HttpRequest,
    captcha_required: bool,
    captcha_question: str | None,
) -> ReviewForm:
    """Create a ReviewForm with the correct captcha parameters."""
    if request.method == "POST":
        return ReviewForm(
            request.POST,
            require_captcha=captcha_required,
            captcha_question=captcha_question,
        )
    return ReviewForm(require_captcha=captcha_required, captcha_question=captcha_question)


def _handle_captcha_failure(request: HttpRequest, place_id: int) -> HttpResponse:
    """Add a message and redirect when the captcha answer is invalid."""
    messages.error(
        request,
        "Security answer was incorrect. Please try again.",
        extra_tags="review",
    )
    return redirect("reviews:add_review", place_id=place_id)


def _enforce_review_restrictions(
    request: HttpRequest,
    place: Place,
    review_text: str,
) -> HttpResponse | None:
    """Return a redirect response if any review restriction fails."""
    if request.user.is_authenticated:
        contribution, _ = Contribution.objects.get_or_create(user=request.user)
        if contribution.review_restriction_active:
            messages.error(
                request,
                "Your account is currently restricted from posting reviews.",
                extra_tags="review",
            )
            return redirect("places:place_detail", pk=place.id)

        if Review.objects.filter(place=place, user=request.user, is_archived=False).exists():
            messages.error(
                request,
                "You have already reviewed this place.",
                extra_tags="review",
            )
            return redirect("places:place_detail", pk=place.id)
    else:
        reviewed_places = request.session.get("guest_reviewed_places", [])
        if place.id in reviewed_places:
            messages.error(
                request,
                "Guest users can only submit one review per place in this session. "
                "Please sign in to edit or add another review.",
                extra_tags="review",
            )
            return redirect("places:place_detail", pk=place.id)

    if is_duplicate_or_similar_review(place, review_text):
        messages.error(
            request,
            "This review looks too similar to an existing one for this place.",
            extra_tags="review",
        )
        return redirect("places:place_detail", pk=place.id)

    return None


def _save_review(request: HttpRequest, place: Place, form: ReviewForm) -> HttpResponse | None:
    """Persist a review and handle duplicate integrity errors."""
    review = form.save(commit=False)
    review.place = place
    if request.user.is_authenticated:
        review.user = request.user

    try:
        review.save()
    except IntegrityError:
        messages.error(
            request,
            "You have already reviewed this place.",
            extra_tags="review",
        )
        return redirect("places:place_detail", pk=place.id)

    if not request.user.is_authenticated:
        reviewed_places = request.session.get("guest_reviewed_places", [])
        if place.id not in reviewed_places:
            reviewed_places.append(place.id)
            request.session["guest_reviewed_places"] = reviewed_places
            request.session.modified = True

    messages.success(request, "Review submitted successfully!", extra_tags="review")
    return redirect("places:place_detail", pk=place.id)


@method_decorator(ratelimit(key="ip", rate="20/h", method="POST", block=False), name="dispatch")
class AddReviewView(View):
    """Create a review for a place with duplicate and restriction safeguards."""

    def get(self, request: HttpRequest, place_id: int) -> HttpResponse:
        """Render the review form.

        :param request: Incoming HTTP request.
        :param place_id: Place primary key.
        :return: Rendered review form response.
        :rtype: HttpResponse
        """
        place = get_object_or_404(Place, id=place_id, is_archived=False)
        if request.GET.get("force_captcha") == "1":
            require_captcha(request)
        captcha_required, captcha_question = get_or_create_captcha(request)
        form = _build_review_form(request, captcha_required, captcha_question)
        return render(
            request,
            "reviews/add_review.html",
            {
                "form": form,
                "place": place,
                "captcha_required": captcha_required,
                "captcha_question": captcha_question,
            },
        )

    def post(self, request: HttpRequest, place_id: int) -> HttpResponse:
        """Handle a review submission.

        :param request: Incoming HTTP request with review form data.
        :param place_id: Place primary key.
        :return: Redirect to place detail or re-render the form on error.
        :rtype: HttpResponse
        """
        place = get_object_or_404(Place, id=place_id, is_archived=False)

        if _rate_limit_requires_captcha(request):
            require_captcha(request)
            messages.error(
                request,
                "Too many attempts detected. Please complete the security check.",
                extra_tags="review",
            )
            return redirect("reviews:add_review", place_id=place.id)

        captcha_required, captcha_question = get_or_create_captcha(request)
        form = _build_review_form(request, captcha_required, captcha_question)

        if form.is_valid():
            if captcha_required and not validate_captcha(request, form.cleaned_data.get("captcha_answer", "")):
                return _handle_captcha_failure(request, place.id)

            restriction_response = _enforce_review_restrictions(
                request,
                place,
                form.cleaned_data["text"],
            )
            if restriction_response:
                return restriction_response

            save_response = _save_review(request, place, form)
            if save_response:
                return save_response

        return render(
            request,
            "reviews/add_review.html",
            {
                "form": form,
                "place": place,
                "captcha_required": captcha_required,
                "captcha_question": captcha_question,
            },
        )


@method_decorator(ratelimit(key="ip", rate="30/h", method="POST", block=False), name="dispatch")
@method_decorator(require_POST, name="dispatch")
class ReportReviewView(LoginRequiredMixin, View):
    """Log a user report for a review and flag it for moderation."""

    def post(self, request: HttpRequest, review_id: int) -> HttpResponse:
        """Handle review report submissions.

        :param request: Incoming HTTP request with a report reason.
        :param review_id: Review primary key.
        :return: Redirect back to the place detail page.
        :rtype: HttpResponse
        """
        review = get_object_or_404(Review, id=review_id, is_archived=False)
        if getattr(request, "limited", False):
            messages.error(
                request,
                "Too many report attempts. Please wait before submitting another report.",
                extra_tags="report",
            )
            return redirect("places:place_detail", pk=review.place.pk)

        if review.user == request.user:
            messages.error(request, "You cannot report your own review.", extra_tags="report")
            return redirect("places:place_detail", pk=review.place.pk)

        report, created = ReviewReport.objects.get_or_create(
            review=review,
            reporter=request.user,
            defaults={"reason": request.POST.get("reason", "")[:255]},
        )
        if not created:
            messages.info(request, "You have already reported this review.", extra_tags="report")
            return redirect("places:place_detail", pk=review.place.pk)

        review.reported = True
        review.report_reason = report.reason
        review.save(update_fields=["reported", "report_reason"])

        messages.success(request, "Review reported for moderation.", extra_tags="report")
        return redirect("places:place_detail", pk=review.place.pk)
