"""Gym databases: Google Sheets, SQLite and CSV behind one interface.

Use :func:`open_store` to get a :class:`GymStore` for the backend chosen
in the settings.
"""

from __future__ import annotations

from PokemonGo.config import Backend, Settings
from PokemonGo.errors import ConfigError, StoreError
from PokemonGo.store.base import GymStore
from PokemonGo.store.csv_store import CsvStore, read_csv_table, write_csv_table
from PokemonGo.store.sheets_store import (
    SheetsStore,
    open_worksheet,
    read_sheet_table,
    write_sheet_table,
)
from PokemonGo.store.sqlite_store import SqliteStore
from PokemonGo.store.table import RawTable

__all__ = [
    "GymStore",
    "open_store",
    "read_table",
    "write_table",
]


def _require(value: object, name: str, backend: Backend) -> None:
    if value is None or value == "":
        msg = f"{name} is required for the {backend.value} backend"
        raise ConfigError(msg)


def open_store(settings: Settings, backend: Backend | None = None) -> GymStore:
    """Open the database for a backend.

    Parameters
    ----------
    settings : Settings
        Where each backend lives.
    backend : Backend, optional
        Which backend to open; defaults to ``settings.backend``.

    Returns
    -------
    GymStore
        The opened database.

    Raises
    ------
    ConfigError
        If the backend's settings (path, key, sheet name) are missing.
    SchemaError
        If the database uses an old layout.
    """
    backend = backend or settings.backend
    if backend is Backend.CSV:
        _require(settings.csv_path, "CSV_PATH", backend)
        assert settings.csv_path is not None
        return CsvStore(settings.csv_path)
    if backend is Backend.SQLITE:
        _require(settings.db_path, "DB_PATH", backend)
        assert settings.db_path is not None
        return SqliteStore(settings.db_path)
    _require(settings.sheet_name, "SHEET_NAME", backend)
    _require(settings.json_key, "JSON_KEY", backend)
    assert settings.json_key is not None
    return SheetsStore(open_worksheet(settings.json_key, settings.sheet_name))


def read_table(settings: Settings, backend: Backend) -> RawTable:
    """Read a database as a raw table, whatever its layout.

    Used by ``pogo upgrade``, which must read databases that
    :func:`open_store` would refuse.

    Raises
    ------
    StoreError
        For SQLite, which is only ever created at the current schema.
    """
    if backend is Backend.CSV:
        _require(settings.csv_path, "CSV_PATH", backend)
        assert settings.csv_path is not None
        return read_csv_table(settings.csv_path)
    if backend is Backend.SHEETS:
        _require(settings.json_key, "JSON_KEY", backend)
        _require(settings.sheet_name, "SHEET_NAME", backend)
        assert settings.json_key is not None
        sheet = open_worksheet(settings.json_key, settings.sheet_name)
        return read_sheet_table(sheet)
    msg = "SQLite databases are always created with the current schema"
    raise StoreError(msg)


def write_table(settings: Settings, backend: Backend, table: RawTable) -> None:
    """Replace a database's contents with a raw table.

    Raises
    ------
    StoreError
        For SQLite, which is never rewritten this way.
    """
    if backend is Backend.CSV:
        assert settings.csv_path is not None
        write_csv_table(settings.csv_path, table)
    elif backend is Backend.SHEETS:
        assert settings.json_key is not None
        sheet = open_worksheet(settings.json_key, settings.sheet_name)
        write_sheet_table(sheet, table)
    else:
        msg = "SQLite databases are never rewritten as a table"
        raise StoreError(msg)
