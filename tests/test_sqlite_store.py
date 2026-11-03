import sqlite3
from pathlib import Path

import pytest

from PokemonGo.errors import SchemaError, StoreError
from PokemonGo.models import Gym
from PokemonGo.store.sqlite_store import SCHEMA_VERSION, SqliteStore
from tests.support.gyms import many, scanned


def test_a_new_database_is_created_with_the_schema(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "gyms.db"
    SqliteStore(path).close()
    with sqlite3.connect(path) as conn:
        assert (
            conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
        )


def test_a_database_with_another_version_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "gyms.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE gyms (x)")
        conn.execute("PRAGMA user_version = 1")
    with pytest.raises(SchemaError, match="schema version 1"):
        SqliteStore(path)


def test_an_unrelated_database_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "other.db"
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE something_else (x)")
    with pytest.raises(SchemaError):
        SqliteStore(path)


def test_a_file_that_is_not_a_database_is_a_store_error(tmp_path: Path) -> None:
    path = tmp_path / "junk.db"
    path.write_bytes(b"this is not sqlite" * 50)
    with pytest.raises(StoreError, match="not a SQLite database"):
        SqliteStore(path)


def test_an_unusable_path_is_a_store_error(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    with pytest.raises(StoreError, match="cannot open"):
        SqliteStore(blocker / "gyms.db")


def test_all_is_always_in_geographic_order(tmp_path: Path) -> None:
    store = SqliteStore(tmp_path / "gyms.db")
    for gym in many():
        store.add(gym)
    assert [g.title for g in store.all()][:2] == ["banana", "Apple"]
    store.sort()  # nothing to do, and harmless


def test_updating_a_missing_row_is_an_error(tmp_path: Path) -> None:
    store = SqliteStore(tmp_path / "gyms.db")
    with pytest.raises(StoreError, match="no gym with row 5"):
        store.update(Gym(1, "x", row=5))


def test_blank_values_are_stored_as_null(tmp_path: Path) -> None:
    path = tmp_path / "gyms.db"
    store = SqliteStore(path)
    store.add(scanned())
    store.add(Gym(None, "seed"))
    store.commit()
    with sqlite3.connect(path) as conn:
        row = conn.execute(
            "SELECT uid, victories, county FROM gyms WHERE title = 'seed'"
        ).fetchone()
    assert row == (None, None, None)
