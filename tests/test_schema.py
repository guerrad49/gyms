from datetime import date

import pytest

from PokemonGo.errors import SchemaError, StoreError
from PokemonGo.models import Activity, Coordinates, Flag, Gym
from PokemonGo.store.schema import (
    COLUMNS,
    LEGACY_COLUMNS,
    check_header,
    geo_key,
    gym_from_cells,
    gym_to_cells,
    known_hashes,
    next_uid,
    text,
    to_float,
    to_int,
)
from tests.support.gyms import scanned, seeded


def test_the_legacy_columns_are_the_v1_sheet() -> None:
    assert len(LEGACY_COLUMNS) == 14
    assert [c for c in COLUMNS if c in LEGACY_COLUMNS] == [
        c for c in LEGACY_COLUMNS if c != "latlon"
    ]
    assert COLUMNS[10:12] == ("latitude", "longitude")
    assert len(COLUMNS) == 20


@pytest.mark.parametrize(
    "gym", [scanned(), seeded()], ids=["scanned", "seeded"]
)
def test_a_gym_round_trips_through_cells(gym: Gym) -> None:
    cells = gym_to_cells(gym)
    assert list(cells) == list(COLUMNS)
    assert gym_from_cells(cells, 5) == gym
    assert gym_from_cells(cells, 5).row == 5


def test_style_and_defended_are_written_but_never_trusted() -> None:
    cells = gym_to_cells(scanned())
    assert cells["style"] == "gold"
    assert cells["defended"] == 21.7917
    cells["style"], cells["defended"] = "100+ days", 999
    assert gym_from_cells(cells).activity == scanned().activity


def test_a_seeded_gym_has_blank_statistics() -> None:
    cells = gym_to_cells(seeded())
    for name in (
        "uid",
        "style",
        "victories",
        "defended",
        "status",
        "scanned_at",
    ):
        assert cells[name] == ""


@pytest.mark.parametrize(
    ("value", "expected"),
    [("448", 448), (12.0, 12), (" 7 ", 7), ("", None), (None, None), ("0", 0)],
)
def test_to_int(value: object, expected: int | None) -> None:
    assert to_int(value, "x") == expected


@pytest.mark.parametrize("value", ["1.5", "abc", "nan", "1e400", "inf", "-inf"])
def test_to_int_rejects_non_integers(value: str) -> None:
    with pytest.raises(StoreError, match="x must be a whole number"):
        to_int(value, "x")


def test_to_float() -> None:
    assert to_float("-73.5", "x") == -73.5
    assert to_float("", "x") is None
    with pytest.raises(StoreError, match="x must be a number"):
        to_float("abc", "x")


def test_text_strips_and_blanks_none() -> None:
    assert text(None) == ""
    assert text("  a ") == "a"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2026-11-02", date(2026, 11, 2)),
        ("2026-11-02T10:00:00", date(2026, 11, 2)),
        ("11/2/2026", date(2026, 11, 2)),
        ("", None),
    ],
)
def test_scanned_at_formats(raw: str, expected: date | None) -> None:
    assert gym_from_cells({"scanned_at": raw}).scanned_at == expected


def test_a_bad_date_is_an_error() -> None:
    with pytest.raises(StoreError, match="row 4: scanned_at must be a date"):
        gym_from_cells({"scanned_at": "13/45/2026"}, 4)


def test_out_of_range_coordinates_are_an_error() -> None:
    cells = {"latitude": "95", "longitude": "0"}
    with pytest.raises(StoreError, match="latitude must be within"):
        gym_from_cells(cells, 3)


def test_out_of_range_statistics_are_an_error() -> None:
    cells = {"victories": 1, "days": 1, "hours": 30, "minutes": 0, "treats": 1}
    with pytest.raises(StoreError, match="hours must be below 24"):
        gym_from_cells(cells)


def test_check_header_accepts_v2_with_extras() -> None:
    check_header([*COLUMNS, "mine"])
    check_header(list(reversed(COLUMNS)))  # order does not matter


def test_check_header_explains_the_old_layout() -> None:
    with pytest.raises(SchemaError, match="pogo upgrade"):
        check_header(LEGACY_COLUMNS)
    with pytest.raises(SchemaError, match=r"missing column.*country"):
        check_header([c for c in COLUMNS if c != "country"])


def test_next_uid_and_known_hashes() -> None:
    assert next_uid([]) == 1
    assert next_uid([Gym(None, "seed"), Gym(41, "a")]) == 42
    gyms = [
        Gym(1, "a", image_sha256="ab"),
        Gym(2, "b"),
        Gym(3, "c", image_sha256="cd"),
    ]
    assert known_hashes(gyms) == frozenset({"ab", "cd"})


def test_geo_key_ignores_case_and_puts_blanks_last() -> None:
    a = Gym(1, "x", state="Maine", county="", city="a")
    b = Gym(2, "x", state="maine", county="york", city="z")
    c = Gym(3, "x", state="", county="", city="")
    assert sorted([c, a, b], key=geo_key) == [b, a, c]


def test_flags_and_coordinates_survive() -> None:
    gym = Gym(1, "x", Coordinates(1.5, 2.5), status=(Flag.NO_COORDS, Flag.CITY))
    again = gym_from_cells(gym_to_cells(gym))
    assert again.status == (Flag.NO_COORDS, Flag.CITY)
    assert again.coordinates == Coordinates(1.5, 2.5)
    assert Activity(0, 0, 0, 0, 0)  # statistics of zero are valid, not blank
