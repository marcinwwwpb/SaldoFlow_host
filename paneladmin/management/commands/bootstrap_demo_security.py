from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from paneladmin.models import UserRole


class Command(BaseCommand):
    help = "Tworzy konta pokazowe i role bezpieczeństwa dla projektu SaldoFlow."

    def handle(self, *args, **options):
        User = get_user_model()

        demo_accounts = [
            {
                'username': 'marcin',
                'password': 'danzel12',
                'email': 'marcin@saldoflow.local',
                'first_name': 'Marcin',
                'last_name': 'Administrator',
                'is_staff': True,
                'is_superuser': True,
                'role': UserRole.ROLE_SUPERADMIN,
                'notes': 'Konto superadministratora projektu.',
            },
            {
                'username': 'ksiegowy',
                'password': 'ksiegowy123',
                'email': 'ksiegowy@saldoflow.local',
                'first_name': 'Karolina',
                'last_name': 'Księgowa',
                'is_staff': False,
                'is_superuser': False,
                'role': UserRole.ROLE_KSIEGOWY,
                'notes': 'Rola operacyjna: może wprowadzać i importować dane.',
            },
            {
                'username': 'audytor',
                'password': 'audytor123',
                'email': 'audytor@saldoflow.local',
                'first_name': 'Adam',
                'last_name': 'Audytor',
                'is_staff': False,
                'is_superuser': False,
                'role': UserRole.ROLE_AUDYTOR,
                'notes': 'Rola tylko do odczytu: audyt i raporty.',
            },
            {
                'username': 'test',
                'password': 'test',
                'email': 'test@saldoflow.local',
                'first_name': 'Test',
                'last_name': 'Pokazowy',
                'is_staff': False,
                'is_superuser': False,
                'role': UserRole.ROLE_UZYTKOWNIK,
                'notes': 'Konto standardowego użytkownika demonstracyjnego.',
            },
        ]

        for spec in demo_accounts:
            user, _ = User.objects.get_or_create(
                username=spec['username'],
                defaults={
                    'email': spec['email'],
                    'is_active': True,
                    'is_staff': spec['is_staff'],
                    'is_superuser': spec['is_superuser'],
                    'first_name': spec['first_name'],
                    'last_name': spec['last_name'],
                },
            )
            user.is_active = True
            user.is_staff = spec['is_staff']
            user.is_superuser = spec['is_superuser']
            user.email = spec['email']
            user.first_name = spec['first_name']
            user.last_name = spec['last_name']
            user.set_password(spec['password'])
            user.save()
            UserRole.objects.update_or_create(
                user=user,
                defaults={'role': spec['role'], 'notes': spec['notes']},
            )
            self.stdout.write(self.style.SUCCESS(f"Konto {spec['username']} / {spec['password']} jest gotowe."))
