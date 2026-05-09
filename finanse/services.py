from __future__ import annotations

import csv
import xml.etree.ElementTree as ET
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.http import HttpResponse
from django.utils.text import slugify

from core.db import call_stored_procedure

from .models import CelOszczednosciowy, Kategoria, KontoDomowe, Operacja, Tag, TypOperacji


class ImportValidationError(ValueError):
    """Raised when imported payload has invalid structure or encoding."""


def parse_import_date(value: str):
    value = (value or "").strip()
    if not value:
        return None

    formats = (
        "%Y-%m-%d",  # 2023-12-06
        "%d.%m.%Y",  # 06.12.2023
        "%d-%m-%Y",  # 06-12-2023
        "%d/%m/%Y",  # 06/12/2023
    )

    for fmt in formats:
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue

    raise ImportValidationError(
        f'Nieobsługiwany format daty: "{value}". '
        'Dozwolone formaty: YYYY-MM-DD, DD.MM.YYYY, DD-MM-YYYY, DD/MM/YYYY.'
    )


def save_operation(form, user):
    operation = form.save(commit=False)
    operation.uzytkownik = user
    operation.save()
    form.save_m2m()
    return operation


def save_account(form, user):
    account = form.save(commit=False)
    account.uzytkownik = user
    account.save()
    return account


def save_savings_goal(form, user, year):
    goal = form.save(commit=False)
    goal.uzytkownik = user
    goal.rok = year
    goal.save()
    return goal


def build_operations_csv_response(user):
    operations = (
        Operacja.objects.filter(uzytkownik=user)
        .select_related('typ_operacji', 'kategoria')
        .prefetch_related('tagi')
        .order_by('data', 'id')
    )

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="operacje.csv"'
    writer = csv.writer(response)
    writer.writerow(['Data', 'Tytuł', 'Kwota', 'Typ', 'Kategoria', 'Tagi', 'Opis'])

    for operation in operations:
        writer.writerow(
            [
                operation.data.isoformat(),
                operation.tytul,
                str(operation.kwota),
                operation.typ_operacji.nazwa,
                operation.kategoria.nazwa,
                ', '.join(operation.tagi.values_list('nazwa', flat=True)),
                operation.opis,
            ]
        )
    return response


def build_operations_xml_response(user):
    operations = (
        Operacja.objects.filter(uzytkownik=user)
        .select_related('typ_operacji', 'kategoria', 'konto')
        .prefetch_related('tagi')
        .order_by('data', 'id')
    )

    root = ET.Element('operacje')
    root.set('uzytkownik', user.username)
    root.set('wygenerowano', datetime.now().isoformat(timespec='seconds'))

    for operation in operations:
        element = ET.SubElement(root, 'operacja')
        ET.SubElement(element, 'data').text = operation.data.isoformat()
        ET.SubElement(element, 'tytul').text = operation.tytul
        ET.SubElement(element, 'kwota').text = str(operation.kwota)
        ET.SubElement(element, 'typ').text = operation.typ_operacji.nazwa
        ET.SubElement(element, 'kategoria').text = operation.kategoria.nazwa
        ET.SubElement(element, 'konto').text = operation.konto.nazwa if operation.konto else ''
        tags_element = ET.SubElement(element, 'tagi')
        for tag_name in operation.tagi.values_list('nazwa', flat=True):
            ET.SubElement(tags_element, 'tag').text = tag_name
        ET.SubElement(element, 'opis').text = operation.opis or ''

    response = HttpResponse(content_type='application/xml; charset=utf-8')
    safe_username = slugify(user.username) or 'uzytkownik'
    response['Content-Disposition'] = f'attachment; filename="operacje-{safe_username}.xml"'
    response.write(ET.tostring(root, encoding='utf-8', xml_declaration=True))
    return response


def import_operations_from_xml(user, fileobj):
    try:
        tree = ET.parse(fileobj)
    except ET.ParseError as exc:
        raise ImportValidationError('Plik XML jest uszkodzony albo ma niepoprawny format.') from exc

    root = tree.getroot()
    created = 0

    for element in root.findall('operacja'):
        date_value = parse_import_date(element.findtext('data') or '')
        title = (element.findtext('tytul') or '').strip()
        amount_raw = (element.findtext('kwota') or '').strip().replace(',', '.')
        type_name = (element.findtext('typ') or 'Wydatek').strip() or 'Wydatek'
        category_name = (element.findtext('kategoria') or 'Inne').strip() or 'Inne'
        account_name = (element.findtext('konto') or '').strip()
        description = (element.findtext('opis') or '').strip()
        tags_parent = element.find('tagi')
        tags = []
        if tags_parent is not None:
            tags = [
                (tag_element.text or '').strip()
                for tag_element in tags_parent.findall('tag')
                if (tag_element.text or '').strip()
            ]

        if not date_value or not title or not amount_raw:
            continue

        try:
            amount = Decimal(amount_raw)
        except InvalidOperation:
            continue

        operation_type, _ = TypOperacji.objects.get_or_create(nazwa=type_name)
        category, _ = Kategoria.objects.get_or_create(nazwa=category_name)
        account = None
        if account_name:
            account, _ = KontoDomowe.objects.get_or_create(
                uzytkownik=user,
                nazwa=account_name,
                defaults={'typ': 'ROR', 'saldo_poczatkowe': 0},
            )

        operation = Operacja.objects.create(
            data=date_value,
            tytul=title,
            kwota=amount,
            typ_operacji=operation_type,
            kategoria=category,
            konto=account,
            opis=description,
            uzytkownik=user,
        )

        for tag_name in tags:
            tag, _ = Tag.objects.get_or_create(nazwa=tag_name)
            operation.tagi.add(tag)

        created += 1

    return created


def import_operations_from_csv(user, fileobj):
    try:
        decoded = fileobj.read().decode('utf-8-sig').splitlines()
    except UnicodeDecodeError as exc:
        raise ImportValidationError('Plik musi być zapisany w kodowaniu UTF-8.') from exc

    reader = csv.reader(decoded)
    next(reader, None)

    created = 0
    for row in reader:
        if len(row) < 6:
            continue

        date_value = parse_import_date(row[0])
        title = row[1].strip()
        amount_raw = row[2].strip().replace(',', '.')
        type_name = row[3].strip() or 'Wydatek'
        category_name = row[4].strip() or 'Inne'
        tags_csv = row[5].strip() if len(row) > 5 else ''
        description = row[6].strip() if len(row) > 6 else ''

        if not date_value or not title or not amount_raw:
            continue

        try:
            amount = Decimal(amount_raw)
        except InvalidOperation:
            continue

        operation_type, _ = TypOperacji.objects.get_or_create(nazwa=type_name)
        category, _ = Kategoria.objects.get_or_create(nazwa=category_name)

        operation = Operacja.objects.create(
            data=date_value,
            tytul=title,
            kwota=amount,
            typ_operacji=operation_type,
            kategoria=category,
            opis=description,
            uzytkownik=user,
        )

        if tags_csv:
            for tag_name in [value.strip() for value in tags_csv.split(',') if value.strip()]:
                tag, _ = Tag.objects.get_or_create(nazwa=tag_name)
                operation.tagi.add(tag)

        created += 1

    return created


def generate_monthly_report(user_id, year, month):
    call_stored_procedure('finanse_generuj_raport_miesieczny', [user_id, year, month])
