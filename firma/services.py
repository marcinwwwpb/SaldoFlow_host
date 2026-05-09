from __future__ import annotations

import csv
from datetime import date, datetime
from decimal import Decimal
from io import BytesIO
import xml.etree.ElementTree as ET
import zipfile

from django.http import HttpResponse

from core.db import call_stored_procedure

from .models import FakturaKosztowa, JPKDeklaracja, UstawieniaFirmy
from .rozliczenia import zbuduj_pakiet_urzedow


class JPKExportError(ValueError):
    """Raised when JPK export prerequisites are missing."""


def save_company_settings(form, user):
    settings = form.save(commit=False)
    settings.user = user
    settings.save()
    return settings


def save_contractor(form, user):
    contractor = form.save(commit=False)
    contractor.user = user
    contractor.save()
    return contractor


def save_sales_invoice(form, user):
    invoice = form.save(commit=False)
    invoice.user = user
    invoice.save()
    return invoice


def save_cost_invoice(form, user):
    invoice = form.save(commit=False)
    invoice.user = user
    invoice.save()
    return invoice


def save_jpk_declaration(form, user, year, month):
    declaration = form.save(commit=False)
    declaration.user = user
    declaration.rok = year
    declaration.miesiac = month
    declaration.save()
    return declaration


def recalculate_jpk_declaration(user_id, year, month):
    call_stored_procedure('firma_przelicz_jpk_deklaracja', [user_id, year, month])


def _pretty_xml(element):
    raw = ET.tostring(element, encoding='utf-8', xml_declaration=True)
    try:
        from xml.dom import minidom

        parsed = minidom.parseString(raw)
        return parsed.toprettyxml(indent='  ', encoding='utf-8')
    except Exception:
        return raw


def _address_parts(company_settings):
    address = (company_settings.adres or '').split(',')
    city = address[1].strip() if len(address) > 1 else ''
    street_part = address[0].strip() if address else ''
    postal_code = ''
    street = street_part
    house_no = ''
    if street_part:
        parts = street_part.rsplit(' ', 1)
        if len(parts) == 2 and any(char.isdigit() for char in parts[1]):
            street, house_no = parts[0], parts[1]
    return {
        'kod_kraju': 'PL',
        'wojewodztwo': '',
        'powiat': '',
        'gmina': '',
        'ulica': street,
        'nr_domu': house_no,
        'nr_lokalu': '',
        'miejscowosc': city,
        'kod_pocztowy': postal_code,
    }


def build_jpk_xml(user, year, month):
    company_settings = UstawieniaFirmy.objects.filter(user=user).first()
    if not company_settings:
        raise JPKExportError('Najpierw uzupełnij ustawienia firmy.')
    if not company_settings.nip or not company_settings.nazwa_firmy or not company_settings.kod_urzedu_skarbowego:
        raise JPKExportError('W ustawieniach firmy uzupełnij nazwę firmy, NIP i kod urzędu skarbowego.')

    declaration = JPKDeklaracja.objects.filter(user=user, rok=year, miesiac=month).first()
    if not declaration:
        raise JPKExportError('Brakuje danych deklaracyjnych JPK dla wybranego miesiąca.')

    invoices = list(FakturaKosztowa.objects.filter(user=user, data_zakupu__year=year, miesiac_jpk=month).order_by('data_zakupu', 'id'))
    if not invoices:
        raise JPKExportError('Brak faktur kosztowych dla wybranego okresu.')

    vat_sum = sum((invoice.kwota_vat for invoice in invoices), Decimal('0.00'))
    net_sum = sum((invoice.kwota_netto for invoice in invoices), Decimal('0.00'))
    gross_sum = sum((invoice.kwota_brutto for invoice in invoices), Decimal('0.00'))
    nsmap = {
        'etd': 'http://crd.gov.pl/wzor/2023/12/27/13064/',
        'xsi': 'http://www.w3.org/2001/XMLSchema-instance',
    }
    ET.register_namespace('', nsmap['etd'])
    ET.register_namespace('xsi', nsmap['xsi'])
    root = ET.Element(
        '{http://crd.gov.pl/wzor/2023/12/27/13064/}JPK',
        {
            '{http://www.w3.org/2001/XMLSchema-instance}schemaLocation': (
                'http://crd.gov.pl/wzor/2023/12/27/13064/ http://crd.gov.pl/wzor/2023/12/27/13064/schemat.xsd'
            )
        },
    )

    header = ET.SubElement(root, '{http://crd.gov.pl/wzor/2023/12/27/13064/}Naglowek')
    ET.SubElement(header, '{http://crd.gov.pl/wzor/2023/12/27/13064/}KodFormularza').text = 'JPK_V7M'
    ET.SubElement(header, '{http://crd.gov.pl/wzor/2023/12/27/13064/}WariantFormularza').text = '1'
    ET.SubElement(header, '{http://crd.gov.pl/wzor/2023/12/27/13064/}CelZlozenia').text = '1'
    ET.SubElement(header, '{http://crd.gov.pl/wzor/2023/12/27/13064/}KodUrzedu').text = company_settings.kod_urzedu_skarbowego
    ET.SubElement(header, '{http://crd.gov.pl/wzor/2023/12/27/13064/}Rok').text = str(year)
    ET.SubElement(header, '{http://crd.gov.pl/wzor/2023/12/27/13064/}Miesiac').text = str(month)

    entity = ET.SubElement(root, '{http://crd.gov.pl/wzor/2023/12/27/13064/}Podmiot1')
    identifier = ET.SubElement(entity, '{http://crd.gov.pl/wzor/2023/12/27/13064/}IdentyfikatorPodmiotu')
    ET.SubElement(identifier, '{http://crd.gov.pl/wzor/2023/12/27/13064/}NIP').text = company_settings.nip
    ET.SubElement(identifier, '{http://crd.gov.pl/wzor/2023/12/27/13064/}PelnaNazwa').text = company_settings.nazwa_firmy

    address_data = _address_parts(company_settings)
    address = ET.SubElement(entity, '{http://crd.gov.pl/wzor/2023/12/27/13064/}AdresPodmiotu')
    for field_name, field_value in [
        ('KodKraju', address_data['kod_kraju']),
        ('Wojewodztwo', address_data['wojewodztwo']),
        ('Powiat', address_data['powiat']),
        ('Gmina', address_data['gmina']),
        ('Ulica', address_data['ulica']),
        ('NrDomu', address_data['nr_domu']),
        ('NrLokalu', address_data['nr_lokalu']),
        ('Miejscowosc', address_data['miejscowosc']),
        ('KodPocztowy', address_data['kod_pocztowy']),
    ]:
        ET.SubElement(address, f'{{http://crd.gov.pl/wzor/2023/12/27/13064/}}{field_name}').text = field_value

    declaration_element = ET.SubElement(root, '{http://crd.gov.pl/wzor/2023/12/27/13064/}Deklaracja')
    for name, value in [
        ('P_17', declaration.p_17),
        ('P_18', declaration.p_18),
        ('P_19', declaration.p_19),
        ('P_20', declaration.p_20),
        ('P_51', declaration.p_51),
        ('P_68', '1' if declaration.p_68 else '0'),
    ]:
        ET.SubElement(declaration_element, f'{{http://crd.gov.pl/wzor/2023/12/27/13064/}}{name}').text = str(value)
    if declaration.uzasadnienie:
        ET.SubElement(
            declaration_element,
            '{http://crd.gov.pl/wzor/2023/12/27/13064/}UzasadnieniePrzyczynyKorekty',
        ).text = declaration.uzasadnienie

    purchase_register = ET.SubElement(root, '{http://crd.gov.pl/wzor/2023/12/27/13064/}EwidencjaZakupow')
    for index, invoice in enumerate(invoices, start=1):
        purchase_row = ET.SubElement(purchase_register, '{http://crd.gov.pl/wzor/2023/12/27/13064/}ZakupWiersz')
        ET.SubElement(purchase_row, '{http://crd.gov.pl/wzor/2023/12/27/13064/}LpZakupu').text = str(index)
        ET.SubElement(purchase_row, '{http://crd.gov.pl/wzor/2023/12/27/13064/}NrDostawcy').text = invoice.nip_dostawcy or ''
        ET.SubElement(purchase_row, '{http://crd.gov.pl/wzor/2023/12/27/13064/}NazwaDostawcy').text = invoice.kontrahent_nazwa or ''
        ET.SubElement(purchase_row, '{http://crd.gov.pl/wzor/2023/12/27/13064/}DowodZakupu').text = invoice.numer_faktury
        ET.SubElement(purchase_row, '{http://crd.gov.pl/wzor/2023/12/27/13064/}DataZakupu').text = invoice.data_zakupu.isoformat()
        ET.SubElement(purchase_row, '{http://crd.gov.pl/wzor/2023/12/27/13064/}K_42').text = str(invoice.kwota_netto)
        ET.SubElement(purchase_row, '{http://crd.gov.pl/wzor/2023/12/27/13064/}K_43').text = str(invoice.kwota_vat)
        ET.SubElement(purchase_row, '{http://crd.gov.pl/wzor/2023/12/27/13064/}ZakupCtrl').text = '1' if invoice.rodzaj_zakupu == 'ST' else '0'

    control = ET.SubElement(purchase_register, '{http://crd.gov.pl/wzor/2023/12/27/13064/}ZakupCtrl')
    ET.SubElement(control, '{http://crd.gov.pl/wzor/2023/12/27/13064/}LiczbaWierszyZakupow').text = str(len(invoices))
    ET.SubElement(control, '{http://crd.gov.pl/wzor/2023/12/27/13064/}PodatekNaliczony').text = str(vat_sum)

    summary = ET.SubElement(root, '{http://crd.gov.pl/wzor/2023/12/27/13064/}Podsumowanie')
    ET.SubElement(summary, '{http://crd.gov.pl/wzor/2023/12/27/13064/}SumaNettoZakupow').text = str(net_sum)
    ET.SubElement(summary, '{http://crd.gov.pl/wzor/2023/12/27/13064/}SumaVatZakupow').text = str(vat_sum)
    ET.SubElement(summary, '{http://crd.gov.pl/wzor/2023/12/27/13064/}SumaBruttoZakupow').text = str(gross_sum)

    return _pretty_xml(root)


def build_jpk_export_response(user, year, months):
    unique_months = sorted(set(months))
    if not unique_months:
        raise JPKExportError('Zaznacz co najmniej jeden miesiąc gotowy do eksportu.')

    if len(unique_months) == 1:
        month = unique_months[0]
        xml_bytes = build_jpk_xml(user, year, month)
        response = HttpResponse(xml_bytes, content_type='application/xml; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="JPK_V7M_{year}_{month:02d}.xml"'
        return response

    memory_file = BytesIO()
    with zipfile.ZipFile(memory_file, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for month in unique_months:
            xml_bytes = build_jpk_xml(user, year, month)
            archive.writestr(f'JPK_V7M_{year}_{month:02d}.xml', xml_bytes)

    memory_file.seek(0)
    response = HttpResponse(memory_file.getvalue(), content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="JPK_V7M_{year}_pakiet.zip"'
    return response


def build_jpk_csv_response(user):
    invoices = FakturaKosztowa.objects.filter(user=user).order_by('data_zakupu', 'id')
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="jpk_vat.csv"'
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['L.p.', 'Numer faktury', 'Data zakupu', 'NIP dostawcy', 'Kontrahent', 'Netto', 'VAT', 'Brutto', 'Kod kraju', 'Rodzaj zakupu'])
    for index, invoice in enumerate(invoices, start=1):
        writer.writerow([
            index,
            invoice.numer_faktury,
            invoice.data_zakupu.isoformat(),
            invoice.nip_dostawcy,
            invoice.kontrahent_nazwa,
            invoice.kwota_netto,
            invoice.kwota_vat,
            invoice.kwota_brutto,
            invoice.kod_kraju,
            invoice.rodzaj_zakupu,
        ])
    return response


def build_office_package_response(user, year, month, scope='ALL'):
    payload = zbuduj_pakiet_urzedow(user, year, month, scope=scope)
    response = HttpResponse(payload, content_type='application/zip')
    response['Content-Disposition'] = f'attachment; filename="rozliczenia_urzedow_{scope.lower()}_{year}_{month:02d}.zip"'
    return response
