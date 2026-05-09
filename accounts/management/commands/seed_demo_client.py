import random
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.services import ensure_finance_dictionary, ensure_user_setup
from finanse.models import CelOszczednosciowy, Kategoria, KontoDomowe, Operacja, RaportMiesieczny, Tag, TypOperacji
from firma.models import FakturaKosztowa, FakturaSprzedazy, JPKDeklaracja, Kontrahent, UstawieniaFirmy
from paneladmin.models import UserRole


class Command(BaseCommand):
    help = "Tworzy konto demo klienta z dużą ilością danych domowych i firmowych."

    def add_arguments(self, parser):
        parser.add_argument("--username", default="klient_demo")
        parser.add_argument("--password", default="KlientDemo123!")
        parser.add_argument("--email", default="klient.demo@example.com")
        parser.add_argument("--clear", action="store_true")

    @transaction.atomic
    def handle(self, *args, **options):
        username = options["username"]
        password = options["password"]
        email = options["email"]
        should_clear = options["clear"]

        ensure_finance_dictionary()

        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "first_name": "Klient",
                "last_name": "Demo",
                "is_active": True,
            },
        )
        user.email = email
        user.first_name = user.first_name or "Klient"
        user.last_name = user.last_name or "Demo"
        user.is_active = True
        user.set_password(password)
        user.save()

        UserRole.objects.update_or_create(
            user=user,
            defaults={"role": UserRole.ROLE_UZYTKOWNIK, "notes": "Konto demonstracyjne"},
        )
        ensure_user_setup(user)

        if should_clear:
            Operacja.objects.filter(uzytkownik=user).delete()
            RaportMiesieczny.objects.filter(uzytkownik=user).delete()
            CelOszczednosciowy.objects.filter(uzytkownik=user).delete()
            KontoDomowe.objects.filter(uzytkownik=user).exclude(nazwa="Konto główne").delete()
            FakturaSprzedazy.objects.filter(user=user).delete()
            FakturaKosztowa.objects.filter(user=user).delete()
            JPKDeklaracja.objects.filter(user=user).delete()
            Kontrahent.objects.filter(user=user).delete()
            UstawieniaFirmy.objects.filter(user=user).delete()

        konta = {
            "Konto główne": KontoDomowe.objects.get_or_create(
                uzytkownik=user,
                nazwa="Konto główne",
                defaults={"typ": "ROR", "saldo_poczatkowe": Decimal("8500.00")},
            )[0],
            "Oszczędności": KontoDomowe.objects.get_or_create(
                uzytkownik=user,
                nazwa="Oszczędności",
                defaults={"typ": "OSZCZEDNOSCIOWE", "saldo_poczatkowe": Decimal("24000.00")},
            )[0],
            "Gotówka": KontoDomowe.objects.get_or_create(
                uzytkownik=user,
                nazwa="Portfel",
                defaults={"typ": "GOTOWKA", "saldo_poczatkowe": Decimal("600.00")},
            )[0],
            "Firmowe": KontoDomowe.objects.get_or_create(
                uzytkownik=user,
                nazwa="Konto firmowe",
                defaults={"typ": "FIRMA", "saldo_poczatkowe": Decimal("12000.00")},
            )[0],
        }

        przychod, _ = TypOperacji.objects.get_or_create(nazwa="Przychod")
        wydatek, _ = TypOperacji.objects.get_or_create(nazwa="Wydatek")
        categories = {name: Kategoria.objects.get_or_create(nazwa=name)[0] for name in [
            "Dom", "Jedzenie", "Transport", "Rachunki", "Zdrowie", "Rozrywka", "Oszczędności", "Firma", "Inne"
        ]}
        tags = {name: Tag.objects.get_or_create(nazwa=name)[0] for name in [
            "stałe", "rodzina", "auto", "subskrypcje", "wakacje", "firma", "zdrowie", "oszczędzanie"
        ]}

        today = date.today()
        start = date(today.year - 1, 1, 1)
        if not Operacja.objects.filter(uzytkownik=user).exists():
            current = start
            while current <= today:
                salary = Operacja.objects.create(
                    uzytkownik=user,
                    konto=konta["Konto główne"],
                    data=current.replace(day=min(5, 28)),
                    tytul="Wynagrodzenie",
                    kwota=Decimal(str(random.randint(7800, 9800))),
                    typ_operacji=przychod,
                    kategoria=categories["Inne"],
                    opis="Wpływ miesięczny",
                )
                salary.tagi.add(tags["stałe"])

                for title, cat, amount_rng, day, acc, extra_tag in [
                    ("Zakupy spożywcze", "Jedzenie", (120, 420), 3, "Konto główne", "rodzina"),
                    ("Paliwo", "Transport", (180, 520), 8, "Konto główne", "auto"),
                    ("Media i rachunki", "Rachunki", (240, 680), 11, "Konto główne", "stałe"),
                    ("Zakupy domowe", "Dom", (90, 360), 14, "Konto główne", "rodzina"),
                    ("Abonamenty", "Rozrywka", (40, 120), 18, "Konto główne", "subskrypcje"),
                    ("Przelew na oszczędności", "Oszczędności", (500, 1500), 20, "Oszczędności", "oszczędzanie"),
                    ("Wydatki firmowe prywatne", "Firma", (80, 320), 23, "Firmowe", "firma"),
                ]:
                    op = Operacja.objects.create(
                        uzytkownik=user,
                        konto=konta[acc],
                        data=current.replace(day=min(day, 28)),
                        tytul=title,
                        kwota=Decimal(str(random.randint(*amount_rng))),
                        typ_operacji=wydatek,
                        kategoria=categories[cat],
                        opis=f"Automatycznie wygenerowane dane demo: {title.lower()}.",
                    )
                    op.tagi.add(tags[extra_tag])

                if current.month in {1, 7, 8, 12}:
                    op = Operacja.objects.create(
                        uzytkownik=user,
                        konto=konta["Konto główne"],
                        data=current.replace(day=min(26, 28)),
                        tytul="Wyjazd / wypoczynek",
                        kwota=Decimal(str(random.randint(600, 2200))),
                        typ_operacji=wydatek,
                        kategoria=categories["Rozrywka"],
                        opis="Sezonowy koszt demonstracyjny.",
                    )
                    op.tagi.add(tags["wakacje"])

                current = (current.replace(day=28) + timedelta(days=4)).replace(day=1)

        for year in {today.year - 1, today.year}:
            CelOszczednosciowy.objects.update_or_create(
                uzytkownik=user,
                rok=year,
                defaults={"kwota_docelowa": Decimal("18000.00") if year == today.year else Decimal("15000.00")},
            )

        UstawieniaFirmy.objects.update_or_create(
            user=user,
            defaults={
                "nazwa_firmy": "Demo Consulting Marcin Test",
                "wlasciciel": "Marcin Testowy",
                "nip": "9661234567",
                "adres": "ul. Przykładowa 10, 15-001 Białystok",
                "kod_urzedu_skarbowego": "2001",
                "forma_opodatkowania": "LINIOWY",
                "vat_czynny": True,
                "typ_zus": "PELNY",
                "czy_chorobowe": True,
            },
        )

        kontrahenci = []
        for idx in range(1, 11):
            kontrahenci.append(
                Kontrahent.objects.get_or_create(
                    user=user,
                    nazwa=f"Kontrahent Demo {idx}",
                    defaults={
                        "nip": f"96612345{idx:02d}",
                        "regon": f"2000000{idx:02d}",
                        "adres": f"ul. Biznesowa {idx}, 15-10{idx} Białystok",
                        "email": f"kontakt{idx}@demo-kontrahent.pl",
                        "telefon": f"5006007{idx:02d}",
                    },
                )[0]
            )

        if not FakturaSprzedazy.objects.filter(user=user).exists():
            current = start
            sale_no = 1
            cost_no = 1
            while current <= today:
                contractor = random.choice(kontrahenci)
                netto = Decimal(str(random.randint(1800, 7500)))
                brutto = (netto * Decimal("1.23")).quantize(Decimal("0.01"))
                FakturaSprzedazy.objects.create(
                    user=user,
                    numer=f"FS/{current.year}/{sale_no:04d}",
                    kontrahent=contractor,
                    data_wystawienia=current.replace(day=min(4, 28)),
                    data_sprzedazy=current.replace(day=min(4, 28)),
                    kwota_netto=netto,
                    kwota_brutto=brutto,
                    czy_oplacona=random.choice([True, True, False]),
                    opis="Usługa konsultingowa / wdrożeniowa demo.",
                )
                sale_no += 1

                for _ in range(2):
                    vendor = random.choice(kontrahenci)
                    netto = Decimal(str(random.randint(250, 2900)))
                    vat = (netto * Decimal("0.23")).quantize(Decimal("0.01"))
                    brutto = netto + vat
                    FakturaKosztowa.objects.create(
                        user=user,
                        numer_faktury=f"FK/{current.year}/{cost_no:04d}",
                        kontrahent=vendor,
                        kontrahent_nazwa=vendor.nazwa,
                        nip_dostawcy=vendor.nip,
                        data_zakupu=current.replace(day=min(random.randint(6, 26), 28)),
                        kwota_netto=netto,
                        kwota_vat=vat,
                        kwota_brutto=brutto,
                        kategoria=random.choice(["Sprzęt", "Usługi obce", "Marketing", "Paliwo", "Biuro"]),
                        rodzaj_zakupu=random.choice(["POZ", "POZ", "ST"]),
                        miesiac_jpk=current.month,
                        opis="Koszt demonstracyjny dla prezentacji modułu firmy.",
                    )
                    cost_no += 1

                JPKDeklaracja.objects.update_or_create(
                    user=user,
                    rok=current.year,
                    miesiac=current.month,
                    defaults={
                        "p_17": Decimal("1000.00"),
                        "p_18": Decimal("230.00"),
                        "p_19": Decimal("0.00"),
                        "p_20": Decimal("0.00"),
                        "p_51": Decimal("230.00"),
                        "p_68": True,
                        "p_ordzu": False,
                        "uzasadnienie": "Dane demo do prezentacji funkcjonalności.",
                    },
                )

                current = (current.replace(day=28) + timedelta(days=4)).replace(day=1)

        self.stdout.write(self.style.SUCCESS(f"Konto demo gotowe: {username} / {password}"))
