from pathlib import Path
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from finanse.models import DemonLog, Kategoria, KontoDomowe, Operacja, TypOperacji
from firma.models import FakturaKosztowa
from .models import OperacjaArchiwum, SignificantDatabaseChange, UserRole


class PanelAdminTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.staff = User.objects.create_user(username='admin', password='x', is_staff=True)
        self.user = User.objects.create_user(username='jan', password='x')
        self.client = Client()
        self.client.login(username='admin', password='x')
        self.konto = KontoDomowe.objects.create(uzytkownik=self.user, nazwa='ROR')
        self.typ, _ = TypOperacji.objects.get_or_create(nazwa='Wydatek')
        self.kategoria, _ = Kategoria.objects.get_or_create(nazwa='Dom')

    def test_dashboard_access(self):
        response = self.client.get(reverse('paneladmin_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_create_dom_operation(self):
        response = self.client.post(reverse('paneladmin_zapisz_dom'), {
            'uzytkownik': self.user.id,
            'konto': self.konto.id,
            'tytul': 'Prąd',
            'kwota': '120.00',
            'data': '2026-03-01',
            'typ_operacji': self.typ.id,
            'kategoria': self.kategoria.id,
            'opis': 'rachunek',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Operacja.objects.filter(tytul='Prąd').exists())

    def test_delete_archives_dom_operation(self):
        operacja = Operacja.objects.create(uzytkownik=self.user, konto=self.konto, tytul='Test', kwota='10.00', data='2026-03-02', typ_operacji=self.typ, kategoria=self.kategoria)
        response = self.client.get(reverse('paneladmin_usun_dom', args=[operacja.id]))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Operacja.objects.filter(id=operacja.id).exists())
        self.assertTrue(OperacjaArchiwum.objects.filter(source_id=operacja.id).exists())

    def test_save_user_role(self):
        response = self.client.post(reverse('paneladmin_zapisz_role'), {'user': self.user.id, 'role': 'KSIEGOWY', 'notes': 'obsługa firmy'})
        self.assertEqual(response.status_code, 302)
        self.assertTrue(UserRole.objects.filter(user=self.user, role='KSIEGOWY').exists())


    def test_significant_change_logged_for_operation_create_and_update(self):
        response = self.client.post(reverse('paneladmin_zapisz_dom'), {
            'uzytkownik': self.user.id,
            'konto': self.konto.id,
            'tytul': 'Internet',
            'kwota': '89.00',
            'data': '2026-03-05',
            'typ_operacji': self.typ.id,
            'kategoria': self.kategoria.id,
            'opis': 'abonament',
        })
        self.assertEqual(response.status_code, 302)
        operacja = Operacja.objects.get(tytul='Internet')
        self.assertTrue(SignificantDatabaseChange.objects.filter(model_name='Operacja', object_pk=str(operacja.id), operation='INSERT').exists())

        response = self.client.post(reverse('paneladmin_zapisz_dom'), {
            'operacja_id': operacja.id,
            'uzytkownik': self.user.id,
            'konto': self.konto.id,
            'tytul': 'Internet Premium',
            'kwota': '99.00',
            'data': '2026-03-05',
            'typ_operacji': self.typ.id,
            'kategoria': self.kategoria.id,
            'opis': 'zmiana',
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(SignificantDatabaseChange.objects.filter(model_name='Operacja', object_pk=str(operacja.id), operation='UPDATE').exists())

    def test_audit_page_available(self):
        response = self.client.get(reverse('paneladmin_audit'))
        self.assertEqual(response.status_code, 200)

    @override_settings(DEMON_STATUS_DIR=Path('/tmp/test-daemon-statuses'))
    def test_daemon_disable_updates_status_file(self):
        status_dir = Path('/tmp/test-daemon-statuses')
        status_dir.mkdir(parents=True, exist_ok=True)
        try:
            with patch('paneladmin.utils._run_systemctl', return_value=(False, 'brak systemctl')):
                response = self.client.post(reverse('paneladmin_demon_action', args=['dom', 'disable']))
            self.assertEqual(response.status_code, 302)
            payload = (status_dir / 'import_watchd_dom.json').read_text(encoding='utf-8')
            self.assertIn('disabled', payload)
        finally:
            for child in status_dir.glob('*'):
                child.unlink()
            status_dir.rmdir()

    @override_settings(DEMON_STATUS_DIR=Path('/tmp/test-daemon-statuses-2'))
    def test_daemon_reset_updates_status_file(self):
        status_dir = Path('/tmp/test-daemon-statuses-2')
        status_dir.mkdir(parents=True, exist_ok=True)
        try:
            with patch('paneladmin.utils._run_systemctl', return_value=(False, 'brak systemctl')):
                response = self.client.post(reverse('paneladmin_demon_action', args=['firma', 'reset']))
            self.assertEqual(response.status_code, 302)
            payload = (status_dir / 'import_watchd_firma.json').read_text(encoding='utf-8')
            self.assertIn('reset', payload)
        finally:
            for child in status_dir.glob('*'):
                child.unlink()
            status_dir.rmdir()



class PanelAdminRolePermissionTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.auditor = User.objects.create_user(username='audytor_panel', password='x')
        UserRole.objects.update_or_create(user=self.auditor, defaults={'role': UserRole.ROLE_AUDYTOR})
        self.client = Client()
        self.client.login(username='audytor_panel', password='x')

    def test_auditor_can_view_admin_dashboard(self):
        response = self.client.get(reverse('paneladmin_dashboard'))
        self.assertEqual(response.status_code, 200)

    def test_auditor_cannot_modify_daemon_state(self):
        response = self.client.post(reverse('paneladmin_demon_action', args=['dom', 'disable']))
        self.assertEqual(response.status_code, 403)
