from django.apps import AppConfig
from django.db.models.signals import post_migrate


class FinanseConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "finanse"
    verbose_name = "Budżet domowy"

    def ready(self):
        from accounts.services import ensure_finance_dictionary

        def seed_finance_dictionary(sender, **kwargs):
            ensure_finance_dictionary()

        post_migrate.connect(seed_finance_dictionary, sender=self)
