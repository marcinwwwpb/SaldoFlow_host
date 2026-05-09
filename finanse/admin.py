from django.contrib import admin

from .models import CelOszczednosciowy, DemonLog, Kategoria, KontoDomowe, Operacja, RaportMiesieczny, Tag, TypOperacji


@admin.register(KontoDomowe)
class KontoDomoweAdmin(admin.ModelAdmin):
    list_display = ("nazwa", "uzytkownik", "typ", "saldo_poczatkowe", "aktywne")
    list_filter = ("typ", "aktywne")
    search_fields = ("nazwa", "uzytkownik__username")


admin.site.register(TypOperacji)
admin.site.register(Kategoria)
admin.site.register(Tag)
admin.site.register(CelOszczednosciowy)
admin.site.register(RaportMiesieczny)


@admin.register(Operacja)
class OperacjaAdmin(admin.ModelAdmin):
    list_display = ("tytul", "uzytkownik", "konto", "kwota", "data", "typ_operacji", "kategoria")
    list_filter = ("typ_operacji", "kategoria", "data")
    search_fields = ("tytul", "opis", "uzytkownik__username")


@admin.register(DemonLog)
class DemonLogAdmin(admin.ModelAdmin):
    list_display = ("utworzono_o", "modul", "poziom", "nazwa_pliku", "wiadomosc")
    list_filter = ("modul", "poziom", "utworzono_o")
    search_fields = ("nazwa_pliku", "sciezka", "wiadomosc", "checksum_sha256")
