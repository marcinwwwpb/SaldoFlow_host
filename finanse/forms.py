from django import forms

from .models import CelOszczednosciowy, KontoDomowe, Operacja


class OperacjaForm(forms.ModelForm):
    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        if user is not None:
            self.fields["konto"].queryset = KontoDomowe.objects.filter(uzytkownik=user, aktywne=True).order_by("nazwa")

    class Meta:
        model = Operacja
        fields = [
            "konto",
            "tytul",
            "kwota",
            "data",
            "typ_operacji",
            "kategoria",
            "tagi",
            "opis",
        ]
        widgets = {
            "konto": forms.Select(attrs={"class": "form-select"}),
            "tytul": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Np. Pensja, zakupy spożywcze, rachunek za prąd",
                }
            ),
            "kwota": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0",
                    "placeholder": "0.00",
                }
            ),
            "data": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                    "id": "datepicker",
                }
            ),
            "typ_operacji": forms.Select(attrs={"class": "form-select"}),
            "kategoria": forms.Select(attrs={"class": "form-select"}),
            "tagi": forms.SelectMultiple(attrs={"class": "form-select"}),
            "opis": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": "Opcjonalny opis operacji",
                }
            ),
        }
        labels = {
            "konto": "Konto",
            "tytul": "Tytuł operacji",
            "kwota": "Kwota (PLN)",
            "data": "Data operacji",
            "typ_operacji": "Rodzaj operacji",
            "kategoria": "Kategoria",
            "tagi": "Tagi",
            "opis": "Opis",
        }


class CelOszczednosciowyForm(forms.ModelForm):
    class Meta:
        model = CelOszczednosciowy
        fields = ["kwota_docelowa"]
        widgets = {
            "kwota_docelowa": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "step": "0.01",
                    "min": "0",
                    "placeholder": "Podaj kwotę celu rocznego",
                }
            )
        }
        labels = {
            "kwota_docelowa": "Kwota celu (PLN)",
        }


class KontoDomoweForm(forms.ModelForm):
    class Meta:
        model = KontoDomowe
        fields = ["nazwa", "typ", "saldo_poczatkowe", "aktywne"]
        widgets = {
            "nazwa": forms.TextInput(attrs={"class": "form-control", "placeholder": "Np. Konto osobiste, oszczędności, portfel"}),
            "typ": forms.Select(attrs={"class": "form-select"}),
            "saldo_poczatkowe": forms.NumberInput(attrs={"class": "form-control", "step": "0.01", "placeholder": "0.00"}),
            "aktywne": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }
        labels = {
            "nazwa": "Nazwa konta",
            "typ": "Typ konta",
            "saldo_poczatkowe": "Saldo początkowe (PLN)",
            "aktywne": "Konto aktywne",
        }
