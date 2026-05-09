from __future__ import annotations

import json
import os
from typing import Any

import oracledb

from django.apps import apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.db.models import BooleanField, JSONField


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default)


def oracle_dsn() -> str:
    explicit = env("ORACLE_DSN")
    if explicit:
        return explicit

    host = env("ORACLE_HOST", "127.0.0.1")
    port = env("ORACLE_PORT", "1521")
    service = env("ORACLE_SERVICE_NAME", "FREEPDB1")
    return f"{host}:{port}/{service}"


def read_lob(value: Any) -> Any:
    if hasattr(value, "read"):
        return value.read()
    return value


class Command(BaseCommand):
    help = "Importuje dane z Oracle do aktualnej bazy Django, np. PostgreSQL na Railway."

    MODELS_IN_ORDER = [
        # Django auth
        ("auth", "User"),
        ("auth", "Group"),

        # słowniki
        ("finanse", "TypOperacji"),
        ("finanse", "Kategoria"),
        ("finanse", "Tag"),

        # dane domowe
        ("finanse", "KontoDomowe"),
        ("finanse", "CelOszczednosciowy"),
        ("finanse", "RaportMiesieczny"),
        ("finanse", "Operacja"),

        # dane firmowe
        ("firma", "UstawieniaFirmy"),
        ("firma", "Kontrahent"),
        ("firma", "FakturaSprzedazy"),
        ("firma", "FakturaKosztowa"),
        ("firma", "JPKDeklaracja"),
        ("firma", "ImportDemona"),

        # panel admina / role / audyt
        ("paneladmin", "UserRole"),
        ("paneladmin", "AdminAuditLog"),
        ("paneladmin", "SignificantDatabaseChange"),
        ("paneladmin", "OperacjaArchiwum"),
        ("paneladmin", "FakturaKosztowaArchiwum"),

        # konta
        ("accounts", "EmailVerification"),

        # logi demona
        ("finanse", "DemonLog"),
    ]

    def add_arguments(self, parser):
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Czyści docelowe tabele przed importem. Zalecane przy pierwszym imporcie na świeżą bazę.",
        )
        parser.add_argument(
            "--no-m2m",
            action="store_true",
            help="Nie importuje tabel many-to-many, np. tagów operacji i grup użytkowników.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Liczba rekordów pobieranych z Oracle w jednej paczce.",
        )

    def handle(self, *args, **options):
        self.batch_size = options["batch_size"]
        self.no_m2m = options["no_m2m"]

        oracle_user = env("ORACLE_USER")
        oracle_password = env("ORACLE_PASSWORD")
        dsn = oracle_dsn()

        if not oracle_user or not oracle_password:
            raise CommandError(
                "Brakuje ORACLE_USER albo ORACLE_PASSWORD w zmiennych środowiskowych."
            )

        self.stdout.write(f"Łączę z Oracle: {dsn} jako {oracle_user}")

        try:
            self.oracle_conn = oracledb.connect(
                user=oracle_user,
                password=oracle_password,
                dsn=dsn,
            )
        except Exception as exc:
            raise CommandError(f"Nie mogę połączyć się z Oracle: {exc}") from exc

        try:
            with transaction.atomic():
                if options["replace"]:
                    self.clear_target_tables()

                for app_label, model_name in self.MODELS_IN_ORDER:
                    model = apps.get_model(app_label, model_name)
                    self.copy_model(model)

                if not self.no_m2m:
                    self.copy_many_to_many_tables()

                self.reset_sequences()

        finally:
            self.oracle_conn.close()

        self.stdout.write(self.style.SUCCESS("Import z Oracle zakończony."))

    def clear_target_tables(self):
        tables = []

        for app_label, model_name in reversed(self.MODELS_IN_ORDER):
            model = apps.get_model(app_label, model_name)
            tables.append(model._meta.db_table)

        if not self.no_m2m:
            tables.extend(self.m2m_tables())

        # Usuwamy duplikaty z zachowaniem kolejności
        seen = set()
        tables = [t for t in tables if not (t in seen or seen.add(t))]

        quoted = ", ".join(connection.ops.quote_name(t) for t in tables)

        self.stdout.write("Czyszczę docelowe tabele...")
        with connection.cursor() as cursor:
            if connection.vendor == "postgresql":
                cursor.execute(f"TRUNCATE {quoted} RESTART IDENTITY CASCADE")
            else:
                for table in tables:
                    cursor.execute(f"DELETE FROM {connection.ops.quote_name(table)}")

    def model_fields(self, model):
        return [
            f for f in model._meta.concrete_fields
            if not f.many_to_many and not f.one_to_many
        ]

    def source_table_candidates(self, table_name: str):
        return [
            table_name.upper(),
            table_name,
            f'"{table_name}"',
            f'"{table_name.upper()}"',
        ]

    def source_column_candidates(self, column_name: str):
        return [
            column_name.upper(),
            column_name,
            f'"{column_name}"',
            f'"{column_name.upper()}"',
        ]

    def normalize_value(self, field, value):
        value = read_lob(value)

        if value is None:
            return None

        if isinstance(field, BooleanField):
            return bool(value)

        if isinstance(field, JSONField):
            if isinstance(value, (dict, list)):
                return json.dumps(value)
            return value

        return value

    def copy_model(self, model):
        table = model._meta.db_table
        fields = self.model_fields(model)

        target_columns = [f.column for f in fields]
        source_columns = [f.column.upper() for f in fields]

        source_select_cols = ", ".join(source_columns)
        source_table = table.upper()

        rows_total = 0

        try:
            source_cursor = self.oracle_conn.cursor()
            source_cursor.execute(f"SELECT {source_select_cols} FROM {source_table}")
        except Exception as exc:
            self.stdout.write(self.style.WARNING(
                f"Pominięto {table}: nie mogę odczytać z Oracle ({exc})"
            ))
            return

        quoted_target_table = connection.ops.quote_name(table)
        quoted_target_cols = ", ".join(connection.ops.quote_name(c) for c in target_columns)
        placeholders = ", ".join(["%s"] * len(target_columns))

        insert_sql = (
            f"INSERT INTO {quoted_target_table} "
            f"({quoted_target_cols}) VALUES ({placeholders})"
        )

        with connection.cursor() as target_cursor:
            while True:
                rows = source_cursor.fetchmany(self.batch_size)
                if not rows:
                    break

                prepared = []
                for row in rows:
                    prepared.append([
                        self.normalize_value(field, value)
                        for field, value in zip(fields, row)
                    ])

                target_cursor.executemany(insert_sql, prepared)
                rows_total += len(prepared)

        source_cursor.close()

        self.stdout.write(self.style.SUCCESS(
            f"{table}: zaimportowano {rows_total} rekordów"
        ))

    def m2m_tables(self):
        User = get_user_model()

        tables = [
            User.groups.through._meta.db_table,
            User.user_permissions.through._meta.db_table,
            Group.permissions.through._meta.db_table,
        ]

        try:
            Operacja = apps.get_model("finanse", "Operacja")
            tables.append(Operacja.tagi.through._meta.db_table)
        except LookupError:
            pass

        return tables

    def copy_many_to_many_tables(self):
        self.stdout.write("Importuję tabele many-to-many...")

        for table in self.m2m_tables():
            self.copy_raw_table(table)

    def copy_raw_table(self, table: str):
        source_table = table.upper()

        try:
            source_cursor = self.oracle_conn.cursor()
            source_cursor.execute(
                """
                SELECT COLUMN_NAME
                FROM USER_TAB_COLUMNS
                WHERE TABLE_NAME = :table_name
                ORDER BY COLUMN_ID
                """,
                table_name=source_table,
            )
            columns = [row[0] for row in source_cursor.fetchall()]
        except Exception as exc:
            self.stdout.write(self.style.WARNING(
                f"Pominięto {table}: nie mogę odczytać kolumn z Oracle ({exc})"
            ))
            return

        if not columns:
            self.stdout.write(self.style.WARNING(
                f"Pominięto {table}: brak tabeli w Oracle"
            ))
            return

        source_cols = ", ".join(columns)
        target_cols = [c.lower() for c in columns]

        try:
            source_cursor.execute(f"SELECT {source_cols} FROM {source_table}")
        except Exception as exc:
            self.stdout.write(self.style.WARNING(
                f"Pominięto {table}: nie mogę odczytać danych ({exc})"
            ))
            return

        quoted_target_table = connection.ops.quote_name(table)
        quoted_target_cols = ", ".join(connection.ops.quote_name(c) for c in target_cols)
        placeholders = ", ".join(["%s"] * len(target_cols))

        insert_sql = (
            f"INSERT INTO {quoted_target_table} "
            f"({quoted_target_cols}) VALUES ({placeholders})"
        )

        rows_total = 0

        with connection.cursor() as target_cursor:
            while True:
                rows = source_cursor.fetchmany(self.batch_size)
                if not rows:
                    break

                prepared = [
                    [read_lob(value) for value in row]
                    for row in rows
                ]

                target_cursor.executemany(insert_sql, prepared)
                rows_total += len(prepared)

        source_cursor.close()

        self.stdout.write(self.style.SUCCESS(
            f"{table}: zaimportowano {rows_total} rekordów"
        ))

    def reset_sequences(self):
        self.stdout.write("Resetuję sekwencje PostgreSQL...")

        apps_to_reset = [
            "auth",
            "accounts",
            "finanse",
            "firma",
            "paneladmin",
        ]

        sql = []

        try:
            from io import StringIO

            out = StringIO()
            call_command("sqlsequencereset", *apps_to_reset, stdout=out)
            sql_text = out.getvalue().strip()
            if sql_text:
                sql = [statement.strip() for statement in sql_text.split(";") if statement.strip()]
        except Exception as exc:
            self.stdout.write(self.style.WARNING(
                f"Nie udało się wygenerować resetu sekwencji: {exc}"
            ))
            return

        if not sql:
            return

        with connection.cursor() as cursor:
            for statement in sql:
                cursor.execute(statement)

        self.stdout.write(self.style.SUCCESS("Sekwencje zresetowane."))
