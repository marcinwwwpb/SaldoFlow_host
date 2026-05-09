# Dane demonstracyjne — SaldoFlow

## Konta
- superadmin: `marcin / danzel12`
- księgowy: `ksiegowy / ksiegowy123`
- audytor: `audytor / audytor123`
- użytkownik testowy: `test / test`
- konta dodatkowe: `user01` ... `user17`
- hasło dla `user01` ... `user17`: `DemoUser123!`

## Zakres danych
- okres danych: od stycznia 2020 do czerwca 2026
- po 1000 operacji budżetu domowego na konto z danymi
- dane firmowe: sprzedaż, koszty, importy demona i deklaracje JPK
- konto `marcin` nie ma własnych danych firmowych — służy do administracji i testów panelu
- dane użytkowników są celowo zróżnicowane: inne kategorie, kwoty, kontrahenci, cykliczność, poziomy VAT i obciążenie modułów

## Jak odtworzyć seed
Oracle:
```bash
./seed_test_data_oracle.sh --force
```

SQLite:
```bash
./seed_test_data_linux.sh --sqlite --force
```
