# Uruchomienie demonstracyjne

Ta paczka jest przygotowana do prezentacji projektu z dużą bazą danych pokazowych i rolami użytkowników.

## Konta demonstracyjne
- superadmin: `marcin / danzel12`
- księgowy: `ksiegowy / ksiegowy123`
- audytor: `audytor / audytor123`
- użytkownik testowy: `test / test`
- dodatkowe konta z danymi: `user01` ... `user17`

## Co tworzy seed pokazowy
- 20 kont z danymi historycznymi
- po **1000 operacji budżetu domowego** na użytkownika z danymi
- dane firmowe za okres **2020-01 do 2026-06**
- zróżnicowane faktury, kontrahenci, koszty, JPK i operacje domowe

## Linux
Najprościej:
```bash
chmod +x *.sh scripts/*.sh
./run_all_oracle_linux.sh start
```

Tryb pomocniczy SQLite:
```bash
./launcher_linux.sh start --sqlite
```

Odbudowa danych:
```bash
./seed_test_data_oracle.sh --force
```

## Adresy po starcie
- strona główna: `http://127.0.0.1:8000/`
- wybór modułu: `http://127.0.0.1:8000/moduly/`
- panel administratora aplikacji: `http://127.0.0.1:8000/panel-admina/`
- Django admin: `http://127.0.0.1:8000/admin/`

## Demon katalogowy
- `runtime/watch/dom` — import budżetu domowego
- `runtime/watch/firma` — import kosztów firmowych
- `runtime/archive/*` — archiwa po imporcie
- `runtime/daemon_status` — heartbeat i stan demonów

## Windows
Projekt nadal zawiera proste skrypty demonstracyjne dla Windows, ale pełna obsługa demona katalogowego jest przewidziana dla Linux/UNIX, bo demon korzysta z API POSIX.
