from django.contrib import admin
from django.urls import path, include
from community_tourism.views import (
    AcceptableUsePolicyView,
    ContributionGuidelinesView,
    HomeView,
    ModerationPolicyView,
)
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('places/', include('places.urls')),
    path('reviews/', include('reviews.urls')),
    path('accounts/', include('accounts.urls')),
    path("policies/contribution-guidelines/", ContributionGuidelinesView.as_view(), name="contribution_guidelines"),
    path("policies/moderation-policy/", ModerationPolicyView.as_view(), name="moderation_policy"),
    path("policies/acceptable-use/", AcceptableUsePolicyView.as_view(), name="acceptable_use_policy"),
    path('', HomeView.as_view(), name='home'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
