from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .services import ensure_user_setup


@receiver(post_save, sender=get_user_model())
def user_post_save(sender, instance, created, **kwargs):
    if created:
        ensure_user_setup(instance)
