from __future__ import annotations

from collections.abc import Sequence

from django.db import connection


class StoredProcedureError(RuntimeError):
    """Raised when a database procedure cannot be executed."""


def call_stored_procedure(name: str, params: Sequence[object] | None = None) -> None:
    """Execute a stored procedure in a way that works for Oracle-first deployments.

    Oracle uses ``cursor.callproc`` while PostgreSQL-compatible engines often expose
    stored procedures through ``CALL ...`` SQL. SQLite is unsupported here on purpose,
    because the procedure-based workflow is meant for production databases.
    """
    proc_params = list(params or [])

    with connection.cursor() as cursor:
        if connection.vendor == 'oracle':
            cursor.callproc(name, proc_params)
            return

        if connection.vendor in {'postgresql', 'mysql'}:
            placeholders = ', '.join(['%s'] * len(proc_params))
            sql = f'CALL {name}({placeholders})' if placeholders else f'CALL {name}()'
            cursor.execute(sql, proc_params)
            return

        raise StoredProcedureError(
            f'Bieżąca baza danych ({connection.vendor}) nie obsługuje procedury {name!r} w tym środowisku.'
        )
