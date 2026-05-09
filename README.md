# SaldoFlow

SaldoFlow to projekt demonstracyjny do zarządzania budżetem domowym, finansami firmy i importem dokumentów przez demona katalogowego. W tej wersji **główną bazą danych jest Oracle**, a środowisko lokalne może być uruchamiane zarówno na Oracle, jak i pomocniczo na SQLite do szybkich testów developerskich.

## Co zawiera paczka
- Oracle jako docelowa baza danych projektu
- role użytkowników i ograniczenia dostępu w aplikacji
- skrypty Oracle z bezpieczeństwem, audytem, VPD, triggerami i procedurami
- demon monitorujący katalog importów
- launcher Linux uruchamiający bazę, aplikację i demona
- generator realistycznych danych testowych
- konta demonstracyjne z różnymi poziomami uprawnień

## Główne konta demonstracyjne
- superadmin: `marcin / danzel12`
- księgowy: `ksiegowy / ksiegowy123`
- audytor: `audytor / audytor123`
- użytkownik testowy: `test / test`
- dodatkowi użytkownicy: `user01` ... `user17` / hasło `DemoUser123!`

## Najwygodniejszy start na Oracle
```bash
chmod +x *.sh scripts/*.sh
./run_all_oracle_linux.sh start
```

To polecenie:
- uruchamia Oracle w Dockerze,
- startuje aplikację i demona,
- po starcie stosuje skrypty bezpieczeństwa Oracle.

## Start na Oracle zewnętrzne
```bash
./run_all_oracle_linux.sh start   --oracle-external   --oracle-dsn 10.10.10.25:1521/FREEPDB1   --oracle-user SALDOFLOW_APP   --oracle-password 'TwojeHaslo'
```

## Szybki tryb developerski na SQLite
```bash
./launcher_linux.sh start --sqlite
```

## Dokumenty w paczce
- `URUCHOMIENIE_DEMO.md` — szybki start środowiska demo
- `URUCHOMIENIE_ORACLE.md` — uruchomienie i konfiguracja Oracle
- `ANALIZA_BIZNESOWA_ORACLE.md` — dokumentacja projektowa do analizy biznesowej i SBD
- `DANE_DEMO.md` — opis danych pokazowych
- `database/oracle/README.md` — opis skryptów Oracle
