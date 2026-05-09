# Oracle w projekcie SaldoFlow

Projekt jest przygotowany do pracy z bazą Oracle jako głównym silnikiem danych.

## Wariant A — pełny start lokalny w Dockerze
Najprostsza ścieżka:
```bash
chmod +x *.sh scripts/*.sh
./run_all_oracle_linux.sh start
```

To polecenie:
1. uruchamia kontener Oracle Free,
2. startuje aplikację Django,
3. uruchamia demona monitorującego katalog,
4. stosuje skrypty Oracle: role, audyt, VPD, procedury i triggery.

Status:
```bash
./run_all_oracle_linux.sh status
```

Logi:
```bash
./run_all_oracle_linux.sh logs
```

Zatrzymanie:
```bash
./run_all_oracle_linux.sh stop
```

## Wariant B — zewnętrzna instancja Oracle
```bash
./run_all_oracle_linux.sh start   --oracle-external   --oracle-dsn 10.10.10.25:1521/FREEPDB1   --oracle-user SALDOFLOW_APP   --oracle-password 'TwojeHaslo'
```

Jeżeli chcesz także automatycznie zastosować skrypty bezpieczeństwa Oracle na zewnętrznej bazie, użyj dodatkowo administratora Oracle:
```bash
./bootstrap_oracle_security.sh   --oracle-external   --oracle-dsn 10.10.10.25:1521/FREEPDB1   --oracle-user SALDOFLOW_APP   --oracle-password 'TwojeHaslo'   --admin-user SYSTEM   --admin-password 'HasloAdministratora'
```

## Dane połączeniowe używane domyślnie lokalnie
- host: `127.0.0.1`
- port: `1521`
- service: `FREEPDB1`
- schemat aplikacji: `SALDOFLOW_APP`
- hasło schematu aplikacji: `change-me`

## Co robi bootstrap bezpieczeństwa Oracle
- tworzy / aktualizuje profile i role Oracle,
- przygotowuje konta techniczne,
- tworzy kontekst bezpieczeństwa sesji,
- tworzy tabelę audytu zmian,
- zakłada polityki VPD dla danych użytkowników,
- zakłada przykładowe triggery audytowe,
- tworzy procedury wykorzystywane przez aplikację.

## Główne role aplikacyjne
- **Administrator / superadministrator** — zarządzanie użytkownikami, danymi i demonem
- **Księgowy / operator** — wprowadzanie danych finansowych i firmowych
- **Audytor** — tylko odczyt, raporty i logi

## Uwaga praktyczna
SQLite zostawiłem jako tryb pomocniczy dla szybkich testów developerskich, ale wersja projektowa i dokumentacyjna jest przygotowana pod **Oracle**.
