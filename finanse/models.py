from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Q


class TypOperacji(models.Model):
    nazwa = models.CharField(max_length=50, unique=True)

    class Meta:
        verbose_name = "Typ operacji"
        verbose_name_plural = "Typy operacji"
        ordering = ["nazwa"]

    def __str__(self):
        return self.nazwa


class Kategoria(models.Model):
    nazwa = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name = "Kategoria"
        verbose_name_plural = "Kategorie"
        ordering = ["nazwa"]

    def __str__(self):
        return self.nazwa


class Tag(models.Model):
    nazwa = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name = "Tag"
        verbose_name_plural = "Tagi"
        ordering = ["nazwa"]

    def __str__(self):
        return self.nazwa


class KontoDomowe(models.Model):
    TYP_CHOICES = [
        ("ROR", "Rachunek bieżący"),
        ("OSZCZEDNOSCIOWE", "Konto oszczędnościowe"),
        ("GOTOWKA", "Gotówka"),
        ("FIRMA", "Konto firmowe"),
    ]

    uzytkownik = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="konta_domowe",
    )
    nazwa = models.CharField(max_length=120)
    typ = models.CharField(max_length=20, choices=TYP_CHOICES, default="ROR")
    saldo_poczatkowe = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    aktywne = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Konto domowe"
        verbose_name_plural = "Konta domowe"
        ordering = ["nazwa"]
        constraints = [
            models.UniqueConstraint(fields=["uzytkownik", "nazwa"], name="uniq_konto_user_nazwa")
        ]

    def __str__(self):
        return self.nazwa


class Operacja(models.Model):
    uzytkownik = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="operacje",
    )
    konto = models.ForeignKey(
        "KontoDomowe",
        on_delete=models.PROTECT,
        related_name="operacje",
        null=True,
        blank=True,
    )
    tytul = models.CharField(max_length=255)
    kwota = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )
    data = models.DateField()
    typ_operacji = models.ForeignKey(
        TypOperacji,
        on_delete=models.PROTECT,
        related_name="operacje",
    )
    kategoria = models.ForeignKey(
        Kategoria,
        on_delete=models.PROTECT,
        related_name="operacje",
    )
    tagi = models.ManyToManyField(
        Tag,
        blank=True,
        related_name="operacje",
    )
    opis = models.TextField(blank=True)

    class Meta:
        verbose_name = "Operacja"
        verbose_name_plural = "Operacje"
        ordering = ["-data", "-id"]
        indexes = [
            models.Index(fields=["uzytkownik", "data"]),
            models.Index(fields=["uzytkownik", "typ_operacji", "data"]),
        ]

    def __str__(self):
        return f"{self.tytul} - {self.kwota} PLN"

    @property
    def czy_przychod(self):
        return self.typ_operacji.nazwa.strip().lower() == "przychod"

    @property
    def czy_wydatek(self):
        return not self.czy_przychod


class CelOszczednosciowy(models.Model):
    uzytkownik = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cele_oszczednosciowe",
    )
    rok = models.PositiveIntegerField()
    kwota_docelowa = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
    )

    class Meta:
        verbose_name = "Cel oszczędnościowy"
        verbose_name_plural = "Cele oszczędnościowe"
        ordering = ["-rok"]
        unique_together = ("uzytkownik", "rok")

    def __str__(self):
        return f"{self.uzytkownik} - {self.rok} - {self.kwota_docelowa} PLN"

class RaportMiesieczny(models.Model):
    uzytkownik = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="raporty_miesieczne",
    )
    rok = models.PositiveIntegerField()
    miesiac = models.PositiveSmallIntegerField()
    suma_przychodow = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    suma_wydatkow = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    saldo = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    wygenerowano_o = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Raport miesięczny"
        verbose_name_plural = "Raporty miesięczne"
        ordering = ["-rok", "-miesiac"]
        constraints = [
            models.UniqueConstraint(fields=["uzytkownik", "rok", "miesiac"], name="uniq_raport_user_rok_miesiac"),
            models.CheckConstraint(condition=Q(miesiac__gte=1) & Q(miesiac__lte=12), name="raport_miesiac_1_12"),
        ]

    def __str__(self):
        return f"Raport {self.rok}-{self.miesiac:02d}"


class DemonLog(models.Model):
    MODUL_DOM = "DOM"
    MODUL_FIRMA = "FIRMA"
    MODUL_CHOICES = [
        (MODUL_DOM, "Budżet domowy"),
        (MODUL_FIRMA, "Budżet firmowy"),
    ]

    POZIOM_INFO = "INFO"
    POZIOM_WARNING = "WARNING"
    POZIOM_ERROR = "ERROR"
    POZIOM_CHOICES = [
        (POZIOM_INFO, "Info"),
        (POZIOM_WARNING, "Ostrzeżenie"),
        (POZIOM_ERROR, "Błąd"),
    ]

    modul = models.CharField(max_length=10, choices=MODUL_CHOICES)
    poziom = models.CharField(max_length=10, choices=POZIOM_CHOICES, default=POZIOM_INFO)
    nazwa_pliku = models.CharField(max_length=255, blank=True)
    sciezka = models.CharField(max_length=500, blank=True)
    checksum_sha256 = models.CharField(max_length=64, blank=True)
    wiadomosc = models.TextField()
    utworzono_o = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Log demona"
        verbose_name_plural = "Logi demona"
        ordering = ["-utworzono_o", "-id"]
        indexes = [
            models.Index(fields=["modul", "utworzono_o"]),
            models.Index(fields=["poziom", "utworzono_o"]),
        ]

    def __str__(self):
        return f"{self.modul} {self.poziom}: {self.wiadomosc[:60]}"
