"""Admin configuration for place moderation and image management."""

from django.contrib import admin
from django.db.models import Avg, Count
from django.utils import timezone
from django.utils.html import format_html

from reviews.moderation import log_moderation_action
from reviews.models import ModerationLog

from .models import Place, PlaceImage


class PlaceImageInline(admin.TabularInline):
    model = PlaceImage
    extra = 0
    readonly_fields = ("image_preview",)
    fields = ("image", "image_preview")

    def image_preview(self, obj):
        """Render a small image preview for the admin inline.

        :param obj: PlaceImage instance.
        :return: HTML string or fallback text.
        :rtype: str
        """
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 150px; border-radius: 6px;" />',
                obj.image.url,
            )
        return "No image"

    image_preview.short_description = "Preview"


@admin.action(description="Approve selected places")
def approve_places(modeladmin, request, queryset):
    """Approve selected places and log moderation action.

    :param modeladmin: Admin instance.
    :param request: Current HTTP request.
    :param queryset: Selected Place records.
    :return: None
    """
    for place in queryset.exclude(moderation_status=Place.ModerationStatus.APPROVED):
        place.moderation_status = Place.ModerationStatus.APPROVED
        place.save(update_fields=["moderation_status", "is_approved"])
        log_moderation_action(
            actor=request.user,
            action=ModerationLog.Action.PLACE_APPROVED,
            target=place,
            notes="Approved from Place admin action.",
        )

@admin.action(description="Mark selected places as rejected")
def reject_places(modeladmin, request, queryset):
    """Reject selected places and log moderation action.

    :param modeladmin: Admin instance.
    :param request: Current HTTP request.
    :param queryset: Selected Place records.
    :return: None
    """
    for place in queryset:
        place.moderation_status = Place.ModerationStatus.REJECTED
        place.is_approved = False
        place.save(update_fields=["moderation_status", "is_approved"])
        log_moderation_action(
            actor=request.user,
            action=ModerationLog.Action.PLACE_REJECTED,
            target=place,
            notes="Rejected from Place admin action.",
        )


@admin.action(description="Archive selected places (soft delete)")
def archive_places(modeladmin, request, queryset):
    """Archive selected places and log moderation action.

    :param modeladmin: Admin instance.
    :param request: Current HTTP request.
    :param queryset: Selected Place records.
    :return: None
    """
    now = timezone.now()
    for place in queryset.filter(is_archived=False):
        place.is_archived = True
        place.archived_at = now
        place.archived_by = request.user
        place.is_approved = False
        place.save(update_fields=["is_archived", "archived_at", "archived_by", "is_approved"])
        log_moderation_action(
            actor=request.user,
            action=ModerationLog.Action.PLACE_ARCHIVED,
            target=place,
            notes="Archived via Place admin.",
        )


@admin.action(description="Restore selected archived places")
def restore_places(modeladmin, request, queryset):
    """Restore archived places to active state.

    :param modeladmin: Admin instance.
    :param request: Current HTTP request.
    :param queryset: Selected Place records.
    :return: None
    """
    for place in queryset.filter(is_archived=True):
        place.is_archived = False
        place.archived_at = None
        place.archived_by = None
        place.save(update_fields=["is_archived", "archived_at", "archived_by"])
        log_moderation_action(
            actor=request.user,
            action=ModerationLog.Action.PLACE_RESTORED,
            target=place,
            notes="Restored via Place admin.",
        )


@admin.register(Place)
class PlaceAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "category",
        "likes_total",
        "avg_rating",
        "review_count",
        "moderation_status",
        "is_archived",
        "created_by",
        "created_at",
    )
    list_filter = ("moderation_status", "is_archived", "category", "created_at")
    search_fields = ("name", "description", "town_city", "postcode", "location_text", "created_by__username")
    actions = [approve_places, reject_places, archive_places, restore_places]
    inlines = [PlaceImageInline]
    date_hierarchy = "created_at"
    list_select_related = ("created_by", "archived_by")
    readonly_fields = ("created_at", "archived_at")

    fieldsets = (
        ("Core", {"fields": ("name", "description", "category", "created_by")}),
        (
            "Location & Contact",
            {
                "fields": (
                    "location_text",
                    "address_line_1",
                    "address_line_2",
                    "town_city",
                    "postcode",
                    "website_url",
                    "phone_number",
                )
            },
        ),
        (
            "Visitor Info",
            {
                "fields": (
                    "best_time_to_visit",
                    "estimated_visit_minutes",
                    "child_friendly",
                    "pet_friendly",
                    "accessibility_info",
                    "transport_info",
                    "parking_info",
                )
            },
        ),
        ("Moderation", {"fields": ("moderation_status", "is_archived", "archived_at", "archived_by", "created_at")}),
    )

    def get_queryset(self, request):
        """Return the queryset with aggregated like and review counts.

        :param request: Current HTTP request.
        :return: Annotated queryset.
        """
        return (
            super()
            .get_queryset(request)
            .annotate(_likes_total=Count("likes", distinct=True), _avg_rating=Avg("reviews__rating"), _review_count=Count("reviews", distinct=True))
        )

    @admin.display(description="Likes", ordering="_likes_total")
    def likes_total(self, obj):
        """Return annotated like total for list display.

        :param obj: Place instance.
        :return: Like count.
        :rtype: int
        """
        return getattr(obj, "_likes_total", 0)

    @admin.display(description="Avg rating", ordering="_avg_rating")
    def avg_rating(self, obj):
        """Return formatted average rating for list display.

        :param obj: Place instance.
        :return: Average rating string or dash.
        :rtype: str
        """
        value = getattr(obj, "_avg_rating", None)
        return f"{value:.1f}" if value is not None else "-"

    @admin.display(description="Reviews", ordering="_review_count")
    def review_count(self, obj):
        """Return annotated review count for list display.

        :param obj: Place instance.
        :return: Review count.
        :rtype: int
        """
        return getattr(obj, "_review_count", 0)

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
        """Archive a place when deleted from the admin detail page.

        :param request: Current HTTP request.
        :param obj: Place instance being deleted.
        :return: None
        """
        obj.is_archived = True
        obj.archived_at = timezone.now()
        obj.archived_by = request.user
        obj.is_approved = False
        obj.save(update_fields=["is_archived", "archived_at", "archived_by", "is_approved"])
        log_moderation_action(
            actor=request.user,
            action=ModerationLog.Action.PLACE_ARCHIVED,
            target=obj,
            notes="Archived via single delete in admin.",
        )

    def delete_queryset(self, request, queryset):
        """Archive multiple places when deleted from the admin list.

        :param request: Current HTTP request.
        :param queryset: Selected Place records.
        :return: None
        """
        archive_places(self, request, queryset)
