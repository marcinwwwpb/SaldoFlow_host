import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class EmailVerification(models.Model):
    PURPOSE_ACTIVATION = "activation"
    PURPOSE_CHOICES = [(PURPOSE_ACTIVATION, "Aktywacja konta")]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="email_verifications")
    email = models.EmailField()
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    purpose = models.CharField(max_length=32, choices=PURPOSE_CHOICES, default=PURPOSE_ACTIVATION)
    sent_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField()

    class Meta:
        ordering = ["-sent_at", "-id"]
        verbose_name = "Potwierdzenie e-mail"
        verbose_name_plural = "Potwierdzenia e-mail"

    def __str__(self):
        return f"{self.email} — {self.get_purpose_display()}"

    @property
    def is_verified(self):
        return bool(self.verified_at)

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at
