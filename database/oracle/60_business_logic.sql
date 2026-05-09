-- Procedury wywoływane bezpośrednio z aplikacji Django.

CREATE OR REPLACE PROCEDURE finanse_generuj_raport_miesieczny(
  p_user_id IN NUMBER,
  p_rok     IN NUMBER,
  p_miesiac IN NUMBER
) AS
  v_przychody NUMBER := 0;
  v_wydatki   NUMBER := 0;
  v_saldo     NUMBER := 0;
BEGIN
  SELECT NVL(SUM(CASE WHEN LOWER(t.nazwa) = 'przychod' THEN o.kwota ELSE 0 END), 0),
         NVL(SUM(CASE WHEN LOWER(t.nazwa) <> 'przychod' THEN o.kwota ELSE 0 END), 0)
    INTO v_przychody, v_wydatki
    FROM FINANSE_OPERACJA o
    JOIN FINANSE_TYPOPERACJI t ON t.ID = o.TYP_OPERACJI_ID
   WHERE o.UZYTKOWNIK_ID = p_user_id
     AND EXTRACT(YEAR FROM o.DATA) = p_rok
     AND EXTRACT(MONTH FROM o.DATA) = p_miesiac;

  v_saldo := v_przychody - v_wydatki;

  MERGE INTO FINANSE_RAPORTMIESIECZNY r
  USING (
    SELECT p_user_id AS UZYTKOWNIK_ID, p_rok AS ROK, p_miesiac AS MIESIAC FROM dual
  ) src
  ON (r.UZYTKOWNIK_ID = src.UZYTKOWNIK_ID AND r.ROK = src.ROK AND r.MIESIAC = src.MIESIAC)
  WHEN MATCHED THEN
    UPDATE SET
      r.SUMA_PRZYCHODOW = v_przychody,
      r.SUMA_WYDATKOW = v_wydatki,
      r.SALDO = v_saldo,
      r.WYGENEROWANO_O = SYSTIMESTAMP
  WHEN NOT MATCHED THEN
    INSERT (ID, UZYTKOWNIK_ID, ROK, MIESIAC, SUMA_PRZYCHODOW, SUMA_WYDATKOW, SALDO, WYGENEROWANO_O)
    VALUES (DEFAULT, p_user_id, p_rok, p_miesiac, v_przychody, v_wydatki, v_saldo, SYSTIMESTAMP);
END;
/

CREATE OR REPLACE PROCEDURE firma_przelicz_jpk_deklaracja(
  p_user_id IN NUMBER,
  p_rok     IN NUMBER,
  p_miesiac IN NUMBER
) AS
  v_p19 NUMBER := 0;
  v_p20 NUMBER := 0;
BEGIN
  SELECT NVL(SUM(KWOTA_NETTO), 0), NVL(SUM(KWOTA_VAT), 0)
    INTO v_p19, v_p20
    FROM FIRMA_FAKTURAKOSZTOWA
   WHERE USER_ID = p_user_id
     AND EXTRACT(YEAR FROM DATA_ZAKUPU) = p_rok
     AND NVL(MIESIAC_JPK, EXTRACT(MONTH FROM DATA_ZAKUPU)) = p_miesiac;

  MERGE INTO FIRMA_JPKDEKLARACJA d
  USING (
    SELECT p_user_id AS USER_ID, p_rok AS ROK, p_miesiac AS MIESIAC FROM dual
  ) src
  ON (d.USER_ID = src.USER_ID AND d.ROK = src.ROK AND d.MIESIAC = src.MIESIAC)
  WHEN MATCHED THEN
    UPDATE SET
      d.P_17 = 0,
      d.P_18 = 0,
      d.P_19 = v_p19,
      d.P_20 = v_p20,
      d.P_43_KOREKTA = 0,
      d.P_44_KOREKTA = 0,
      d.P_45_KOREKTA = 0,
      d.P_46_KOREKTA = 0,
      d.P_51 = 0,
      d.P_68 = 1,
      d.P_ORDZU = 0,
      d.UZASADNIENIE = 'Automatyczne przeliczenie deklaracji na podstawie faktur kosztowych.'
  WHEN NOT MATCHED THEN
    INSERT (ID, USER_ID, ROK, MIESIAC, P_17, P_18, P_19, P_20, P_43_KOREKTA, P_44_KOREKTA, P_45_KOREKTA, P_46_KOREKTA, P_51, P_68, P_ORDZU, UZASADNIENIE)
    VALUES (DEFAULT, p_user_id, p_rok, p_miesiac, 0, 0, v_p19, v_p20, 0, 0, 0, 0, 0, 1, 0, 'Automatyczne przeliczenie deklaracji na podstawie faktur kosztowych.');
END;
/
