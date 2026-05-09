from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.db.models import Count, Sum

from .constants import MIESIACE_PL
from .models import (
    FakturaKosztowa,
    FakturaSprzedazy,
    ImportDemona,
    JPKDeklaracja,
    Kontrahent,
    UstawieniaFirmy,
)
from .rozliczenia import zbuduj_urzedy_context


ZERO = Decimal('0.00')


def company_years(user):
    sales_years = list(
        FakturaSprzedazy.objects.filter(user=user)
        .values_list('data_wystawienia__year', flat=True)
        .distinct()
        .order_by('data_wystawienia__year')
    )
    cost_years = list(
        FakturaKosztowa.objects.filter(user=user)
        .values_list('data_zakupu__year', flat=True)
        .distinct()
        .order_by('data_zakupu__year')
    )
    declaration_years = list(
        JPKDeklaracja.objects.filter(user=user)
        .values_list('rok', flat=True)
        .distinct()
        .order_by('rok')
    )
    years = sorted(set(sales_years + cost_years + declaration_years))
    return years or [date.today().year]


def resolve_year(year_param, years):
    try:
        year = int(year_param) if year_param else max(years)
    except (TypeError, ValueError):
        year = max(years)
    if year not in years:
        years = sorted(set([*years, year]))
    return year, years


def resolve_month(month_param, fallback_month=None):
    month_default = fallback_month or date.today().month
    try:
        month = int(month_param) if month_param else month_default
    except (TypeError, ValueError):
        month = month_default
    return month if 1 <= month <= 12 else month_default


def sales_year_queryset(user, year):
    return FakturaSprzedazy.objects.filter(user=user, data_wystawienia__year=year).select_related('kontrahent')


def costs_year_queryset(user, year):
    return FakturaKosztowa.objects.filter(user=user, data_zakupu__year=year)


def month_status(cost_count, has_declaration):
    if cost_count > 0 and has_declaration:
        return 'gotowe', 'JPK gotowe', 'Miesiąc ma koszty i zapisane dane deklaracyjne.'
    if cost_count > 0 and not has_declaration:
        return 'wymaga_deklaracji', 'Uzupełnij deklarację', 'Koszty są gotowe, ale brakuje danych deklaracyjnych.'
    if cost_count == 0 and has_declaration:
        return 'bez_kosztow', 'Sprawdź koszty', 'Deklaracja istnieje, ale brak kosztów przypisanych do JPK.'
    return 'brak_danych', 'Brak danych', 'Miesiąc nie ma jeszcze dokumentów do rozliczenia.'


def dashboard_months(user, year):
    sales_aggregates = {
        row['data_wystawienia__month']: row['suma'] or ZERO
        for row in sales_year_queryset(user, year).filter(czy_oplacona=True)
        .values('data_wystawienia__month')
        .annotate(suma=Sum('kwota_brutto'))
    }
    costs_aggregates = {
        row['data_zakupu__month']: row['suma'] or ZERO
        for row in costs_year_queryset(user, year)
        .values('data_zakupu__month')
        .annotate(suma=Sum('kwota_brutto'))
    }
    jpk_costs = {
        row['miesiac_jpk']: {
            'liczba_kosztow': row['liczba_kosztow'],
            'suma_kosztow': row['suma_kosztow'] or ZERO,
        }
        for row in costs_year_queryset(user, year).filter(miesiac_jpk__isnull=False)
        .values('miesiac_jpk')
        .annotate(liczba_kosztow=Count('id'), suma_kosztow=Sum('kwota_brutto'))
    }
    declarations = {declaration.miesiac: declaration for declaration in JPKDeklaracja.objects.filter(user=user, rok=year)}

    months = []
    for month_no in range(1, 13):
        income = sales_aggregates.get(month_no, ZERO)
        cost = costs_aggregates.get(month_no, ZERO)
        cost_info = jpk_costs.get(month_no, {'liczba_kosztow': 0, 'suma_kosztow': ZERO})
        has_declaration = month_no in declarations
        status_code, status_label, status_description = month_status(cost_info['liczba_kosztow'], has_declaration)
        months.append(
            {
                'nr': month_no,
                'nazwa': MIESIACE_PL[month_no],
                'przychod': income,
                'koszt': cost,
                'bilans': income - cost,
                'liczba_kosztow': cost_info['liczba_kosztow'],
                'suma_kosztow_jpk': cost_info['suma_kosztow'],
                'ma_deklaracje': has_declaration,
                'gotowe': status_code == 'gotowe',
                'status_kod': status_code,
                'status_etykieta': status_label,
                'status_opis': status_description,
            }
        )
    return months


def company_dashboard_context(user, year, years):
    sales_qs = sales_year_queryset(user, year)
    costs_qs = costs_year_queryset(user, year)
    income = sales_qs.filter(czy_oplacona=True).aggregate(suma=Sum('kwota_brutto'))['suma'] or ZERO
    costs = costs_qs.aggregate(suma=Sum('kwota_brutto'))['suma'] or ZERO
    months = dashboard_months(user, year)
    ready_months = sum(1 for month in months if month['gotowe'])
    return {
        'rok': year,
        'lata': years,
        'przychod': income,
        'koszty': costs,
        'dochod': income - costs,
        'miesiace': months,
        'gotowe_miesiace': ready_months,
        'miesiace_z_deklaracja': sum(1 for month in months if month['ma_deklaracje']),
        'miesiace_z_kosztami_jpk': sum(1 for month in months if month['liczba_kosztow'] > 0),
        'jpk_progres': int((ready_months / 12) * 100),
        'pozostale_miesiace': 12 - ready_months,
    }


def company_month_detail_context(user, year, month, years):
    if year not in years:
        years = sorted(set([*years, year]))

    sales = (
        FakturaSprzedazy.objects.filter(user=user, data_wystawienia__year=year, data_wystawienia__month=month)
        .select_related('kontrahent')
        .order_by('-data_wystawienia', '-id')
    )
    costs = FakturaKosztowa.objects.filter(user=user, data_zakupu__year=year, data_zakupu__month=month).order_by('-data_zakupu', '-id')
    declaration = JPKDeklaracja.objects.filter(user=user, rok=year, miesiac=month).first()
    income = sales.filter(czy_oplacona=True).aggregate(suma=Sum('kwota_brutto'))['suma'] or ZERO
    cost = costs.aggregate(suma=Sum('kwota_brutto'))['suma'] or ZERO
    jpk_cost_count = costs.exclude(miesiac_jpk__isnull=True).count()
    status_code, status_label, status_description = month_status(jpk_cost_count, bool(declaration))

    return {
        'rok': year,
        'miesiac': month,
        'miesiac_nazwa': MIESIACE_PL[month],
        'lata': years,
        'sprzedaze': sales,
        'koszty': costs,
        'deklaracja': declaration,
        'przychod': income,
        'koszt': cost,
        'dochod': income - cost,
        'liczba_kosztow_jpk': jpk_cost_count,
        'status_kod': status_code,
        'status_etykieta': status_label,
        'status_opis': status_description,
    }


def company_settings_instance(user):
    return UstawieniaFirmy.objects.filter(user=user).first()


def contractors_context(user):
    return {'kontrahenci': Kontrahent.objects.filter(user=user).order_by('nazwa')}


def sales_invoices_context(user):
    return {'faktury': FakturaSprzedazy.objects.filter(user=user).select_related('kontrahent').order_by('-data_wystawienia', '-id')}


def cost_invoices_context(user):
    return {'faktury': FakturaKosztowa.objects.filter(user=user).order_by('-data_zakupu', '-id')}


def daemon_imports_context(user):
    return {'importy': ImportDemona.objects.filter(user=user).order_by('-created_at', '-id')[:100]}


def declaration_context(user, year, years, month):
    return {
        'rok': year,
        'miesiac': month,
        'lata': years,
        'instance': JPKDeklaracja.objects.filter(user=user, rok=year, miesiac=month).first(),
    }


def jpk_export_context(user, year, years):
    months = dashboard_months(user, year)
    return {
        'rok': year,
        'lata': years,
        'miesiace': months,
        'gotowe_count': sum(1 for month in months if month['gotowe']),
    }


def office_settlements_context(user, year, years, month):
    return {
        'rok': year,
        'lata': years,
        'miesiac': month,
        'miesiac_nazwa': MIESIACE_PL[month],
        'miesiace_nazwy': MIESIACE_PL,
        'miesiace_opcje': [(index, MIESIACE_PL[index]) for index in range(1, 13)],
        **zbuduj_urzedy_context(user, year, month),
    }
