from django.apps import AppConfig


class ReviewPlaceConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'review_place'

    def ready(self):
        pass
