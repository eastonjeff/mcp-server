"""Read-only PostgreSQL access for the MCP tools."""

from __future__ import annotations

import os
from typing import Any

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

load_dotenv(override=True)


class Database:
    """Small PostgreSQL adapter that opens a fresh read-only connection per call."""

    def __init__(self, dsn: str | None = None) -> None:
        self.dsn = dsn or os.getenv("DATABASE_URL")

    def _connect(self) -> psycopg.Connection[Any]:
        if not self.dsn:
            raise ValueError("DATABASE_URL must be set to the existing PostgreSQL database.")
        try:
            connect_timeout = int(os.getenv("DB_CONNECT_TIMEOUT", "5"))
        except ValueError as error:
            raise ValueError("DB_CONNECT_TIMEOUT must be an integer number of seconds.") from error
        if connect_timeout <= 0:
            raise ValueError("DB_CONNECT_TIMEOUT must be greater than zero.")
        return psycopg.connect(
            self.dsn,
            connect_timeout=connect_timeout,
            autocommit=True,
            options="-c default_transaction_read_only=on",
            row_factory=dict_row,
        )

    def list_tables(self) -> list[str]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_type = 'BASE TABLE'
                  AND table_schema NOT IN ('pg_catalog', 'information_schema')
                ORDER BY table_schema, table_name
                """
            ).fetchall()
        return [
            f"{row['table_schema']}.{row['table_name']}"
            if row["table_schema"] != "public"
            else row["table_name"]
            for row in rows
        ]

    def describe_table(self, table_name: str) -> list[dict[str, Any]]:
        schema, name = self._split_table_name(table_name)
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT column_name, data_type, is_nullable, ordinal_position
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
                """,
                (schema, name),
            ).fetchall()
        if not rows:
            raise ValueError(f"Table not found: {table_name}")
        return [dict(row) for row in rows]

    def execute_readonly(self, query: str, parameters: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with self._connect() as connection:
            cursor = (
                connection.execute(query, parameters)
                if parameters
                else connection.execute(query)
            )
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def _split_table_name(table_name: str) -> tuple[str, str]:
        parts = table_name.split(".")
        if len(parts) == 1:
            schema, name = "public", parts[0]
        elif len(parts) == 2:
            schema, name = parts
        else:
            raise ValueError("Table names must be in the form table or schema.table.")
        if not schema or not name or any(
            not part.replace("_", "").isalnum() for part in (schema, name)
        ):
            raise ValueError("Table names may contain only letters, numbers, underscores, and one dot.")
        return schema, name
