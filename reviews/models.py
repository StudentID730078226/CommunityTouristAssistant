"""Models for reviews, reports, and moderation logs."""

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models

from .validators import validate_review_language


class Review(models.Model):
    """User-submitted review of a place with moderation metadata."""
    place = models.ForeignKey(
        "places.Place",
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )
    text = models.TextField(validators=[validate_review_language])
    rating = models.PositiveSmallIntegerField(default=5)
    is_approved = models.BooleanField(default=True)

    reported = models.BooleanField(default=False)
    report_reason = models.CharField(max_length=255, blank=True)
    moderation_penalty_applied = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="archived_reviews",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["place", "user"],
                condition=models.Q(is_archived=False),
                name="one_review_per_user_per_place",
            )
        ]
        indexes = [
            models.Index(fields=["place", "is_approved", "is_archived", "created_at"], name="review_place_vis_created_idx"),
            models.Index(fields=["reported", "is_archived", "created_at"], name="review_report_arch_created_idx"),
            models.Index(fields=["user", "is_archived", "created_at"], name="review_user_arch_created_idx"),
            models.Index(fields=["rating"], name="review_rating_idx"),
        ]

    def __str__(self):
        """Return a readable label for the review.

        :return: Summary string with user or guest label.
        :rtype: str
        """
        return f"Review by {self.user.username}" if self.user else "Review by Guest"


class ReviewReport(models.Model):
    """User report filed against a review for moderation."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        UPHELD = "upheld", "Upheld"
        DISMISSED = "dismissed", "Dismissed"

    review = models.ForeignKey(Review, on_delete=models.CASCADE, related_name="reports")
    reporter = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="review_reports")
    reason = models.CharField(max_length=255, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["review", "reporter"],
                name="one_report_per_user_per_review",
            )
        ]
        indexes = [
            models.Index(fields=["status", "created_at"], name="revrep_status_created_idx"),
            models.Index(fields=["review", "status"], name="reviewreport_review_status_idx"),
        ]

    def __str__(self):
        """Return a readable label for the report.

        :return: Summary string with review id and reporter.
        :rtype: str
        """
        return f"Report on review {self.review_id} by {self.reporter.username}"


class ModerationLog(models.Model):
    """Audit log entry for moderation actions on reviews or places."""

    class Action(models.TextChoices):
        PLACE_APPROVED = "place_approved", "Place Approved"
        PLACE_REJECTED = "place_rejected", "Place Rejected"
        PLACE_ARCHIVED = "place_archived", "Place Archived"
        PLACE_RESTORED = "place_restored", "Place Restored"
        REVIEW_UPHELD = "review_upheld", "Review Report Upheld"
        REVIEW_DISMISSED = "review_dismissed", "Review Report Dismissed"
        REVIEW_ARCHIVED = "review_archived", "Review Archived"
        REVIEW_RESTORED = "review_restored", "Review Restored"

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="moderation_actions",
    )
    action = models.CharField(max_length=40, choices=Action.choices)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    target = GenericForeignKey("content_type", "object_id")
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action", "created_at"], name="modlog_action_created_idx"),
            models.Index(fields=["content_type", "object_id"], name="modlog_target_idx"),
            models.Index(fields=["actor", "created_at"], name="modlog_actor_created_idx"),
        ]

    def __str__(self):
        """Return a readable label for the moderation log entry.

        :return: Summary string describing the action and target.
        :rtype: str
        """
        return f"{self.get_action_display()} on {self.content_type}#{self.object_id}"
