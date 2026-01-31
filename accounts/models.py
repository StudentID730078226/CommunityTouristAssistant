"""Models for tracking user contributions, trust levels, and moderation impacts."""

from django.db import models
from django.contrib.auth.models import User

class Contribution(models.Model):
    """Track contribution counts, points, and trust levels for a user.

    :param user: The user this contribution record belongs to.
    :param places_added: Count of approved place submissions by the user.
    :param reviews_added: Count of reviews posted by the user.
    :param points: Total contribution points accumulated by the user.
    :param upheld_reports_count: Count of upheld reports against the user's reviews.
    :param review_restriction_active: Flag indicating if the user is blocked from posting reviews.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='contribution'
    )
    places_added = models.PositiveIntegerField(default=0)
    reviews_added = models.PositiveIntegerField(default=0)
    points = models.IntegerField(default=0)
    upheld_reports_count = models.PositiveIntegerField(default=0)
    review_restriction_active = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["points"], name="contrib_points_idx"),
            models.Index(fields=["review_restriction_active"], name="contrib_review_restrict_idx"),
        ]

    TRUSTED_THRESHOLD = 120

    LEVELS = [
        (0, "New Explorer", "secondary"),
        (50, "Local Contributor", "info"),
        (120, "Trusted Guide", "success"),
        (250, "Community Champion", "warning"),
    ]

    def is_trusted(self):
        """Return True if the user's points meet the trusted threshold.

        :return: True when points are at or above TRUSTED_THRESHOLD.
        :rtype: bool
        """
        return self.points >= self.TRUSTED_THRESHOLD

    @property
    def level_name(self):
        """Return the display name for the user's current contribution level.

        :return: The current level name based on points.
        :rtype: str
        """
        name = self.LEVELS[0][1]
        for threshold, level_name, _badge_class in self.LEVELS:
            if self.points >= threshold:
                name = level_name
            else:
                break
        return name

    @property
    def level_badge_class(self):
        """Return the Bootstrap badge class for the user's current level.

        :return: The badge class string.
        :rtype: str
        """
        badge = self.LEVELS[0][2]
        for threshold, _level_name, badge_class in self.LEVELS:
            if self.points >= threshold:
                badge = badge_class
            else:
                break
        return badge

    @property
    def next_level_name(self):
        """Return the next level name the user is working toward.

        :return: The next level name or None if already at top level.
        :rtype: str | None
        """
        for threshold, level_name, _badge_class in self.LEVELS:
            if self.points < threshold:
                return level_name
        return None

    @property
    def points_to_next_level(self):
        """Return the number of points required to reach the next level.

        :return: Points remaining to next level, or 0 if at top level.
        :rtype: int
        """
        for threshold, _level_name, _badge_class in self.LEVELS:
            if self.points < threshold:
                return threshold - self.points
        return 0

    @property
    def level_progress_percent(self):
        """Return the user's progress toward the next level as a percentage.

        :return: Progress percentage from 0 to 100.
        :rtype: int
        """
        current_threshold = 0
        next_threshold = None
        for threshold, _level_name, _badge_class in self.LEVELS:
            if self.points >= threshold:
                current_threshold = threshold
            elif next_threshold is None:
                next_threshold = threshold
                break

        if next_threshold is None:
            return 100
        span = next_threshold - current_threshold
        if span <= 0:
            return 100
        return int(((self.points - current_threshold) / span) * 100)

    def __str__(self):
        """Return a human-readable summary of the contribution record.

        :return: Summary string with username and points.
        :rtype: str
        """
        return f"{self.user.username} ({self.points} pts)"
