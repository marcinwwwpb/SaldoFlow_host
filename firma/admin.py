from django.contrib import admin
from .models import (
    UstawieniaFirmy,
    Kontrahent,
    FakturaSprzedazy,
    FakturaKosztowa,
    ImportDemona,
    JPKDeklaracja,
)


admin.site.register(UstawieniaFirmy)
admin.site.register(Kontrahent)
admin.site.register(FakturaSprzedazy)
admin.site.register(JPKDeklaracja)


@admin.register(FakturaKosztowa)
class FakturaKosztowaAdmin(admin.ModelAdmin):
    list_display = ("numer_faktury", "user", "kontrahent_nazwa", "data_zakupu", "kwota_netto", "kwota_vat", "kwota_brutto")
    list_filter = ("rodzaj_zakupu", "miesiac_jpk", "data_zakupu")
    search_fields = ("numer_faktury", "kontrahent_nazwa", "nip_dostawcy")


@admin.register(ImportDemona)
class ImportDemonaAdmin(admin.ModelAdmin):
    list_display = ("nazwa_pliku", "user", "status", "liczba_rekordow", "liczba_bledow", "data_przetworzenia", "created_at")
    list_filter = ("status", "created_at")
    search_fields = ("nazwa_pliku", "sciezka_zrodlowa", "komunikat", "checksum_sha256", "user__username")
