"""Upgrade a v1 database (14 columns, ``latlon``) to schema v2.

The upgrade works on a raw table and never loses data: it splits
``latlon`` into numeric ``latitude`` and ``longitude``, adds the new
columns, drops the unnamed index column some CSV exports carry, and keeps
any extra columns a person added.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from PokemonGo.errors import ParseError
from PokemonGo.models import Flag
from PokemonGo.parsing import format_status, parse_coordinates, parse_status
from PokemonGo.store.csv_store import write_csv_table
from PokemonGo.store.schema import COLUMNS, Cell, text
from PokemonGo.store.table import RawTable

_INDEX_NAMES = frozenset({"", "unnamed: 0", "index"})


@dataclass(frozen=True, slots=True)
class UpgradePlan:
    """What an upgrade changes.

    Attributes
    ----------
    rows : int
        Data rows that are not blank.
    dropped : tuple of str
        Columns removed (``latlon``, an unnamed index column).
    added : tuple of str
        Schema v2 columns that were missing and are added.
    bad_coordinates : tuple of tuple
        ``(row number, text)`` for each ``latlon`` that could not be
        parsed. Those rows are left without coordinates and flagged
        ``NO_COORDS``.
    """

    rows: int
    dropped: tuple[str, ...]
    added: tuple[str, ...]
    bad_coordinates: tuple[tuple[int, str], ...]

    @property
    def changes_anything(self) -> bool:
        """Whether the table is not already on schema v2."""
        return bool(self.dropped or self.added)


def needs_upgrade(header: Sequence[str]) -> bool:
    """Return whether a header is not schema v2.

    Examples
    --------
    >>> needs_upgrade(["uid", "title", "latlon"])
    True
    >>> needs_upgrade(list(COLUMNS))
    False
    """
    names = {text(name) for name in header}
    return "latlon" in names or any(c not in names for c in COLUMNS)


def upgrade_table(table: RawTable) -> tuple[RawTable, UpgradePlan]:
    """Convert a table to schema v2.

    Parameters
    ----------
    table : RawTable
        The table as read from a CSV file or a sheet. Already-current
        tables come back unchanged.

    Returns
    -------
    tuple
        The new table, and a description of what changed.

    Examples
    --------
    >>> old = RawTable(["uid", "title", "latlon"], [["1", "a", "1.5,-2"]])
    >>> new, plan = upgrade_table(old)
    >>> new.rows[0][new.header.index("latitude")]
    1.5
    >>> plan.dropped
    ('latlon',)
    """
    header = [text(name) for name in table.header]
    rows = [list(row) for row in table.rows]
    dropped: list[str] = []
    if header and header[0].lower() in _INDEX_NAMES:
        dropped.append("(unnamed index column)")
        header = header[1:]
        rows = [row[1:] for row in rows]

    legacy = "latlon" in header
    if legacy:
        dropped.append("latlon")
    extras = [h for h in header if h and h not in COLUMNS and h != "latlon"]
    position = {name: i for i, name in enumerate(header) if name}
    new_rows: list[list[Cell]] = []
    bad: list[tuple[int, str]] = []
    rows_seen = 0

    for number, row in enumerate(rows, start=2):
        row = row + [""] * (len(header) - len(row))
        cells = {name: row[i] for name, i in position.items()}
        blank = all(not text(cell) for cell in row)
        rows_seen += 0 if blank else 1
        out: dict[str, Cell] = {name: cells.get(name, "") for name in COLUMNS}
        flags = parse_status(text(out["status"]))
        if legacy and not blank:
            raw = text(cells.get("latlon"))
            try:
                point = parse_coordinates(raw)
                out["latitude"], out["longitude"] = (
                    point.latitude,
                    point.longitude,
                )
            except ParseError:
                bad.append((number, raw))
                flags = (*flags, Flag.NO_COORDS)
        out["status"] = format_status(dict.fromkeys(flags))
        new_rows.append(
            [out[name] for name in COLUMNS] + [cells.get(h, "") for h in extras]
        )

    present = set(header)
    added = tuple(c for c in COLUMNS if c not in present)
    plan = UpgradePlan(rows_seen, tuple(dropped), added, tuple(bad))
    if not plan.changes_anything:
        return table, plan
    return RawTable(list(COLUMNS) + extras, new_rows), plan


def backup_table(table: RawTable, directory: Path, label: str) -> Path:
    """Save a copy of a table as a timestamped CSV before changing it.

    Parameters
    ----------
    table : RawTable
        The table as it is now.
    directory : pathlib.Path
        The backup folder, created if needed.
    label : str
        A name for the source, used in the file name.

    Returns
    -------
    pathlib.Path
        The file written.
    """
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    path = directory / f"{label}-{stamp}.csv"
    write_csv_table(path, table)
    return path
