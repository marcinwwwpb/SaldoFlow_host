# Naprawa panelu administratora

## Co było problemem
Panel administratora budował ciężki, wspólny kontekst na każdej podstronie. Przy większym seedzie oznaczało to:
- pobieranie zbyt dużej liczby danych naraz,
- ładowanie formularzy z pełnymi słownikami wszystkich użytkowników, kont i kontrahentów,
- wykonywanie kosztownych zapytań także tam, gdzie nie były potrzebne.

## Co zostało zmienione
- rozdzielenie selektorów na osobne konteksty dla dashboardu, użytkowników, danych, audytu i demonów,
- paginacja listy użytkowników,
- zawężenie formularzy danych do wybranego użytkownika,
- brak ładowania pełnych słowników kont i kontrahentów bez wybranego użytkownika,
- pozostawienie wyglądu panelu bez istotnych zmian wizualnych.

## Efekt
Panel admina otwiera się stabilnie także przy większych zestawach danych demonstracyjnych i nadal zachowuje pełną funkcjonalność administracyjną.
