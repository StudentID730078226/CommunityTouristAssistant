"""Views for browsing, searching, reviewing, and submitting places."""

from __future__ import annotations

from math import asin, cos, radians, sin, sqrt
from typing import Any, Dict, Optional, Tuple, Type

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Avg, Count, FloatField, Q, QuerySet, Value
from django.db.models.functions import Coalesce
from django.http import HttpRequest, HttpResponse, HttpResponseNotAllowed, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.decorators import method_decorator
from django.views import View
from django_ratelimit.decorators import ratelimit

from accounts.models import Contribution
from reviews.forms import ReviewForm
from reviews.models import Review
from reviews.spam import get_or_create_captcha, is_duplicate_or_similar_review, require_captcha, validate_captcha

from .forms import (
    ActivityPlaceForm,
    BeachPlaceForm,
    FoodPlaceForm,
    HeritagePlaceForm,
    PlaceOpeningHoursForm,
    PlaceForm,
)
from .models import (
    ActivityPlace,
    BeachPlace,
    FoodPlace,
    HeritagePlace,
    Place,
    PlaceImage,
    PlaceLike,
)
from .utils import geocode_location


ALLOWED_PER_PAGE = [5, 10, 20]
NEARBY_RADIUS_KM = 12
NEARBY_LIMIT = 8


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return straight-line distance between two coordinate points in km.

    :param lat1: Latitude of the first point.
    :param lon1: Longitude of the first point.
    :param lat2: Latitude of the second point.
    :param lon2: Longitude of the second point.
    :return: Distance in kilometers.
    :rtype: float
    """
    lat1_rad = radians(lat1)
    lon1_rad = radians(lon1)
    lat2_rad = radians(lat2)
    lon2_rad = radians(lon2)

    delta_lat = lat2_rad - lat1_rad
    delta_lon = lon2_rad - lon1_rad
    a = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lon / 2) ** 2
    c = 2 * asin(sqrt(a))
    return 6371.0 * c


def _get_nearby_places(place: Place, radius_km: int = NEARBY_RADIUS_KM, limit: int = NEARBY_LIMIT) -> list[Place]:
    """Return nearby approved places within radius, sorted by shortest distance.

    :param place: Reference place used for distance calculation.
    :param radius_km: Maximum search radius in kilometers.
    :param limit: Maximum number of places to return.
    :return: List of nearby Place instances with distance_km set.
    :rtype: list[Place]
    """
    if place.latitude is None or place.longitude is None:
        return []

    nearby_candidates = (
        Place.objects.filter(is_approved=True, is_archived=False, latitude__isnull=False, longitude__isnull=False)
        .exclude(pk=place.pk)
        .annotate(
            avg_rating=Coalesce(Avg("reviews__rating"), Value(0.0), output_field=FloatField()),
            likes_total=Count("likes", distinct=True),
        )
        .prefetch_related("images")
    )

    place_lat = float(place.latitude)
    place_lon = float(place.longitude)

    nearby_with_distance = []
    for candidate in nearby_candidates:
        distance_km = _haversine_km(place_lat, place_lon, float(candidate.latitude), float(candidate.longitude))
        if distance_km <= radius_km:
            candidate.distance_km = round(distance_km, 1)
            nearby_with_distance.append(candidate)

    nearby_with_distance.sort(key=lambda item: item.distance_km)
    return nearby_with_distance[:limit]


def _resolve_detail_type(place: Place) -> str:
    """Return a template-friendly type label based on concrete polymorphic class.

    :param place: Place instance to resolve.
    :return: Type label string for templates.
    :rtype: str
    """
    if isinstance(place, HeritagePlace):
        return "heritage"
    if isinstance(place, FoodPlace):
        return "food"
    if isinstance(place, ActivityPlace):
        return "activity"
    if isinstance(place, BeachPlace):
        return "beach"
    return "other"


@method_decorator(ratelimit(key="ip", rate="20/h", method="POST", block=False), name="dispatch")
class PlaceDetailView(View):
    """Show place details, reviews, metrics, and handle in-page review submissions."""

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        """Render a place detail page with reviews, ratings, and nearby places.

        :param request: Incoming HTTP request.
        :param pk: Place primary key.
        :return: Rendered place detail page.
        """
        place = self._get_place(pk)
        nearby_places = _get_nearby_places(place)
        detail_type = _resolve_detail_type(place)
        features = place  # Polymorphic instance already carries type-specific fields.
        user_has_liked = self._get_user_like_state(request, place)

        base_reviews_qs = self._get_base_reviews(place)
        rating_summary = self._build_rating_summary(base_reviews_qs)

        reviews_qs, rating_filter = self._apply_rating_filter(
            base_reviews_qs,
            request.GET.get("rating"),
        )
        reviews_qs, sort_option = self._apply_sort_option(
            reviews_qs,
            request.GET.get("sort", "recent"),
        )

        per_page = self._parse_per_page(request.GET.get("per_page"))
        paginator = Paginator(reviews_qs, per_page)
        reviews_page = paginator.get_page(request.GET.get("page"))

        if request.GET.get("force_captcha") == "1":
            require_captcha(request)
        captcha_required, captcha_question = get_or_create_captcha(request)
        form = self._build_review_form(request, captcha_required, captcha_question)
        can_add_opening_hours, can_edit_opening_hours = self._opening_hours_flags(request, place)

        context: Dict[str, Any] = {
            "place": place,
            "features": features,
            "detail_type": detail_type,
            "can_add_opening_hours": can_add_opening_hours,
            "can_edit_opening_hours": can_edit_opening_hours,
            "user_has_liked": user_has_liked,
            "reviews": reviews_page,
            "form": form,
            "total_reviews": rating_summary["total_reviews"],
            "average_rating": rating_summary["average_rating"],
            "rating_breakdown": rating_summary["rating_breakdown"],
            "rating_percentages": rating_summary["rating_percentages"],
            "rating_rows": rating_summary["rating_rows"],
            "rating_filter": rating_filter,
            "sort_option": sort_option,
            "per_page": per_page,
            "allowed_per_page": ALLOWED_PER_PAGE,
            "rating_stars": [5, 4, 3, 2, 1],
            "captcha_required": captcha_required,
            "captcha_question": captcha_question,
            "nearby_places": nearby_places,
            "nearby_radius_km": NEARBY_RADIUS_KM,
        }
        return render(request, "places/place_detail.html", context)

    @staticmethod
    def _get_place(pk: int) -> Place:
        """Fetch an approved, non-archived place by primary key.

        :param pk: Place primary key.
        :return: Place instance.
        :rtype: Place
        """
        return get_object_or_404(Place, pk=pk, is_approved=True, is_archived=False)

    @staticmethod
    def _get_user_like_state(request: HttpRequest, place: Place) -> bool:
        """Return True if the authenticated user has liked the place.

        :param request: Incoming HTTP request.
        :param place: Place instance.
        :return: True if liked, False otherwise.
        :rtype: bool
        """
        return request.user.is_authenticated and PlaceLike.objects.filter(
            place=place,
            user=request.user,
        ).exists()

    @staticmethod
    def _get_base_reviews(place: Place) -> QuerySet[Review]:
        """Return the base approved reviews queryset for a place.

        :param place: Place instance.
        :return: Approved reviews queryset.
        :rtype: QuerySet[Review]
        """
        return place.reviews.filter(is_approved=True, is_archived=False).select_related("user")

    @staticmethod
    def _build_rating_summary(reviews_qs: QuerySet[Review]) -> Dict[str, Any]:
        """Compute totals, averages, and per-star breakdown for reviews.

        :param reviews_qs: Reviews queryset.
        :return: Dictionary of rating summary values.
        :rtype: dict[str, Any]
        """
        total_reviews = reviews_qs.count()
        average_rating = reviews_qs.aggregate(avg=Avg("rating"))["avg"] or 0

        rating_counts = reviews_qs.values("rating").annotate(count=Count("rating"))
        rating_breakdown = {i: 0 for i in range(1, 6)}
        for item in rating_counts:
            rating_breakdown[item["rating"]] = item["count"]

        rating_percentages = {
            star: round((count / total_reviews) * 100) if total_reviews > 0 else 0
            for star, count in rating_breakdown.items()
        }
        rating_rows = [
            {"star": i, "count": rating_breakdown[i], "percent": rating_percentages[i]}
            for i in range(5, 0, -1)
        ]

        return {
            "total_reviews": total_reviews,
            "average_rating": average_rating,
            "rating_breakdown": rating_breakdown,
            "rating_percentages": rating_percentages,
            "rating_rows": rating_rows,
        }

    @staticmethod
    def _apply_rating_filter(
        reviews_qs: QuerySet[Review],
        rating_filter_raw: str | None,
    ) -> Tuple[QuerySet[Review], Optional[int]]:
        """Apply rating filter to a reviews queryset.

        :param reviews_qs: Reviews queryset to filter.
        :param rating_filter_raw: Raw rating value from query params.
        :return: Tuple of filtered queryset and parsed rating filter.
        :rtype: tuple[QuerySet[Review], int | None]
        """
        rating_filter: Optional[int] = None
        if rating_filter_raw:
            try:
                parsed = int(rating_filter_raw)
                if 1 <= parsed <= 5:
                    rating_filter = parsed
                    reviews_qs = reviews_qs.filter(rating=parsed)
            except (TypeError, ValueError):
                rating_filter = None
        return reviews_qs, rating_filter

    @staticmethod
    def _apply_sort_option(
        reviews_qs: QuerySet[Review],
        sort_option: str,
    ) -> Tuple[QuerySet[Review], str]:
        """Apply the selected sort option to the reviews queryset.

        :param reviews_qs: Reviews queryset to sort.
        :param sort_option: Sort option from query params.
        :return: Tuple of sorted queryset and normalized sort option.
        :rtype: tuple[QuerySet[Review], str]
        """
        if sort_option == "oldest":
            return reviews_qs.order_by("created_at"), sort_option
        if sort_option == "highest":
            return reviews_qs.order_by("-rating", "-created_at"), sort_option
        if sort_option == "lowest":
            return reviews_qs.order_by("rating", "-created_at"), sort_option
        return reviews_qs.order_by("-created_at"), "recent"

    @staticmethod
    def _parse_per_page(per_page_raw: str | None) -> int:
        """Parse pagination size and clamp to allowed values.

        :param per_page_raw: Raw per-page value from query params.
        :return: Validated per-page value.
        :rtype: int
        """
        try:
            per_page = int(per_page_raw or "5")
        except (TypeError, ValueError):
            per_page = 5
        if per_page not in ALLOWED_PER_PAGE:
            per_page = 5
        return per_page

    @staticmethod
    def _build_review_form(
        request: HttpRequest,
        captcha_required: bool,
        captcha_question: str | None,
    ) -> ReviewForm:
        """Build a ReviewForm with optional captcha fields.

        :param request: Incoming HTTP request.
        :param captcha_required: True if captcha is required.
        :param captcha_question: Captcha prompt text.
        :return: ReviewForm instance.
        :rtype: ReviewForm
        """
        if request.method == "POST":
            return ReviewForm(request.POST, require_captcha=captcha_required, captcha_question=captcha_question)
        return ReviewForm(require_captcha=captcha_required, captcha_question=captcha_question)

    @staticmethod
    def _opening_hours_flags(request: HttpRequest, place: Place) -> Tuple[bool, bool]:
        """Compute opening hours action flags for the current user.

        :param request: Incoming HTTP request.
        :param place: Place instance.
        :return: Tuple of (can_add_opening_hours, can_edit_opening_hours).
        :rtype: tuple[bool, bool]
        """
        can_add_opening_hours = (
            request.user.is_authenticated and place.supports_opening_hours and not place.has_opening_hours
        )
        can_edit_opening_hours = (
            request.user.is_authenticated
            and place.supports_opening_hours
            and ((not place.has_opening_hours) or request.user == place.created_by or request.user.is_staff)
        )
        return can_add_opening_hours, can_edit_opening_hours

    @staticmethod
    def _handle_review_rate_limit(request: HttpRequest, place: Place) -> HttpResponse | None:
        """Return a redirect response when rate limits require captcha.

        :param request: Incoming HTTP request.
        :param place: Place instance.
        :return: Redirect response or None.
        :rtype: HttpResponse | None
        """
        if getattr(request, "limited", False):
            require_captcha(request)
            messages.error(
                request,
                "Too many attempts detected. Please complete the security check.",
                extra_tags="review",
            )
            return redirect("places:place_detail", pk=place.pk)
        return None

    @staticmethod
    def _enforce_review_restrictions(
        request: HttpRequest,
        place: Place,
        review_text: str,
    ) -> HttpResponse | None:
        """Return a redirect response when review restrictions fail.

        :param request: Incoming HTTP request.
        :param place: Place instance.
        :param review_text: Review text from the form.
        :return: Redirect response or None.
        :rtype: HttpResponse | None
        """
        if request.user.is_authenticated:
            contribution, _ = Contribution.objects.get_or_create(user=request.user)
            if contribution.review_restriction_active:
                messages.error(
                    request,
                    "Your account is currently restricted from posting reviews.",
                    extra_tags="review",
                )
                return redirect("places:place_detail", pk=place.pk)
            if Review.objects.filter(place=place, user=request.user).exists():
                messages.error(
                    request,
                    "You have already reviewed this place.",
                    extra_tags="review",
                )
                return redirect("places:place_detail", pk=place.pk)
        else:
            reviewed_places = request.session.get("guest_reviewed_places", [])
            if place.id in reviewed_places:
                messages.error(
                    request,
                    "Guest users can only submit one review per place in this session. "
                    "Please sign in to edit or add another review.",
                    extra_tags="review",
                )
                return redirect("places:place_detail", pk=place.pk)
        if is_duplicate_or_similar_review(place, review_text):
            messages.error(
                request,
                "This review looks too similar to an existing one for this place.",
                extra_tags="review",
            )
            return redirect("places:place_detail", pk=place.pk)
        return None

    @staticmethod
    def _save_review(request: HttpRequest, place: Place, form: ReviewForm) -> HttpResponse | None:
        """Persist a review and return a redirect on success or duplicate error.

        :param request: Incoming HTTP request.
        :param place: Place instance.
        :param form: Valid ReviewForm instance.
        :return: Redirect response or None.
        :rtype: HttpResponse | None
        """
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
            return redirect("places:place_detail", pk=place.pk)

        if not request.user.is_authenticated:
            reviewed_places = request.session.get("guest_reviewed_places", [])
            if place.id not in reviewed_places:
                reviewed_places.append(place.id)
                request.session["guest_reviewed_places"] = reviewed_places
                request.session.modified = True

        messages.success(request, "Review submitted!", extra_tags="review")
        return redirect("places:place_detail", pk=place.pk)

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        """Handle review submissions from the place detail page.

        :param request: Incoming HTTP request with review form data.
        :param pk: Place primary key.
        :return: Redirect back to place detail page.
        """
        place = self._get_place(pk)
        rate_limit_response = self._handle_review_rate_limit(request, place)
        if rate_limit_response:
            return rate_limit_response

        captcha_required, captcha_question = get_or_create_captcha(request)
        form = self._build_review_form(request, captcha_required, captcha_question)
        if form.is_valid():
            if captcha_required and not validate_captcha(request, form.cleaned_data.get("captcha_answer", "")):
                messages.error(
                    request,
                    "Security answer was incorrect. Please try again.",
                    extra_tags="review",
                )
                return redirect("places:place_detail", pk=place.pk)

            restriction_response = self._enforce_review_restrictions(
                request,
                place,
                form.cleaned_data["text"],
            )
            if restriction_response:
                return restriction_response

            save_response = self._save_review(request, place, form)
            if save_response:
                return save_response

        return self.get(request, pk)


def _build_add_place_context(
    place_form: PlaceForm,
    heritage_form: HeritagePlaceForm,
    food_form: FoodPlaceForm,
    activity_form: ActivityPlaceForm,
    beach_form: BeachPlaceForm,
) -> Dict[str, Any]:
    """Build template context for the add place view.

    :param place_form: Base place form instance.
    :param heritage_form: Heritage subtype form instance.
    :param food_form: Food subtype form instance.
    :param activity_form: Activity subtype form instance.
    :param beach_form: Beach subtype form instance.
    :return: Context dictionary for template rendering.
    :rtype: dict[str, Any]
    """
    return {
        "form": place_form,
        "heritage_form": heritage_form,
        "food_form": food_form,
        "activity_form": activity_form,
        "beach_form": beach_form,
    }


@method_decorator(ratelimit(key="ip", rate="12/h", method="POST", block=False), name="dispatch")
class AddPlaceView(LoginRequiredMixin, View):
    """Create a new polymorphic place submission with optional images."""

    @staticmethod
    def _build_forms(request: HttpRequest) -> Dict[str, Any]:
        """Instantiate base and subtype forms for the add place workflow.

        :param request: Incoming HTTP request.
        :return: Dictionary containing all forms.
        :rtype: dict[str, Any]
        """
        if request.method == "POST":
            return {
                "place_form": PlaceForm(request.POST),
                "heritage_form": HeritagePlaceForm(request.POST),
                "food_form": FoodPlaceForm(request.POST),
                "activity_form": ActivityPlaceForm(request.POST),
                "beach_form": BeachPlaceForm(request.POST),
            }
        return {
            "place_form": PlaceForm(),
            "heritage_form": HeritagePlaceForm(),
            "food_form": FoodPlaceForm(),
            "activity_form": ActivityPlaceForm(),
            "beach_form": BeachPlaceForm(),
        }

    @staticmethod
    def _resolve_place_type(place_type: str | None) -> Tuple[Type[Place], Optional[Any]] | None:
        """Resolve the place subtype and related form based on the input value.

        :param place_type: Raw place type string from form data.
        :return: Tuple of place model and subtype form, or None if invalid.
        :rtype: tuple[Type[Place], Any | None] | None
        """
        form_map: Dict[str, Tuple[Type[Place], Optional[Any]]] = {
            "heritage": (HeritagePlace, None),
            "food": (FoodPlace, None),
            "activity": (ActivityPlace, None),
            "beach": (BeachPlace, None),
            "other": (Place, None),
        }
        return form_map.get(place_type or "")

    @staticmethod
    def _get_specific_form(place_type: str | None, forms: Dict[str, Any]) -> Optional[Any]:
        """Return the subtype form for the selected place type.

        :param place_type: Raw place type string from form data.
        :param forms: Dictionary of form instances.
        :return: Subtype form or None for base Place type.
        :rtype: Any | None
        """
        form_key_map = {
            "heritage": "heritage_form",
            "food": "food_form",
            "activity": "activity_form",
            "beach": "beach_form",
        }
        key = form_key_map.get(place_type or "")
        return forms.get(key) if key else None

    @staticmethod
    def _validate_forms(place_form: PlaceForm, specific_form: Optional[Any]) -> bool:
        """Validate base and subtype forms.

        :param place_form: Base place form instance.
        :param specific_form: Subtype form instance or None.
        :return: True if all forms are valid.
        :rtype: bool
        """
        is_base_valid = place_form.is_valid()
        is_specific_valid = specific_form.is_valid() if specific_form is not None else True
        return is_base_valid and is_specific_valid

    @staticmethod
    def _geocode_place(place: Place) -> Tuple[Optional[float], Optional[float]]:
        """Resolve latitude/longitude from the place address fields.

        :param place: Place instance (not yet saved).
        :return: Tuple of (lat, lng) or (None, None) if not found.
        :rtype: tuple[float | None, float | None]
        """
        geocode_query = (
            place.location_text
            or place.postcode
            or " ".join(part for part in [place.address_line_1, place.town_city, place.postcode] if part).strip()
        )
        return geocode_location(geocode_query) if geocode_query else (None, None)

    @staticmethod
    def _save_place_images(place: Place, images: list) -> None:
        """Persist uploaded images for a place.

        :param place: Place instance.
        :param images: List of uploaded image files.
        :return: None
        """
        for image in images:
            PlaceImage.objects.create(place=place, image=image)

    @staticmethod
    def _is_rate_limited(request: HttpRequest) -> bool:
        """Return True if the request is currently rate limited.

        :param request: Incoming HTTP request.
        :return: True if limited, False otherwise.
        :rtype: bool
        """
        return bool(getattr(request, "limited", False))

    def get(self, request: HttpRequest) -> HttpResponse:
        """Render an empty add-place form for authenticated users.

        :param request: Incoming HTTP request.
        :return: Rendered add place page.
        """
        forms = self._build_forms(request)
        return render(
            request,
            "places/add_place.html",
            _build_add_place_context(
                forms["place_form"],
                forms["heritage_form"],
                forms["food_form"],
                forms["activity_form"],
                forms["beach_form"],
            ),
        )

    def post(self, request: HttpRequest) -> HttpResponse:
        """Handle add-place form submission and persist the new place.

        :param request: Incoming HTTP request with form data and files.
        :return: Redirect to place list on success or re-render form on error.
        """
        forms = self._build_forms(request)
        place_form = forms["place_form"]
        heritage_form = forms["heritage_form"]
        food_form = forms["food_form"]
        activity_form = forms["activity_form"]
        beach_form = forms["beach_form"]

        if self._is_rate_limited(request):
            messages.error(request, "Too many place submissions. Please wait and try again.")
            return render(
                request,
                "places/add_place.html",
                _build_add_place_context(place_form, heritage_form, food_form, activity_form, beach_form),
            )
        place_type = request.POST.get("place_type")

        place_model_entry = self._resolve_place_type(place_type)
        if place_model_entry is None:
            messages.error(request, "Please select a place type.")
            return render(
                request,
                "places/add_place.html",
                _build_add_place_context(place_form, heritage_form, food_form, activity_form, beach_form),
            )

        place_model, _ = place_model_entry
        specific_form = self._get_specific_form(place_type, forms)
        if not self._validate_forms(place_form, specific_form):
            messages.error(request, "Please correct the errors below.")
            return render(
                request,
                "places/add_place.html",
                _build_add_place_context(place_form, heritage_form, food_form, activity_form, beach_form),
            )

        with transaction.atomic():
            specific_data = specific_form.cleaned_data if specific_form is not None else {}
            place_data = dict(place_form.cleaned_data)
            place_data.pop("opening_days_list", None)
            place = place_model(
                **place_data,
                **specific_data,
                created_by=request.user,
                moderation_status=Place.ModerationStatus.PENDING,
            )

            lat, lng = self._geocode_place(place)
            if lat is None or lng is None:
                messages.error(request, "We couldn't find that location.")
                return render(
                    request,
                    "places/add_place.html",
                    _build_add_place_context(place_form, heritage_form, food_form, activity_form, beach_form),
                )

            place.latitude = lat
            place.longitude = lng
            place.save()

            images = request.FILES.getlist("images")
            if len(images) > 30:
                messages.error(request, "Maximum 30 images are allowed.")
                return render(
                    request,
                    "places/add_place.html",
                    _build_add_place_context(place_form, heritage_form, food_form, activity_form, beach_form),
                )

            self._save_place_images(place, images)

        messages.success(request, "Place submitted successfully and is pending approval.")
        return redirect("places:search_places")


class SearchPlacesView(View):
    """Search approved places with richer filtering, sorting, and pagination."""

    @staticmethod
    def _apply_text_filter(places: QuerySet[Place], query: str) -> QuerySet[Place]:
        """Apply free-text search across name, description, and location fields.

        :param places: Base queryset.
        :param query: Search query string.
        :return: Filtered queryset.
        :rtype: QuerySet[Place]
        """
        if not query:
            return places
        return places.filter(
            Q(name__icontains=query)
            | Q(description__icontains=query)
            | Q(location_text__icontains=query)
            | Q(town_city__icontains=query)
            | Q(postcode__icontains=query)
        )

    @staticmethod
    def _base_queryset() -> QuerySet[Place]:
        """Return the base queryset for approved, non-archived places.

        :return: Annotated queryset with rating and image counts.
        :rtype: QuerySet[Place]
        """
        return (
            Place.objects.filter(is_approved=True, is_archived=False)
            .annotate(
                avg_rating=Coalesce(Avg("reviews__rating"), Value(0.0), output_field=FloatField()),
                likes_total=Count("likes", distinct=True),
                reviews_total=Count("reviews", distinct=True),
                images_total=Count("images", distinct=True),
            )
            .prefetch_related("images")
        )

    @staticmethod
    def _apply_category_filter(places: QuerySet[Place], category: str | None) -> QuerySet[Place]:
        """Apply category filter when provided.

        :param places: Base queryset.
        :param category: Category filter value.
        :return: Filtered queryset.
        :rtype: QuerySet[Place]
        """
        return places.filter(category=category) if category else places

    @staticmethod
    def _apply_min_rating_filter(places: QuerySet[Place], min_rating: str | None) -> QuerySet[Place]:
        """Apply minimum rating filter when valid.

        :param places: Base queryset.
        :param min_rating: Raw minimum rating value.
        :return: Filtered queryset.
        :rtype: QuerySet[Place]
        """
        if not min_rating:
            return places
        try:
            rating_value = int(min_rating)
        except (TypeError, ValueError):
            return places
        if 1 <= rating_value <= 5:
            return places.filter(avg_rating__gte=rating_value)
        return places

    @staticmethod
    def _apply_images_filter(places: QuerySet[Place], has_images: str | None) -> QuerySet[Place]:
        """Filter places to those with images when requested.

        :param places: Base queryset.
        :param has_images: Raw has-images flag.
        :return: Filtered queryset.
        :rtype: QuerySet[Place]
        """
        return places.filter(images_total__gt=0) if has_images == "1" else places

    @staticmethod
    def _apply_sort(places: QuerySet[Place], sort: str) -> Tuple[QuerySet[Place], str]:
        """Apply a sort option to the queryset.

        :param places: Base queryset.
        :param sort: Raw sort option string.
        :return: Tuple of sorted queryset and normalized sort value.
        :rtype: tuple[QuerySet[Place], str]
        """
        sort_map = {
            "top_rated": ["-avg_rating", "-likes_total", "name"],
            "most_liked": ["-likes_total", "-avg_rating", "name"],
            "newest": ["-created_at"],
            "name_az": ["name"],
            "rating_low_high": ["avg_rating", "-likes_total", "name"],
        }
        normalized = sort if sort in sort_map else "top_rated"
        return places.order_by(*sort_map[normalized]), normalized

    @staticmethod
    def _apply_open_now_filter(places: QuerySet[Place], open_now: str | None) -> list[Place] | QuerySet[Place]:
        """Filter places by opening hours status when requested.

        :param places: Base queryset.
        :param open_now: Raw open-now flag.
        :return: Filtered list or queryset.
        :rtype: list[Place] | QuerySet[Place]
        """
        if open_now != "1":
            return places
        places = places.exclude(category=Place.Category.BEACH).filter(
            opening_time__isnull=False,
            closing_time__isnull=False,
        )
        return [place for place in places if place.is_open_now is True]

    @staticmethod
    def _parse_per_page(per_page_raw: str | None) -> int:
        """Parse pagination size and clamp to supported values.

        :param per_page_raw: Raw per-page value.
        :return: Validated per-page size.
        :rtype: int
        """
        try:
            per_page = int(per_page_raw or "12")
        except (TypeError, ValueError):
            per_page = 12
        if per_page not in [6, 12, 24]:
            per_page = 12
        return per_page

    def get(self, request: HttpRequest) -> HttpResponse:
        """Render the search page with filtered and sorted results.

        :param request: Incoming HTTP request with filter query params.
        :return: Rendered search results page.
        """
        places = self._base_queryset()

        q = (request.GET.get("q") or "").strip()
        category = request.GET.get("category")
        min_rating = request.GET.get("min_rating")
        has_images = request.GET.get("has_images")
        open_now = request.GET.get("open_now")
        sort = (request.GET.get("sort") or "top_rated").strip()

        places = self._apply_text_filter(places, q)
        places = self._apply_category_filter(places, category)
        places = self._apply_min_rating_filter(places, min_rating)
        places = self._apply_images_filter(places, has_images)
        places, sort = self._apply_sort(places, sort)
        places_list = self._apply_open_now_filter(places, open_now)

        per_page = self._parse_per_page(request.GET.get("per_page"))

        paginator = Paginator(places_list, per_page)
        page_obj = paginator.get_page(request.GET.get("page"))

        return render(
            request,
            "places/search.html",
            {
                "places": page_obj,
                "categories": Place.Category.choices,
                "q": q,
                "selected_category": category or "",
                "selected_min_rating": min_rating or "",
                "selected_has_images": has_images == "1",
                "selected_open_now": open_now == "1",
                "selected_sort": sort,
                "selected_per_page": per_page,
                "per_page_options": [6, 12, 24],
            },
        )


class EditOpeningHoursView(LoginRequiredMixin, View):
    """Allow logged-in users to add opening hours when missing; owners/staff can update."""

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        """Render the opening hours edit form when user has permission.

        :param request: Incoming HTTP request.
        :param pk: Place primary key.
        :return: Rendered opening hours edit page or redirect on error.
        """
        place = get_object_or_404(Place, pk=pk, is_approved=True, is_archived=False)
        if not place.supports_opening_hours:
            messages.error(request, "Opening hours are not applicable for this place type.")
            return redirect("places:place_detail", pk=pk)

        can_edit = (not place.has_opening_hours) or request.user == place.created_by or request.user.is_staff
        if not can_edit:
            messages.error(request, "Opening hours are already set for this place.")
            return redirect("places:place_detail", pk=pk)

        form = PlaceOpeningHoursForm(instance=place)
        return render(request, "places/edit_opening_hours.html", {"place": place, "form": form})

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        """Handle opening hours updates and persist changes.

        :param request: Incoming HTTP request with opening hour data.
        :param pk: Place primary key.
        :return: Redirect to place detail on success or re-render form on error.
        """
        place = get_object_or_404(Place, pk=pk, is_approved=True, is_archived=False)
        if not place.supports_opening_hours:
            messages.error(request, "Opening hours are not applicable for this place type.")
            return redirect("places:place_detail", pk=pk)

        can_edit = (not place.has_opening_hours) or request.user == place.created_by or request.user.is_staff
        if not can_edit:
            messages.error(request, "Opening hours are already set for this place.")
            return redirect("places:place_detail", pk=pk)

        form = PlaceOpeningHoursForm(request.POST, instance=place)
        if form.is_valid():
            form.save()
            messages.success(request, "Opening hours saved.")
            return redirect("places:place_detail", pk=pk)
        messages.error(request, "Please correct the opening hours details.")
        return render(request, "places/edit_opening_hours.html", {"place": place, "form": form})


class ToggleLikeView(LoginRequiredMixin, View):
    """Toggle like state for a place. Returns JSON for AJAX requests."""

    def post(self, request: HttpRequest, pk: int) -> HttpResponse:
        """Toggle the current user's like for a place.

        :param request: Incoming HTTP request.
        :param pk: Place primary key.
        :return: JSON response for AJAX or redirect for standard requests.
        """
        place = get_object_or_404(Place, pk=pk, is_approved=True, is_archived=False)

        like_qs = PlaceLike.objects.filter(place=place, user=request.user)
        if like_qs.exists():
            like_qs.delete()
            liked = False
        else:
            PlaceLike.objects.create(place=place, user=request.user)
            liked = True

        if request.headers.get("x-requested-with") == "XMLHttpRequest":
            return JsonResponse({"liked": liked, "likes_count": place.likes_count})

        return redirect("places:place_detail", pk=pk)

    def get(self, request: HttpRequest, pk: int) -> HttpResponse:
        """Disallow GET on like toggles.

        :param request: Incoming HTTP request.
        :param pk: Place primary key.
        :return: HTTP 405 response.
        """
        return HttpResponseNotAllowed(["POST"])
