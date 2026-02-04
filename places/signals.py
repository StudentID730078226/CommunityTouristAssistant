"""Signals for place moderation side effects."""

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from accounts.models import Contribution
from places.models import ActivityPlace, BeachPlace, FoodPlace, HeritagePlace, Place


def _set_previous_status(instance):
    """Store the previous moderation status on the instance for post-save checks."""
    previous_status = None
    if instance.pk:
        previous_status = (
            Place.objects.filter(pk=instance.pk)
            .values_list("moderation_status", flat=True)
            .first()
        )
    instance._previous_moderation_status = previous_status


def _award_points_if_newly_approved(instance):
    """Award contribution points when a place is approved for the first time."""
    previous_status = getattr(instance, "_previous_moderation_status", None)
    if previous_status == Place.ModerationStatus.APPROVED:
        return
    if instance.moderation_status != Place.ModerationStatus.APPROVED:
        return
    if not instance.created_by:
        return

    contribution, _ = Contribution.objects.get_or_create(user=instance.created_by)
    contribution.places_added += 1
    contribution.points += 50
    contribution.save(update_fields=["places_added", "points"])


def _store_previous_status(sender, instance, **_kwargs):
    """Record the previous moderation status before saving a place.

    :param sender: Model class sending the signal.
    :param instance: Place instance being saved.
    :param _kwargs: Additional signal kwargs.
    :return: None
    """
    _set_previous_status(instance)


def _award_points_on_approval(sender, instance, **_kwargs):
    """Award contribution points after a place is approved.

    :param sender: Model class sending the signal.
    :param instance: Place instance being saved.
    :param _kwargs: Additional signal kwargs.
    :return: None
    """
    _award_points_if_newly_approved(instance)


def _connect_place_signals(sender):
    """Attach moderation signal handlers to a given place model class.

    :param sender: Place subclass to receive signal hooks.
    :return: None
    """
    pre_save.connect(
        _store_previous_status,
        sender=sender,
        dispatch_uid=f"place_previous_status_{sender.__name__}",
    )
    post_save.connect(
        _award_points_on_approval,
        sender=sender,
        dispatch_uid=f"place_award_points_{sender.__name__}",
    )


for _sender in (Place, HeritagePlace, FoodPlace, ActivityPlace, BeachPlace):
    _connect_place_signals(_sender)
