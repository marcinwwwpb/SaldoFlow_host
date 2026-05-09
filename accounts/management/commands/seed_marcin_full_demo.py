import calendar
import random
from collections import defaultdict
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from finanse.models import (
    CelOszczednosciowy,
    Kategoria,
    KontoDomowe,
    Operacja,
    RaportMiesieczny,
    Tag,
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


class Command(BaseCommand):
    help = "Szybko tworzy superusera marcin/admin oraz dane demo domowe i firmowe."

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true")
        parser.add_argument("--start-year", type=int, default=2021)
        parser.add_argument("--end-year", type=int, default=2026)
        parser.add_argument("--home-per-year", type=int, default=180)
        parser.add_argument("--firm-per-year", type=int, default=180)

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(20260509)

        start_year = options["start_year"]
        end_year = options["end_year"]
        home_per_year = options["home_per_year"]
        firm_per_year = options["firm_per_year"]

        User = get_user_model()

        user, _ = User.objects.get_or_create(
            username="marcin",
            defaults={
                "email": "marcin@saldoflow.local",
                "first_name": "Marcin",
                "last_name": "Admin",
                "is_active": True,
                "is_staff": True,
                "is_superuser": True,
                "date_joined": timezone.now(),
            },
        )

        user.email = "marcin@saldoflow.local"
        user.first_name = "Marcin"
        user.last_name = "Admin"
        user.is_active = True
        user.is_staff = True
        user.is_superuser = True
        user.set_password("admin")
        user.save()

        UserRole.objects.update_or_create(
            user=user,
            defaults={
                "role": UserRole.ROLE_SUPERADMIN,
                "notes": "Superuser demo: marcin/admin",
            },
        )

        if options["clear"]:
            self.stdout.write("Czyszczę dane użytkownika marcin...")

            Operacja.tagi.through.objects.filter(operacja__uzytkownik=user).delete()
            Operacja.objects.filter(uzytkownik=user).delete()
            RaportMiesieczny.objects.filter(uzytkownik=user).delete()
            CelOszczednosciowy.objects.filter(uzytkownik=user).delete()
            KontoDomowe.objects.filter(uzytkownik=user).delete()

            FakturaSprzedazy.objects.filter(user=user).delete()
            FakturaKosztowa.objects.filter(user=user).delete()
            JPKDeklaracja.objects.filter(user=user).delete()
            Kontrahent.objects.filter(user=user).delete()
            UstawieniaFirmy.objects.filter(user=user).delete()

        przychod, _ = TypOperacji.objects.get_or_create(nazwa="Przychod")
        wydatek, _ = TypOperacji.objects.get_or_create(nazwa="Wydatek")

        category_names = [
            "Wynagrodzenie", "Dom", "Jedzenie", "Transport", "Rachunki",
            "Zdrowie", "Rozrywka", "Oszczędności", "Firma", "Podróże",
            "Edukacja", "Prezenty", "Inne",
        ]
        categories = {
            name: Kategoria.objects.get_or_create(nazwa=name)[0]
            for name in category_names
        }

        tag_names = [
            "stałe", "jednorazowe", "rodzina", "auto", "online", "firma",
            "zdrowie", "mieszkanie", "wakacje", "oszczędzanie", "B2B", "VAT",
        ]
        tags = {
            name: Tag.objects.get_or_create(nazwa=name)[0]
            for name in tag_names
        }

        konta = [
            KontoDomowe(
                uzytkownik=user,
                nazwa="Konto główne",
                typ="ROR",
                saldo_poczatkowe=Decimal("15000.00"),
                aktywne=True,
            ),
            KontoDomowe(
                uzytkownik=user,
                nazwa="Oszczędności",
                typ="OSZCZEDNOSCIOWE",
                saldo_poczatkowe=Decimal("42000.00"),
                aktywne=True,
            ),
            KontoDomowe(
                uzytkownik=user,
                nazwa="Gotówka",
                typ="GOTOWKA",
                saldo_poczatkowe=Decimal("1200.00"),
                aktywne=True,
            ),
            KontoDomowe(
                uzytkownik=user,
                nazwa="Konto firmowe",
                typ="FIRMA",
                saldo_poczatkowe=Decimal("28000.00"),
                aktywne=True,
            ),
        ]
        KontoDomowe.objects.bulk_create(konta, batch_size=500)

        konto_glowne = KontoDomowe.objects.get(uzytkownik=user, nazwa="Konto główne")
        konto_oszczednosci = KontoDomowe.objects.get(uzytkownik=user, nazwa="Oszczędności")
        konto_gotowka = KontoDomowe.objects.get(uzytkownik=user, nazwa="Gotówka")
        konto_firmowe = KontoDomowe.objects.get(uzytkownik=user, nazwa="Konto firmowe")

        UstawieniaFirmy.objects.create(
            user=user,
            nazwa_firmy="Marcin Consulting",
            wlasciciel="Marcin Admin",
            nip="5420000001",
            adres="ul. Testowa 10, 15-001 Białystok",
            kod_urzedu_skarbowego="2001",
            forma_opodatkowania="LINIOWY",
            vat_czynny=True,
            typ_zus="PELNY",
            czy_chorobowe=True,
        )

        cities = ["Białystok", "Warszawa", "Gdańsk", "Kraków", "Poznań", "Wrocław"]
        contractor_names = [
            "Nova Tech", "Alpha Media", "Baltic Soft", "Green Office", "Pixel Forge",
            "Finovo", "Smart Logistics", "Delta Trade", "OptiWeb", "Code Harbor",
            "Data Craft", "Vision ERP", "Office Partner", "Tax Point", "Blue River",
            "Centrum Druku", "Mikro Partner", "Creative Hub", "Netline", "Nord Energy",
            "Inwest Plus", "Top Serwis", "Termo Instal", "Smart Med", "Aero Print",
            "Start Biznes", "Kancelaria Sigma", "Mercator PL", "City Logistics", "Meblo-Projekt",
        ]

        kontrahenci_objs = []
        for i, name in enumerate(contractor_names, start=1):
            kontrahenci_objs.append(
                Kontrahent(
                    user=user,
                    nazwa=f"{name} sp. z o.o.",
                    nip=f"542{i:07d}",
                    regon=f"200{i:06d}",
                    adres=f"ul. Przemysłowa {i}, 15-{100 + i:03d} {random.choice(cities)}",
                    email=f"kontakt{i}@demo-firma.pl",
                    telefon=f"500700{i:03d}",
                    strona_www=f"https://demo-kontrahent-{i}.pl",
                    status_rejestru="AKTYWNY",
                )
            )

        Kontrahent.objects.bulk_create(kontrahenci_objs, batch_size=500)
        kontrahenci = list(Kontrahent.objects.filter(user=user))

        def money(min_value, max_value):
            return Decimal(str(random.uniform(min_value, max_value))).quantize(Decimal("0.01"))

        def random_date_in_year(year):
            month = random.randint(1, 12)
            day = random.randint(1, calendar.monthrange(year, month)[1])
            return date(year, month, day)

        home_expenses = [
            ("Zakupy spożywcze", "Jedzenie", 40, 450, konto_glowne, ["rodzina"]),
            ("Paliwo", "Transport", 120, 650, konto_glowne, ["auto"]),
            ("Czynsz", "Dom", 1200, 2200, konto_glowne, ["stałe", "mieszkanie"]),
            ("Prąd", "Rachunki", 120, 420, konto_glowne, ["stałe"]),
            ("Internet i telefon", "Rachunki", 100, 280, konto_glowne, ["online", "stałe"]),
            ("Apteka", "Zdrowie", 30, 280, konto_glowne, ["zdrowie"]),
            ("Restauracja", "Rozrywka", 60, 420, konto_glowne, ["jednorazowe"]),
            ("Wyjazd weekendowy", "Podróże", 300, 2600, konto_glowne, ["wakacje"]),
            ("Kurs / książki", "Edukacja", 80, 1200, konto_glowne, ["online"]),
            ("Prezent", "Prezenty", 70, 600, konto_gotowka, ["jednorazowe"]),
            ("Przelew na oszczędności", "Oszczędności", 300, 2500, konto_oszczednosci, ["oszczędzanie"]),
        ]

        home_incomes = [
            ("Wynagrodzenie", "Wynagrodzenie", 7000, 13000, konto_glowne, ["stałe"]),
            ("Premia", "Wynagrodzenie", 800, 4500, konto_glowne, ["jednorazowe"]),
            ("Dodatkowe zlecenie", "Firma", 900, 5500, konto_firmowe, ["firma"]),
            ("Zwrot / cashback", "Inne", 50, 700, konto_glowne, ["jednorazowe"]),
        ]

        sales_descriptions = [
            "Usługa konsultingowa", "Wdrożenie systemu", "Opieka techniczna",
            "Analiza procesów", "Automatyzacja raportów", "Prace programistyczne",
        ]
        cost_categories = ["Sprzęt", "Usługi obce", "Marketing", "Biuro", "Paliwo", "Internet", "Księgowość", "Szkolenia"]

        operacje = []
        operacja_tags = []
        cele = []
        raport_sums = defaultdict(lambda: {"in": Decimal("0.00"), "out": Decimal("0.00")})
        home_created_by_year = defaultdict(int)

        self.stdout.write("Generuję operacje domowe w pamięci...")

        for year in range(start_year, end_year + 1):
            for month in range(1, 13):
                d = date(year, month, min(10, calendar.monthrange(year, month)[1]))
                kwota = money(7000, 13000)

                op = Operacja(
                    uzytkownik=user,
                    konto=konto_glowne,
                    tytul="Wynagrodzenie",
                    kwota=kwota,
                    data=d,
                    typ_operacji=przychod,
                    kategoria=categories["Wynagrodzenie"],
                    opis=f"Dane testowe {year}: stały przychód miesięczny.",
                )
                operacje.append(op)
                operacja_tags.append(["stałe"])
                raport_sums[(year, month)]["in"] += kwota
                home_created_by_year[year] += 1

            while home_created_by_year[year] < home_per_year:
                is_income = random.random() < 0.16

                if is_income:
                    title, cat, mn, mx, konto, tag_list = random.choice(home_incomes[1:])
                    typ = przychod
                else:
                    title, cat, mn, mx, konto, tag_list = random.choice(home_expenses)
                    typ = wydatek

                d = random_date_in_year(year)
                kwota = money(mn, mx)

                op = Operacja(
                    uzytkownik=user,
                    konto=konto,
                    tytul=title,
                    kwota=kwota,
                    data=d,
                    typ_operacji=typ,
                    kategoria=categories[cat],
                    opis=f"Dane testowe budżetu domowego za {year}.",
                )
                operacje.append(op)
                operacja_tags.append(tag_list)

                if typ.id == przychod.id:
                    raport_sums[(year, d.month)]["in"] += kwota
                else:
                    raport_sums[(year, d.month)]["out"] += kwota

                home_created_by_year[year] += 1

            cele.append(
                CelOszczednosciowy(
                    uzytkownik=user,
                    rok=year,
                    kwota_docelowa=Decimal("30000.00") + Decimal(str((year - start_year) * 3500)),
                )
            )

        Operacja.objects.bulk_create(operacje, batch_size=1000)
        operacje = list(Operacja.objects.filter(uzytkownik=user).order_by("id"))

        through = Operacja.tagi.through
        m2m = []
        for op, tag_list in zip(operacje, operacja_tags):
            for tag_name in tag_list:
                m2m.append(through(operacja_id=op.id, tag_id=tags[tag_name].id))
        through.objects.bulk_create(m2m, batch_size=2000, ignore_conflicts=True)

        CelOszczednosciowy.objects.bulk_create(cele, batch_size=500)

        faktury_s = []
        faktury_k = []
        jpk_sums = defaultdict(lambda: {
            "sales_net": Decimal("0.00"),
            "sales_vat": Decimal("0.00"),
            "cost_net": Decimal("0.00"),
            "cost_vat": Decimal("0.00"),
        })
        firm_created_by_year = defaultdict(int)

        self.stdout.write("Generuję faktury firmowe w pamięci...")

        for year in range(start_year, end_year + 1):
            sales_target = firm_per_year // 2
            costs_target = firm_per_year - sales_target

            for i in range(1, sales_target + 1):
                contractor = random.choice(kontrahenci)
                issued = random_date_in_year(year)
                netto = money(1200, 14500)
                brutto = (netto * Decimal("1.23")).quantize(Decimal("0.01"))
                vat = brutto - netto

                faktury_s.append(
                    FakturaSprzedazy(
                        user=user,
                        numer=f"FS/{year}/{i:04d}",
                        kontrahent=contractor,
                        data_wystawienia=issued,
                        data_sprzedazy=issued,
                        kwota_netto=netto,
                        kwota_brutto=brutto,
                        czy_oplacona=random.choice([True, True, True, False]),
                        opis=random.choice(sales_descriptions),
                    )
                )
                jpk_sums[(year, issued.month)]["sales_net"] += netto
                jpk_sums[(year, issued.month)]["sales_vat"] += vat
                firm_created_by_year[year] += 1

            for i in range(1, costs_target + 1):
                contractor = random.choice(kontrahenci)
                purchased = random_date_in_year(year)
                netto = money(80, 6200)
                vat = (netto * Decimal("0.23")).quantize(Decimal("0.01"))
                brutto = netto + vat

                faktury_k.append(
                    FakturaKosztowa(
                        user=user,
                        numer_faktury=f"FK/{year}/{i:04d}",
                        kontrahent=contractor,
                        kontrahent_nazwa=contractor.nazwa,
                        nip_dostawcy=contractor.nip,
                        kod_kraju="PL",
                        data_zakupu=purchased,
                        kwota_netto=netto,
                        kwota_vat=vat,
                        kwota_brutto=brutto,
                        kategoria=random.choice(cost_categories),
                        rodzaj_zakupu=random.choice(["POZ", "POZ", "POZ", "ST"]),
                        miesiac_jpk=purchased.month,
                        opis=f"Dane testowe kosztów firmowych za {year}.",
                    )
                )
                jpk_sums[(year, purchased.month)]["cost_net"] += netto
                jpk_sums[(year, purchased.month)]["cost_vat"] += vat
                firm_created_by_year[year] += 1

        FakturaSprzedazy.objects.bulk_create(faktury_s, batch_size=1000)
        FakturaKosztowa.objects.bulk_create(faktury_k, batch_size=1000)

        raporty = []
        jpki = []

        for year in range(start_year, end_year + 1):
            for month in range(1, 13):
                sums = raport_sums[(year, month)]
                raporty.append(
                    RaportMiesieczny(
                        uzytkownik=user,
                        rok=year,
                        miesiac=month,
                        suma_przychodow=sums["in"],
                        suma_wydatkow=sums["out"],
                        saldo=sums["in"] - sums["out"],
                    )
                )

                j = jpk_sums[(year, month)]
                jpki.append(
                    JPKDeklaracja(
                        user=user,
                        rok=year,
                        miesiac=month,
                        p_17=j["sales_net"],
                        p_18=j["sales_vat"],
                        p_19=Decimal("0.00"),
                        p_20=Decimal("0.00"),
                        p_43_korekta=j["cost_net"],
                        p_44_korekta=j["cost_vat"],
                        p_45_korekta=Decimal("0.00"),
                        p_46_korekta=Decimal("0.00"),
                        p_51=max(j["sales_vat"] - j["cost_vat"], Decimal("0.00")),
                        p_68=True,
                        p_ordzu=False,
                        uzasadnienie="Dane testowe wygenerowane automatycznie.",
                    )
                )

        RaportMiesieczny.objects.bulk_create(raporty, batch_size=1000)
        JPKDeklaracja.objects.bulk_create(jpki, batch_size=1000)

        self.stdout.write(self.style.SUCCESS("Gotowe."))
        self.stdout.write(self.style.SUCCESS("Login: marcin"))
        self.stdout.write(self.style.SUCCESS("Hasło: admin"))

        self.stdout.write(self.style.SUCCESS(f"Operacje domowe: {len(operacje)}"))
        self.stdout.write(self.style.SUCCESS(f"Faktury sprzedaży: {len(faktury_s)}"))
        self.stdout.write(self.style.SUCCESS(f"Faktury kosztowe: {len(faktury_k)}"))

        for year in range(start_year, end_year + 1):
            self.stdout.write(
                f"{year}: domowe={home_created_by_year[year]}, firmowe={firm_created_by_year[year]}"
            )
