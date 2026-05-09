# Analiza biznesowa i założenia projektowe — SaldoFlow / Oracle

## 1. Cel projektu
SaldoFlow wspiera dwa obszary biznesowe:
- budżet domowy użytkownika indywidualnego,
- finanse małej firmy prowadzonej przez właściciela lub księgowego.

Projekt ma dodatkowo obsługiwać automatyczny import danych z katalogów monitorowanych przez demona systemowego oraz zapewniać kontrolę bezpieczeństwa i historii zmian w bazie Oracle.

## 2. Główne obszary funkcjonalne
- zarządzanie kontami użytkowników i rolami,
- budżet domowy: konta, operacje, raporty miesięczne, import/export CSV i XML,
- budżet firmowy: ustawienia firmy, kontrahenci, faktury sprzedażowe, faktury kosztowe, deklaracje JPK,
- panel administracyjny aplikacji,
- demon monitorujący katalog importu,
- audyt zmian i historia usuniętych rekordów.

## 3. Lista głównych encji
### Użytkownicy i bezpieczeństwo
- `auth_user` / użytkownik systemu
- `paneladmin_userrole` / rola użytkownika
- `accounts_emailverification` / weryfikacja e-mail
- `paneladmin_adminauditlog` / log administracyjny
- `paneladmin_significantdatabasechange` / historia istotnych zmian

### Budżet domowy
- `finanse_kontodomowe`
- `finanse_typoperacji`
- `finanse_operacja`
- `finanse_celoszczednosciowy`
- `finanse_raportmiesieczny`

### Budżet firmowy
- `firma_ustawieniafirmy`
- `firma_kontrahent`
- `firma_fakturasprzedazy`
- `firma_fakturakosztowa`
- `firma_jpkdeklaracja`
- `firma_importdemona`

### Archiwum i historia biznesowa
- `paneladmin_operacjaarchiwum`
- `paneladmin_fakturakosztowaarchiwum`
- `SF_DB_CHANGE_LOG` (Oracle)
- `SF_KEY_OPERATION_METRIC` (Oracle)

## 4. Rozmiar początkowy i przewidywany przyrost danych
### Rozmiar początkowy dla wersji demonstracyjnej
- 20 użytkowników z danymi
- ok. 20 000 operacji budżetu domowego
- ok. 1 500–2 000 rekordów firmowych (sprzedaż, koszty, JPK, importy)
- logi administracyjne i historia zmian rosnące wraz z użyciem systemu

### Szacowany przyrost miesięczny w środowisku produkcyjnym
- `finanse_operacja`: 1 000 – 50 000 rekordów / miesiąc
- `firma_fakturakosztowa`: 100 – 10 000 rekordów / miesiąc
- `firma_fakturasprzedazy`: 100 – 10 000 rekordów / miesiąc
- `firma_importdemona`: zależne od częstotliwości importów, zwykle 100 – 5 000 rekordów / miesiąc
- `SF_DB_CHANGE_LOG`: przyrost proporcjonalny do liczby modyfikacji krytycznych danych

## 5. Tabele o największym obciążeniu
### Największa liczba rekordów
- `finanse_operacja`
- `firma_fakturakosztowa`
- `firma_fakturasprzedazy`
- `paneladmin_significantdatabasechange`
- `SF_DB_CHANGE_LOG`

### Najczęściej przeszukiwane
- `finanse_operacja` — filtrowanie po użytkowniku, miesiącu, typie operacji
- `firma_fakturakosztowa` — raporty VAT, koszty, JPK
- `firma_fakturasprzedazy` — sprzedaż, przychód, raporty miesięczne
- `firma_kontrahent` — wyszukiwanie po NIP i nazwie
- `firma_importdemona` — monitoring importów i błędów

## 6. Historia zmian i mechanizmy archiwizacji
### Poziom aplikacyjny
- `AdminAuditLog` zapisuje operacje administracyjne,
- `SignificantDatabaseChange` zapisuje istotne zmiany biznesowe,
- archiwa usuniętych rekordów przechowują dane po kasowaniu.

### Poziom Oracle
- `SF_DB_CHANGE_LOG` przechowuje historię zmian z triggerów,
- kontekst sesji (`SF_CTX`) zapisuje, jaki użytkownik aplikacyjny wykonał operację,
- VPD ogranicza zakres danych widocznych dla zwykłych użytkowników.

## 7. Role i uprawnienia / rodzaje użytkowników
Dla projektu przyjęto trzy podstawowe role biznesowe:

### 1. Administrator
Uprawnienia:
- zarządzanie użytkownikami i ich rolami,
- dostęp do panelu administracyjnego,
- podgląd i modyfikacja danych,
- sterowanie demonem,
- dostęp do logów i audytu.

### 2. Księgowy / operator
Uprawnienia:
- dodawanie i edycja operacji budżetu domowego,
- dodawanie i edycja danych firmowych,
- import i eksport danych,
- uruchamianie procedur raportowych i JPK,
- brak możliwości zarządzania rolami i demonem.

### 3. Audytor
Uprawnienia:
- tylko odczyt,
- dostęp do raportów, deklaracji, logów i stanu demonów,
- brak możliwości zapisu, importu, usuwania i sterowania usługami.

Dodatkowo technicznie występuje superadministrator oraz konto techniczne demona.

## 8. Dodatkowe metody zabezpieczeń danych wrażliwych
- polityka haseł Oracle przez profil `SF_APP_PROFILE`,
- role Oracle dla aplikacji, audytu i demona,
- `HttpOnly`, `SameSite`, `Secure` dla ciasteczek sesyjnych,
- ochrona CSRF i X-Frame-Options,
- ograniczanie danych przez VPD / Row-Level Security,
- osobne konto techniczne dla demona,
- audyt operacji modyfikujących dane,
- filtrowanie danych po właścicielu na poziomie ORM i formularzy.

## 9. Wymagane widoki, triggery, funkcje i procedury
### Widoki Oracle
- `SF_V_MONTHLY_DATA_LOAD` — podsumowanie miesięcznego przyrostu najważniejszych danych.

### Funkcje Oracle
- `SF_POLICY_OWNER_USER`
- `SF_POLICY_OWNER_UZYTKOWNIK`

### Procedury Oracle
- `finanse_generuj_raport_miesieczny`
- `firma_przelicz_jpk_deklaracja`
- `SF_SECURITY_PKG.SET_CONTEXT`
- `SF_SECURITY_PKG.CLEAR_CONTEXT`

### Triggery Oracle
- `SF_TRG_AUDIT_FINANSE_OPERACJA`
- `SF_TRG_AUDIT_FIRMA_KOSZT`
- `SF_TRG_AUDIT_FIRMA_JPK`

## 10. Wymagania funkcjonalne
- logowanie i rozróżnianie ról użytkowników,
- dodawanie i przegląd budżetu domowego,
- dodawanie faktur i kontrahentów,
- pobieranie danych firmy po NIP z CEIDG,
- import i eksport danych,
- generowanie raportów miesięcznych,
- obliczanie deklaracji JPK procedurą Oracle,
- monitoring katalogów przez demona,
- podgląd logów i audytu.

## 11. Wymagania niefunkcjonalne
- baza danych Oracle jako docelowy silnik systemu,
- możliwość pracy wielu typów użytkowników,
- odseparowanie uprawnień do odczytu i zapisu,
- pełna ścieżka audytowa dla istotnych zmian,
- możliwość dalszego skalowania liczby operacji i faktur,
- czytelny interfejs z jednoznaczną nawigacją,
- możliwość automatycznego uruchomienia środowiska na Linux.

## 12. Szczegółowe wymagania klienta zaadresowane w projekcie
- Oracle jako główna baza danych,
- trzy podstawowe typy użytkowników z różnymi uprawnieniami,
- zabezpieczenia aplikacyjne i bazodanowe,
- działający demon katalogowy,
- przycisk pobierania danych z CEIDG,
- realistyczne dane testowe,
- poprawiona nawigacja i naprawa martwych linków,
- jeden plik wykonywalny uruchamiający bazę, aplikację i demona.

## 13. Potencjalne trudności
- różnice między SQLite i Oracle w trakcie developmentu,
- konieczność utrzymania zgodności procedur Oracle z modelem Django,
- konfiguracja Oracle na maszynach uczelnianych lub lokalnych,
- większy koszt utrzymania audytu i VPD przy bardzo dużym przyroście danych,
- testowanie demona katalogowego w środowiskach innych niż Linux.

## 14. Rekomendacje projektowe
- w środowisku docelowym używać wyłącznie Oracle,
- wydzielić regularny backup danych i archiwów importu,
- dla produkcji rozważyć serwer aplikacyjny Gunicorn/uWSGI zamiast `runserver`,
- rozważyć indeksy dodatkowe po datach i identyfikatorach właściciela na największych tabelach,
- rozbudować zestaw testów integracyjnych dla uprawnień i nawigacji.
