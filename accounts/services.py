from datetime import timedelta

from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from finanse.models import Kategoria, KontoDomowe, TypOperacji
from paneladmin.models import UserRole

from .models import EmailVerification


DEFAULT_CATEGORIES = [
    "Dom",
    "Jedzenie",
    "Transport",
    "Rachunki",
    "Zdrowie",
    "Rozrywka",
    "Oszczędności",
    "Firma",
    "Inne",
]


def ensure_user_setup(user):
    UserRole.objects.get_or_create(user=user, defaults={"role": UserRole.ROLE_UZYTKOWNIK})
    KontoDomowe.objects.get_or_create(
        uzytkownik=user,
        nazwa="Konto główne",
        defaults={"typ": "ROR", "saldo_poczatkowe": 0},
    )


def ensure_finance_dictionary():
    for typ in ["Przychod", "Wydatek"]:
        TypOperacji.objects.get_or_create(nazwa=typ)
    for category in DEFAULT_CATEGORIES:
        Kategoria.objects.get_or_create(nazwa=category)


def create_activation(user):
    EmailVerification.objects.filter(user=user, purpose=EmailVerification.PURPOSE_ACTIVATION, verified_at__isnull=True).delete()
    return EmailVerification.objects.create(
        user=user,
        email=user.email,
        purpose=EmailVerification.PURPOSE_ACTIVATION,
        expires_at=timezone.now() + timedelta(days=2),
    )


def send_activation_email(request, verification):
    activation_url = request.build_absolute_uri(
        reverse("accounts_activate", kwargs={"token": str(verification.token)})
    )
    context = {
        "user": verification.user,
        "activation_url": activation_url,
        "app_name": getattr(settings, "APP_NAME", "SaldoFlow"),
        "app_tagline": getattr(settings, "APP_TAGLINE", "Dom i firma pod pełną kontrolą."),
    }
    subject = render_to_string("accounts/emails/activation_subject.txt", context).strip()
    body = render_to_string("accounts/emails/activation_body.txt", context)
    send_mail(
        subject=subject,
        message=body,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[verification.email],
        fail_silently=False,
    )
