from django.urls import path
from . import views


urlpatterns = [
    path("", views.dashboard_firmy, name="firma_dashboard"),
    path("miesiac/<int:rok>/<int:miesiac>/", views.miesiac_firmy_detail, name="firma_miesiac_detail"),

    path("ustawienia/", views.ustawienia_firmy, name="ustawienia_firmy"),
    path("rozliczenia-urzedy/", views.rozliczenia_urzedow, name="rozliczenia_urzedow"),

    path("kontrahenci/", views.lista_kontrahentow, name="kontrahenci"),
    path("kontrahenci/dodaj/", views.dodaj_kontrahenta, name="dodaj_kontrahenta"),
    path("api/ceidg/po-nip/", views.api_ceidg_po_nip, name="api_ceidg_po_nip"),

    path("sprzedaz/", views.lista_faktur_sprzedazy, name="faktury_sprzedazy"),
    path("sprzedaz/dodaj/", views.dodaj_fakture_sprzedazy, name="dodaj_fakture_sprzedazy"),

    path("koszty/", views.lista_faktur_kosztowych, name="faktury_kosztowe"),
    path("koszty/dodaj/", views.dodaj_fakture_kosztowa, name="dodaj_fakture_kosztowa"),
    path("koszty/import-excel/", views.import_kosztow_excel, name="import_kosztow_excel"),
    path("koszty/importy-demona/", views.lista_importow_demona, name="importy_demona"),

    path("deklaracja-jpk/", views.deklaracja_jpk, name="deklaracja_jpk"),
    path("jpk-vat/", views.eksport_jpk_v7m, name="eksport_jpk_v7m"),
]