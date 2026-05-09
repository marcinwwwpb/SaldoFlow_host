# SaldoFlow v2 — architektura

Ta wersja zachowuje wygląd i funkcjonalności aplikacji, ale upraszcza kod zaplecza.

## Co zmieniono
- widoki w `finanse`, `firma` i `paneladmin` zostały odchudzone,
- logika odczytu danych została wyniesiona do `selectors.py`,
- logika zapisu/eksportu/importu została wyniesiona do `services.py`,
- dodano `core/db.py` do bezpieczniejszego uruchamiania procedur bazodanowych dla Oracle,
- pozostawiono te same szablony i assety, żeby nie zmieniać warstwy wizualnej.

## Efekt
- łatwiej rozwijać kolejne funkcje bez rozrastania `views.py`,
- łatwiej testować logikę niezależnie od warstwy HTTP,
- projekt jest bardziej przygotowany pod środowisko Oracle-first.
