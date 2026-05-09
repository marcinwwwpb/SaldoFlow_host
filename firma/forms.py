from decimal import Decimal, ROUND_HALF_UP

from django import forms

from .models import (
    FakturaKosztowa,
    FakturaSprzedazy,
    JPKDeklaracja,
    Kontrahent,
    UstawieniaFirmy,
)


VAT_RATE_CHOICES = [
    ("23", "23%"),
    ("8", "8%"),
    ("5", "5%"),
    ("0", "0%"),
    ("ZW", "zw."),
]

MIESIAC_JPK_CHOICES = [
    ("", "Wybierz miesiąc"),
    ("1", "Styczeń"),
    ("2", "Luty"),
    ("3", "Marzec"),
    ("4", "Kwiecień"),
    ("5", "Maj"),
    ("6", "Czerwiec"),
    ("7", "Lipiec"),
    ("8", "Sierpień"),
    ("9", "Wrzesień"),
    ("10", "Październik"),
    ("11", "Listopad"),
    ("12", "Grudzień"),
]


class StyledModelForm(forms.ModelForm):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user

        for _, field in self.fields.items():
            widget = field.widget

            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Select):
                widget.attrs["class"] = "form-select"
            elif isinstance(widget, forms.Textarea):
                widget.attrs["class"] = "form-control"
                widget.attrs.setdefault("rows", 4)
            else:
                widget.attrs["class"] = "form-control"

            if isinstance(widget, forms.DateInput):
                widget.input_type = "date"


class KontrahentForm(StyledModelForm):
    class Meta:
        model = Kontrahent
        exclude = ["user"]
        labels = {
            "nazwa": "Nazwa firmy",
            "nip": "NIP",
            "regon": "REGON",
            "adres": "Adres",
            "email": "E-mail",
            "telefon": "Telefon",
            "strona_www": "Strona WWW",
            "status_rejestru": "Status rejestru",
        }

    def clean_nip(self):
        return "".join(ch for ch in str(self.cleaned_data.get("nip") or "") if ch.isdigit())


class FakturaSprzedazyForm(StyledModelForm):
    vat_rate = forms.ChoiceField(
        label="Stawka VAT",
        choices=VAT_RATE_CHOICES,
        required=False,
        initial="23",
    )

    class Meta:
        model = FakturaSprzedazy
        exclude = ["user"]
        labels = {
            "numer": "Numer faktury",
            "kontrahent": "Kontrahent",
            "data_wystawienia": "Data wystawienia",
            "data_sprzedazy": "Data sprzedaży",
            "kwota_netto": "Kwota netto (PLN)",
            "kwota_brutto": "Kwota brutto (PLN)",
            "czy_oplacona": "Faktura opłacona",
            "opis": "Opis usługi / notatka",
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, user=user, **kwargs)
        if user:
            self.fields["kontrahent"].queryset = Kontrahent.objects.filter(user=user).order_by("nazwa")
        self.fields["kwota_brutto"].widget.attrs["readonly"] = "readonly"

    def clean(self):
        cleaned = super().clean()
        netto = cleaned.get("kwota_netto") or Decimal("0.00")
        vat_rate = cleaned.get("vat_rate") or "23"

        if vat_rate == "ZW":
            brutto = netto
        else:
            try:
                rate_decimal = Decimal(str(vat_rate))
            except Exception:
                rate_decimal = Decimal("23")
            brutto = (netto * (Decimal("1") + rate_decimal / Decimal("100"))).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )

        cleaned["kwota_brutto"] = brutto
        return cleaned


class FakturaKosztowaForm(StyledModelForm):
    vat_rate = forms.ChoiceField(
        label="Stawka VAT",
        choices=VAT_RATE_CHOICES,
        required=False,
        initial="23",
    )

    miesiac_jpk = forms.ChoiceField(
        label="Miesiąc JPK",
        choices=MIESIAC_JPK_CHOICES,
        required=False,
    )

    class Meta:
        model = FakturaKosztowa
        exclude = ["user"]
        labels = {
            "numer_faktury": "Numer faktury",
            "kontrahent": "Powiązany kontrahent",
            "kontrahent_nazwa": "Dostawca",
            "nip_dostawcy": "NIP dostawcy",
            "kod_kraju": "Kod kraju",
            "data_zakupu": "Data zakupu",
            "kwota_netto": "Kwota netto (PLN)",
            "kwota_vat": "Kwota VAT (PLN)",
            "kwota_brutto": "Kwota brutto (PLN)",
            "kategoria": "Kategoria kosztu",
            "rodzaj_zakupu": "Rodzaj zakupu",
            "opis": "Opis / notatka",
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, user=user, **kwargs)

        if "kontrahent" in self.fields and user:
            self.fields["kontrahent"].queryset = Kontrahent.objects.filter(user=user).order_by("nazwa")

        self.fields["kwota_netto"].widget.attrs.setdefault("inputmode", "decimal")
        self.fields["kwota_vat"].widget.attrs.setdefault("inputmode", "decimal")
        self.fields["kwota_brutto"].widget.attrs.setdefault("inputmode", "decimal")

        self.fields["kwota_vat"].widget.attrs["readonly"] = "readonly"
        self.fields["kwota_brutto"].widget.attrs["readonly"] = "readonly"

        instance = getattr(self, "instance", None)
        if instance and instance.pk:
            if instance.miesiac_jpk:
                self.fields["miesiac_jpk"].initial = str(instance.miesiac_jpk)

            netto = instance.kwota_netto or Decimal("0.00")
            vat = instance.kwota_vat or Decimal("0.00")
            detected = "23"

            if netto and netto > 0:
                rate = (vat / netto * Decimal("100")).quantize(
                    Decimal("1"),
                    rounding=ROUND_HALF_UP,
                )
                if rate in {Decimal("23"), Decimal("8"), Decimal("5"), Decimal("0")}:
                    detected = str(int(rate))
            elif vat == 0:
                detected = "0"

            self.fields["vat_rate"].initial = detected

    def clean_nip_dostawcy(self):
        return "".join(ch for ch in str(self.cleaned_data.get("nip_dostawcy") or "") if ch.isdigit())

    def clean_kod_kraju(self):
        value = str(self.cleaned_data.get("kod_kraju") or "PL").strip().upper()
        return value[:2] or "PL"

    def clean_miesiac_jpk(self):
        value = self.cleaned_data.get("miesiac_jpk")
        if value in ("", None):
            return None
        try:
            month = int(value)
        except (TypeError, ValueError):
            raise forms.ValidationError("Wybierz poprawny miesiąc.")
        if not 1 <= month <= 12:
            raise forms.ValidationError("Wybierz poprawny miesiąc.")
        return month

    def clean(self):
        cleaned = super().clean()

        netto = cleaned.get("kwota_netto") or Decimal("0.00")
        vat_rate = cleaned.get("vat_rate") or "23"

        if vat_rate == "ZW":
            vat = Decimal("0.00")
        else:
            try:
                rate_decimal = Decimal(str(vat_rate))
            except Exception:
                rate_decimal = Decimal("23")
            vat = (netto * rate_decimal / Decimal("100")).quantize(
                Decimal("0.01"),
                rounding=ROUND_HALF_UP,
            )

        brutto = (netto + vat).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

        cleaned["kwota_vat"] = vat
        cleaned["kwota_brutto"] = brutto

        kontrahent = cleaned.get("kontrahent")
        kontrahent_nazwa = (cleaned.get("kontrahent_nazwa") or "").strip()
        if not kontrahent_nazwa and kontrahent:
            cleaned["kontrahent_nazwa"] = kontrahent.nazwa

        data_zakupu = cleaned.get("data_zakupu")
        if cleaned.get("miesiac_jpk") is None and data_zakupu:
            cleaned["miesiac_jpk"] = data_zakupu.month

        return cleaned


class UstawieniaFirmyForm(StyledModelForm):
    class Meta:
        model = UstawieniaFirmy
        exclude = ["user"]
        labels = {
            "nazwa_firmy": "Nazwa firmy",
            "wlasciciel": "Właściciel",
            "nip": "NIP",
            "adres": "Adres",
            "kod_urzedu_skarbowego": "Kod urzędu skarbowego",
            "forma_opodatkowania": "Forma opodatkowania",
            "vat_czynny": "VAT czynny",
            "typ_zus": "Typ ZUS",
            "czy_chorobowe": "Składka chorobowa",
        }

    def clean_nip(self):
        return "".join(ch for ch in str(self.cleaned_data.get("nip") or "") if ch.isdigit())


class ImportKosztowExcelForm(forms.Form):
    plik = forms.FileField(label="Plik Excel")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["plik"].widget.attrs["class"] = "form-control"
        self.fields["plik"].widget.attrs["accept"] = ".xlsx,.xlsm"
        self.fields["plik"].widget.attrs.setdefault("aria-describedby", "import-excel-help")


class EksportJPKForm(forms.Form):
    rok = forms.IntegerField(min_value=2000, max_value=2100, label="Rok")
    miesiac = forms.IntegerField(min_value=1, max_value=12, label="Miesiąc")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["rok"].widget.attrs["class"] = "form-control"
        self.fields["miesiac"].widget.attrs["class"] = "form-control"


class JPKDeklaracjaForm(StyledModelForm):
    class Meta:
        model = JPKDeklaracja
        exclude = ["user"]
        labels = {
            "rok": "Rok",
            "miesiac": "Miesiąc",
            "p_17": "P_17 – podstawa opodatkowania 8%",
            "p_18": "P_18 – VAT należny 8%",
            "p_19": "P_19 – podstawa opodatkowania 23%",
            "p_20": "P_20 – VAT należny 23%",
            "p_43_korekta": "Korekta P_43",
            "p_44_korekta": "Korekta P_44",
            "p_45_korekta": "Korekta P_45",
            "p_46_korekta": "Korekta P_46",
            "p_51": "P_51 – nadwyżka z poprzedniej deklaracji",
            "p_68": "P_68",
            "p_ordzu": "P_ORDZU",
            "uzasadnienie": "Uzasadnienie / notatki",
        }