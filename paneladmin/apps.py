from django.apps import AppConfig


class PaneladminConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "paneladmin"
    verbose_name = "Panel administratora"

    def ready(self):
        from . import signals  # noqa: F401
