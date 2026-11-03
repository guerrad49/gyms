from pathlib import Path

import pytest

from PokemonGo import store as store_module
from PokemonGo.config import Backend, Settings
from PokemonGo.errors import ConfigError, StoreError
from PokemonGo.store import open_store, read_table, write_table
from PokemonGo.store.csv_store import CsvStore
from PokemonGo.store.sheets_store import SheetsStore
from PokemonGo.store.sqlite_store import SqliteStore
from PokemonGo.store.table import RawTable
from tests.support.sheets import FakeWorksheet


def test_each_backend_is_opened_from_the_settings(tmp_path: Path) -> None:
    settings = Settings(csv_path=tmp_path / "g.csv", db_path=tmp_path / "g.db")
    assert isinstance(open_store(settings, Backend.CSV), CsvStore)
    assert isinstance(open_store(settings, Backend.SQLITE), SqliteStore)


def test_the_default_is_the_configured_backend(tmp_path: Path) -> None:
    settings = Settings(backend=Backend.CSV, csv_path=tmp_path / "g.csv")
    assert isinstance(open_store(settings), CsvStore)


@pytest.mark.parametrize(
    ("backend", "needed"),
    [
        (Backend.CSV, "CSV_PATH"),
        (Backend.SQLITE, "DB_PATH"),
        (Backend.SHEETS, "SHEET_NAME"),
    ],
)
def test_missing_settings_are_named(backend: Backend, needed: str) -> None:
    with pytest.raises(ConfigError, match=needed):
        open_store(Settings(), backend)


def test_sheets_needs_a_key_as_well() -> None:
    with pytest.raises(ConfigError, match="JSON_KEY"):
        open_store(Settings(sheet_name="gyms"), Backend.SHEETS)


def test_sheets_are_opened_through_the_worksheet_helper(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sheet = FakeWorksheet()
    monkeypatch.setattr(store_module, "open_worksheet", lambda key, name: sheet)
    settings = Settings(sheet_name="gyms", json_key=tmp_path / "k.json")
    assert isinstance(open_store(settings, Backend.SHEETS), SheetsStore)


def test_tables_can_be_read_and_written_raw(tmp_path: Path) -> None:
    settings = Settings(csv_path=tmp_path / "g.csv")
    write_table(settings, Backend.CSV, RawTable(["a", "b"], [["1", "2"]]))
    assert read_table(settings, Backend.CSV) == RawTable(
        ["a", "b"], [["1", "2"]]
    )


def test_raw_sheet_tables(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    sheet = FakeWorksheet([["a"], ["1"]])
    monkeypatch.setattr(store_module, "open_worksheet", lambda key, name: sheet)
    settings = Settings(sheet_name="gyms", json_key=tmp_path / "k.json")
    assert read_table(settings, Backend.SHEETS).header == ["a"]
    write_table(settings, Backend.SHEETS, RawTable(["a", "b"], [["1", "2"]]))
    assert sheet.values == [["a", "b"], ["1", "2"]]


def test_sqlite_is_never_read_or_written_as_a_table(tmp_path: Path) -> None:
    settings = Settings(db_path=tmp_path / "g.db")
    with pytest.raises(StoreError, match="current schema"):
        read_table(settings, Backend.SQLITE)
    with pytest.raises(StoreError, match="never rewritten"):
        write_table(settings, Backend.SQLITE, RawTable([]))
