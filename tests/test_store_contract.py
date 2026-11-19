"""One contract, three backends: CSV, SQLite and (a fake) Google Sheet."""

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path

import pytest

from PokemonGo.errors import StoreError
from PokemonGo.models import Activity, Gym
from PokemonGo.store.base import GymStore
from PokemonGo.store.csv_store import CsvStore
from PokemonGo.store.sheets_store import SheetsStore
from PokemonGo.store.sqlite_store import SqliteStore
from tests.support.gyms import (
    EXPECTED_ORDER,
    many,
    scanned,
    seeded,
    unicode_gym,
)
from tests.support.sheets import FakeWorksheet

Opener = Callable[[], GymStore]


@pytest.fixture(params=["csv", "sqlite", "sheets"])
def opener(request: pytest.FixtureRequest, tmp_path: Path) -> Opener:
    """Return a function that opens the same database again each time."""
    if request.param == "csv":
        csv_path = tmp_path / "gyms.csv"
        return lambda: CsvStore(csv_path)
    if request.param == "sqlite":
        db_path = tmp_path / "gyms.db"
        return lambda: SqliteStore(db_path)
    sheet = FakeWorksheet()
    return lambda: SheetsStore(sheet)


def _by_uid(gyms: list[Gym]) -> list[Gym]:
    return sorted(gyms, key=lambda g: (g.uid is None, g.uid or 0, g.title))


def test_a_new_store_is_empty(opener: Opener) -> None:
    assert opener().all() == []


def test_added_gyms_survive_a_reopen(opener: Opener) -> None:
    gyms = [seeded(), scanned(), unicode_gym()]
    store = opener()
    for gym in gyms:
        store.add(gym)
    store.commit()
    store.close()
    assert _by_uid(opener().all()) == _by_uid(gyms)


def test_rows_are_distinct_and_stable_across_a_reopen(opener: Opener) -> None:
    store = opener()
    gyms = [seeded(), scanned(), unicode_gym()]
    for gym in gyms:
        store.add(gym)
    store.commit()
    store.close()
    added = {g.title: g.row for g in gyms}
    assert None not in added.values()
    assert len(set(added.values())) == 3
    assert {g.title: g.row for g in opener().all()} == added


def test_updating_a_seeded_gym_fills_it_in_place(opener: Opener) -> None:
    store = opener()
    seed = seeded()
    store.add(seed)
    store.add(scanned())
    store.commit()
    row = seed.row
    seed.uid = 8
    seed.activity = Activity(2, 3, 4, 5, 6)
    seed.city = "new york"
    store.update(seed)
    store.commit()
    store.close()
    found = {g.title: g for g in opener().all()}["maple park"]
    assert (found.uid, found.city, found.row) == (8, "new york", row)
    assert found.activity == Activity(2, 3, 4, 5, 6)


def test_update_needs_a_row_that_exists(opener: Opener) -> None:
    store = opener()
    gym = scanned()
    store.add(gym)
    with pytest.raises(StoreError):
        store.update(replace(gym, row=None))
    with pytest.raises(StoreError):
        store.update(replace(gym, row=999))


def test_uids_are_unique(opener: Opener) -> None:
    store = opener()
    store.add(scanned())
    with pytest.raises(StoreError, match="already used"):
        store.add(Gym(7, "duplicate"))
    other = Gym(8, "other")
    store.add(other)
    other.uid = 7
    with pytest.raises(StoreError, match="already used"):
        store.update(other)


def test_changes_are_lost_without_a_commit(opener: Opener) -> None:
    store = opener()
    store.add(scanned())
    store.commit()
    store.add(unicode_gym())
    store.close()
    assert [g.uid for g in opener().all()] == [7]


def test_committing_twice_and_then_adding_more_works(opener: Opener) -> None:
    store = opener()
    store.add(scanned())
    store.commit()
    store.commit()
    store.add(unicode_gym())
    store.commit()
    store.close()
    assert sorted(g.uid or 0 for g in opener().all()) == [7, 12]


def test_sort_is_geographic_with_blanks_last(opener: Opener) -> None:
    store = opener()
    for gym in many():
        store.add(gym)
    store.sort()
    store.commit()
    store.close()
    assert [g.title for g in opener().all()] == EXPECTED_ORDER


def test_rows_from_all_work_for_updates_after_a_sort(opener: Opener) -> None:
    store = opener()
    for gym in many():
        store.add(gym)
    store.sort()
    store.commit()
    target = next(g for g in store.all() if g.title == "banana")
    target.notes = "edited"
    store.update(target)
    store.commit()
    store.close()
    notes = {g.title: g.notes for g in opener().all()}
    assert notes["banana"] == "edited"
    assert notes["Apple"] == ""
    assert len(notes) == 6
