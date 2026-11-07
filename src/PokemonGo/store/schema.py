"""The database layout (schema v2) and the mapping to and from gyms.

Every backend stores the same columns. A *table* is a header plus rows of
cells; this module turns a row of cells into a :class:`~PokemonGo.models.Gym`
and back, so the backends only differ in where the cells live.

Schema v2 keeps every column of the v1 sheet except ``latlon``, which is
replaced by numeric ``latitude`` and ``longitude`` columns, and appends
five new ones.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Final

from PokemonGo.errors import ParseError, SchemaError, StoreError
from PokemonGo.models import Activity, Coordinates, Gym
from PokemonGo.parsing import format_status, parse_status

COLUMNS: Final = (
    "uid",
    "title",
    "model",
    "style",
    "victories",
    "days",
    "hours",
    "minutes",
    "defended",
    "treats",
    "latitude",
    "longitude",
    "city",
    "county",
    "state",
    "country",
    "status",
    "scanned_at",
    "notes",
    "image_sha256",
)
"""The canonical column order of schema v2."""

LEGACY_COLUMNS: Final = (
    "uid",
    "title",
    "model",
    "style",
    "victories",
    "days",
    "hours",
    "minutes",
    "defended",
    "treats",
    "latlon",
    "city",
    "county",
    "state",
)
"""The v1 columns (A to N of the old sheet)."""

_STATS: Final = ("victories", "days", "hours", "minutes", "treats")

Cell = object
"""A table cell: text from a CSV, or text or a number from a spreadsheet."""


def text(value: Cell) -> str:
    """Return a cell as stripped text; ``None`` becomes ``""``.

    Examples
    --------
    >>> text(None), text(" a "), text(12.0)
    ('', 'a', '12.0')
    """
    return "" if value is None else str(value).strip()


def to_int(value: Cell, name: str) -> int | None:
    """Convert a cell to an ``int``, accepting ``12``, ``"12"`` and ``12.0``.

    Parameters
    ----------
    value : object
        The cell.
    name : str
        The column name, for error messages.

    Returns
    -------
    int or None
        ``None`` for a blank cell.

    Raises
    ------
    StoreError
        If the cell is not a whole number.

    Examples
    --------
    >>> to_int("448", "victories"), to_int(12.0, "uid"), to_int("", "uid")
    (448, 12, None)
    """
    raw = text(value)
    if not raw:
        return None
    try:
        number = float(raw)
    except ValueError:
        number = float("nan")
    if not math.isfinite(number) or number != int(number):
        msg = f"{name} must be a whole number, got {raw!r}"
        raise StoreError(msg)
    return int(number)


def to_float(value: Cell, name: str) -> float | None:
    """Convert a cell to a ``float``; ``None`` for a blank cell.

    Raises
    ------
    StoreError
        If the cell is not a number.
    """
    raw = text(value)
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        msg = f"{name} must be a number, got {raw!r}"
        raise StoreError(msg) from None


def _to_date(value: Cell) -> date | None:
    """Parse ``2026-11-02`` (or the US ``11/2/2026`` a spreadsheet shows)."""
    raw = text(value)
    if not raw:
        return None
    try:
        return date.fromisoformat(raw[:10])
    except ValueError:
        pass
    try:
        month, day, year = (int(part) for part in raw.split("/"))
        return date(year, month, day)
    except ValueError:
        msg = f"scanned_at must be a date like 2026-11-02, got {raw!r}"
        raise StoreError(msg) from None


def gym_to_cells(gym: Gym) -> dict[str, Cell]:
    """Convert a gym to ``{column: cell}`` for every canonical column.

    Numbers stay numbers and blanks are ``""``. ``style`` and ``defended``
    are computed from the statistics, for compatibility with the v1 sheet.

    Parameters
    ----------
    gym : Gym
        The gym to write.

    Returns
    -------
    dict
        One entry per name in :data:`COLUMNS`.

    Examples
    --------
    >>> cells = gym_to_cells(Gym(None, "starbucks"))
    >>> cells["uid"], cells["victories"], cells["status"]
    ('', '', '')
    """
    activity = gym.activity
    cells: dict[str, Cell] = {
        "uid": "" if gym.uid is None else gym.uid,
        "title": gym.title,
        "model": gym.model,
        "style": "" if activity is None else activity.style.value,
        "defended": "" if activity is None else activity.defended,
        "latitude": "" if gym.latitude is None else gym.latitude,
        "longitude": "" if gym.longitude is None else gym.longitude,
        "city": gym.city,
        "county": gym.county,
        "state": gym.state,
        "country": gym.country,
        "status": format_status(gym.status),
        "scanned_at": ""
        if gym.scanned_at is None
        else gym.scanned_at.isoformat(),
        "notes": gym.notes,
        "image_sha256": gym.image_sha256,
    }
    for name in _STATS:
        cells[name] = "" if activity is None else getattr(activity, name)
    return {name: cells[name] for name in COLUMNS}


def gym_from_cells(cells: Mapping[str, Cell], row: int | None = None) -> Gym:
    """Build a gym from ``{column: cell}``.

    ``style`` and ``defended`` are ignored: they are recomputed from the
    statistics, so a hand-edited value cannot disagree with them.

    Parameters
    ----------
    cells : mapping
        Cells by column name; missing columns count as blank.
    row : int, optional
        The store's row number, used in error messages and kept on the
        gym.

    Returns
    -------
    Gym
        The gym.

    Raises
    ------
    StoreError
        If a cell is invalid, or the statistics are only partly filled.
        The message names the row.
    """
    where = f"row {row}: " if row is not None else ""
    try:
        values = [to_int(cells.get(name), name) for name in _STATS]
        present = [v for v in values if v is not None]
        if not present:
            activity = None
        elif len(present) == len(_STATS):
            activity = Activity(*present)
        else:
            msg = "statistics are only partly filled in"
            raise StoreError(msg)

        lat = to_float(cells.get("latitude"), "latitude")
        lon = to_float(cells.get("longitude"), "longitude")
        if (lat is None) != (lon is None):
            msg = "latitude and longitude must both be set or both blank"
            raise StoreError(msg)
        coordinates = (
            None if lat is None or lon is None else Coordinates(lat, lon)
        )

        return Gym(
            uid=to_int(cells.get("uid"), "uid"),
            title=text(cells.get("title")),
            coordinates=coordinates,
            model=text(cells.get("model")),
            activity=activity,
            city=text(cells.get("city")),
            county=text(cells.get("county")),
            state=text(cells.get("state")),
            country=text(cells.get("country")),
            status=parse_status(text(cells.get("status"))),
            scanned_at=_to_date(cells.get("scanned_at")),
            notes=text(cells.get("notes")),
            image_sha256=text(cells.get("image_sha256")),
            row=row,
        )
    except (StoreError, ParseError, ValueError) as error:
        raise StoreError(where + str(error)) from error


GeoKey = tuple[tuple[bool, str], ...]
"""A sort key made of one ``(is_blank, lowercase text)`` pair per field."""


def geo_key_parts(state: str, county: str, city: str, title: str) -> GeoKey:
    """Return the key for the geographic order.

    Gyms are ordered by state, then county, city and title, ignoring
    case, with blank values **last** (as Google Sheets sorts, and as the
    v1 tool left the sheet). Every backend uses this order.

    Examples
    --------
    >>> geo_key_parts("Iowa", "", "Ames", "B")[:2]
    ((False, 'iowa'), (True, ''))
    """
    return tuple(
        (not part, part.lower()) for part in (state, county, city, title)
    )


def geo_key(gym: Gym) -> GeoKey:
    """Return the geographic sort key of a gym.

    Examples
    --------
    >>> geo_key(Gym(1, "B", city="Ames", state="Iowa"))[0]
    (False, 'iowa')
    """
    return geo_key_parts(gym.state, gym.county, gym.city, gym.title)


def check_header(header: Sequence[str]) -> None:
    """Check that a header is exactly schema v2 or schema v2 plus extras.

    Parameters
    ----------
    header : sequence of str
        The column names.

    Raises
    ------
    SchemaError
        If a canonical column is missing. If the old ``latlon`` column is
        present, the message says to run ``pogo upgrade``.
    """
    names = {text(name) for name in header}
    missing = [name for name in COLUMNS if name not in names]
    if not missing:
        return
    if "latlon" in names:
        msg = (
            "this database uses the old layout (a 'latlon' column); "
            "run 'pogo upgrade' first"
        )
    else:
        msg = f"missing column(s): {', '.join(missing)}; run 'pogo upgrade'"
    raise SchemaError(msg)


def next_uid(gyms: Sequence[Gym]) -> int:
    """Return the next free ``uid``: one more than the largest, or 1.

    Examples
    --------
    >>> next_uid([]), next_uid([Gym(7, "a"), Gym(None, "b")])
    (1, 8)
    """
    return max((g.uid for g in gyms if g.uid is not None), default=0) + 1


def known_hashes(gyms: Sequence[Gym]) -> frozenset[str]:
    """Return the screenshot hashes already recorded.

    Examples
    --------
    >>> known_hashes([Gym(1, "a", image_sha256="ab"), Gym(2, "b")])
    frozenset({'ab'})
    """
    return frozenset(g.image_sha256 for g in gyms if g.image_sha256)
