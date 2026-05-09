from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from .constants import MIESIACE_PL
from .models import CelOszczednosciowy, KontoDomowe, Operacja, RaportMiesieczny


ZERO = Decimal('0.00')


def get_user_years(user):
    lata_operacji = list(
        Operacja.objects.filter(uzytkownik=user)
        .values_list('data__year', flat=True)
        .distinct()
        .order_by('data__year')
    )
    lata_celow = list(
        CelOszczednosciowy.objects.filter(uzytkownik=user)
        .values_list('rok', flat=True)
        .distinct()
        .order_by('rok')
    )
    lata = sorted(set(lata_operacji + lata_celow))
    return lata or [datetime.now().year]


def resolve_year(year_param, years):
    try:
        year = int(year_param) if year_param else max(years)
    except (TypeError, ValueError):
        year = max(years)
    if year not in years:
        years = sorted(set([*years, year]))
    return year, years


def monthly_dashboard_context(user, year):
    operations_year = list(
        Operacja.objects.filter(uzytkownik=user, data__year=year)
        .select_related('typ_operacji', 'kategoria')
        .order_by('data', 'id')
    )

    months = []
    category_totals = {}
    incomes_year = ZERO
    expenses_year = ZERO
    incomes_series = []
    expenses_series = []

    for month in range(1, 13):
        operations_month = [operation for operation in operations_year if operation.data.month == month]
        incomes = ZERO
        expenses = ZERO

        for operation in operations_month:
            amount = operation.kwota
            if operation.czy_przychod:
                incomes += amount
                incomes_year += amount
            else:
                expenses += amount
                expenses_year += amount
                category_name = operation.kategoria.nazwa
                category_totals[category_name] = category_totals.get(category_name, ZERO) + amount

        balance = incomes - expenses
        incomes_series.append(float(round(incomes, 2)))
        expenses_series.append(float(round(expenses, 2)))
        months.append(
            {
                'nr': month,
                'nazwa': MIESIACE_PL[month],
                'przychody': incomes,
                'wydatki': expenses,
                'saldo': balance,
            }
        )

    savings = incomes_year - expenses_year
    goal = CelOszczednosciowy.objects.filter(uzytkownik=user, rok=year).first()
    progress = None
    if goal and goal.kwota_docelowa > 0:
        progress_value = (savings / goal.kwota_docelowa) * 100
        progress = max(0, min(round(float(progress_value), 2), 100))

    return {
        'miesiace': months,
        'przychody_rok': incomes_year,
        'wydatki_rok': expenses_year,
        'oszczednosci': savings,
        'przychody_mies': incomes_series,
        'wydatki_mies': expenses_series,
        'cel': goal,
        'procent': progress,
        'labels_kategorie': list(category_totals.keys()),
        'values_kategorie': [float(round(value, 2)) for value in category_totals.values()],
    }


def monthly_detail_context(user, year, month, query=''):
    operations = (
        Operacja.objects.filter(
            uzytkownik=user,
            data__year=year,
            data__month=month,
        )
        .select_related('typ_operacji', 'kategoria')
        .order_by('-data', '-id')
    )

    if query:
        operations = operations.filter(tytul__icontains=query)

    incomes = ZERO
    expenses = ZERO
    categories = {}

    for operation in operations:
        amount = operation.kwota
        if operation.czy_przychod:
            incomes += amount
        else:
            expenses += amount
            category_name = operation.kategoria.nazwa
            categories[category_name] = categories.get(category_name, ZERO) + amount

    return {
        'operacje': operations,
        'rok': year,
        'miesiac': month,
        'nazwa_miesiaca': MIESIACE_PL[month],
        'przychody': incomes,
        'wydatki': expenses,
        'saldo': incomes - expenses,
        'labels': list(categories.keys()),
        'values': [float(round(value, 2)) for value in categories.values()],
        'q': query,
    }


def accounts_context(user):
    return {'konta': KontoDomowe.objects.filter(uzytkownik=user).order_by('nazwa')}


def savings_goal_context(user, year):
    current_goal = CelOszczednosciowy.objects.filter(uzytkownik=user, rok=year).first()
    return {
        'rok': year,
        'obecny_cel': current_goal,
    }


def monthly_reports_context(user, year, month):
    return {
        'raporty': RaportMiesieczny.objects.filter(uzytkownik=user).order_by('-rok', '-miesiac')[:24],
        'rok': year,
        'miesiac': month,
    }
