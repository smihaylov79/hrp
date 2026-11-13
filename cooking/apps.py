from django.apps import AppConfig


class CookingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'cooking'

    def ready(self):
        import cooking.signals
        import cooking.services  # cache invalidation signals
