from datetime import date
from typing import Any

import pytest

from PokemonGo.errors import ParseError, PogoError
from PokemonGo.models import Activity, Coordinates, Flag, Gym, Style
from tests.support.expected import ALL, Expected


@pytest.mark.parametrize("case", ALL, ids=lambda c: c.file)
def test_activity_matches_the_ground_truth(case: Expected) -> None:
    activity = Activity(**case.activity)
    assert activity.defended == case.defended
    assert activity.style.value == case.style


@pytest.mark.parametrize(
    ("days", "style"),
    [(0, Style.GOLD), (99, Style.GOLD), (100, Style.LONG_TERM)],
)
def test_style_threshold_is_one_hundred_days(days: int, style: Style) -> None:
    assert Activity(0, days, 23, 59, 0).style is style


@pytest.mark.parametrize(
    ("values", "error", "message"),
    [
        ((-1, 0, 0, 0, 0), ValueError, "victories must not be negative"),
        ((0, -1, 0, 0, 0), ValueError, "days must not be negative"),
        ((0, 0, 24, 0, 0), ValueError, "hours must be below 24"),
        ((0, 0, 0, 60, 0), ValueError, "minutes must be below 60"),
        ((1.5, 0, 0, 0, 0), TypeError, "victories must be an int"),
        ((0, "5", 0, 0, 0), TypeError, "days must be an int"),
        ((0, 0, 0, 0, True), TypeError, "treats must be an int"),
    ],
)
def test_activity_rejects_invalid_values(
    values: tuple[Any, ...], error: type[Exception], message: str
) -> None:
    with pytest.raises(error, match=message):
        Activity(*values)


def test_activity_is_immutable() -> None:
    activity = Activity(1, 2, 3, 4, 5)
    with pytest.raises(AttributeError):
        activity.days = 9  # type: ignore[misc]


@pytest.mark.parametrize(
    ("lat", "lon"), [(0, 0), (90, 180), (-90, -180), (40.758186, -73.985585)]
)
def test_coordinates_accept_valid_values(lat: float, lon: float) -> None:
    point = Coordinates(lat, lon)
    assert (point.latitude, point.longitude) == (lat, lon)


@pytest.mark.parametrize(
    ("lat", "lon"),
    [
        (90.1, 0),
        (-91, 0),
        (0, 180.5),
        (0, -181),
        (float("nan"), 0),
        (0, float("inf")),
    ],
)
def test_coordinates_reject_invalid_values(lat: float, lon: float) -> None:
    with pytest.raises(ValueError, match="must be within"):
        Coordinates(lat, lon)


def test_coordinates_format_without_space() -> None:
    assert str(Coordinates(40.758186, -73.985585)) == "40.758186,-73.985585"


def test_gym_defaults() -> None:
    gym = Gym(uid=None, title="starbucks")
    assert gym.is_seeded
    assert gym.coordinates is None
    assert gym.latitude is None
    assert gym.longitude is None
    assert gym.status == ()
    assert gym.scanned_at is None


def test_gym_exposes_coordinate_parts() -> None:
    gym = Gym(7, "x", Coordinates(1.5, 2.5), scanned_at=date(2026, 10, 29))
    assert not gym.is_seeded
    assert (gym.latitude, gym.longitude) == (1.5, 2.5)


def test_gym_flags_are_not_duplicated() -> None:
    gym = Gym(1, "x")
    gym.add_flag(Flag.CITY)
    gym.add_flag(Flag.STATE)
    gym.add_flag(Flag.CITY)
    assert gym.status == (Flag.CITY, Flag.STATE)
    assert gym.has_flag(Flag.STATE)
    assert not gym.has_flag(Flag.TITLE)


def test_errors_share_a_base_class() -> None:
    assert issubclass(ParseError, PogoError)
    assert issubclass(ParseError, ValueError)
