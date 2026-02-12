from django.urls import path
from . import views

app_name = 'reviews'

urlpatterns = [
    path('place/<int:place_id>/reviews/', views.PlaceReviewsView.as_view(), name='place_reviews'),
    path('place/<int:place_id>/add-review/', views.AddReviewView.as_view(), name='add_review'),
    path(
        'report/<int:review_id>/',
        views.ReportReviewView.as_view(),
        name='report_review'
    ),
]
