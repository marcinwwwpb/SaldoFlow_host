from django.conf import settings
from django.db import models


class UstawieniaFirmy(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    nazwa_firmy = models.CharField(max_length=200)
    wlasciciel = models.CharField(max_length=200)
    nip = models.CharField(max_length=20)
    adres = models.CharField(max_length=300)
    kod_urzedu_skarbowego = models.CharField(max_length=10, blank=True)

    forma_opodatkowania = models.CharField(
        max_length=20,
        choices=[
            ("LINIOWY", "Podatek liniowy"),
        ],
        default="LINIOWY",
    )

    vat_czynny = models.BooleanField(default=False)

    typ_zus = models.CharField(
        max_length=30,
        choices=[
            ("PELNY", "Pełny ZUS"),
            ("PREFERENCYJNY", "Preferencyjny ZUS"),
            ("ULGA", "Ulga na start"),
        ],
        default="PELNY",
    )

    czy_chorobowe = models.BooleanField(default=True)

    def __str__(self):
        return self.nazwa_firmy


class Kontrahent(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    nazwa = models.CharField(max_length=200)
    nip = models.CharField(max_length=20, blank=True)
    regon = models.CharField(max_length=20, blank=True)
    adres = models.CharField(max_length=300, blank=True)
    email = models.CharField(max_length=200, blank=True)
    telefon = models.CharField(max_length=50, blank=True)
    strona_www = models.CharField(max_length=200, blank=True)
    status_rejestru = models.CharField(max_length=100, blank=True)

    def __str__(self):
        return self.nazwa


class FakturaSprzedazy(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    numer = models.CharField(max_length=50)
    kontrahent = models.ForeignKey(Kontrahent, on_delete=models.CASCADE)

    data_wystawienia = models.DateField()
    data_sprzedazy = models.DateField()

    kwota_netto = models.DecimalField(max_digits=12, decimal_places=2)
    kwota_brutto = models.DecimalField(max_digits=12, decimal_places=2)

    czy_oplacona = models.BooleanField(default=False)
    opis = models.TextField(blank=True)

    def __str__(self):
        return self.numer


class FakturaKosztowa(models.Model):
    RODZAJ_ZAKUPU_CHOICES = [
        ("POZ", "Pozostały zakup"),
        ("ST", "Środek trwały"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    numer_faktury = models.CharField(max_length=100)
    kontrahent = models.ForeignKey(Kontrahent, on_delete=models.SET_NULL, null=True, blank=True, related_name="faktury_kosztowe")
    kontrahent_nazwa = models.CharField(max_length=200)

    nip_dostawcy = models.CharField(max_length=20, blank=True)
    kod_kraju = models.CharField(max_length=2, default="PL")

    data_zakupu = models.DateField()

    kwota_netto = models.DecimalField(max_digits=12, decimal_places=2)
    kwota_vat = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    kwota_brutto = models.DecimalField(max_digits=12, decimal_places=2)

    kategoria = models.CharField(max_length=200)
    rodzaj_zakupu = models.CharField(
        max_length=10,
        choices=RODZAJ_ZAKUPU_CHOICES,
        default="POZ",
    )
    miesiac_jpk = models.PositiveSmallIntegerField(null=True, blank=True)

    opis = models.TextField(blank=True)

    class Meta:
        ordering = ["-data_zakupu", "-id"]
        indexes = [
            models.Index(fields=["user", "data_zakupu"]),
            models.Index(fields=["user", "miesiac_jpk"]),
        ]

    def __str__(self):
        return self.numer_faktury


class JPKDeklaracja(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    rok = models.PositiveIntegerField()
    miesiac = models.PositiveSmallIntegerField()

    p_17 = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    p_18 = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    p_19 = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    p_20 = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    p_43_korekta = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    p_44_korekta = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    p_45_korekta = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    p_46_korekta = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    p_51 = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    p_68 = models.BooleanField(default=True)
    p_ordzu = models.BooleanField(default=False)
    uzasadnienie = models.TextField(blank=True)

    class Meta:
        unique_together = ("user", "rok", "miesiac")
        ordering = ["-rok", "-miesiac", "-id"]

    def __str__(self):
        return f"JPK {self.rok}-{self.miesiac:02d}"

class ImportDemona(models.Model):
    STATUS_NOWY = "NOWY"
    STATUS_PRZETWARZANY = "PRZETWARZANY"
    STATUS_OK = "OK"
    STATUS_CZESCIOWO = "CZESCIOWO"
    STATUS_BLAD = "BLAD"

    STATUS_CHOICES = [
        (STATUS_NOWY, "Nowy"),
        (STATUS_PRZETWARZANY, "Przetwarzany"),
        (STATUS_OK, "OK"),
        (STATUS_CZESCIOWO, "Częściowo"),
        (STATUS_BLAD, "Błąd"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    nazwa_pliku = models.CharField(max_length=255)
    sciezka_zrodlowa = models.CharField(max_length=500)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_NOWY)
    liczba_rekordow = models.PositiveIntegerField(default=0)
    liczba_bledow = models.PositiveIntegerField(default=0)
    komunikat = models.TextField(blank=True)
    checksum_sha256 = models.CharField(max_length=64, blank=True)
    data_przetworzenia = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"{self.nazwa_pliku} ({self.status})"
