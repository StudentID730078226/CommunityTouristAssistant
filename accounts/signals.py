"""Signal handlers for contribution tracking."""

from django.contrib.auth.models import User
from django.db.models.signals import post_save
from django.dispatch import receiver

from reviews.models import Review

from .models import Contribution


@receiver(post_save, sender=User)
def create_contribution(sender, instance, created, **kwargs):
    """Create a Contribution record when a new user is created.

    :param sender: The model class sending the signal.
    :param instance: The newly created User instance.
    :param created: True if the user was created in this save.
    :param kwargs: Additional signal keyword arguments.
    :return: None
    """
    if created:
        Contribution.objects.get_or_create(user=instance)


@receiver(post_save, sender=Review)
def award_points_for_review(sender, instance, created, **kwargs):
    """Award contribution points when a user posts a review.

    :param sender: The Review model class.
    :param instance: The Review instance that was saved.
    :param created: True if the review was created in this save.
    :param kwargs: Additional signal keyword arguments.
    :return: None
    """
    if created and instance.user:
        contribution, _ = Contribution.objects.get_or_create(user=instance.user)
        contribution.reviews_added += 1
        contribution.points += 10
        contribution.save(update_fields=["reviews_added", "points"])
