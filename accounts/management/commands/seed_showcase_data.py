from __future__ import annotations

import random
from calendar import monthrange
from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.services import ensure_finance_dictionary, ensure_user_setup
from finanse.models import (
    CelOszczednosciowy,
    Kategoria,
    KontoDomowe,
    Operacja,
    RaportMiesieczny,
    TypOperacji,
)
from firma.models import (
    FakturaKosztowa,
    FakturaSprzedazy,
    JPKDeklaracja,
    Kontrahent,
    UstawieniaFirmy,
)
from paneladmin.models import UserRole


START_DATE = date(2020, 1, 1)
END_DATE = date(2026, 6, 30)
USERS_WITH_DATA = ["test", "ksiegowy", "audytor", *[f"user{i:02d}" for i in range(1, 18)]]
ROWS_PER_USER = 1000
DEFAULT_USER_PASSWORD = "DemoUser123!"
TEST_PASSWORD = "test"

PERSONAS = [
    {"first": "Anna", "last": "Nowak", "city": "Warszawa", "style": "single", "company": "Nova Atelier", "salary": (7200, 9800)},
    {"first": "Piotr", "last": "Kowalski", "city": "Wrocław", "style": "family", "company": "Kowalski Consulting", "salary": (8600, 12800)},
    {"first": "Magda", "last": "Lis", "city": "Gdańsk", "style": "traveller", "company": "Blue Compass Studio", "salary": (9100, 14500)},
    {"first": "Tomasz", "last": "Wójcik", "city": "Poznań", "style": "eco", "company": "Zielony Kadr", "salary": (7800, 11600)},
    {"first": "Karolina", "last": "Mazur", "city": "Kraków", "style": "single", "company": "Pixel Harbor", "salary": (7600, 11800)},
    {"first": "Jakub", "last": "Zieliński", "city": "Łódź", "style": "family", "company": "North Mile", "salary": (8200, 13200)},
    {"first": "Natalia", "last": "Kubiak", "city": "Szczecin", "style": "traveller", "company": "Nomad Works", "salary": (9500, 15000)},
    {"first": "Michał", "last": "Pawlak", "city": "Lublin", "style": "eco", "company": "Pawlak Data Lab", "salary": (8400, 12200)},
    {"first": "Alicja", "last": "Sikora", "city": "Katowice", "style": "single", "company": "Aster Creative", "salary": (7300, 10800)},
    {"first": "Bartosz", "last": "Król", "city": "Białystok", "style": "family", "company": "Król Systems", "salary": (8900, 13800)},
    {"first": "Joanna", "last": "Duda", "city": "Rzeszów", "style": "traveller", "company": "Orbit Trail", "salary": (9300, 14900)},
    {"first": "Kamil", "last": "Zając", "city": "Toruń", "style": "eco", "company": "Green Byte", "salary": (8100, 12100)},
    {"first": "Ewa", "last": "Michalak", "city": "Olsztyn", "style": "single", "company": "Mika Studio", "salary": (7100, 10100)},
    {"first": "Damian", "last": "Jabłoński", "city": "Bydgoszcz", "style": "family", "company": "Jabłoński Advisory", "salary": (8800, 13400)},
    {"first": "Paulina", "last": "Piotrowska", "city": "Opole", "style": "traveller", "company": "Skyline Projects", "salary": (9600, 15200)},
    {"first": "Mateusz", "last": "Grabowski", "city": "Gdynia", "style": "eco", "company": "Baltic Metrics", "salary": (8000, 11900)},
    {"first": "Sylwia", "last": "Kaczmarek", "city": "Kielce", "style": "single", "company": "K Studio", "salary": (7400, 11000)},
    {"first": "Rafał", "last": "Walczak", "city": "Gliwice", "style": "family", "company": "Walczak Tech", "salary": (9000, 14000)},
    {"first": "Monika", "last": "Adamska", "city": "Sopot", "style": "traveller", "company": "Seaside Office", "salary": (9200, 14700)},
    {"first": "Łukasz", "last": "Rutkowski", "city": "Częstochowa", "style": "eco", "company": "Rutkowski Lab", "salary": (7900, 11700)},
]

STYLE_EXPENSES = {
    "single": [
        ("Zakupy spożywcze", "Jedzenie", "ROR", (90, 340)),
        ("Kawa i lunch na mieście", "Rozrywka", "ROR", (30, 120)),
        ("Abonament streamingowy", "Rozrywka", "ROR", (25, 85)),
        ("Przelew na oszczędności", "Oszczędności", "OSZCZEDNOSCIOWE", (300, 1300)),
        ("Rachunek za mieszkanie", "Rachunki", "ROR", (850, 1650)),
    ],
    "family": [
        ("Zakupy spożywcze", "Jedzenie", "ROR", (220, 760)),
        ("Paliwo", "Transport", "ROR", (180, 650)),
        ("Czynsz i opłaty", "Rachunki", "ROR", (1200, 2300)),
        ("Zajęcia dodatkowe dzieci", "Dom", "ROR", (90, 340)),
        ("Przelew na oszczędności", "Oszczędności", "OSZCZEDNOSCIOWE", (350, 1500)),
    ],
    "traveller": [
        ("Bilety lotnicze / przejazdy", "Transport", "ROR", (150, 980)),
        ("Rezerwacja noclegu", "Rozrywka", "ROR", (180, 1200)),
        ("Zakupy spożywcze", "Jedzenie", "ROR", (110, 380)),
        ("Karta SIM / roaming", "Rachunki", "ROR", (40, 130)),
        ("Przelew na oszczędności", "Oszczędności", "OSZCZEDNOSCIOWE", (250, 1250)),
    ],
    "eco": [
        ("Zakupy spożywcze", "Jedzenie", "ROR", (80, 300)),
        ("Bilet miesięczny / kolej", "Transport", "ROR", (70, 220)),
        ("Rachunek za mieszkanie", "Rachunki", "ROR", (760, 1540)),
        ("Sklep zero waste / dom", "Dom", "ROR", (40, 180)),
        ("Przelew na oszczędności", "Oszczędności", "OSZCZEDNOSCIOWE", (320, 1350)),
    ],
}

BONUS_TITLES = [
    "Premia kwartalna",
    "Dodatkowe zlecenie",
    "Rozliczenie projektu",
    "Premia za wynik",
]

SALE_DESCRIPTIONS = [
    "Abonament serwisowy",
    "Usługa wdrożeniowa",
    "Pakiet konsultingowy",
    "Rozliczenie miesięczne",
    "Wsparcie operacyjne",
    "Audyt i rekomendacje",
]

COST_CATEGORIES = [
    "Oprogramowanie",
    "Marketing",
    "Sprzęt",
    "Biuro",
    "Telekomunikacja",
    "Transport",
    "Usługi zewnętrzne",
    "Szkolenia",
]

CONTRACTOR_PREFIXES = [
    "Studio", "Biuro", "Pracownia", "Agencja", "Partner", "Kancelaria", "Atelier", "Grupa"
]
CONTRACTOR_NAMES = [
    "Orbit", "North", "Vista", "Horyzont", "Pixel", "Meridian", "Blue", "Sigma", "Nova", "Lumen", "Frame", "Vector"
]
STREETS = ["Lipowa", "Słoneczna", "Polna", "Morska", "Leśna", "Spacerowa", "Rzemieślnicza", "Długa"]


@dataclass(frozen=True)
class MonthlyAllocation:
    year: int
    month: int
    rows: int


class Command(BaseCommand):
    help = (
        "Tworzy duży zestaw danych pokazowych: 20 kont użytkowników z danymi 2020-01 do 2026-06, "
        "po 1000 operacji na użytkownika, z kontami marcin/danzel12 oraz test/test."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Usuń i odbuduj dane pokazowe dla wszystkich zarządzanych użytkowników.",
        )

    def handle(self, *args, **options):
        should_force = options["force"]
        random.seed(20260329)
        self.user_model = get_user_model()
        ensure_finance_dictionary()
        self._prepare_dictionaries()
        self._ensure_admin_account()

        created = 0
        reused = 0
        for index, username in enumerate(USERS_WITH_DATA, start=1):
            changed = self._ensure_showcase_user(username=username, seed=index * 97, force=should_force)
            if changed:
                created += 1
            else:
                reused += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Gotowe. Użytkownicy z danymi: {len(USERS_WITH_DATA)} | odbudowano: {created} | bez zmian: {reused}."
            )
        )
        self.stdout.write(self.style.SUCCESS("Konto administratora: marcin / danzel12"))
        self.stdout.write(self.style.SUCCESS("Konto testowe: test / test"))
        self.stdout.write(self.style.SUCCESS("Konto księgowego: ksiegowy / ksiegowy123"))
        self.stdout.write(self.style.SUCCESS("Konto audytora: audytor / audytor123"))

    def _persona_for(self, username: str, seed: int):
        if username == "test":
            return {"first": "Tomasz", "last": "Testowy", "city": "Warszawa", "style": "single", "company": "Test Labs", "salary": (6800, 9200)}
        idx = (seed // 97 - 1) % len(PERSONAS)
        return PERSONAS[idx]

    def _prepare_dictionaries(self):
        for name in ["Przychod", "Wydatek"]:
            TypOperacji.objects.get_or_create(nazwa=name)
        for name in ["Dom", "Jedzenie", "Transport", "Rachunki", "Zdrowie", "Rozrywka", "Oszczędności", "Firma", "Inne"]:
            Kategoria.objects.get_or_create(nazwa=name)

    def _ensure_admin_account(self):
        admin, _ = self.user_model.objects.get_or_create(
            username="marcin",
            defaults={
                "email": "marcin@saldoflow.local",
                "is_active": True,
                "is_staff": True,
                "is_superuser": True,
                "first_name": "Marcin",
                "last_name": "Administrator",
            },
        )
        admin.is_active = True
        admin.is_staff = True
        admin.is_superuser = True
        admin.email = admin.email or "marcin@saldoflow.local"
        admin.first_name = admin.first_name or "Marcin"
        admin.last_name = admin.last_name or "Administrator"
        admin.set_password("danzel12")
        admin.save()
        UserRole.objects.update_or_create(
            user=admin,
            defaults={"role": UserRole.ROLE_SUPERADMIN, "notes": "Konto administracyjne do prezentacji projektu."},
        )
        self._purge_user_business_data(admin)

    def _ensure_showcase_user(self, *, username: str, seed: int, force: bool) -> bool:
        persona = self._persona_for(username, seed)
        password = TEST_PASSWORD if username == "test" else DEFAULT_USER_PASSWORD
        user, _ = self.user_model.objects.get_or_create(
            username=username,
            defaults={
                "email": f"{username}@saldoflow.local",
                "is_active": True,
                "first_name": persona["first"],
                "last_name": persona["last"],
            },
        )
        user.email = f"{username}@saldoflow.local"
        user.is_active = True
        user.first_name = persona["first"]
        user.last_name = persona["last"]
        user.set_password(password)
        user.save()
        role_code = UserRole.ROLE_UZYTKOWNIK
        notes = "Konto z dużym zestawem danych demonstracyjnych."
        if username == "ksiegowy":
            role_code = UserRole.ROLE_KSIEGOWY
            notes = "Rola operacyjna: pełne wprowadzanie i import danych."
        elif username == "audytor":
            role_code = UserRole.ROLE_AUDYTOR
            notes = "Rola tylko do odczytu: analityka i audyt danych."
        UserRole.objects.update_or_create(
            user=user,
            defaults={"role": role_code, "notes": notes},
        )
        ensure_user_setup(user)

        if not force and self._user_dataset_exists(user):
            self.stdout.write(f"[SKIP] {username}: dane pokazowe już istnieją.")
            return False

        self.stdout.write(f"[BUILD] {username}: buduję zestaw danych...")
        self._purge_user_business_data(user)
        with transaction.atomic():
            accounts = self._ensure_accounts(user, persona, seed)
            contractors = self._ensure_contractors(user, persona, seed)
            self._ensure_company_settings(user, persona, seed)
            self._build_finance_data(user, accounts, persona, seed)
            self._build_company_data(user, contractors, persona, seed)
        return True

    def _user_dataset_exists(self, user) -> bool:
        return (
            Operacja.objects.filter(uzytkownik=user).count() >= ROWS_PER_USER
            and FakturaSprzedazy.objects.filter(user=user).exists()
            and FakturaKosztowa.objects.filter(user=user).exists()
            and JPKDeklaracja.objects.filter(user=user, rok=2026, miesiac=6).exists()
            and UstawieniaFirmy.objects.filter(user=user).exists()
        )

    def _purge_user_business_data(self, user):
        RaportMiesieczny.objects.filter(uzytkownik=user).delete()
        CelOszczednosciowy.objects.filter(uzytkownik=user).delete()
        Operacja.objects.filter(uzytkownik=user).delete()
        FakturaSprzedazy.objects.filter(user=user).delete()
        FakturaKosztowa.objects.filter(user=user).delete()
        JPKDeklaracja.objects.filter(user=user).delete()
        Kontrahent.objects.filter(user=user).delete()
        UstawieniaFirmy.objects.filter(user=user).delete()
        KontoDomowe.objects.filter(uzytkownik=user).exclude(nazwa="Konto główne").delete()

    def _ensure_accounts(self, user, persona, seed: int):
        rng = random.Random(seed + 17)
        defaults = [
            ("Konto główne", "ROR", Decimal(str(rng.randint(2800, 7200)))),
            ("Oszczędności", "OSZCZEDNOSCIOWE", Decimal(str(rng.randint(6000, 24000)))),
            ("Portfel", "GOTOWKA", Decimal(str(rng.randint(120, 950)))),
            ("Konto firmowe", "FIRMA", Decimal(str(rng.randint(4500, 16000)))),
        ]
        result = {}
        for name, account_type, starting_balance in defaults:
            account, _ = KontoDomowe.objects.get_or_create(
                uzytkownik=user,
                nazwa=name,
                defaults={"typ": account_type, "saldo_poczatkowe": starting_balance},
            )
            account.typ = account_type
            account.saldo_poczatkowe = starting_balance
            account.aktywne = True
            account.save()
            result[account_type] = account
        return result

    def _ensure_contractors(self, user, persona, seed: int):
        rng = random.Random(seed + 501)
        contractors = []
        for idx in range(1, 13):
            company_name = f"{rng.choice(CONTRACTOR_PREFIXES)} {rng.choice(CONTRACTOR_NAMES)} {idx:02d}"
            contractor, _ = Kontrahent.objects.get_or_create(
                user=user,
                nazwa=company_name,
                defaults={
                    "nip": f"52{rng.randint(10000000, 99999999)}",
                    "regon": str(rng.randint(100000000, 999999999)),
                    "adres": f"ul. {rng.choice(STREETS)} {idx}, {rng.randint(10,89)}-{rng.randint(100,999)} {persona['city']}",
                    "email": f"kontakt{idx}@{company_name.lower().replace(' ', '')}.pl",
                    "telefon": f"5{rng.randint(10,99)}{rng.randint(1000000, 9999999)}",
                    "strona_www": f"https://{company_name.lower().replace(' ', '-')}.pl",
                    "status_rejestru": "AKTYWNY",
                },
            )
            contractors.append(contractor)
        return contractors

    def _ensure_company_settings(self, user, persona, seed: int):
        idx = (seed % 19) + 1
        UstawieniaFirmy.objects.update_or_create(
            user=user,
            defaults={
                "nazwa_firmy": f"{persona['company']} {user.last_name}",
                "wlasciciel": f"{user.first_name} {user.last_name}",
                "nip": f"71{seed:08d}"[:10],
                "adres": f"ul. {STREETS[idx % len(STREETS)]} {idx}, 00-{120 + idx} {persona['city']}",
                "kod_urzedu_skarbowego": f"{1400 + idx}",
                "forma_opodatkowania": "LINIOWY",
                "vat_czynny": True,
                "typ_zus": ["PELNY", "PREFERENCYJNY", "ULGA"][seed % 3],
                "czy_chorobowe": True,
            },
        )

    def _build_finance_data(self, user, accounts, persona, seed: int):
        rng = random.Random(seed)
        income_type = TypOperacji.objects.get(nazwa="Przychod")
        expense_type = TypOperacji.objects.get(nazwa="Wydatek")
        categories = {category.nazwa: category for category in Kategoria.objects.all()}

        allocations = self._monthly_allocations(ROWS_PER_USER)
        operations_to_create = []
        monthly_totals = defaultdict(lambda: {"income": Decimal("0.00"), "expense": Decimal("0.00")})
        expense_templates = STYLE_EXPENSES[persona["style"]]

        for month_index, allocation in enumerate(allocations):
            month_operations = []
            last_day = monthrange(allocation.year, allocation.month)[1]

            salary_amount = self._money(rng.randint(*persona["salary"]))
            salary_day = min(5, last_day)
            month_operations.append(
                Operacja(
                    uzytkownik=user,
                    konto=accounts["ROR"],
                    tytul="Wynagrodzenie / główny wpływ",
                    kwota=salary_amount,
                    data=date(allocation.year, allocation.month, salary_day),
                    typ_operacji=income_type,
                    kategoria=categories["Inne"],
                    opis=f"Stały wpływ miesięczny dla {user.first_name} {user.last_name}.",
                )
            )
            monthly_totals[(allocation.year, allocation.month)]["income"] += salary_amount

            if allocation.month in {3, 6, 9, 12}:
                bonus_amount = self._money(rng.randint(900, 5200))
                month_operations.append(
                    Operacja(
                        uzytkownik=user,
                        konto=accounts["ROR"],
                        tytul=BONUS_TITLES[(month_index + seed) % len(BONUS_TITLES)],
                        kwota=bonus_amount,
                        data=date(allocation.year, allocation.month, min(17, last_day)),
                        typ_operacji=income_type,
                        kategoria=categories["Firma"],
                        opis="Dodatkowy wpływ kwartalny.",
                    )
                )
                monthly_totals[(allocation.year, allocation.month)]["income"] += bonus_amount

            while len(month_operations) < allocation.rows:
                title, category_name, account_type, amount_range = expense_templates[(len(month_operations) + month_index + seed) % len(expense_templates)]
                amount = self._money(rng.randint(*amount_range))
                day = min(last_day, max(1, 2 + (len(month_operations) * 2) % 27))
                month_operations.append(
                    Operacja(
                        uzytkownik=user,
                        konto=accounts[account_type],
                        tytul=title,
                        kwota=amount,
                        data=date(allocation.year, allocation.month, day),
                        typ_operacji=expense_type,
                        kategoria=categories[category_name],
                        opis=f"Wydatek demonstracyjny dla stylu {persona['style']} za {allocation.year}-{allocation.month:02d}.",
                    )
                )
                monthly_totals[(allocation.year, allocation.month)]["expense"] += amount

            operations_to_create.extend(month_operations[: allocation.rows])

        Operacja.objects.bulk_create(operations_to_create, batch_size=500)

        RaportMiesieczny.objects.bulk_create(
            [
                RaportMiesieczny(
                    uzytkownik=user,
                    rok=year,
                    miesiac=month,
                    suma_przychodow=values["income"],
                    suma_wydatkow=values["expense"],
                    saldo=(values["income"] - values["expense"]).quantize(Decimal("0.01")),
                )
                for (year, month), values in sorted(monthly_totals.items())
            ],
            batch_size=200,
        )

        for year in range(START_DATE.year, END_DATE.year + 1):
            CelOszczednosciowy.objects.update_or_create(
                uzytkownik=user,
                rok=year,
                defaults={"kwota_docelowa": Decimal("12000.00") + Decimal(str((year - START_DATE.year) * 1500))},
            )

    def _build_company_data(self, user, contractors, persona, seed: int):
        rng = random.Random(seed + 9000)
        sales = []
        costs = []
        jpk_rows = []
        sale_counter = 1
        cost_counter = 1
        current_year = START_DATE.year
        current_month = START_DATE.month

        while (current_year, current_month) <= (END_DATE.year, END_DATE.month):
            last_day = monthrange(current_year, current_month)[1]
            contractor = contractors[(sale_counter + seed) % len(contractors)]
            net_sale = self._money(rng.randint(3000, 22000))
            gross_sale = self._gross(net_sale)
            sales.append(
                FakturaSprzedazy(
                    user=user,
                    numer=f"FS/{current_year}/{sale_counter:04d}",
                    kontrahent=contractor,
                    data_wystawienia=date(current_year, current_month, min(3, last_day)),
                    data_sprzedazy=date(current_year, current_month, min(3, last_day)),
                    kwota_netto=net_sale,
                    kwota_brutto=gross_sale,
                    czy_oplacona=(sale_counter + seed) % 4 != 0,
                    opis=SALE_DESCRIPTIONS[(sale_counter + seed) % len(SALE_DESCRIPTIONS)],
                )
            )
            sale_counter += 1

            monthly_cost_net = Decimal("0.00")
            monthly_cost_vat = Decimal("0.00")
            for offset in range(2):
                vendor = contractors[(cost_counter + offset + seed) % len(contractors)]
                net_cost = self._money(rng.randint(300, 7800))
                vat_cost = self._vat(net_cost)
                gross_cost = (net_cost + vat_cost).quantize(Decimal("0.01"))
                category = COST_CATEGORIES[(cost_counter + offset + seed) % len(COST_CATEGORIES)]
                costs.append(
                    FakturaKosztowa(
                        user=user,
                        numer_faktury=f"FK/{current_year}/{cost_counter:04d}",
                        kontrahent=vendor,
                        kontrahent_nazwa=vendor.nazwa,
                        nip_dostawcy=vendor.nip,
                        kod_kraju="PL",
                        data_zakupu=date(current_year, current_month, min(8 + offset * 10, last_day)),
                        kwota_netto=net_cost,
                        kwota_vat=vat_cost,
                        kwota_brutto=gross_cost,
                        kategoria=category,
                        rodzaj_zakupu="ST" if (cost_counter + offset + seed) % 9 == 0 else "POZ",
                        miesiac_jpk=current_month,
                        opis=f"Koszt demonstracyjny: {category.lower()} dla firmy {persona['company']}.",
                    )
                )
                monthly_cost_net += net_cost
                monthly_cost_vat += vat_cost
                cost_counter += 1

            jpk_rows.append(
                JPKDeklaracja(
                    user=user,
                    rok=current_year,
                    miesiac=current_month,
                    p_17=monthly_cost_net,
                    p_18=monthly_cost_vat,
                    p_19=Decimal("0.00"),
                    p_20=Decimal("0.00"),
                    p_43_korekta=Decimal("0.00"),
                    p_44_korekta=Decimal("0.00"),
                    p_45_korekta=Decimal("0.00"),
                    p_46_korekta=Decimal("0.00"),
                    p_51=(monthly_cost_vat * Decimal("0.20")).quantize(Decimal("0.01")),
                    p_68=True,
                    p_ordzu=False,
                    uzasadnienie="Dane pokazowe wygenerowane automatycznie.",
                )
            )

            if current_month == 12:
                current_month = 1
                current_year += 1
            else:
                current_month += 1

        FakturaSprzedazy.objects.bulk_create(sales, batch_size=300)
        FakturaKosztowa.objects.bulk_create(costs, batch_size=300)
        JPKDeklaracja.objects.bulk_create(jpk_rows, batch_size=200)

    def _monthly_allocations(self, total_rows: int) -> list[MonthlyAllocation]:
        months = []
        year, month = START_DATE.year, START_DATE.month
        while (year, month) <= (END_DATE.year, END_DATE.month):
            months.append((year, month))
            if month == 12:
                month = 1
                year += 1
            else:
                month += 1
        base_rows = total_rows // len(months)
        extra_rows = total_rows % len(months)
        allocations = []
        for index, (year, month) in enumerate(months):
            allocations.append(MonthlyAllocation(year=year, month=month, rows=base_rows + (1 if index < extra_rows else 0)))
        return allocations

    @staticmethod
    def _money(value: int | float | Decimal) -> Decimal:
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    @staticmethod
    def _vat(net_value: Decimal) -> Decimal:
        return (net_value * Decimal("0.23")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    def _gross(self, net_value: Decimal) -> Decimal:
        return (net_value + self._vat(net_value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
