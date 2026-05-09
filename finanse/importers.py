from __future__ import annotations

import csv
import hashlib
from decimal import Decimal, InvalidOperation
from pathlib import Path

from django.contrib.auth import get_user_model
from django.db import transaction

from .models import DemonLog, Kategoria, Operacja, Tag, TypOperacji
from paneladmin.utils import audit_log


def log_demon_event(*, modul, poziom, wiadomosc, nazwa_pliku="", sciezka="", checksum_sha256=""):
    DemonLog.objects.create(
        modul=modul,
        poziom=poziom,
        wiadomosc=wiadomosc,
        nazwa_pliku=nazwa_pliku,
        sciezka=sciezka,
        checksum_sha256=checksum_sha256,
    )


def import_operacje_csv_for_user(*, user, fileobj, source_name: str, source_path: str = ""):
    decoded = fileobj.read().decode("utf-8-sig").splitlines()
    reader = csv.reader(decoded)
    next(reader, None)

    dodane = 0
    bledy = []

    with transaction.atomic():
        for idx, row in enumerate(reader, start=2):
            if len(row) < 6:
                continue

            data_str = str(row[0]).strip()
            tytul = str(row[1]).strip()
            kwota_str = str(row[2]).strip().replace(",", ".")
            typ_nazwa = str(row[3]).strip() or "Wydatek"
            kategoria_nazwa = str(row[4]).strip() or "Inne"
            tagi_csv = str(row[5]).strip() if len(row) > 5 else ""
            opis = str(row[6]).strip() if len(row) > 6 else ""

            if not data_str or not tytul or not kwota_str:
                continue

            try:
                kwota = Decimal(kwota_str)
                typ_operacji, _ = TypOperacji.objects.get_or_create(nazwa=typ_nazwa)
                kategoria, _ = Kategoria.objects.get_or_create(nazwa=kategoria_nazwa)
                existing = Operacja.objects.filter(uzytkownik=user, data=data_str, tytul=tytul, kwota=kwota, typ_operacji=typ_operacji, kategoria=kategoria).first()
                if existing:
                    bledy.append(f"Wiersz {idx}: potencjalny duplikat operacji — rekord już istnieje")
                    audit_log(actor=user, module="DOM", entity_type="Operacja", entity_id=existing.id, action="IMPORT_SKIP", payload={"source_name": source_name, "row": idx, "title": tytul})
                    continue
                operacja = Operacja.objects.create(
                    data=data_str,
                    tytul=tytul,
                    kwota=kwota,
                    typ_operacji=typ_operacji,
                    kategoria=kategoria,
                    opis=opis,
                    uzytkownik=user,
                )
                if tagi_csv:
                    for nazwa_tagu in [t.strip() for t in tagi_csv.split(",") if t.strip()]:
                        tag, _ = Tag.objects.get_or_create(nazwa=nazwa_tagu)
                        operacja.tagi.add(tag)
                dodane += 1
            except (InvalidOperation, ValueError) as exc:
                bledy.append(f"Wiersz {idx}: {exc}")

    return {
        "dodane": dodane,
        "bledy": bledy,
        "source_name": source_name,
        "source_path": source_path,
    }


def import_operacje_csv_from_path(*, username: str, path: str):
    User = get_user_model()
    user = User.objects.get(username=username)
    src = Path(path)
    checksum = hashlib.sha256(src.read_bytes()).hexdigest() if src.exists() and src.is_file() else ""
    log_demon_event(
        modul=DemonLog.MODUL_DOM,
        poziom=DemonLog.POZIOM_INFO,
        wiadomosc="Rozpoczęto import pliku budżetu domowego.",
        nazwa_pliku=src.name,
        sciezka=str(src),
        checksum_sha256=checksum,
    )
    try:
        with src.open("rb") as f:
            summary = import_operacje_csv_for_user(user=user, fileobj=f, source_name=src.name, source_path=str(src))
        log_demon_event(
            modul=DemonLog.MODUL_DOM,
            poziom=DemonLog.POZIOM_WARNING if summary["bledy"] else DemonLog.POZIOM_INFO,
            wiadomosc=(
                f"Import domowy zakończony. Dodano {summary['dodane']} rekordów, błędów {len(summary['bledy'])}."
            ),
            nazwa_pliku=src.name,
            sciezka=str(src),
            checksum_sha256=checksum,
        )
        return summary
    except Exception as exc:
        log_demon_event(
            modul=DemonLog.MODUL_DOM,
            poziom=DemonLog.POZIOM_ERROR,
            wiadomosc=f"Import domowy zakończony błędem: {exc}",
            nazwa_pliku=src.name,
            sciezka=str(src),
            checksum_sha256=checksum,
        )
        raise
