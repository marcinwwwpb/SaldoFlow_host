from __future__ import annotations

from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.db import transaction
from django.urls import reverse

from paneladmin.permissions import finance_write_required

from .forms import CelOszczednosciowyForm, KontoDomoweForm, OperacjaForm
from .selectors import (
    accounts_context,
    get_user_years,
    monthly_dashboard_context,
    monthly_detail_context,
    monthly_reports_context,
    resolve_year,
    savings_goal_context,
)
from .services import (
    ImportValidationError,
    build_operations_csv_response,
    build_operations_xml_response,
    generate_monthly_report,
    import_operations_from_csv,
    import_operations_from_xml,
    save_account,
    save_operation,
    save_savings_goal,
)


@login_required
def lista_miesiecy(request):
    current_year = datetime.now().year
    years = get_user_years(request.user)
    year, years = resolve_year(request.GET.get('rok'), years)
    context = {
        'rok': year,
        'aktualny_rok': current_year,
        'lata': years,
        **monthly_dashboard_context(request.user, year),
    }
    return render(request, 'finanse/miesiace.html', context)


@login_required
def miesiac_detail(request, rok, miesiac):
    query = request.GET.get('q', '').strip()
    return render(request, 'finanse/miesiac_detail.html', monthly_detail_context(request.user, rok, miesiac, query))


@login_required
def centrum_importu_eksportu(request):
    return render(request, 'finanse/import_export_hub.html')


@finance_write_required
def dodaj_operacje(request):
    form = OperacjaForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        save_operation(form, request.user)
        messages.success(request, 'Operacja została zapisana.')
        return redirect('lista_miesiecy')
    return render(request, 'finanse/dodaj.html', {'form': form})


@login_required
def eksport_csv(request):
    return build_operations_csv_response(request.user)


@login_required
def eksport_xml(request):
    return build_operations_xml_response(request.user)


@finance_write_required
@transaction.atomic
def import_xml(request):
    if request.method == 'POST':
        uploaded_file = request.FILES.get('plik')
        if not uploaded_file:
            messages.error(request, 'Nie wybrano pliku XML.')
            return redirect('import_xml')
        try:
            created = import_operations_from_xml(request.user, uploaded_file)
        except ImportValidationError as exc:
            messages.error(request, str(exc))
            return redirect('import_xml')
        messages.success(request, f'Zaimportowano {created} operacji z XML.')
        return redirect('lista_miesiecy')
    return render(request, 'finanse/import_xml.html')


@finance_write_required
@transaction.atomic
def import_csv(request):
    if request.method == 'POST':
        uploaded_file = request.FILES.get('plik')
        if not uploaded_file:
            messages.error(request, 'Nie wybrano pliku CSV.')
            return redirect('import_csv')
        try:
            created = import_operations_from_csv(request.user, uploaded_file)
        except ImportValidationError as exc:
            messages.error(request, str(exc))
            return redirect('import_csv')
        messages.success(request, f'Zaimportowano {created} operacji.')
        return redirect('lista_miesiecy')
    return render(request, 'finanse/import.html')


@finance_write_required
def ustaw_cel(request):
    year = datetime.now().year
    context = savings_goal_context(request.user, year)
    form = CelOszczednosciowyForm(request.POST or None, instance=context['obecny_cel'])
    if request.method == 'POST' and form.is_valid():
        save_savings_goal(form, request.user, year)
        messages.success(request, 'Cel oszczędnościowy został zapisany.')
        return redirect('lista_miesiecy')
    context['form'] = form
    return render(request, 'finanse/ustaw_cel.html', context)


@login_required
def lista_kont(request):
    return render(request, 'finanse/konta_lista.html', accounts_context(request.user))


@finance_write_required
def dodaj_konto(request):
    form = KontoDomoweForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        save_account(form, request.user)
        messages.success(request, 'Konto zostało zapisane.')
        return redirect('lista_kont')
    return render(request, 'finanse/dodaj_konto.html', {'form': form})


@finance_write_required
def raporty_miesieczne(request):
    year = int(request.GET.get('rok') or datetime.now().year)
    month = int(request.GET.get('miesiac') or datetime.now().month)
    if request.method == 'POST':
        generate_monthly_report(request.user.id, year, month)
        messages.success(request, f'Wygenerowano raport dla {year}-{month:02d}.')
        return redirect(f"{reverse('raporty_miesieczne')}?rok={year}&miesiac={month}")
    return render(request, 'finanse/raporty_miesieczne.html', monthly_reports_context(request.user, year, month))
