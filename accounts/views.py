from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone

from .forms import EmailAuthenticationForm, RegistrationForm, ResendActivationForm
from .models import EmailVerification
from .services import create_activation, send_activation_email


class PublicLoginView(LoginView):
    template_name = "accounts/login_page.html"
    authentication_form = EmailAuthenticationForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return self.get_redirect_url() or reverse_lazy("module_selector")


class PublicLogoutView(LogoutView):
    next_page = reverse_lazy("home")


def register_view(request):
    if request.user.is_authenticated:
        return redirect("module_selector")

    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            verification = create_activation(user)
            send_activation_email(request, verification)
            messages.success(request, "Konto zostało utworzone. Sprawdź skrzynkę e-mail i aktywuj dostęp.")
            return redirect("accounts_activation_sent")
    else:
        form = RegistrationForm()
    return render(request, "accounts/register_page.html", {"form": form})


def activation_sent_view(request):
    return render(request, "accounts/activation_sent.html")


def activate_view(request, token):
    verification = get_object_or_404(EmailVerification, token=token)
    if verification.is_verified:
        messages.info(request, "Ten link został już wykorzystany. Możesz się zalogować.")
        return redirect("accounts_login")
    if verification.is_expired:
        messages.error(request, "Link aktywacyjny wygasł. Wyślij nowy link aktywacyjny.")
        return redirect("accounts_resend_activation")

    verification.verified_at = timezone.now()
    verification.save(update_fields=["verified_at"])
    user = verification.user
    user.is_active = True
    user.save(update_fields=["is_active"])
    login(request, user, backend="accounts.backends.EmailBackend")
    messages.success(request, "Adres e-mail został potwierdzony. Konto jest aktywne.")
    return redirect("module_selector")


def resend_activation_view(request):
    if request.method == "POST":
        form = ResendActivationForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"]
            verification = (
                EmailVerification.objects.select_related("user")
                .filter(email__iexact=email, verified_at__isnull=True)
                .order_by("-sent_at")
                .first()
            )
            if verification and not verification.user.is_active:
                verification = create_activation(verification.user)
                send_activation_email(request, verification)
            messages.success(request, "Jeśli konto istnieje i czeka na aktywację, wysłaliśmy nowy link.")
            return redirect("accounts_login")
    else:
        form = ResendActivationForm()
    return render(request, "accounts/resend_activation.html", {"form": form})


@login_required
def account_overview(request):
    return redirect("module_selector")
