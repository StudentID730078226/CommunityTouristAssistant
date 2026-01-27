from django.urls import path
from . import views

app_name = 'places'

urlpatterns = [
    path("<int:pk>/", views.PlaceDetailView.as_view(), name="place_detail"),
    path("add/", views.AddPlaceView.as_view(), name="add_place"),
    path("<int:pk>/opening-hours/", views.EditOpeningHoursView.as_view(), name="edit_opening_hours"),
    path("search/", views.SearchPlacesView.as_view(), name="search_places"),
    path("<int:pk>/like/", views.ToggleLikeView.as_view(), name="toggle_like"),
]
