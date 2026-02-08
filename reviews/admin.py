"""Admin configuration for moderation-first review workflows."""

from __future__ import annotations

from django.contrib import admin
from django.utils import timezone

from accounts.models import Contribution

from .models import ModerationLog, Review, ReviewReport
from .moderation import log_moderation_action


class ReviewReportInline(admin.TabularInline):
    model = ReviewReport
    extra = 0
    readonly_fields = ("reporter", "reason", "status", "created_at")
    can_delete = False


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "place",
        "user",
        "rating",
        "is_approved",
        "reported",
        "is_archived",
        "pending_reports_count",
        "moderation_penalty_applied",
        "created_at",
    )
    list_filter = ("is_approved", "reported", "is_archived", "moderation_penalty_applied", "created_at")
    search_fields = ("text", "user__username", "place__name", "report_reason")
    inlines = [ReviewReportInline]
    actions = ["uphold_reported_reviews", "dismiss_reported_reviews", "archive_reviews", "restore_reviews"]
    list_select_related = ("place", "user", "archived_by")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at", "archived_at")
    autocomplete_fields = ("place", "user")

    fieldsets = (
        ("Review", {"fields": ("place", "user", "rating", "text", "created_at")}),
        (
            "Moderation",
            {
                "fields": (
                    "is_approved",
                    "reported",
                    "report_reason",
                    "moderation_penalty_applied",
                    "is_archived",
                    "archived_at",
                    "archived_by",
                )
            },
        ),
    )

    @admin.display(description="Pending reports")
    def pending_reports_count(self, obj):
        """Return the number of pending reports for a review.

        :param obj: Review instance.
        :return: Count of pending ReviewReport rows.
        :rtype: int
        """
        return obj.reports.filter(status=ReviewReport.Status.PENDING).count()

    @admin.action(description="Upheld reports: hide reviews and penalize author")
    def uphold_reported_reviews(self, request, queryset):
        """Upheld reports: hide reviews and apply contribution penalties.

        :param request: Current HTTP request.
        :param queryset: Selected Review records.
        :return: None
        """
        for review in queryset.filter(reported=True, is_archived=False):
            review.reports.filter(status=ReviewReport.Status.PENDING).update(status=ReviewReport.Status.UPHELD)
            review.is_approved = False
            review.reported = False

            if review.user and not review.moderation_penalty_applied:
                contribution, _ = Contribution.objects.get_or_create(user=review.user)
                contribution.upheld_reports_count += 1
                contribution.points = max(0, contribution.points - 30)
                if contribution.upheld_reports_count >= 3:
                    contribution.review_restriction_active = True
                contribution.save(update_fields=["upheld_reports_count", "points", "review_restriction_active"])
                review.moderation_penalty_applied = True

            review.save(update_fields=["is_approved", "reported", "moderation_penalty_applied"])
            log_moderation_action(
                actor=request.user,
                action=ModerationLog.Action.REVIEW_UPHELD,
                target=review,
                notes="Upheld reported review in admin.",
            )

    @admin.action(description="Dismiss reports and keep review visible")
    def dismiss_reported_reviews(self, request, queryset):
        """Dismiss reports and keep review visible.

        :param request: Current HTTP request.
        :param queryset: Selected Review records.
        :return: None
        """
        for review in queryset.filter(reported=True, is_archived=False):
            review.reports.filter(status=ReviewReport.Status.PENDING).update(status=ReviewReport.Status.DISMISSED)
            review.reported = False
            review.save(update_fields=["reported"])
            log_moderation_action(
                actor=request.user,
                action=ModerationLog.Action.REVIEW_DISMISSED,
                target=review,
                notes="Dismissed reported review in admin.",
            )

    @admin.action(description="Archive selected reviews (soft delete)")
    def archive_reviews(self, request, queryset):
        """Archive selected reviews (soft delete) and log the action.

        :param request: Current HTTP request.
        :param queryset: Selected Review records.
        :return: None
        """
        now = timezone.now()
        for review in queryset.filter(is_archived=False):
            review.is_archived = True
            review.archived_at = now
            review.archived_by = request.user
            review.is_approved = False
            review.reported = False
            review.save(update_fields=["is_archived", "archived_at", "archived_by", "is_approved", "reported"])
            log_moderation_action(
                actor=request.user,
                action=ModerationLog.Action.REVIEW_ARCHIVED,
                target=review,
                notes="Archived review via admin.",
            )

    @admin.action(description="Restore selected archived reviews")
    def restore_reviews(self, request, queryset):
        """Restore selected archived reviews and log the action.

        :param request: Current HTTP request.
        :param queryset: Selected Review records.
        :return: None
        """
        for review in queryset.filter(is_archived=True):
            review.is_archived = False
            review.archived_at = None
            review.archived_by = None
            review.save(update_fields=["is_archived", "archived_at", "archived_by"])
            log_moderation_action(
                actor=request.user,
                action=ModerationLog.Action.REVIEW_RESTORED,
                target=review,
                notes="Restored archived review via admin.",
            )

    def get_actions(self, request):
        """Remove destructive bulk delete in favor of archiving.

        :param request: Current HTTP request.
        :return: Actions dictionary.
        :rtype: dict
        """
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions

    def delete_model(self, request, obj):
        """Archive a review when deleted from the admin detail page.

        :param request: Current HTTP request.
        :param obj: Review instance being deleted.
        :return: None
        """
        obj.is_archived = True
        obj.archived_at = timezone.now()
        obj.archived_by = request.user
        obj.is_approved = False
        obj.reported = False
        obj.save(update_fields=["is_archived", "archived_at", "archived_by", "is_approved", "reported"])
        log_moderation_action(
            actor=request.user,
            action=ModerationLog.Action.REVIEW_ARCHIVED,
            target=obj,
            notes="Archived via single delete in admin.",
        )

    def delete_queryset(self, request, queryset):
        """Archive multiple reviews when deleted from the admin list.

        :param request: Current HTTP request.
        :param queryset: Selected Review records.
        :return: None
        """
        self.archive_reviews(request, queryset)


@admin.register(ReviewReport)
class ReviewReportAdmin(admin.ModelAdmin):
    list_display = ("id", "review", "reporter", "status", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("review__text", "review__place__name", "reporter__username", "reason")
    actions = ("mark_upheld", "mark_dismissed")
    list_select_related = ("review", "reporter")
    date_hierarchy = "created_at"
    readonly_fields = ("created_at",)
    autocomplete_fields = ("review", "reporter")

    fieldsets = (
        ("Report", {"fields": ("review", "reporter", "reason", "status", "created_at")}),
    )

    @admin.action(description="Mark selected reports as upheld")
    def mark_upheld(self, request, queryset):
        """Mark selected review reports as upheld.

        :param request: Current HTTP request.
        :param queryset: Selected ReviewReport records.
        :return: None
        """
        queryset.update(status=ReviewReport.Status.UPHELD)

    @admin.action(description="Mark selected reports as dismissed")
    def mark_dismissed(self, request, queryset):
        """Mark selected review reports as dismissed.

        :param request: Current HTTP request.
        :param queryset: Selected ReviewReport records.
        :return: None
        """
        queryset.update(status=ReviewReport.Status.DISMISSED)


@admin.register(ModerationLog)
class ModerationLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "actor", "content_type", "object_id")
    list_filter = ("action", "content_type", "created_at")
    search_fields = ("notes", "actor__username")
    readonly_fields = ("created_at", "action", "actor", "content_type", "object_id", "notes")

    def has_add_permission(self, request):
        """Prevent manual creation of audit log entries in admin.

        :param request: Current HTTP request.
        :return: False to disable add.
        :rtype: bool
        """
        return False

    def has_change_permission(self, request, obj=None):
        """Prevent editing of audit log entries in admin.

        :param request: Current HTTP request.
        :param obj: Optional ModerationLog instance.
        :return: False to disable change.
        :rtype: bool
        """
        return False
