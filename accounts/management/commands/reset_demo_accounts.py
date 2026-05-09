import random
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from accounts.services import ensure_finance_dictionary, ensure_user_setup
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
    help = "Ustawia konta marcin/admin i test/test oraz tworzy duży, wiarygodny zestaw danych demo."

    def add_arguments(self, parser):
        parser.add_argument("--clear", action="store_true", help="Czyści stare dane demo przed wygenerowaniem nowych.")

    @transaction.atomic
    def handle(self, *args, **options):
        should_clear = options["clear"]

        ensure_finance_dictionary()

        admin_user, _ = User.objects.get_or_create(
            username="marcin",
            defaults={
                "email": "marcin@local.test",
                "first_name": "Marcin",
                "last_name": "Admin",
                "is_active": True,
                "is_staff": True,
                "is_superuser": True,
                "date_joined": timezone.now(),
            },
        )
        admin_user.first_name = "Marcin"
        admin_user.last_name = "Admin"
        admin_user.email = admin_user.email or "marcin@local.test"
        admin_user.is_active = True
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.set_password("admin")
        admin_user.save()

        UserRole.objects.update_or_create(
            user=admin_user,
            defaults={"role": UserRole.ROLE_SUPERADMIN, "notes": "Główne konto administratora"},
        )

        demo_user, _ = User.objects.get_or_create(
            username="test",
            defaults={
                "email": "test@demo.local",
                "first_name": "Konto",
                "last_name": "Testowe",
                "is_active": True,
                "date_joined": timezone.now(),
            },
        )
        demo_user.first_name = "Konto"
        demo_user.last_name = "Testowe"
        demo_user.email = "test@demo.local"
        demo_user.is_active = True
        demo_user.is_staff = False
        demo_user.is_superuser = False
        demo_user.set_password("test")
        demo_user.save()

        UserRole.objects.update_or_create(
            user=demo_user,
            defaults={"role": UserRole.ROLE_UZYTKOWNIK, "notes": "Duże konto demonstracyjne"},
        )

        ensure_user_setup(demo_user)

        if should_clear:
            Operacja.objects.filter(uzytkownik=demo_user).delete()
            RaportMiesieczny.objects.filter(uzytkownik=demo_user).delete()
            CelOszczednosciowy.objects.filter(uzytkownik=demo_user).delete()
            KontoDomowe.objects.filter(uzytkownik=demo_user).exclude(nazwa="Konto główne").delete()
            FakturaSprzedazy.objects.filter(user=demo_user).delete()
            FakturaKosztowa.objects.filter(user=demo_user).delete()
            JPKDeklaracja.objects.filter(user=demo_user).delete()
            Kontrahent.objects.filter(user=demo_user).delete()
            UstawieniaFirmy.objects.filter(user=demo_user).delete()

        konto_glowne, _ = KontoDomowe.objects.get_or_create(
            uzytkownik=demo_user,
            nazwa="Konto główne",
            defaults={"typ": "ROR", "saldo_poczatkowe": Decimal("12500.00")},
        )
        konto_oszcz, _ = KontoDomowe.objects.get_or_create(
            uzytkownik=demo_user,
            nazwa="Oszczędności",
            defaults={"typ": "OSZCZEDNOSCIOWE", "saldo_poczatkowe": Decimal("38200.00")},
        )
        konto_gotowka, _ = KontoDomowe.objects.get_or_create(
            uzytkownik=demo_user,
            nazwa="Portfel",
            defaults={"typ": "GOTOWKA", "saldo_poczatkowe": Decimal("850.00")},
        )
        konto_firma, _ = KontoDomowe.objects.get_or_create(
            uzytkownik=demo_user,
            nazwa="Konto firmowe",
            defaults={"typ": "FIRMA", "saldo_poczatkowe": Decimal("21400.00")},
        )

        przychod, _ = TypOperacji.objects.get_or_create(nazwa="Przychod")
        wydatek, _ = TypOperacji.objects.get_or_create(nazwa="Wydatek")

        categories = {
            name: Kategoria.objects.get_or_create(nazwa=name)[0]
            for name in [
                "Dom",
                "Jedzenie",
                "Transport",
                "Rachunki",
                "Zdrowie",
                "Rozrywka",
                "Oszczędności",
                "Firma",
                "Inne",
            ]
        }

        tags = {
            name: Tag.objects.get_or_create(nazwa=name)[0]
            for name in [
                "stałe",
                "rodzina",
                "auto",
                "subskrypcje",
                "wakacje",
                "firma",
                "zdrowie",
                "oszczędzanie",
                "online",
                "mieszkanie",
                "dzieci",
            ]
        }

        UstawieniaFirmy.objects.update_or_create(
            user=demo_user,
            defaults={
                "nazwa_firmy": "Test Consulting",
                "wlasciciel": "Jan Testowy",
                "nip": "9661234567",
                "adres": "ul. Lipowa 21/4, 15-427 Białystok",
                "kod_urzedu_skarbowego": "2001",
                "forma_opodatkowania": "LINIOWY",
                "vat_czynny": True,
                "typ_zus": "PELNY",
                "czy_chorobowe": True,
            },
        )

        kontrahenci = []
        cities = ["Warszawa", "Białystok", "Gdańsk", "Kraków", "Poznań", "Wrocław", "Lublin", "Katowice"]
        contractor_names = [
            "Nova Tech", "Biuro Expert", "Alpha Media", "Green Office", "Baltic Soft",
            "Pixel Forge", "Finovo", "Termo Instal", "Smart Med", "Delta Trade",
            "OptiWeb", "City Logistics", "Meblo-Projekt", "Netline", "Kancelaria Sigma",
            "Creative Hub", "Aero Print", "Code Harbor", "Start Biznes", "Nord Energy",
            "Mikro Partner", "Vision ERP", "Top Serwis", "Inwest Plus", "Data Craft",
            "Mercator PL", "Centrum Druku", "Office Partner", "Blue River", "Tax Point",
        ]

        for idx, name in enumerate(contractor_names, start=1):
            kontrahenci.append(
                Kontrahent.objects.get_or_create(
                    user=demo_user,
                    nazwa=f"{name} sp. z o.o.",
                    defaults={
                        "nip": f"966{idx:07d}",
                        "regon": f"200{idx:06d}",
                        "adres": f"ul. Przemysłowa {idx}, 15-{100 + (idx % 80):03d} {random.choice(cities)}",
                        "email": f"kontakt{idx}@demo-kontrahent.pl",
                        "telefon": f"500700{idx:03d}",
                        "strona_www": f"https://www.demo-{idx}.pl",
                        "status_rejestru": "AKTYWNY",
                    },
                )[0]
            )

        if not Operacja.objects.filter(uzytkownik=demo_user).exists():
            start_date = date.today() - timedelta(days=730)

            monthly_fixed = [
                ("Czynsz i administracja", "Dom", (1450, 1850), 1, konto_glowne, ["stałe", "mieszkanie"]),
                ("Prąd", "Rachunki", (140, 280), 6, konto_glowne, ["stałe", "mieszkanie"]),
                ("Internet i telefon", "Rachunki", (110, 220), 7, konto_glowne, ["stałe", "subskrypcje"]),
                ("Gaz", "Rachunki", (90, 210), 8, konto_glowne, ["stałe", "mieszkanie"]),
                ("Ubezpieczenie", "Dom", (120, 280), 9, konto_glowne, ["stałe"]),
                ("Żłobek / szkoła / zajęcia", "Dom", (280, 780), 10, konto_glowne, ["dzieci"]),
                ("Zakupy spożywcze - duże", "Jedzenie", (280, 620), 4, konto_glowne, ["rodzina"]),
                ("Zakupy spożywcze - tydzień 2", "Jedzenie", (140, 360), 11, konto_glowne, ["rodzina"]),
                ("Zakupy spożywcze - tydzień 3", "Jedzenie", (130, 340), 18, konto_glowne, ["rodzina"]),
                ("Zakupy spożywcze - tydzień 4", "Jedzenie", (150, 390), 25, konto_glowne, ["rodzina"]),
                ("Paliwo", "Transport", (180, 520), 12, konto_glowne, ["auto"]),
                ("Serwis auta / parking / myjnia", "Transport", (50, 260), 20, konto_glowne, ["auto"]),
                ("Apteka / zdrowie", "Zdrowie", (40, 220), 13, konto_glowne, ["zdrowie"]),
                ("Streaming i subskrypcje", "Rozrywka", (35, 120), 15, konto_glowne, ["subskrypcje"]),
                ("Restauracje i kawa", "Rozrywka", (60, 320), 21, konto_glowne, ["rodzina"]),
                ("Zakupy online", "Dom", (70, 380), 22, konto_glowne, ["online"]),
                ("Przelew na oszczędności", "Oszczędności", (700, 1800), 26, konto_oszcz, ["oszczędzanie"]),
            ]

            extra_titles = [
                ("Biedronka", "Jedzenie", konto_glowne, ["rodzina"]),
                ("Lidl", "Jedzenie", konto_glowne, ["rodzina"]),
                ("Żabka", "Jedzenie", konto_gotowka, ["rodzina"]),
                ("Orlen", "Transport", konto_glowne, ["auto"]),
                ("Circle K", "Transport", konto_glowne, ["auto"]),
                ("Rossmann", "Zdrowie", konto_glowne, ["zdrowie"]),
                ("Empik", "Rozrywka", konto_glowne, ["online"]),
                ("Allegro", "Dom", konto_glowne, ["online"]),
                ("IKEA", "Dom", konto_glowne, ["mieszkanie"]),
                ("Media Expert", "Dom", konto_glowne, ["online"]),
                ("Kino / wydarzenie", "Rozrywka", konto_glowne, ["rodzina"]),
                ("Lekarz / badania", "Zdrowie", konto_glowne, ["zdrowie"]),
                ("Taxi / Uber", "Transport", konto_glowne, ["auto"]),
                ("Piekarnia", "Jedzenie", konto_gotowka, ["rodzina"]),
                ("Warzywniak", "Jedzenie", konto_gotowka, ["rodzina"]),
            ]

            monthly_company_titles = [
                ("Sprzęt biurowy", "Firma"),
                ("Abonament SaaS", "Firma"),
                ("Koszt reklamy", "Firma"),
                ("Usługi księgowe", "Firma"),
                ("Internet firmowy", "Firma"),
                ("Delegacja / nocleg", "Firma"),
            ]

            ops_created = 0
            current = date(start_date.year, start_date.month, 1)

            while current <= date.today():
                salary = Operacja.objects.create(
                    uzytkownik=demo_user,
                    konto=konto_glowne,
                    data=current.replace(day=5),
                    tytul="Wynagrodzenie etat",
                    kwota=Decimal(str(random.randint(8200, 10900))),
                    typ_operacji=przychod,
                    kategoria=categories["Inne"],
                    opis="Comiesięczne wynagrodzenie netto.",
                )
                salary.tagi.add(tags["stałe"])
                ops_created += 1

                freelance = Operacja.objects.create(
                    uzytkownik=demo_user,
                    konto=konto_firma,
                    data=current.replace(day=7),
                    tytul="Wpływ za projekt B2B",
                    kwota=Decimal(str(random.randint(2800, 8600))),
                    typ_operacji=przychod,
                    kategoria=categories["Firma"],
                    opis="Wpływ za zrealizowaną usługę doradczą lub wdrożeniową.",
                )
                freelance.tagi.add(tags["firma"])
                ops_created += 1

                for title, cat, rng, day, acc, tag_names in monthly_fixed:
                    op = Operacja.objects.create(
                        uzytkownik=demo_user,
                        konto=acc,
                        data=current.replace(day=min(day, 28)),
                        tytul=title,
                        kwota=Decimal(str(random.randint(*rng))),
                        typ_operacji=wydatek,
                        kategoria=categories[cat],
                        opis=f"Stały lub typowy koszt kategorii: {cat.lower()}.",
                    )
                    for tag_name in tag_names:
                        op.tagi.add(tags[tag_name])
                    ops_created += 1

                for _ in range(7):
                    title, cat, acc, tag_names = random.choice(extra_titles)
                    op = Operacja.objects.create(
                        uzytkownik=demo_user,
                        konto=acc,
                        data=current.replace(day=random.randint(1, 28)),
                        tytul=title,
                        kwota=Decimal(str(random.randint(15, 290))),
                        typ_operacji=wydatek,
                        kategoria=categories[cat],
                        opis="Dodatkowy wydatek codzienny wygenerowany dla danych demonstracyjnych.",
                    )
                    for tag_name in tag_names:
                        op.tagi.add(tags[tag_name])
                    ops_created += 1

                for title, cat in monthly_company_titles:
                    op = Operacja.objects.create(
                        uzytkownik=demo_user,
                        konto=konto_firma,
                        data=current.replace(day=random.randint(3, 27)),
                        tytul=title,
                        kwota=Decimal(str(random.randint(120, 2400))),
                        typ_operacji=wydatek,
                        kategoria=categories[cat],
                        opis="Wydatek związany z prowadzeniem działalności gospodarczej.",
                    )
                    op.tagi.add(tags["firma"])
                    ops_created += 1

                if current.month in (1, 6, 7, 8, 12):
                    op = Operacja.objects.create(
                        uzytkownik=demo_user,
                        konto=konto_glowne,
                        data=current.replace(day=24),
                        tytul="Weekend / krótki wyjazd",
                        kwota=Decimal(str(random.randint(450, 2600))),
                        typ_operacji=wydatek,
                        kategoria=categories["Rozrywka"],
                        opis="Wydatek sezonowy: wyjazd, hotel, bilety lub atrakcje.",
                    )
                    op.tagi.add(tags["wakacje"])
                    ops_created += 1

                current = (current.replace(day=28) + timedelta(days=4)).replace(day=1)

        for year in {date.today().year - 1, date.today().year, date.today().year + 1}:
            CelOszczednosciowy.objects.update_or_create(
                uzytkownik=demo_user,
                rok=year,
                defaults={"kwota_docelowa": Decimal("24000.00")},
            )

        if not FakturaSprzedazy.objects.filter(user=demo_user).exists():
            start_date = date.today() - timedelta(days=730)
            current = date(start_date.year, start_date.month, 1)
            sale_no = 1
            cost_no = 1

            while current <= date.today():
                for _ in range(8):
                    contractor = random.choice(kontrahenci)
                    netto = Decimal(str(random.randint(1800, 9600)))
                    brutto = (netto * Decimal("1.23")).quantize(Decimal("0.01"))
                    FakturaSprzedazy.objects.create(
                        user=demo_user,
                        numer=f"FS/{current.year}/{sale_no:05d}",
                        kontrahent=contractor,
                        data_wystawienia=current.replace(day=random.randint(1, 28)),
                        data_sprzedazy=current.replace(day=random.randint(1, 28)),
                        kwota_netto=netto,
                        kwota_brutto=brutto,
                        czy_oplacona=random.choice([True, True, True, False]),
                        opis=random.choice([
                            "Usługa wdrożeniowa dla klienta.",
                            "Abonament opieki technicznej.",
                            "Pakiet konsultacji i analizy procesów.",
                            "Prace rozwojowe nad systemem klienta.",
                        ]),
                    )
                    sale_no += 1

                for _ in range(5):
                    vendor = random.choice(kontrahenci)
                    netto = Decimal(str(random.randint(180, 4200)))
                    vat = (netto * Decimal("0.23")).quantize(Decimal("0.01"))
                    brutto = netto + vat
                    FakturaKosztowa.objects.create(
                        user=demo_user,
                        numer_faktury=f"FK/{current.year}/{cost_no:05d}",
                        kontrahent=vendor,
                        kontrahent_nazwa=vendor.nazwa,
                        nip_dostawcy=vendor.nip,
                        data_zakupu=current.replace(day=random.randint(1, 28)),
                        kwota_netto=netto,
                        kwota_vat=vat,
                        kwota_brutto=brutto,
                        kategoria=random.choice(["Sprzęt", "Usługi obce", "Marketing", "Paliwo", "Biuro", "Internet"]),
                        rodzaj_zakupu=random.choice(["POZ", "POZ", "POZ", "ST"]),
                        miesiac_jpk=current.month,
                        opis="Koszt firmowy do prezentacji modułu przedsiębiorcy.",
                    )
                    cost_no += 1

                JPKDeklaracja.objects.update_or_create(
                    user=demo_user,
                    rok=current.year,
                    miesiac=current.month,
                    defaults={
                        "p_17": Decimal(str(random.randint(6000, 18000))),
                        "p_18": Decimal(str(random.randint(1200, 4200))),
                        "p_19": Decimal("0.00"),
                        "p_20": Decimal("0.00"),
                        "p_51": Decimal(str(random.randint(800, 3200))),
                        "p_68": True,
                        "p_ordzu": False,
                        "uzasadnienie": "Dane demonstracyjne do pokazu modułu JPK/VAT.",
                    },
                )

                current = (current.replace(day=28) + timedelta(days=4)).replace(day=1)

        operacje_count = Operacja.objects.filter(uzytkownik=demo_user).count()
        fs_count = FakturaSprzedazy.objects.filter(user=demo_user).count()
        fk_count = FakturaKosztowa.objects.filter(user=demo_user).count()
        jpk_count = JPKDeklaracja.objects.filter(user=demo_user).count()
        kontr_count = Kontrahent.objects.filter(user=demo_user).count()
        total = operacje_count + fs_count + fk_count + jpk_count + kontr_count

        self.stdout.write(self.style.SUCCESS(f"Admin: marcin / admin"))
        self.stdout.write(self.style.SUCCESS(f"Demo:  test / test"))
        self.stdout.write(self.style.SUCCESS(
            f"Wygenerowano rekordy demo: operacje={operacje_count}, sprzedaz={fs_count}, koszty={fk_count}, jpk={jpk_count}, kontrahenci={kontr_count}, razem={total}"
        ))
