from django.urls import path

from .views import (
    PublicLoginView,
    PublicLogoutView,
    account_overview,
    activate_view,
    activation_sent_view,
    register_view,
    resend_activation_view,
)

urlpatterns = [
    path("", account_overview, name="accounts_overview"),
    path("logowanie/", PublicLoginView.as_view(), name="accounts_login"),
    path("wyloguj/", PublicLogoutView.as_view(), name="accounts_logout"),
    path("rejestracja/", register_view, name="accounts_register"),
    path("aktywacja-wyslana/", activation_sent_view, name="accounts_activation_sent"),
    path("aktywuj/<uuid:token>/", activate_view, name="accounts_activate"),
    path("wyslij-aktywacje-ponownie/", resend_activation_view, name="accounts_resend_activation"),
]
