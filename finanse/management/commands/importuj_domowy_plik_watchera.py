from django.core.management.base import BaseCommand, CommandError

from finanse.importers import import_operacje_csv_from_path


class Command(BaseCommand):
    help = "Importuje plik CSV budżetu domowego wskazany przez demona monitorującego katalog."

    def add_arguments(self, parser):
        parser.add_argument("--username", required=True, help="Login użytkownika Django, do którego przypisać import.")
        parser.add_argument("--path", required=True, help="Pełna ścieżka do pliku CSV wykrytego przez demona.")

    def handle(self, *args, **options):
        try:
            summary = import_operacje_csv_from_path(username=options["username"], path=options["path"])
        except Exception as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(self.style.SUCCESS(
            f"Import domowy zakończony. Dodano: {summary['dodane']}, błędy: {len(summary['bledy'])}, plik: {summary['source_name']}"
        ))
