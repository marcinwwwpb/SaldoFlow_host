from django.urls import path
from . import views

urlpatterns = [
    path("", views.dashboard, name="paneladmin_dashboard"),
    path("logowanie/", views.PanelAdminLoginView.as_view(), name="paneladmin_login"),
    path("wyloguj/", views.PanelAdminLogoutView.as_view(), name="paneladmin_logout"),
    path("uzytkownicy/", views.users_view, name="paneladmin_users"),
    path("dane/", views.records_view, name="paneladmin_records"),
    path("demon/", views.daemon_view, name="paneladmin_demon"),
    path("audyt/", views.audit_view, name="paneladmin_audit"),
    path("demon/<str:module>/<str:action>/", views.daemon_action, name="paneladmin_demon_action"),
    path("dom/zapisz/", views.zapisz_operacje_dom, name="paneladmin_zapisz_dom"),
    path("dom/usun/<int:pk>/", views.usun_operacje_dom, name="paneladmin_usun_dom"),
    path("firma/zapisz/", views.zapisz_pozycje_firmowa, name="paneladmin_zapisz_firma"),
    path("firma/usun/<int:pk>/", views.usun_pozycje_firmowa, name="paneladmin_usun_firma"),
    path("role/zapisz/", views.zapisz_role, name="paneladmin_zapisz_role"),
]
