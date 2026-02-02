"""Models for places, place types, images, and likes."""

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Avg
from django.utils import timezone
from polymorphic.models import PolymorphicModel


class Place(PolymorphicModel):
    """Base model for all place types with shared attributes and moderation fields."""
    class Category(models.TextChoices):
        HERITAGE = "heritage", "Heritage"
        BEACH = "beach", "Beach / Lake"
        PARK = "park", "Park"
        BEAUTY = "beauty", "Beauty Spot"
        NIGHTLIFE = "nightlife", "Nightlife"
        FOOD = "food", "Food & Drink"
        ACTIVITY = "activity", "Activity"
        OTHER = "other", "Other"

    class ModerationStatus(models.TextChoices):
        PENDING = "pending", "Pending Review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    name = models.CharField(max_length=200)
    description = models.TextField()
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.OTHER)
    location_text = models.CharField(max_length=255, help_text="Postcode or address", blank=True)
    address_line_1 = models.CharField(max_length=255, blank=True)
    address_line_2 = models.CharField(max_length=255, blank=True)
    town_city = models.CharField(max_length=100, blank=True)
    postcode = models.CharField(max_length=20, blank=True)
    website_url = models.URLField(blank=True)
    phone_number = models.CharField(max_length=30, blank=True)
    accessibility_info = models.TextField(blank=True, help_text="Wheelchair access, step-free notes, toilets, etc.")
    transport_info = models.TextField(blank=True, help_text="Public transport tips and nearest stops.")
    parking_info = models.CharField(max_length=255, blank=True)
    best_time_to_visit = models.CharField(max_length=100, blank=True, help_text="e.g. Early morning, sunset, summer.")
    child_friendly = models.BooleanField(default=False)
    pet_friendly = models.BooleanField(default=False)
    estimated_visit_minutes = models.PositiveIntegerField(null=True, blank=True)
    opening_days = models.CharField(
        max_length=120,
        blank=True,
        help_text="Optional. Example: Mon-Sun, Mon-Fri, Sat-Sun, or Mon,Wed,Fri",
    )
    opening_time = models.TimeField(null=True, blank=True)
    closing_time = models.TimeField(null=True, blank=True)
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_places",
    )
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="archived_places",
    )
    is_approved = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    moderation_status = models.CharField(
        max_length=20,
        choices=ModerationStatus.choices,
        default=ModerationStatus.PENDING,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [
            models.Index(fields=["is_approved", "is_archived", "category"], name="place_pub_arch_cat_idx"),
            models.Index(fields=["is_approved", "is_archived", "created_at"], name="place_pub_arch_created_idx"),
            models.Index(fields=["moderation_status", "is_archived"], name="place_mod_arch_idx"),
            models.Index(fields=["town_city"], name="place_town_idx"),
            models.Index(fields=["postcode"], name="place_postcode_idx"),
            models.Index(fields=["name"], name="place_name_idx"),
        ]

    @property
    def likes_count(self):
        """Return the total number of likes for this place.

        :return: Count of PlaceLike records.
        :rtype: int
        """
        return self.likes.count()

    @property
    def average_rating(self):
        """Return the rounded average rating for this place.

        :return: Average rating rounded to two decimals, or None if no reviews.
        :rtype: float | None
        """
        avg = getattr(self, "avg_rating", None)
        if avg is None:
            avg = self.reviews.aggregate(Avg("rating"))["rating__avg"]
        return round(avg, 2) if avg is not None else None

    @property
    def has_opening_hours(self):
        """Return True when both opening and closing times are set.

        :return: True if opening hours are present.
        :rtype: bool
        """
        return self.opening_time is not None and self.closing_time is not None

    @property
    def supports_opening_hours(self):
        """Return True if opening hours are applicable for this place type.

        :return: False for beaches, True otherwise.
        :rtype: bool
        """
        # Beaches are generally open public spaces, so opening hours are not shown for this type.
        return self.category != self.Category.BEACH

    @staticmethod
    def _parse_day_token(token):
        """Convert a day token into a weekday integer.

        :param token: Day token such as 'mon', 'tue', or 'sunday'.
        :return: Weekday integer where Monday is 0, or None if unrecognized.
        :rtype: int | None
        """
        token_to_day = {
            "mon": 0,
            "tue": 1,
            "wed": 2,
            "thu": 3,
            "fri": 4,
            "sat": 5,
            "sun": 6,
        }
        return token_to_day.get(token.strip().lower()[:3])

    def _is_open_today_by_days(self, weekday):
        """Determine if a place is open on a given weekday based on opening_days.

        :param weekday: Integer day of week where Monday is 0.
        :return: True if the place is open on that weekday.
        :rtype: bool
        """
        if not self.opening_days:
            return True

        raw = self.opening_days.lower().replace(" ", "")
        if raw in {"mon-sun", "daily", "everyday"}:
            return True

        allowed_days = set()
        for part in raw.split(","):
            if "-" in part:
                start_raw, end_raw = part.split("-", 1)
                start_day = self._parse_day_token(start_raw)
                end_day = self._parse_day_token(end_raw)
                if start_day is None or end_day is None:
                    continue
                if start_day <= end_day:
                    allowed_days.update(range(start_day, end_day + 1))
                else:
                    allowed_days.update(range(start_day, 7))
                    allowed_days.update(range(0, end_day + 1))
            else:
                day = self._parse_day_token(part)
                if day is not None:
                    allowed_days.add(day)

        if not allowed_days:
            return True
        return weekday in allowed_days

    @property
    def opening_days_display(self):
        """Return a human-readable display of opening days.

        :return: Display string such as 'Mon, Wed, Fri' or 'Daily'.
        :rtype: str
        """
        if not self.opening_days:
            return "Daily"
        day_labels = {
            "mon": "Mon",
            "tue": "Tue",
            "wed": "Wed",
            "thu": "Thu",
            "fri": "Fri",
            "sat": "Sat",
            "sun": "Sun",
        }
        tokens = [token.strip().lower() for token in self.opening_days.split(",") if token.strip()]
        if not tokens:
            return "Daily"
        return ", ".join(day_labels.get(token, token.title()) for token in tokens)

    @property
    def is_open_now(self):
        """Return whether the place is open at the current time.

        :return: True if open now, False if closed, None if not applicable.
        :rtype: bool | None
        """
        if not self.supports_opening_hours or not self.has_opening_hours:
            return None

        now = timezone.localtime()
        if not self._is_open_today_by_days(now.weekday()):
            return False

        now_time = now.time()
        if self.opening_time <= self.closing_time:
            return self.opening_time <= now_time <= self.closing_time
        return now_time >= self.opening_time or now_time <= self.closing_time

    def __str__(self):
        """Return the place name for display.

        :return: Place name.
        :rtype: str
        """
        return self.name

    def save(self, *args, **kwargs):
        """Save the place and synchronize is_approved from moderation_status.

        :param args: Positional arguments forwarded to Model.save.
        :param kwargs: Keyword arguments forwarded to Model.save.
        :return: None
        """
        previous_status = None
        if self.pk:
            previous_status = (
                Place.objects.filter(pk=self.pk)
                .values_list("moderation_status", flat=True)
                .first()
            )

        self.is_approved = self.moderation_status == self.ModerationStatus.APPROVED
        super().save(*args, **kwargs)


class HeritagePlace(Place):
    """Place subtype for heritage sites with historical details."""
    period = models.CharField(max_length=100, blank=True, help_text="e.g. Roman, Medieval, Victorian")
    is_listed = models.BooleanField(default=False)
    entry_fee = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    guided_tours_available = models.BooleanField(default=False)


class FoodPlace(Place):
    """Place subtype for food and drink venues with cuisine and dietary options."""
    cuisine = models.CharField(max_length=100, help_text="e.g. Italian, Pub food, Vegan")
    price_range = models.PositiveSmallIntegerField(
        choices=[
            (1, "£"),
            (2, "££"),
            (3, "£££"),
        ],
        default=2,
    )
    vegetarian_options = models.BooleanField(default=False)
    vegan_options = models.BooleanField(default=False)
    takeaway_available = models.BooleanField(default=False)


class ActivityPlace(Place):
    """Place subtype for activities with age and booking details."""
    activity_type = models.CharField(max_length=100, help_text="e.g. Hiking, Climbing, Escape Room")
    min_age = models.PositiveSmallIntegerField(null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(null=True, blank=True)
    booking_required = models.BooleanField(default=False)


class BeachPlace(Place):
    """Place subtype for beaches and lakes with safety and facility info."""
    dog_friendly = models.BooleanField(default=False)
    lifeguard_present = models.BooleanField(default=False)
    water_quality = models.CharField(max_length=50, blank=True, help_text="e.g. Excellent, Good, Poor")
    facilities_available = models.BooleanField(default=False, help_text="Toilets, parking, cafes nearby")


def validate_image_size(image):
    """Validate image size for place uploads.

    :param image: Uploaded image file.
    :return: None if valid.
    :raises ValidationError: If the image exceeds the size limit.
    """
    max_size_mb = 5
    if image.size > max_size_mb * 1024 * 1024:
        raise ValidationError(f"Image size must be under {max_size_mb}MB")


class PlaceImage(models.Model):
    """Image associated with a place."""
    place = models.ForeignKey(Place, related_name="images", on_delete=models.CASCADE)
    image = models.ImageField(upload_to="place_images/", validators=[validate_image_size])
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        """Return a readable label for the image.

        :return: Label with place name.
        :rtype: str
        """
        return f"Image for {self.place.name}"


class PlaceLike(models.Model):
    """Like relationship between a user and a place."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="place_likes")
    place = models.ForeignKey(Place, on_delete=models.CASCADE, related_name="likes")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["user", "place"], name="unique_place_like"),
        ]
        indexes = [
            models.Index(fields=["place", "created_at"], name="placelike_place_created_idx"),
            models.Index(fields=["user", "created_at"], name="placelike_user_created_idx"),
        ]

    def __str__(self):
        """Return a readable label for the like.

        :return: Label with user and place.
        :rtype: str
        """
        return f"{self.user} likes {self.place}"
