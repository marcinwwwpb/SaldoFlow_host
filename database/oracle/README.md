Skrypty w tym katalogu przygotowują wdrożenie Oracle dla projektu SaldoFlow.

Kolejność uruchomienia:
1. `00_users_roles.sql` — użytkownicy, profile haseł i role techniczne.
2. `10_security_context.sql` — kontekst sesji ustawiany przez middleware Django.
3. `20_audit_table.sql` — tabela audytowa zmian po stronie Oracle.
4. `30_vpd_policy.sql` — polityki VPD / row-level security dla tabel biznesowych.
5. `40_key_ops_metrics.sql` — metryki obciążenia i widok raportowy największych tabel.
6. `50_trigger_examples.sql` — triggery audytowe.
7. `60_business_logic.sql` — procedury wymagane przez aplikację (`finanse_generuj_raport_miesieczny`, `firma_przelicz_jpk_deklaracja`).

Założenia bezpieczeństwa:
- aplikacja działa w schemacie `SALDOFLOW_APP`,
- demon może działać na osobnym koncie technicznym `SALDOFLOW_DAEMON`,
- audyt i raporty mogą być realizowane z konta `SALDOFLOW_AUDIT`,
- role biznesowe na poziomie aplikacji to: administrator, księgowy/operator i audytor,
- sesja Oracle dostaje `USER_ID` oraz `ROLE_CODE` przez `SF_SECURITY_PKG.SET_CONTEXT`,
- VPD ogranicza dostęp do rekordów użytkownika dla zwykłych kont.

Uwaga praktyczna:
- skrypt `00_users_roles.sql` uruchamiaj jako użytkownik z uprawnieniami administracyjnymi Oracle,
- pozostałe skrypty uruchamiaj w schemacie aplikacji `SALDOFLOW_APP`.
