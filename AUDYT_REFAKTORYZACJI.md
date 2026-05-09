# Audyt i zakres przebudowy

## Co było problemem w oryginalnej paczce
- repo zawierało artefakty środowiska (`.venv`, `.venv_test`),
- dołączona była lokalna baza SQLite i lokalny `.env`,
- były obecne pliki cache (`__pycache__`, `.pyc`) i skompilowany binarny demon,
- konfiguracja projektu była skupiona w jednym module `budzet/settings.py`,
- projekt deklarował Oracle, ale paczka była realnie przygotowana także pod SQLite i PostgreSQL bez wyraźnego rozdzielenia środowisk,
- część logiki domenowej była rozproszona między widoki i pomocnicze pliki.

## Co zostało zrobione
- przebudowano projekt do nowej struktury z `config/` i `core/`,
- Oracle ustawiono jako domyślny kierunek konfiguracji (`DB_ENGINE=oracle` w `.env.example`),
- zostawiono możliwość użycia SQLite tylko do lokalnego developmentu i testów,
- zachowano moduły funkcjonalne: `accounts`, `finanse`, `firma`, `paneladmin`, `demon`,
- zachowano istniejące szablony HTML i assety CSS/IMG, aby utrzymać wygląd aplikacji,
- wygenerowano czyste migracje początkowe na bazie aktualnych modeli,
- usunięto zbędne pliki z paczki wynikowej,
- dodano czystą dokumentację uruchomienia i plik `.gitignore`.

## Zachowane funkcjonalności
- logowanie i rejestracja z aktywacją e-mail,
- wybór modułu po zalogowaniu,
- budżet domowy: operacje, konta, cele, raporty, import/eksport,
- budżet firmowy: kontrahenci, sprzedaż, koszty, import Excela, JPK, rozliczenia,
- panel administratora z audytem i sterowaniem demonem,
- integracja CEIDG,
- obsługa watchera/importu plików.

## Co zostało poprawione architektonicznie
- wydzielona konfiguracja projektu (`config/settings/base.py`, `dev.py`, `test.py`),
- wspólne widoki i context processor przeniesione do `core/`,
- brak sekretów i danych lokalnych w repo,
- gotowa paczka pod wdrożenie z Oracle Free w Docker Compose,
- skrypty Oracle odseparowane do `database/oracle/`.

## Walidacja
- `DB_ENGINE=sqlite python manage.py check` → OK,
- `DB_ENGINE=sqlite python manage.py migrate` → OK,
- testy aplikacji: **14/14 OK**.

## Dalsze kroki, które nadal warto zrobić
- rozbić największe widoki (`finanse/views.py`, `firma/views.py`, `paneladmin/views.py`) na selektory i serwisy,
- zamienić część podsumowań liczonych w Pythonie na agregacje SQL (`annotate`, `Sum`, `Count`),
- dodać paginację do list sprzedaży, kosztów i kontrahentów,
- rozszerzyć testy integracyjne pod Oracle,
- rozważyć przejście na własny model użytkownika, jeśli projekt będzie dalej rozwijany.
