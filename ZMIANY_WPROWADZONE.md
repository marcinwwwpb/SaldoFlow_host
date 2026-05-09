# Zmiany wprowadzone w wersji Oracle

## Najważniejsze poprawki funkcjonalne
- naprawiono martwe linki w centrum modułów i panelu administracyjnym,
- uporządkowano nawigację w budżecie domowym i firmowym,
- rozwiązano problem rozwijanego importu/eksportu w budżecie domowym przez osobne centrum importu i eksportu,
- uruchomiono przycisk pobierania danych z CEIDG także w trybie demonstracyjnym,
- usunięto starą nazwę aplikacji z dopiskiem `(UNIX)`.

## Oracle i bezpieczeństwo
- przygotowano projekt z Oracle jako docelową bazą danych,
- dodano skrypty Oracle: role, profile haseł, kontekst bezpieczeństwa, VPD, audyt, triggery i procedury,
- dodano bootstrap bezpieczeństwa Oracle uruchamiany osobnym skryptem,
- poprawiono domyślny użytkownik Oracle na `SALDOFLOW_APP`,
- dodano dodatkowe ustawienia bezpieczeństwa sesji i ciasteczek.

## Role i uprawnienia
- wprowadzono spójne role aplikacyjne z różnymi poziomami dostępu,
- administrator może zarządzać danymi, użytkownikami i demonem,
- księgowy może pracować na danych finansowych,
- audytor ma dostęp tylko do odczytu, raportów i logów.

## Demon i uruchamianie środowiska
- zachowano działający demon monitorujący katalog importów,
- dodano skrypt `run_all_oracle_linux.sh`, który uruchamia bazę Oracle, aplikację i demona,
- dodano skrypt `bootstrap_oracle_security.sh` do zastosowania zabezpieczeń Oracle,
- pozostawiono tryb SQLite wyłącznie jako pomocniczy tryb developerski.

## Dane testowe i dokumentacja
- dane testowe są zróżnicowane między użytkownikami,
- dodano konta demonstracyjne: superadmin, księgowy, audytor i użytkownik testowy,
- przygotowano dokument `ANALIZA_BIZNESOWA_ORACLE.md` zgodny z wymaganiami przedmiotowymi,
- zaktualizowano README i instrukcje uruchomienia.

## Walidacja
- testy Django: 27/27 OK,
- `manage.py check`: OK,
- demon C kompiluje się poprawnie,
- skrypty bash przechodzą kontrolę składni.
