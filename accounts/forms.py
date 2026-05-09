from django import forms
from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError

User = get_user_model()


class StyledMixin:
    def style_fields(self):
        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(widget, forms.Textarea):
                widget.attrs.setdefault("class", "form-control")
                widget.attrs.setdefault("rows", 4)
            else:
                widget.attrs.setdefault("class", "form-control")


class RegistrationForm(forms.Form, StyledMixin):
    first_name = forms.CharField(label="Imię", max_length=150)
    last_name = forms.CharField(label="Nazwisko", max_length=150)
    email = forms.EmailField(label="E-mail")
    password1 = forms.CharField(label="Hasło", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Powtórz hasło", widget=forms.PasswordInput)
    privacy = forms.BooleanField(label="Akceptuję regulamin i politykę prywatności")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()
        self.fields["first_name"].widget.attrs.setdefault("placeholder", "Imię")
        self.fields["last_name"].widget.attrs.setdefault("placeholder", "Nazwisko")
        self.fields["email"].widget.attrs.setdefault("placeholder", "twoj@email.pl")

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if get_user_model().objects.filter(email__iexact=email).exists():
            raise ValidationError("Konto z tym adresem e-mail już istnieje.")
        return email

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Hasła muszą być identyczne.")
        if password1 and len(password1) < 8:
            self.add_error("password1", "Hasło musi mieć co najmniej 8 znaków.")
        return cleaned

    def save(self):
        email = self.cleaned_data["email"].strip().lower()
        user = get_user_model().objects.create_user(
            username=email,
            email=email,
            first_name=self.cleaned_data["first_name"].strip(),
            last_name=self.cleaned_data["last_name"].strip(),
            password=self.cleaned_data["password1"],
            is_active=False,
        )
        return user


class EmailAuthenticationForm(AuthenticationForm, StyledMixin):
    username = forms.CharField(label="E-mail lub login")

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self.style_fields()
        self.fields["username"].widget.attrs.setdefault("placeholder", "E-mail lub login")
        self.fields["password"].widget.attrs.setdefault("placeholder", "Hasło")

    def clean(self):
        username = (self.cleaned_data.get("username") or "").strip()
        password = self.cleaned_data.get("password")

        if username and password:
            self.user_cache = authenticate(self.request, username=username, password=password)
            if self.user_cache is None:
                UserModel = get_user_model()
                existing_user = UserModel.objects.filter(email__iexact=username).first() or UserModel.objects.filter(username__iexact=username).first()
                if existing_user and existing_user.check_password(password) and not existing_user.is_active:
                    raise ValidationError(
                        "Konto nie zostało jeszcze aktywowane. Sprawdź wiadomość e-mail lub wyślij link ponownie.",
                        code="inactive",
                    )
                raise ValidationError(
                    "Nieprawidłowy login lub hasło.",
                    code="invalid_login",
                )
            self.confirm_login_allowed(self.user_cache)

        return self.cleaned_data


class ResendActivationForm(forms.Form, StyledMixin):
    email = forms.EmailField(label="E-mail")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.style_fields()

    def clean_email(self):
        return self.cleaned_data["email"].strip().lower()
