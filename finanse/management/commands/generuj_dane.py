import random
from calendar import monthrange
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from finanse.models import Kategoria, Operacja, Tag, TypOperacji


class Command(BaseCommand):
    help = "Generuje realistyczne dane testowe dla aplikacji budżetu domowego za lata 2021–2026."

    DZIS = date(2026, 3, 16)

    KATEGORIE = [
        "Jedzenie",
        "Zakupy spożywcze",
        "Restauracje",
        "Transport",
        "Paliwo",
        "Komunikacja miejska",
        "Mieszkanie",
        "Czynsz",
        "Prąd",
        "Gaz",
        "Woda",
        "Internet",
        "Telefon",
        "Zdrowie",
        "Apteka",
        "Lekarz",
        "Ubrania",
        "Dom",
        "Chemia domowa",
        "Rozrywka",
        "Streaming",
        "Kultura",
        "Podróże",
        "Edukacja",
        "Dziecko",
        "Prezenty",
        "Ubezpieczenie",
        "Raty",
        "Subskrypcje",
        "Sport",
        "Zwierzęta",
        "Naprawy",
        "Hobby",
        "Oszczędności",
        "Inne",
    ]

    TAGI = [
        "stały",
        "jednorazowy",
        "dom",
        "auto",
        "rodzina",
        "praca",
        "online",
        "wakacje",
        "zdrowie",
        "pilne",
        "weekend",
        "rachunki",
        "codzienne",
        "większy wydatek",
        "oszczędzanie",
    ]

    MAPA_WYDATKOW = {
        "Zakupy spożywcze": [
            "Biedronka",
            "Lidl",
            "Carrefour",
            "Zakupy spożywcze",
            "Weekendowe zakupy",
        ],
        "Jedzenie": [
            "Sklep osiedlowy",
            "Codzienne zakupy",
            "Produkty spożywcze",
        ],
        "Restauracje": [
            "Obiad na mieście",
            "Pizza",
            "Sushi",
            "Kawa i ciasto",
            "Kolacja w restauracji",
        ],
        "Transport": [
            "Taxi",
            "Parking",
            "Bilet PKP",
            "Przejazd służbowy",
        ],
        "Paliwo": [
            "Tankowanie",
            "Stacja benzynowa",
            "Paliwo do auta",
        ],
        "Komunikacja miejska": [
            "Bilet miesięczny",
            "Doładowanie karty miejskiej",
            "Bilet autobusowy",
        ],
        "Mieszkanie": [
            "Wyposażenie mieszkania",
            "Drobne zakupy do domu",
        ],
        "Czynsz": [
            "Czynsz za mieszkanie",
        ],
        "Prąd": [
            "Rachunek za prąd",
        ],
        "Gaz": [
            "Rachunek za gaz",
        ],
        "Woda": [
            "Rachunek za wodę",
        ],
        "Internet": [
            "Rachunek za internet",
        ],
        "Telefon": [
            "Abonament telefoniczny",
        ],
        "Zdrowie": [
            "Badania kontrolne",
            "Zakupy medyczne",
        ],
        "Apteka": [
            "Apteka",
            "Leki",
            "Suplementy",
        ],
        "Lekarz": [
            "Wizyta u lekarza",
            "Dentysta",
            "Specjalista",
        ],
        "Ubrania": [
            "Nowe ubrania",
            "Buty",
            "Kurtka",
            "Zakupy odzieżowe",
        ],
        "Dom": [
            "Akcesoria do domu",
            "Dekoracje",
            "Naprawa w domu",
        ],
        "Chemia domowa": [
            "Środki czystości",
            "Chemia gospodarcza",
        ],
        "Rozrywka": [
            "Wyjście ze znajomymi",
            "Bilard",
            "Kino",
            "Planszówki",
        ],
        "Streaming": [
            "Netflix",
            "Spotify",
            "HBO Max",
            "YouTube Premium",
        ],
        "Kultura": [
            "Teatr",
            "Koncert",
            "Muzeum",
            "Książki",
        ],
        "Podróże": [
            "Bilety lotnicze",
            "Nocleg",
            "Weekendowy wyjazd",
            "Rezerwacja hotelu",
        ],
        "Edukacja": [
            "Kurs online",
            "Szkolenie",
            "Materiały edukacyjne",
        ],
        "Dziecko": [
            "Przedszkole",
            "Artykuły szkolne",
            "Zabawki",
        ],
        "Prezenty": [
            "Prezent urodzinowy",
            "Prezent świąteczny",
            "Kwiaty",
        ],
        "Ubezpieczenie": [
            "Ubezpieczenie samochodu",
            "Ubezpieczenie mieszkania",
            "Polisa",
        ],
        "Raty": [
            "Rata kredytu",
            "Rata sprzętu",
        ],
        "Subskrypcje": [
            "Aplikacja premium",
            "Subskrypcja usługi",
            "Chmura",
        ],
        "Sport": [
            "Siłownia",
            "Basen",
            "Sprzęt sportowy",
        ],
        "Zwierzęta": [
            "Karma dla zwierząt",
            "Weterynarz",
            "Akcesoria dla pupila",
        ],
        "Naprawy": [
            "Serwis samochodu",
            "Naprawa AGD",
            "Wymiana części",
        ],
        "Hobby": [
            "Akcesoria hobby",
            "Gadżety",
            "Materiały",
        ],
        "Oszczędności": [
            "Przelew na oszczędności",
        ],
        "Inne": [
            "Inny wydatek",
            "Niespodziewany koszt",
        ],
    }

    KATEGORIE_STALE = {
        "Czynsz",
        "Prąd",
        "Gaz",
        "Woda",
        "Internet",
        "Telefon",
        "Raty",
        "Subskrypcje",
        "Komunikacja miejska",
    }

    KATEGORIE_SPORADYCZNE = {
        "Podróże",
        "Prezenty",
        "Naprawy",
        "Lekarz",
        "Kultura",
        "Ubrania",
        "Sport",
        "Zwierzęta",
        "Dziecko",
    }

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            type=str,
            default="testuser",
            help="Nazwa użytkownika, dla którego mają zostać wygenerowane dane.",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Usuń dotychczasowe operacje użytkownika przed wygenerowaniem nowych.",
        )
        parser.add_argument(
            "--seed",
            type=int,
            default=42,
            help="Seed do losowania dla powtarzalnych wyników.",
        )

    def handle(self, *args, **options):
        username = options["username"]
        clear = options["clear"]
        seed = options["seed"]

        random.seed(seed)

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": f"{username}@example.com"},
        )

        if created:
            user.set_password("test1234")
            user.save()

        self._prepare_dictionaries()

        with transaction.atomic():
            if clear:
                deleted_count, _ = Operacja.objects.filter(uzytkownik=user).delete()
                self.stdout.write(
                    self.style.WARNING(
                        f"Usunięto wszystkie istniejące operacje użytkownika {username}: {deleted_count}"
                    )
                )
            else:
                deleted_future_count = self._delete_future_operations(user)
                if deleted_future_count > 0:
                    self.stdout.write(
                        self.style.WARNING(
                            f"Usunięto operacje z przyszłości użytkownika {username}: {deleted_future_count}"
                        )
                    )

            generated = self._generate_for_user(user)

            # Dodatkowe zabezpieczenie po generacji.
            deleted_future_after_generate = self._delete_future_operations(user)
            if deleted_future_after_generate > 0:
                self.stdout.write(
                    self.style.WARNING(
                        f"Po generacji usunięto jeszcze operacje z przyszłości: {deleted_future_after_generate}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"Wygenerowano {generated} operacji testowych dla użytkownika: {username}"
            )
        )

    def _delete_future_operations(self, user):
        deleted_count, _ = Operacja.objects.filter(
            uzytkownik=user,
            data__gt=self.DZIS,
        ).delete()
        return deleted_count

    def _prepare_dictionaries(self):
        self.typ_przychod, _ = TypOperacji.objects.get_or_create(nazwa="Przychod")
        self.typ_wydatek, _ = TypOperacji.objects.get_or_create(nazwa="Wydatek")

        self.kategorie_objects = {}
        for nazwa in self.KATEGORIE:
            obj, _ = Kategoria.objects.get_or_create(nazwa=nazwa)
            self.kategorie_objects[nazwa] = obj

        self.tagi_objects = {}
        for nazwa in self.TAGI:
            obj, _ = Tag.objects.get_or_create(nazwa=nazwa)
            self.tagi_objects[nazwa] = obj

    def _generate_for_user(self, user):
        total = 0

        for rok in range(2021, 2027):
            for miesiac in range(1, 13):
                if rok == 2026 and miesiac > 3:
                    continue

                last_day = monthrange(rok, miesiac)[1]
                if rok == 2026 and miesiac == 3:
                    last_day = 16

                total += self._generate_month(user, rok, miesiac, last_day)

        return total

    def _generate_month(self, user, rok, miesiac, last_day):
        generated = 0

        base_income = Decimal("4200") + Decimal(str((rok - 2021) * 280))
        seasonal_bonus_chance = 0.20
        side_income_chance = 0.32

        deficit_month = random.random() < 0.35
        cost_growth = Decimal("1.00") + Decimal(str((rok - 2021) * 0.05))

        month_progress = Decimal(str(last_day / monthrange(rok, miesiac)[1]))

        month_income_total = Decimal("0.00")

        pensja_kwota = self._money(
            base_income * Decimal(str(random.uniform(0.96, 1.08))) * month_progress
            if (rok == 2026 and miesiac == 3)
            else base_income * Decimal(str(random.uniform(0.96, 1.08)))
        )
        pensja_data = self._random_day(rok, miesiac, 1, min(last_day, 10))
        generated += self._create_operation(
            user=user,
            typ=self.typ_przychod,
            kategoria=self.kategorie_objects["Inne"],
            tytul="Pensja",
            kwota=pensja_kwota,
            operation_date=pensja_data,
            tags=["stały", "praca"],
            opis="Miesięczne wynagrodzenie",
        )
        month_income_total += pensja_kwota

        if random.random() < seasonal_bonus_chance:
            bonus_kwota = self._money(
                Decimal(str(random.uniform(400, 1800))) * month_progress
                if (rok == 2026 and miesiac == 3)
                else Decimal(str(random.uniform(400, 1800)))
            )
            bonus_title = random.choice(["Premia kwartalna", "Premia uznaniowa"])
            bonus_data = self._random_day(rok, miesiac, 10, last_day)
            generated += self._create_operation(
                user=user,
                typ=self.typ_przychod,
                kategoria=self.kategorie_objects["Inne"],
                tytul=bonus_title,
                kwota=bonus_kwota,
                operation_date=bonus_data,
                tags=["praca", "jednorazowy"],
                opis="Dodatkowy wpływ związany z pracą",
            )
            month_income_total += bonus_kwota

        if random.random() < side_income_chance:
            extra_kwota = self._money(
                Decimal(str(random.uniform(150, 1200))) * month_progress
                if (rok == 2026 and miesiac == 3)
                else Decimal(str(random.uniform(150, 1200)))
            )
            extra_title = random.choice(
                ["Praca dodatkowa", "Zlecenie", "Sprzedaż rzeczy", "Zwrot podatku"]
            )
            extra_data = self._random_day(rok, miesiac, 8, last_day)
            generated += self._create_operation(
                user=user,
                typ=self.typ_przychod,
                kategoria=self.kategorie_objects["Inne"],
                tytul=extra_title,
                kwota=extra_kwota,
                operation_date=extra_data,
                tags=["jednorazowy"],
                opis="Dodatkowy wpływ do budżetu",
            )
            month_income_total += extra_kwota

        if deficit_month:
            target_expenses = month_income_total + Decimal(
                str(random.uniform(150, 1200))
            )
        else:
            max_surplus = Decimal("1500")
            planned_surplus = Decimal(str(random.uniform(50, float(max_surplus))))
            target_expenses = max(Decimal("0.00"), month_income_total - planned_surplus)

        target_expenses = self._money(target_expenses * cost_growth)

        generated += self._generate_expenses_for_month(
            user=user,
            rok=rok,
            miesiac=miesiac,
            last_day=last_day,
            target_expenses=target_expenses,
        )

        return generated

    def _generate_expenses_for_month(self, user, rok, miesiac, last_day, target_expenses):
        generated = 0
        created_expenses_sum = Decimal("0.00")

        for nazwa in sorted(self.KATEGORIE_STALE):
            kwota = self._fixed_cost_amount(nazwa, rok)
            if rok == 2026 and miesiac == 3:
                kwota = self._money(kwota * Decimal(str(random.uniform(0.45, 0.90))))

            operation_date = self._random_day(rok, miesiac, 1, min(last_day, 12))
            title = random.choice(self.MAPA_WYDATKOW.get(nazwa, ["Stały wydatek"]))
            generated += self._create_operation(
                user=user,
                typ=self.typ_wydatek,
                kategoria=self.kategorie_objects[nazwa],
                tytul=title,
                kwota=kwota,
                operation_date=operation_date,
                tags=["stały", "rachunki", "dom"] if nazwa in {"Czynsz", "Prąd", "Gaz", "Woda", "Internet"} else ["stały"],
                opis="Stały miesięczny koszt",
            )
            created_expenses_sum += kwota

        regular_categories = [
            "Zakupy spożywcze",
            "Jedzenie",
            "Transport",
            "Paliwo",
            "Rozrywka",
            "Chemia domowa",
            "Apteka",
            "Streaming",
            "Subskrypcje",
            "Hobby",
            "Dom",
        ]

        if miesiac in [6, 7, 8, 12]:
            regular_categories += ["Podróże", "Prezenty", "Ubrania"]

        if miesiac in [1, 9]:
            regular_categories += ["Ubezpieczenie", "Edukacja"]

        operations_count = random.randint(12, 24)
        if rok == 2026 and miesiac == 3:
            operations_count = random.randint(7, 13)

        for _ in range(operations_count):
            nazwa = random.choice(regular_categories)
            kwota = self._variable_cost_amount(nazwa, rok, miesiac)

            if created_expenses_sum + kwota > target_expenses:
                remaining = target_expenses - created_expenses_sum
                if remaining < Decimal("20.00"):
                    break
                kwota = self._money(
                    min(
                        kwota,
                        max(Decimal("15.00"), remaining)
                    )
                )

            operation_date = self._random_day(rok, miesiac, 1, last_day)
            title = random.choice(self.MAPA_WYDATKOW.get(nazwa, ["Wydatek"]))
            tags = self._pick_tags_for_category(nazwa)

            generated += self._create_operation(
                user=user,
                typ=self.typ_wydatek,
                kategoria=self.kategorie_objects[nazwa],
                tytul=title,
                kwota=kwota,
                operation_date=operation_date,
                tags=tags,
                opis="Wydatek bieżący",
            )
            created_expenses_sum += kwota

        sporadic_attempts = random.randint(1, 4)
        if rok == 2026 and miesiac == 3:
            sporadic_attempts = random.randint(0, 2)

        for _ in range(sporadic_attempts):
            if created_expenses_sum >= target_expenses:
                break

            nazwa = random.choice(sorted(self.KATEGORIE_SPORADYCZNE))
            kwota = self._sporadic_cost_amount(nazwa, rok, miesiac)

            remaining = target_expenses - created_expenses_sum
            if remaining < Decimal("50.00"):
                break

            kwota = self._money(min(kwota, remaining))
            operation_date = self._random_day(rok, miesiac, 1, last_day)
            title = random.choice(self.MAPA_WYDATKOW.get(nazwa, ["Wydatek okazjonalny"]))

            generated += self._create_operation(
                user=user,
                typ=self.typ_wydatek,
                kategoria=self.kategorie_objects[nazwa],
                tytul=title,
                kwota=kwota,
                operation_date=operation_date,
                tags=["jednorazowy", "większy wydatek"],
                opis="Większy lub okazjonalny koszt",
            )
            created_expenses_sum += kwota

        while created_expenses_sum + Decimal("25.00") <= target_expenses:
            nazwa = random.choice(
                ["Zakupy spożywcze", "Jedzenie", "Transport", "Rozrywka", "Inne"]
            )
            remaining = target_expenses - created_expenses_sum

            upper = min(float(remaining), 220.0)
            if upper < 25.0:
                break

            kwota = self._money(Decimal(str(random.uniform(25, upper))))
            operation_date = self._random_day(rok, miesiac, 1, last_day)
            title = random.choice(self.MAPA_WYDATKOW.get(nazwa, ["Dodatkowy wydatek"]))

            generated += self._create_operation(
                user=user,
                typ=self.typ_wydatek,
                kategoria=self.kategorie_objects[nazwa],
                tytul=title,
                kwota=kwota,
                operation_date=operation_date,
                tags=["codzienne"],
                opis="Uzupełniający wydatek miesięczny",
            )
            created_expenses_sum += kwota

        return generated

    def _fixed_cost_amount(self, category_name, rok):
        growth = Decimal("1.00") + Decimal(str((rok - 2021) * 0.04))

        ranges = {
            "Czynsz": (1100, 1650),
            "Prąd": (110, 260),
            "Gaz": (70, 210),
            "Woda": (50, 140),
            "Internet": (55, 95),
            "Telefon": (35, 85),
            "Raty": (180, 700),
            "Subskrypcje": (20, 80),
            "Komunikacja miejska": (55, 160),
        }

        low, high = ranges.get(category_name, (50, 150))
        amount = Decimal(str(random.uniform(low, high))) * growth
        return self._money(amount)

    def _variable_cost_amount(self, category_name, rok, miesiac):
        growth = Decimal("1.00") + Decimal(str((rok - 2021) * 0.05))

        ranges = {
            "Zakupy spożywcze": (40, 220),
            "Jedzenie": (20, 120),
            "Transport": (15, 90),
            "Paliwo": (120, 420),
            "Rozrywka": (20, 160),
            "Chemia domowa": (20, 100),
            "Apteka": (15, 140),
            "Streaming": (15, 45),
            "Subskrypcje": (20, 70),
            "Hobby": (30, 180),
            "Dom": (35, 220),
            "Podróże": (150, 900),
            "Prezenty": (70, 450),
            "Ubrania": (80, 500),
            "Ubezpieczenie": (180, 900),
            "Edukacja": (60, 350),
        }

        low, high = ranges.get(category_name, (20, 120))

        if category_name == "Podróże" and miesiac in [6, 7, 8]:
            high *= 1.4
        if category_name == "Prezenty" and miesiac == 12:
            high *= 1.8
        if category_name == "Ubrania" and miesiac in [3, 10, 11]:
            high *= 1.25

        amount = Decimal(str(random.uniform(low, high))) * growth
        return self._money(amount)

    def _sporadic_cost_amount(self, category_name, rok, miesiac):
        growth = Decimal("1.00") + Decimal(str((rok - 2021) * 0.05))

        ranges = {
            "Podróże": (300, 1800),
            "Prezenty": (120, 700),
            "Naprawy": (180, 1400),
            "Lekarz": (120, 650),
            "Kultura": (60, 260),
            "Ubrania": (120, 700),
            "Sport": (80, 450),
            "Zwierzęta": (70, 420),
            "Dziecko": (100, 650),
        }

        low, high = ranges.get(category_name, (80, 300))

        if category_name == "Podróże" and miesiac in [6, 7, 8]:
            high *= 1.3
        if category_name == "Prezenty" and miesiac == 12:
            high *= 1.5

        amount = Decimal(str(random.uniform(low, high))) * growth
        return self._money(amount)

    def _pick_tags_for_category(self, category_name):
        if category_name in self.KATEGORIE_STALE:
            return ["stały"]
        if category_name in {"Zakupy spożywcze", "Jedzenie", "Transport"}:
            return ["codzienne"]
        if category_name in {"Podróże", "Prezenty", "Naprawy"}:
            return ["jednorazowy"]
        return random.sample(self.TAGI, k=random.randint(1, 2))

    def _create_operation(self, user, typ, kategoria, tytul, kwota, operation_date, tags=None, opis=""):
        operacja = Operacja.objects.create(
            uzytkownik=user,
            typ_operacji=typ,
            kategoria=kategoria,
            tytul=tytul,
            kwota=kwota,
            data=operation_date,
            opis=opis,
        )

        if tags:
            for nazwa in tags:
                tag = self.tagi_objects.get(nazwa)
                if tag:
                    operacja.tagi.add(tag)

        return 1

    def _random_day(self, rok, miesiac, day_start, day_end):
        day_start = max(1, day_start)
        day_end = max(day_start, day_end)
        day = random.randint(day_start, day_end)
        return date(rok, miesiac, day)

    def _money(self, value):
        return Decimal(value).quantize(Decimal("0.01"))