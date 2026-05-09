from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from io import BytesIO
import json
import zipfile

from .models import FakturaKosztowa, FakturaSprzedazy, JPKDeklaracja, UstawieniaFirmy

TWOPLACES = Decimal('0.01')

ZUS_2026 = {
    'PELNY': {
        'podstawa_spoleczne': Decimal('5652.00'),
        'emerytalne': Decimal('1103.27'),
        'rentowe': Decimal('452.16'),
        'wypadkowe': Decimal('94.39'),
        'chorobowe': Decimal('138.47'),
        'fp_fs': Decimal('138.47'),
        'spoleczne_z_chorobowym': Decimal('1926.76'),
        'spoleczne_bez_chorobowego': Decimal('1788.29'),
    },
    'PREFERENCYJNY': {
        'podstawa_spoleczne': Decimal('1441.80'),
        'emerytalne': Decimal('281.44'),
        'rentowe': Decimal('115.34'),
        'wypadkowe': Decimal('24.08'),
        'chorobowe': Decimal('35.32'),
        'fp_fs': Decimal('0.00'),
        'spoleczne_z_chorobowym': Decimal('456.18'),
        'spoleczne_bez_chorobowego': Decimal('420.86'),
    },
    'ULGA': {
        'podstawa_spoleczne': Decimal('0.00'),
        'emerytalne': Decimal('0.00'),
        'rentowe': Decimal('0.00'),
        'wypadkowe': Decimal('0.00'),
        'chorobowe': Decimal('0.00'),
        'fp_fs': Decimal('0.00'),
        'spoleczne_z_chorobowym': Decimal('0.00'),
        'spoleczne_bez_chorobowego': Decimal('0.00'),
    },
}

ZUS_HEALTH_MIN_2026 = {
    1: Decimal('314.96'),
    'default': Decimal('432.54'),
}

US_DOCS = [
    ('PIT_ZALICZKA', 'Zaliczka PIT'),
    ('PIT36L_ROCZNE', 'PIT-36L roczne'),
    ('JPK_V7M', 'JPK_V7M / VAT'),
]

ZUS_DOCS = [
    ('ZUS_DRA', 'ZUS DRA'),
    ('ZUS_RCA', 'ZUS RCA'),
    ('ZUS_RSA', 'ZUS RSA'),
]


@dataclass
class OkresFirmy:
    przychod: Decimal
    koszt: Decimal
    dochod: Decimal
    vat_naliczone: Decimal
    liczba_sprzedazy: int
    liczba_kosztow: int


def q(value: Decimal | int | float | str) -> Decimal:
    return Decimal(value).quantize(TWOPLACES)


def okres_firmy(user, rok: int, miesiac: int) -> OkresFirmy:
    sprzedaz_qs = FakturaSprzedazy.objects.filter(
        user=user,
        data_wystawienia__year=rok,
        data_wystawienia__month=miesiac,
    )
    koszty_qs = FakturaKosztowa.objects.filter(
        user=user,
        data_zakupu__year=rok,
        data_zakupu__month=miesiac,
    )
    przychod = sum((f.kwota_brutto for f in sprzedaz_qs if f.czy_oplacona), Decimal('0.00'))
    koszt = sum((f.kwota_brutto for f in koszty_qs), Decimal('0.00'))
    vat_naliczone = sum((f.kwota_vat for f in koszty_qs), Decimal('0.00'))
    return OkresFirmy(
        przychod=q(przychod),
        koszt=q(koszt),
        dochod=q(przychod - koszt),
        vat_naliczone=q(vat_naliczone),
        liczba_sprzedazy=sprzedaz_qs.count(),
        liczba_kosztow=koszty_qs.count(),
    )


def ustawienia_firmy(user):
    return UstawieniaFirmy.objects.filter(user=user).first()


def status_jpk(user, rok: int, miesiac: int) -> dict:
    ma_deklaracje = JPKDeklaracja.objects.filter(user=user, rok=rok, miesiac=miesiac).exists()
    pozycje = FakturaKosztowa.objects.filter(user=user, data_zakupu__year=rok, miesiac_jpk=miesiac).count()
    return {
        'ma_deklaracje': ma_deklaracje,
        'pozycje': pozycje,
        'gotowe': ma_deklaracje and pozycje > 0,
    }


def wylicz_pit_liniowy(user, rok: int, miesiac: int) -> dict:
    okres = okres_firmy(user, rok, miesiac)
    dochod = max(okres.dochod, Decimal('0.00'))
    podatek = q(dochod * Decimal('0.19'))
    termin = f'{rok}-{miesiac:02d}-20'
    return {
        'typ': 'PIT_ZALICZKA',
        'nazwa': 'Zaliczka PIT (robocza)',
        'rok': rok,
        'miesiac': miesiac,
        'przychod': str(okres.przychod),
        'koszt': str(okres.koszt),
        'dochod': str(dochod),
        'stawka': '19%',
        'kwota_podatku': str(podatek),
        'termin_platnosci': termin,
        'uwaga': 'To robocze wyliczenie na podstawie danych z aplikacji. Nie obejmuje różnic rocznych, ulg, korekt i pełnego rozliczenia zdrowotnego.',
    }


def wylicz_pit36l_roczne(user, rok: int) -> dict:
    sprzedaz_qs = FakturaSprzedazy.objects.filter(user=user, data_wystawienia__year=rok)
    koszty_qs = FakturaKosztowa.objects.filter(user=user, data_zakupu__year=rok)
    przychod = sum((f.kwota_brutto for f in sprzedaz_qs if f.czy_oplacona), Decimal('0.00'))
    koszt = sum((f.kwota_brutto for f in koszty_qs), Decimal('0.00'))
    dochod = max(q(przychod - koszt), Decimal('0.00'))
    podatek = q(dochod * Decimal('0.19'))
    return {
        'typ': 'PIT36L_ROCZNE',
        'nazwa': 'PIT-36L roczne (zestaw danych)',
        'rok': rok,
        'przychod_roczny': str(q(przychod)),
        'koszt_roczny': str(q(koszt)),
        'dochod_roczny': str(dochod),
        'stawka': '19%',
        'podatek_roczny_szacowany': str(podatek),
        'termin_zlozenia': f'{rok + 1}-04-30',
        'uwaga': 'Zestaw pomaga przygotować dane do formularza rocznego PIT-36L. Końcowe rozliczenie wymaga weryfikacji w e-US lub przez księgowość.',
    }


def wylicz_zus_dra(user, rok: int, miesiac: int) -> dict:
    ustawienia = ustawienia_firmy(user)
    okres = okres_firmy(user, rok, miesiac)
    typ_zus = getattr(ustawienia, 'typ_zus', 'PELNY') or 'PELNY'
    czy_chorobowe = bool(getattr(ustawienia, 'czy_chorobowe', True))
    rates = ZUS_2026.get(typ_zus, ZUS_2026['PELNY'])

    minimum_health = ZUS_HEALTH_MIN_2026[1] if miesiac == 1 else ZUS_HEALTH_MIN_2026['default']
    zdrowotna = q(max(okres.dochod * Decimal('0.049'), minimum_health))
    spoleczne = rates['spoleczne_z_chorobowym'] if czy_chorobowe else rates['spoleczne_bez_chorobowego']
    razem = q(spoleczne + zdrowotna)
    termin = f'{rok}-{miesiac:02d}-20'
    return {
        'typ': 'ZUS_DRA',
        'nazwa': 'ZUS DRA (robocza)',
        'rok': rok,
        'miesiac': miesiac,
        'tryb_zus': typ_zus,
        'czy_chorobowe': czy_chorobowe,
        'podstawa_spoleczne': str(rates['podstawa_spoleczne']),
        'emerytalne': str(rates['emerytalne']),
        'rentowe': str(rates['rentowe']),
        'wypadkowe': str(rates['wypadkowe']),
        'chorobowe': str(rates['chorobowe'] if czy_chorobowe else Decimal('0.00')),
        'fundusz_pracy': str(rates['fp_fs']),
        'zdrowotna': str(zdrowotna),
        'razem': str(razem),
        'termin_wysylki_i_platnosci': termin,
        'uwaga': 'Wyliczenie zakłada działalność bez listy płac. Przy pracownikach trzeba przygotować też RCA/RSA/RPA.',
    }


def szablon_zus_rca(user, rok: int, miesiac: int) -> dict:
    return {
        'typ': 'ZUS_RCA',
        'nazwa': 'Szablon ZUS RCA',
        'rok': rok,
        'miesiac': miesiac,
        'kolumny': ['PESEL/NIP', 'Nazwisko i imię', 'Kod tytułu ubezpieczenia', 'Podstawa emerytalna', 'Podstawa rentowa', 'Podstawa zdrowotna'],
        'uwaga': 'RCA wymaga danych kadrowo-płacowych pracowników lub wspólników. Projekt nie ma jeszcze modułu kadr, dlatego generowany jest szablon roboczy.',
    }


def szablon_zus_rsa(user, rok: int, miesiac: int) -> dict:
    return {
        'typ': 'ZUS_RSA',
        'nazwa': 'Szablon ZUS RSA',
        'rok': rok,
        'miesiac': miesiac,
        'kolumny': ['PESEL/NIP', 'Nazwisko i imię', 'Kod świadczenia/przerwy', 'Okres od', 'Okres do', 'Liczba dni', 'Kwota'],
        'uwaga': 'RSA jest potrzebne przy zasiłkach i przerwach w opłacaniu składek. Projekt nie ma ewidencji absencji, więc generowany jest szablon roboczy.',
    }


def zbuduj_urzedy_context(user, rok: int, miesiac: int) -> dict:
    okres = okres_firmy(user, rok, miesiac)
    pit = wylicz_pit_liniowy(user, rok, miesiac)
    pit_roczne = wylicz_pit36l_roczne(user, rok)
    zus = wylicz_zus_dra(user, rok, miesiac)
    jpk = status_jpk(user, rok, miesiac)
    return {
        'okres': okres,
        'pit': pit,
        'pit_roczne': pit_roczne,
        'zus': zus,
        'jpk': jpk,
        'us_docs': US_DOCS,
        'zus_docs': ZUS_DOCS,
    }


def _txt_from_dict(title: str, data: dict) -> str:
    lines = [title, '=' * len(title), '']
    for key, value in data.items():
        lines.append(f'{key}: {value}')
    lines.append('')
    return '\n'.join(lines)


def _json_bytes(data: dict) -> bytes:
    return json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')


def _txt_bytes(title: str, data: dict) -> bytes:
    return _txt_from_dict(title, data).encode('utf-8')


def zbuduj_pakiet_urzedow(user, rok: int, miesiac: int, scope: str = 'ALL') -> bytes:
    pit = wylicz_pit_liniowy(user, rok, miesiac)
    pit_roczne = wylicz_pit36l_roczne(user, rok)
    zus = wylicz_zus_dra(user, rok, miesiac)
    rca = szablon_zus_rca(user, rok, miesiac)
    rsa = szablon_zus_rsa(user, rok, miesiac)
    jpk = status_jpk(user, rok, miesiac)
    memory = BytesIO()
    with zipfile.ZipFile(memory, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        if scope in ('ALL', 'US'):
            archive.writestr(f'US_PIT_ZALICZKA_{rok}_{miesiac:02d}.json', _json_bytes(pit))
            archive.writestr(f'US_PIT_ZALICZKA_{rok}_{miesiac:02d}.txt', _txt_bytes('Zaliczka PIT', pit))
            archive.writestr(f'US_PIT36L_ROCZNE_{rok}.json', _json_bytes(pit_roczne))
            archive.writestr(f'US_PIT36L_ROCZNE_{rok}.txt', _txt_bytes('PIT-36L roczne', pit_roczne))
            archive.writestr(
                f'US_JPK_STATUS_{rok}_{miesiac:02d}.json',
                _json_bytes({
                    'typ': 'JPK_V7M',
                    'rok': rok,
                    'miesiac': miesiac,
                    **jpk,
                }),
            )
        if scope in ('ALL', 'ZUS'):
            archive.writestr(f'ZUS_DRA_{rok}_{miesiac:02d}.json', _json_bytes(zus))
            archive.writestr(f'ZUS_DRA_{rok}_{miesiac:02d}.txt', _txt_bytes('ZUS DRA', zus))
            archive.writestr(f'ZUS_RCA_SZABLON_{rok}_{miesiac:02d}.json', _json_bytes(rca))
            archive.writestr(f'ZUS_RSA_SZABLON_{rok}_{miesiac:02d}.json', _json_bytes(rsa))
    memory.seek(0)
    return memory.getvalue()
