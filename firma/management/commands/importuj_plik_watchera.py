from django.core.management.base import BaseCommand, CommandError

from firma.importers import import_koszty_excel_from_path


class Command(BaseCommand):
    help = "Importuje plik kosztów wskazany przez demona monitorującego katalog."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True, help="Login użytkownika Django, do którego przypisać import.")
        parser.add_argument("--path", required=True, help="Pełna ścieżka do pliku Excel wykrytego przez demona.")

    def handle(self, *args, **options):
        try:
            summary = import_koszty_excel_from_path(username=options["username"], path=options["path"])
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(
            f"Import zakończony. Dodano: {summary['dodane']}, błędy: {len(summary['bledy'])}, plik: {summary['source_name']}"
        ))
