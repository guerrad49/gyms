import csv
from collections.abc import Callable
from pathlib import Path

import pytest

from PokemonGo.errors import StoreError
from PokemonGo.export import MY_MAPS_COLUMNS, write_my_maps_csv
from PokemonGo.models import Activity, Coordinates, Gym
from PokemonGo.store.base import GymStore
from PokemonGo.store.csv_store import CsvStore
from PokemonGo.store.migrate import copy_gyms
from PokemonGo.store.sheets_store import SheetsStore
from PokemonGo.store.sqlite_store import SqliteStore
from tests.support.gyms import many, scanned, seeded, unicode_gym
from tests.support.sheets import FakeWorksheet

Make = Callable[[Path], GymStore]

KINDS: dict[str, Make] = {
    "csv": lambda tmp: CsvStore(tmp / "t.csv"),
    "sqlite": lambda tmp: SqliteStore(tmp / "t.db"),
    "sheets": lambda tmp: SheetsStore(FakeWorksheet()),
}


def _by_uid(gyms: list[Gym]) -> list[Gym]:
    return sorted(gyms, key=lambda g: (g.uid is None, g.uid or 0, g.title))


@pytest.mark.parametrize(
    ("source", "target"),
    [
        ("csv", "sqlite"),
        ("sqlite", "csv"),
        ("csv", "sheets"),
        ("sheets", "csv"),
        ("sqlite", "sheets"),
        ("sheets", "sqlite"),
    ],
)
def test_copying_between_backends_keeps_every_gym(
    tmp_path: Path, source: str, target: str
) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    src, dst = KINDS[source](tmp_path / "a"), KINDS[target](tmp_path / "b")
    originals = [seeded(), scanned(), unicode_gym()]
    for gym in originals:
        src.add(gym)
    src.commit()
    assert copy_gyms(src, dst) == 3
    assert _by_uid(dst.all()) == _by_uid(originals)


def test_copying_does_not_share_rows_with_the_source(tmp_path: Path) -> None:
    src = SqliteStore(tmp_path / "s.db")
    for gym in many():
        src.add(gym)
    dst = CsvStore(tmp_path / "t.csv")
    copy_gyms(src, dst)
    assert sorted(g.row or 0 for g in dst.all()) == [2, 3, 4, 5, 6, 7]


def test_a_migration_never_mixes_two_databases(tmp_path: Path) -> None:
    src = CsvStore(tmp_path / "s.csv")
    src.add(scanned())
    dst = CsvStore(tmp_path / "t.csv")
    dst.add(unicode_gym())
    with pytest.raises(StoreError, match="not empty"):
        copy_gyms(src, dst)
    assert [g.uid for g in dst.all()] == [12]


def test_copying_an_empty_database_copies_nothing(tmp_path: Path) -> None:
    assert (
        copy_gyms(CsvStore(tmp_path / "s.csv"), CsvStore(tmp_path / "t.csv"))
        == 0
    )


def _read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def test_the_my_maps_export_has_position_columns_first(tmp_path: Path) -> None:
    out = tmp_path / "maps.csv"
    assert write_my_maps_csv([scanned()], out) == 1
    [row] = _read(out)
    assert list(row) == list(MY_MAPS_COLUMNS)
    assert list(row)[:3] == ["title", "latitude", "longitude"]
    assert row["latitude"] == "-13.329799"
    assert row["style"] == "gold"
    assert row["defended"] == "21.7917"
    assert row["state"] == "cusco"


def test_only_scanned_gyms_are_exported_by_default(tmp_path: Path) -> None:
    out = tmp_path / "maps.csv"
    gyms = [scanned(), seeded()]
    assert write_my_maps_csv(gyms, out) == 1
    assert write_my_maps_csv(gyms, out, include_seeded=True) == 2
    rows = _read(out)
    assert rows[1]["title"] == "maple park"
    assert rows[1]["style"] == ""


def test_gyms_without_coordinates_are_skipped(tmp_path: Path) -> None:
    out = tmp_path / "maps.csv"
    nowhere = Gym(3, "nowhere", activity=Activity(1, 1, 1, 1, 1))
    here = Gym(4, "here", Coordinates(1, 2), activity=Activity(1, 1, 1, 1, 1))
    assert write_my_maps_csv([nowhere, here], out, include_seeded=True) == 1
    assert [r["title"] for r in _read(out)] == ["here"]


def test_the_export_keeps_unicode(tmp_path: Path) -> None:
    out = tmp_path / "maps.csv"
    write_my_maps_csv([unicode_gym()], out)
    assert _read(out)[0]["title"] == "\u5927\u962a\u57ce"
