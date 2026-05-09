from django import forms
from django.contrib.auth import get_user_model

from finanse.models import Kategoria, KontoDomowe, Operacja, TypOperacji
from firma.models import FakturaKosztowa, Kontrahent
from .models import UserRole


User = get_user_model()


class BaseStyledForm(forms.Form):
    def _style_fields(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, (forms.Select, forms.SelectMultiple)):
                widget.attrs.setdefault("class", "form-select")
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("class", "form-control")
                widget.attrs.setdefault("rows", 3)
            else:
                widget.attrs.setdefault("class", "form-control")
            if isinstance(widget, forms.DateInput):
                widget.input_type = "date"


class AdminOperacjaForm(forms.ModelForm, BaseStyledForm):
    uzytkownik = forms.ModelChoiceField(queryset=User.objects.none(), label="Użytkownik")

    class Meta:
        model = Operacja
        fields = ["uzytkownik", "konto", "tytul", "kwota", "data", "typ_operacji", "kategoria", "tagi", "opis"]
        widgets = {
            "data": forms.DateInput(attrs={"type": "date"}),
            "opis": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, target_user=None, user_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["uzytkownik"].queryset = user_queryset or User.objects.filter(is_active=True).order_by("username")
        self.fields["konto"].queryset = self._konto_queryset(target_user)
        self.fields["typ_operacji"].queryset = TypOperacji.objects.order_by("nazwa")
        self.fields["kategoria"].queryset = Kategoria.objects.order_by("nazwa")
        self._style_fields()

    def _resolve_user_id(self, explicit_target=None):
        if explicit_target is not None:
            return getattr(explicit_target, 'pk', explicit_target)
        if self.is_bound:
            return self.data.get('uzytkownik') or None
        if self.instance and self.instance.pk:
            return self.instance.uzytkownik_id
        initial_user = self.initial.get('uzytkownik')
        return getattr(initial_user, 'pk', initial_user)

    def _konto_queryset(self, explicit_target=None):
        user_id = self._resolve_user_id(explicit_target)
        if not user_id:
            return KontoDomowe.objects.none()
        return KontoDomowe.objects.filter(uzytkownik_id=user_id).select_related("uzytkownik").order_by("nazwa")


class AdminFakturaKosztowaForm(forms.ModelForm, BaseStyledForm):
    user = forms.ModelChoiceField(queryset=User.objects.none(), label="Użytkownik")

    class Meta:
        model = FakturaKosztowa
        fields = [
            "user", "numer_faktury", "kontrahent", "kontrahent_nazwa", "nip_dostawcy", "kod_kraju",
            "data_zakupu", "kwota_netto", "kwota_vat", "kwota_brutto", "kategoria", "rodzaj_zakupu",
            "miesiac_jpk", "opis"
        ]
        widgets = {
            "data_zakupu": forms.DateInput(attrs={"type": "date"}),
            "opis": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, target_user=None, user_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["user"].queryset = user_queryset or User.objects.filter(is_active=True).order_by("username")
        self.fields["kontrahent"].queryset = self._kontrahent_queryset(target_user)
        self._style_fields()

    def _resolve_user_id(self, explicit_target=None):
        if explicit_target is not None:
            return getattr(explicit_target, 'pk', explicit_target)
        if self.is_bound:
            return self.data.get('user') or None
        if self.instance and self.instance.pk:
            return self.instance.user_id
        initial_user = self.initial.get('user')
        return getattr(initial_user, 'pk', initial_user)

    def _kontrahent_queryset(self, explicit_target=None):
        user_id = self._resolve_user_id(explicit_target)
        if not user_id:
            return Kontrahent.objects.none()
        return Kontrahent.objects.filter(user_id=user_id).order_by("nazwa")


class AdminLogFilterForm(BaseStyledForm):
    modul = forms.ChoiceField(required=False, choices=[("", "Wszystkie moduły"), ("DOM", "Budżet domowy"), ("FIRMA", "Budżet firmowy")])
    poziom = forms.ChoiceField(required=False, choices=[("", "Wszystkie poziomy"), ("INFO", "Info"), ("WARNING", "Ostrzeżenie"), ("ERROR", "Błąd")])
    q = forms.CharField(required=False, label="Szukaj")
    date_from = forms.DateField(required=False, label="Od", widget=forms.DateInput(attrs={"type": "date"}))
    date_to = forms.DateField(required=False, label="Do", widget=forms.DateInput(attrs={"type": "date"}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()


class UserRoleForm(forms.ModelForm, BaseStyledForm):
    user = forms.ModelChoiceField(queryset=User.objects.filter(is_active=True).order_by("username"), label="Użytkownik")

    class Meta:
        model = UserRole
        fields = ["user", "role", "notes"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._style_fields()
