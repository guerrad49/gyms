"""A gym database in a SQLite file."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Final

from PokemonGo.errors import SchemaError, StoreError
from PokemonGo.models import Gym
from PokemonGo.store.schema import COLUMNS, Cell, gym_from_cells, gym_to_cells

SCHEMA_VERSION: Final = 2
"""Stored in ``PRAGMA user_version``; the same number as the schema."""

_TYPES: Final = {
    "uid": "INTEGER UNIQUE",
    "victories": "INTEGER",
    "days": "INTEGER",
    "hours": "INTEGER",
    "minutes": "INTEGER",
    "defended": "REAL",
    "treats": "INTEGER",
    "latitude": "REAL",
    "longitude": "REAL",
}

_CREATE: Final = (
    "CREATE TABLE gyms (id INTEGER PRIMARY KEY AUTOINCREMENT, "
    + ", ".join(f"{name} {_TYPES.get(name, 'TEXT')}" for name in COLUMNS)
    + ")"
)
_INDEX: Final = "CREATE INDEX gyms_geo ON gyms (state, county, city, title)"
_ORDER: Final = (
    "ORDER BY state IS NULL, lower(state), county IS NULL, lower(county), "
    "city IS NULL, lower(city), title IS NULL, lower(title), id"
)
_INSERT: Final = (
    f"INSERT INTO gyms ({', '.join(COLUMNS)}) "
    f"VALUES ({', '.join(':' + name for name in COLUMNS)})"
)
_UPDATE: Final = (
    "UPDATE gyms SET "
    + ", ".join(f"{name} = :{name}" for name in COLUMNS)
    + " WHERE id = :id"
)


def _params(gym: Gym) -> dict[str, Cell]:
    """Convert a gym to SQL parameters: blanks become NULL."""
    return {n: (None if v == "" else v) for n, v in gym_to_cells(gym).items()}


class SqliteStore:
    """A gym database stored in a SQLite file.

    The database is always read in geographic order, so :meth:`sort` has
    nothing to do. Rows are identified by the table's integer ``id``.

    Parameters
    ----------
    path : pathlib.Path
        The database file; created, with the schema, if it does not exist.

    Raises
    ------
    SchemaError
        If the file is a SQLite database with another schema version.
    StoreError
        If the file cannot be opened.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(path)
        except (OSError, sqlite3.Error) as error:
            msg = f"cannot open {path}: {error}"
            raise StoreError(msg) from error
        self._conn.row_factory = sqlite3.Row
        try:
            version = self._conn.execute("PRAGMA user_version").fetchone()[0]
            fresh = version == 0 and not self._tables()
        except sqlite3.DatabaseError as error:
            self._conn.close()
            msg = f"{path} is not a SQLite database: {error}"
            raise StoreError(msg) from error
        if fresh:
            self._conn.execute(_CREATE)
            self._conn.execute(_INDEX)
            self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
            self._conn.commit()
        elif version != SCHEMA_VERSION:
            self._conn.close()
            msg = (
                f"{path} has schema version {version}, "
                f"expected {SCHEMA_VERSION}"
            )
            raise SchemaError(msg)

    def _tables(self) -> list[str]:
        rows = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        )
        return [row[0] for row in rows if not row[0].startswith("sqlite_")]

    def all(self) -> list[Gym]:
        """Return every gym in geographic order."""
        rows = self._conn.execute(f"SELECT * FROM gyms {_ORDER}")
        return [gym_from_cells(dict(row), row["id"]) for row in rows]

    def add(self, gym: Gym) -> None:
        """Insert a gym and set its ``row`` to the new id."""
        try:
            cursor = self._conn.execute(_INSERT, _params(gym))
        except sqlite3.IntegrityError as error:
            msg = f"uid {gym.uid} is already used"
            raise StoreError(msg) from error
        gym.row = cursor.lastrowid

    def update(self, gym: Gym) -> None:
        """Overwrite the gym with the id in ``gym.row``."""
        if gym.row is None:
            msg = "cannot update a gym with no row"
            raise StoreError(msg)
        try:
            cursor = self._conn.execute(
                _UPDATE, {**_params(gym), "id": gym.row}
            )
        except sqlite3.IntegrityError as error:
            msg = f"uid {gym.uid} is already used"
            raise StoreError(msg) from error
        if cursor.rowcount == 0:
            msg = f"there is no gym with row {gym.row}"
            raise StoreError(msg)

    def sort(self) -> None:
        """Do nothing: :meth:`all` is always in geographic order."""

    def commit(self) -> None:
        """Commit the open transaction."""
        self._conn.commit()

    def close(self) -> None:
        """Close the database, discarding uncommitted changes."""
        self._conn.close()
