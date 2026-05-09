from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import redirect, render

from paneladmin.permissions import can_manage_finance_data, finance_write_required

from .ceidg import lookup_company_by_nip
from .forms import (
    FakturaKosztowaForm,
    FakturaSprzedazyForm,
    ImportKosztowExcelForm,
    JPKDeklaracjaForm,
    KontrahentForm,
    UstawieniaFirmyForm,
)
from .importers import import_koszty_excel_for_user
from .selectors import (
    company_dashboard_context,
    company_month_detail_context,
    company_settings_instance,
    company_years,
    contractors_context,
    cost_invoices_context,
    daemon_imports_context,
    declaration_context,
    jpk_export_context,
    office_settlements_context,
    resolve_month,
    resolve_year,
    sales_invoices_context,
)
from .services import (
    JPKExportError,
    build_jpk_csv_response,
    build_jpk_export_response,
    build_office_package_response,
    recalculate_jpk_declaration,
    save_company_settings,
    save_contractor,
    save_cost_invoice,
    save_jpk_declaration,
    save_sales_invoice,
)


@login_required
def dashboard_firmy(request):
    years = company_years(request.user)
    year, years = resolve_year(request.GET.get('rok') or request.POST.get('rok'), years)
    return render(request, 'firma/dashboard.html', company_dashboard_context(request.user, year, years))


@login_required
def miesiac_firmy_detail(request, rok, miesiac):
    years = company_years(request.user)
    return render(request, 'firma/miesiac_detail.html', company_month_detail_context(request.user, rok, miesiac, years))


@finance_write_required
def ustawienia_firmy(request):
    instance = company_settings_instance(request.user)
    form = UstawieniaFirmyForm(request.POST or None, instance=instance, user=request.user)
    if request.method == 'POST' and form.is_valid():
        save_company_settings(form, request.user)
        messages.success(request, 'Zapisano ustawienia firmy.')
        return redirect('firma_dashboard')
    return render(request, 'firma/ustawienia_firmy_form.html', {'form': form})


@login_required
def api_ceidg_po_nip(request):
    nip = request.GET.get('nip', '')
    try:
        data = lookup_company_by_nip(nip)
        return JsonResponse({'ok': True, 'dane': data})
    except Exception as exc:
        return JsonResponse({'ok': False, 'error': str(exc)}, status=400)


@login_required
def lista_kontrahentow(request):
    return render(request, 'firma/kontrahenci_lista.html', contractors_context(request.user))


@finance_write_required
def dodaj_kontrahenta(request):
    form = KontrahentForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        save_contractor(form, request.user)
        messages.success(request, 'Dodano kontrahenta.')
        return redirect('kontrahenci')
    return render(request, 'firma/kontrahent_form.html', {'form': form})


@login_required
def lista_faktur_sprzedazy(request):
    return render(request, 'firma/faktury_sprzedaz_lista.html', sales_invoices_context(request.user))


@finance_write_required
def dodaj_fakture_sprzedazy(request):
    form = FakturaSprzedazyForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        save_sales_invoice(form, request.user)
        messages.success(request, 'Dodano fakturę sprzedaży.')
        return redirect('faktury_sprzedazy')
    return render(request, 'firma/faktura_sprzedaz_form.html', {'form': form})


@login_required
def lista_faktur_kosztowych(request):
    return render(request, 'firma/faktury_koszt_lista.html', cost_invoices_context(request.user))


@finance_write_required
def dodaj_fakture_kosztowa(request):
    form = FakturaKosztowaForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        save_cost_invoice(form, request.user)
        messages.success(request, 'Dodano fakturę kosztową.')
        return redirect('faktury_kosztowe')
    return render(request, 'firma/faktura_koszt_form.html', {'form': form})


@finance_write_required
def import_kosztow_excel(request):
    form = ImportKosztowExcelForm(request.POST or None, request.FILES or None)
    if request.method == 'POST' and form.is_valid():
        uploaded_file = form.cleaned_data['plik']
        try:
            summary = import_koszty_excel_for_user(
                user=request.user,
                fileobj=uploaded_file,
                source_name=getattr(uploaded_file, 'name', 'import.xlsx'),
            )
        except Exception as exc:
            messages.error(request, str(exc))
            return render(request, 'firma/import_kosztow_excel.html', {'form': form})

        if summary['bledy']:
            messages.warning(
                request,
                f"Zaimportowano {summary['dodane']} pozycji, ale część wierszy pominięto. " + ' | '.join(summary['bledy'][:5]),
            )
        else:
            messages.success(request, f"Zaimportowano {summary['dodane']} pozycji kosztowych.")
        return redirect('faktury_kosztowe')
    return render(request, 'firma/import_kosztow_excel.html', {'form': form})


@login_required
def lista_importow_demona(request):
    return render(request, 'firma/importy_demona_lista.html', daemon_imports_context(request.user))


@login_required
def deklaracja_jpk(request):
    years = company_years(request.user)
    year, years = resolve_year(request.GET.get('rok') or request.POST.get('rok'), years)
    month = resolve_month(request.GET.get('miesiac') or request.POST.get('miesiac'))
    context = declaration_context(request.user, year, years, month)
    can_edit = can_manage_finance_data(request.user)

    if request.method == 'POST' and not can_edit:
        messages.error(request, 'To konto ma dostęp tylko do odczytu.')
        return redirect(f'{request.path}?rok={year}&miesiac={month}')

    if request.method == 'POST' and request.POST.get('auto_wylicz') == '1':
        recalculate_jpk_declaration(request.user.id, year, month)
        messages.success(request, 'Deklaracja została przeliczona procedurą bazy danych.')
        return redirect(f'{request.path}?rok={year}&miesiac={month}')

    form = JPKDeklaracjaForm(request.POST or None, instance=context['instance'], user=request.user)
    if not can_edit:
        for field in form.fields.values():
            field.disabled = True
    if request.method == 'POST' and form.is_valid():
        save_jpk_declaration(form, request.user, year, month)
        messages.success(request, 'Zapisano dane deklaracyjne JPK.')
        return redirect('firma_miesiac_detail', rok=year, miesiac=month)

    context['form'] = form
    context['can_edit'] = can_edit
    context.pop('instance', None)
    return render(request, 'firma/deklaracja_jpk_form.html', context)


@login_required
def eksport_jpk_v7m(request):
    years = company_years(request.user)
    year, years = resolve_year(request.GET.get('rok') or request.POST.get('rok'), years)
    context = jpk_export_context(request.user, year, years)

    if request.method == 'POST':
        selected = request.POST.getlist('miesiace')
        if request.POST.get('pobierz_wszystkie'):
            selected = [str(month['nr']) for month in context['miesiace'] if month['gotowe']]

        months = []
        for value in selected:
            try:
                month_no = int(value)
            except (TypeError, ValueError):
                continue
            if 1 <= month_no <= 12:
                months.append(month_no)

        try:
            return build_jpk_export_response(request.user, year, months)
        except JPKExportError as exc:
            messages.error(request, str(exc))
            return redirect(f'{request.path}?rok={year}')

    return render(request, 'firma/eksport_jpk.html', context)


@login_required
def eksport_jpk_csv(request):
    return build_jpk_csv_response(request.user)


@login_required
def rozliczenia_urzedow(request):
    years = company_years(request.user)
    year, years = resolve_year(request.GET.get('rok') or request.POST.get('rok'), years)
    month = resolve_month(request.GET.get('miesiac') or request.POST.get('miesiac'))

    if request.method == 'POST' and request.POST.get('akcja') == 'pobierz_pakiet':
        scope = request.POST.get('scope', 'ALL')
        return build_office_package_response(request.user, year, month, scope=scope)

    return render(request, 'firma/rozliczenia_urzedow.html', office_settlements_context(request.user, year, years, month))
