"""Shared moderation helpers for logging admin actions."""

from __future__ import annotations

from .models import ModerationLog


def log_moderation_action(*, actor, action: str, target, notes: str = "") -> None:
    """Create a moderation log entry for the given action and target.

    :param actor: User performing the action.
    :param action: Action enum value from ModerationLog.Action.
    :param target: Model instance being moderated.
    :param notes: Optional free-text notes for audit context.
    :return: None
    """
    ModerationLog.objects.create(
        actor=actor if getattr(actor, "is_authenticated", False) else None,
        action=action,
        target=target,
        notes=notes,
    )
