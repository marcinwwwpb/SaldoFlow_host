from __future__ import annotations

from decimal import Decimal

from django.db.models import Sum
from django.urls import reverse

from finanse.models import KontoDomowe, Operacja
from firma.models import FakturaKosztowa, FakturaSprzedazy, UstawieniaFirmy
from paneladmin.permissions import can_access_admin_panel


def module_selector_context(user):
    dom_accounts = KontoDomowe.objects.filter(uzytkownik=user).count()
    dom_operations = Operacja.objects.filter(uzytkownik=user).count()
    dom_balance = (
        Operacja.objects.filter(uzytkownik=user).aggregate(suma=Sum('kwota'))['suma']
        or Decimal('0.00')
    )

    company_settings_ready = UstawieniaFirmy.objects.filter(user=user).exists()
    company_sales = FakturaSprzedazy.objects.filter(user=user).count()
    company_costs = FakturaKosztowa.objects.filter(user=user).count()
    company_turnover = (
        FakturaSprzedazy.objects.filter(user=user).aggregate(suma=Sum('kwota_brutto'))['suma']
        or Decimal('0.00')
    )
    company_documents = company_sales + company_costs

    onboarding = [
        {'label': 'Aktywne konto', 'done': user.is_active},
        {'label': 'Pierwsze konto domowe', 'done': dom_accounts > 0},
        {'label': 'Ustawienia firmy', 'done': company_settings_ready},
        {'label': 'Pierwsza operacja lub faktura', 'done': (dom_operations + company_documents) > 0},
    ]

    next_step = None
    if dom_accounts == 0:
        next_step = {'label': 'Dodaj pierwsze konto domowe', 'url': reverse('dodaj_konto')}
    elif dom_operations == 0:
        next_step = {'label': 'Dodaj pierwszą operację', 'url': reverse('dodaj_operacje')}
    elif not company_settings_ready:
        next_step = {'label': 'Uzupełnij ustawienia firmy', 'url': reverse('ustawienia_firmy')}
    elif company_documents == 0:
        next_step = {'label': 'Dodaj pierwszą fakturę', 'url': reverse('dodaj_fakture_sprzedazy')}

    return {
        'dom_accounts': dom_accounts,
        'dom_operations': dom_operations,
        'dom_balance': dom_balance,
        'company_settings_ready': company_settings_ready,
        'company_sales': company_sales,
        'company_costs': company_costs,
        'company_turnover': company_turnover,
        'company_documents': company_documents,
        'onboarding': onboarding,
        'onboarding_done': sum(1 for item in onboarding if item['done']),
        'next_step': next_step,
        'show_admin_shortcuts': can_access_admin_panel(user),
    }
