# reviews/apps.py
from django.apps import AppConfig

class ReviewsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'reviews'

    def ready(self):
        """Register signal handlers for the reviews app.

        :return: None
        """
        import reviews.signals
