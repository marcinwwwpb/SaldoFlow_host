from io import BytesIO

import openpyxl
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from .importers import import_koszty_excel_for_user
from .models import FakturaKosztowa, Kontrahent


class FirmaImporterTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='jan', password='x')

    def _build_workbook(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Data zakupu", "Numer faktury", "NIP dostawcy", "Netto", "VAT", "Brutto", "Kod kraju", "Rodzaj zakupu", "Miesiąc JPK"])
        ws.append(["2026-03-01", "FV/1", "123", "10", "2.3", "12.3", "PL", "POZ", "3"])
        bio = BytesIO()
        wb.save(bio)
        bio.seek(0)
        return bio

    def test_duplicate_invoice_is_skipped(self):
        FakturaKosztowa.objects.create(user=self.user, numer_faktury='FV/1', kontrahent_nazwa='A', data_zakupu='2026-03-01', kwota_netto='10.00', kwota_vat='2.30', kwota_brutto='12.30', kategoria='Import Excel')
        summary = import_koszty_excel_for_user(user=self.user, fileobj=self._build_workbook(), source_name='x.xlsx')
        self.assertEqual(summary['dodane'], 0)
        self.assertEqual(FakturaKosztowa.objects.count(), 1)


class FirmaViewsTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(username='anna', password='x')
        self.client.force_login(self.user)
        self.kontrahent = Kontrahent.objects.create(user=self.user, nazwa='Studio Orbit', nip='1234567890')

    def test_sales_form_uses_business_labels(self):
        response = self.client.get(reverse('dodaj_fakture_sprzedazy'))
        self.assertContains(response, 'Numer faktury')
        self.assertContains(response, 'Data sprzedaży')
        self.assertContains(response, 'Faktura opłacona')

    def test_cost_form_uses_customer_friendly_labels(self):
        response = self.client.get(reverse('dodaj_fakture_kosztowa'))
        self.assertContains(response, 'Powiązany kontrahent')
        self.assertContains(response, 'Kategoria kosztu')
        self.assertContains(response, 'Opis / notatka')
from django.test import override_settings

from paneladmin.models import UserRole


class CeidgEndpointTests(TestCase):
    @override_settings(CEIDG_AUTH_TOKEN='', CEIDG_DEMO_MODE=True)
    def test_ceidg_endpoint_returns_demo_payload_when_token_missing(self):
        User = get_user_model()
        user = User.objects.create_user(username='ceidg', password='x')
        self.client.force_login(user)
        response = self.client.get(reverse('api_ceidg_po_nip'), {'nip': '1234567890'})
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['dane']['nip'], '1234567890')
        self.assertEqual(payload['dane']['source'], 'demo')


class FirmaRolePermissionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.auditor = User.objects.create_user(username='audytor_test', password='x')
        UserRole.objects.update_or_create(user=self.auditor, defaults={'role': UserRole.ROLE_AUDYTOR})
        self.client.force_login(self.auditor)

    def test_auditor_cannot_open_cost_invoice_create_page(self):
        response = self.client.get(reverse('dodaj_fakture_kosztowa'))
        self.assertEqual(response.status_code, 403)

    def test_auditor_can_still_open_dashboard(self):
        response = self.client.get(reverse('firma_dashboard'))
        self.assertEqual(response.status_code, 200)
