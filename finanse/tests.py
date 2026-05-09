from io import BytesIO

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .importers import import_operacje_csv_for_user
from .models import Kategoria, KontoDomowe, Operacja, TypOperacji


class FinanseImporterTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='jan', password='x')

    def test_duplicate_domestic_row_is_skipped(self):
        typ, _ = TypOperacji.objects.get_or_create(nazwa='Wydatek')
        kat, _ = Kategoria.objects.get_or_create(nazwa='Inne')
        Operacja.objects.create(uzytkownik=self.user, konto_id=None, tytul='Sklep', kwota='12.30', data='2026-03-01', typ_operacji=typ, kategoria=kat)
        payload = 'Data,Tytuł,Kwota,Typ,Kategoria,Tagi,Opis\n2026-03-01,Sklep,12.30,Wydatek,Inne,,\n'
        summary = import_operacje_csv_for_user(user=self.user, fileobj=BytesIO(payload.encode('utf-8')), source_name='x.csv')
        self.assertEqual(summary['dodane'], 0)
        self.assertEqual(Operacja.objects.count(), 1)


class FinanseViewsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='anna', password='x')
        self.client.force_login(self.user)
        self.konto = KontoDomowe.objects.create(uzytkownik=self.user, nazwa='Konto osobiste', typ='ROR', saldo_poczatkowe='500.00')

    def test_add_operation_page_contains_account_field(self):
        response = self.client.get(reverse('dodaj_operacje'))
        self.assertContains(response, 'Konto')
        self.assertContains(response, 'name="konto"', html=False)

    def test_accounts_page_uses_customer_friendly_labels(self):
        response = self.client.get(reverse('lista_kont'))
        self.assertContains(response, 'Konta domowe')
        self.assertContains(response, 'Saldo początkowe')
        self.assertContains(response, 'Konto osobiste')


class NavigationSmokeTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='nawigator', password='x')
        self.client.force_login(self.user)

    def test_module_selector_uses_working_add_operation_link(self):
        response = self.client.get(reverse('module_selector'))
        self.assertContains(response, reverse('dodaj_operacje'))
        self.assertNotContains(response, '/dom/operacje/dodaj/')

    def test_import_export_hub_is_available(self):
        response = self.client.get(reverse('centrum_importu_eksportu'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Import i eksport budżetu domowego')
