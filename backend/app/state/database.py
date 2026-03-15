from __future__ import annotations

from pathlib import Path
import sqlite3
from typing import Any, TypeAlias

DatabaseConnection: TypeAlias = sqlite3.Connection | Any


def _resolve_sqlite_path(database_url: str) -> str:
    if database_url == "sqlite:///:memory:":
        return ":memory:"
    if database_url.startswith("sqlite:///"):
        return database_url.removeprefix("sqlite:///")
    raise ValueError(f"unsupported sqlite database url: {database_url}")


def _normalize_postgres_url(database_url: str) -> str:
    if database_url.startswith("postgresql+psycopg://"):
        return database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    if database_url.startswith("postgresql://"):
        return database_url
    raise ValueError(f"unsupported postgres database url: {database_url}")


def _connect_postgres(database_url: str) -> Any:
    import psycopg
    from psycopg.rows import dict_row

    return psycopg.connect(
        _normalize_postgres_url(database_url),
        autocommit=True,
        row_factory=dict_row,
    )


def connect_state_database(database_url: str) -> DatabaseConnection:
    if database_url.startswith("sqlite:///") or database_url == "sqlite:///:memory:":
        path = _resolve_sqlite_path(database_url)
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, check_same_thread=False)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
    if database_url.startswith("postgresql"):
        return _connect_postgres(database_url)
    raise ValueError(f"unsupported state database url: {database_url}")


def execute_query(
    connection: DatabaseConnection,
    query: str,
    parameters: tuple[object, ...] = (),
) -> Any:
    if isinstance(connection, sqlite3.Connection):
        return connection.execute(query, parameters)
    return connection.execute(query.replace("?", "%s"), parameters)
