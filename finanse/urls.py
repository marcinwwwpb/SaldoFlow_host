from django.urls import path

from . import views

urlpatterns = [
    path(
        "konta/",
        views.lista_kont,
        name="lista_kont",
    ),
    path(
        "konta/dodaj/",
        views.dodaj_konto,
        name="dodaj_konto",
    ),
    path(
        "raporty/",
        views.raporty_miesieczne,
        name="raporty_miesieczne",
    ),
    path("", views.lista_miesiecy, name="lista_miesiecy"),
    path(
        "miesiac/<int:rok>/<int:miesiac>/",
        views.miesiac_detail,
        name="miesiac_detail",
    ),
    path(
        "dodaj/",
        views.dodaj_operacje,
        name="dodaj_operacje",
    ),
    path(
        "import-eksport/",
        views.centrum_importu_eksportu,
        name="centrum_importu_eksportu",
    ),
    path(
        "eksport/",
        views.eksport_csv,
        name="eksport_csv",
    ),
    path(
        "import/",
        views.import_csv,
        name="import_csv",
    ),
    path(
        "eksport/xml/",
        views.eksport_xml,
        name="eksport_xml",
    ),
    path(
        "import/xml/",
        views.import_xml,
        name="import_xml",
    ),
    path(
        "ustaw-cel/",
        views.ustaw_cel,
        name="ustaw_cel",
    ),
]