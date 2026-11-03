"""Shared logic for stores that keep a header and rows of cells.

CSV files and spreadsheets are both tables: a header row of column names
followed by one row per gym. :class:`TableStore` implements everything
except where the cells are saved. Columns are found by name, so extra
columns a person added are preserved untouched.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from PokemonGo.errors import StoreError
from PokemonGo.models import Gym
from PokemonGo.store.schema import (
    COLUMNS,
    Cell,
    GeoKey,
    check_header,
    geo_key_parts,
    gym_from_cells,
    gym_to_cells,
    text,
    to_int,
)

_GEO_COLUMNS = ("state", "county", "city", "title")


@dataclass
class RawTable:
    """A header and rows of cells, exactly as stored.

    Attributes
    ----------
    header : list of str
        The column names.
    rows : list of list of object
        The data rows. They need not all be as long as the header.
    """

    header: list[str]
    rows: list[list[Cell]] = field(default_factory=list)


class TableStore:
    """A gym database held as a table in memory.

    Subclasses implement ``_flush`` to save changes. The first data
    row is row 2, as in a spreadsheet, whatever the file format.

    Parameters
    ----------
    table : RawTable
        The table as read.

    Raises
    ------
    SchemaError
        If the header lacks a schema v2 column.
    StoreError
        If two rows share a ``uid``.
    """

    def __init__(self, table: RawTable) -> None:
        check_header(table.header)
        self._header = [text(name) for name in table.header]
        self._col = {name: index for index, name in enumerate(self._header)}
        self._rows = [self._pad(list(row)) for row in table.rows]
        self._saved = len(self._rows)
        self._dirty: set[int] = set()
        self._full = False
        self._force = False  # subclasses: save even if nothing changed
        self._uids: dict[int, int] = {}
        for index, row in enumerate(self._rows):
            try:
                uid = to_int(row[self._col["uid"]], "uid")
            except StoreError as error:
                msg = f"row {index + 2}: {error}"
                raise StoreError(msg) from error
            if uid is not None:
                if uid in self._uids:
                    msg = f"row {index + 2}: uid {uid} is already used"
                    msg += f" by row {self._uids[uid] + 2}"
                    raise StoreError(msg)
                self._uids[uid] = index

    def _pad(self, row: list[Cell]) -> list[Cell]:
        """Extend a short row with blanks to the header's length."""
        return row + [""] * (len(self._header) - len(row))

    def _cells(self, row: Sequence[Cell]) -> dict[str, Cell]:
        return {name: row[index] for name, index in self._col.items()}

    def _is_blank(self, row: Sequence[Cell]) -> bool:
        return all(not text(row[self._col[name]]) for name in COLUMNS)

    # --- GymStore ------------------------------------------------------

    def all(self) -> list[Gym]:
        """Return every gym; see ``GymStore.all``."""
        return [
            gym_from_cells(self._cells(row), index + 2)
            for index, row in enumerate(self._rows)
            if not self._is_blank(row)
        ]

    def add(self, gym: Gym) -> None:
        """Append a gym; see ``GymStore.add``."""
        if gym.uid is not None and gym.uid in self._uids:
            owner = self._uids[gym.uid] + 2
            msg = f"uid {gym.uid} is already used by row {owner}"
            raise StoreError(msg)
        row = self._pad([])
        self._write(row, gym)
        self._rows.append(row)
        index = len(self._rows) - 1
        if gym.uid is not None:
            self._uids[gym.uid] = index
        gym.row = index + 2

    def update(self, gym: Gym) -> None:
        """Overwrite a stored gym; see ``GymStore.update``."""
        if gym.row is None or not 2 <= gym.row <= len(self._rows) + 1:
            msg = f"cannot update a gym with row {gym.row!r}"
            raise StoreError(msg)
        index = gym.row - 2
        owner = self._uids.get(gym.uid) if gym.uid is not None else index
        if owner is not None and owner != index:
            msg = f"uid {gym.uid} is already used by row {owner + 2}"
            raise StoreError(msg)
        old = to_int(self._rows[index][self._col["uid"]], "uid")
        if old is not None:
            self._uids.pop(old, None)
        if gym.uid is not None:
            self._uids[gym.uid] = index
        self._write(self._rows[index], gym)
        if index < self._saved:
            self._dirty.add(index)

    def sort(self) -> None:
        """Order rows geographically in memory; see ``GymStore.sort``."""

        def key(row: list[Cell]) -> tuple[bool, GeoKey]:
            parts = (text(row[self._col[n]]) for n in _GEO_COLUMNS)
            return (self._is_blank(row), geo_key_parts(*parts))

        self._rows.sort(key=key)
        self._uids = {
            uid: index
            for index, row in enumerate(self._rows)
            if (uid := to_int(row[self._col["uid"]], "uid")) is not None
        }
        self._full = True

    def commit(self) -> None:
        """Save all changes; see ``GymStore.commit``."""
        new = range(self._saved, len(self._rows))
        if self._force or self._full or self._dirty or len(new):
            self._flush(
                full=self._full, dirty=sorted(self._dirty), new=list(new)
            )
        self._saved = len(self._rows)
        self._dirty.clear()
        self._full = False
        self._force = False

    def close(self) -> None:
        """Discard uncommitted changes; see ``GymStore.close``."""

    # --- for subclasses ------------------------------------------------

    def _write(self, row: list[Cell], gym: Gym) -> None:
        """Put a gym's canonical cells into a row, leaving extras alone."""
        for name, value in gym_to_cells(gym).items():
            row[self._col[name]] = value

    def _flush(self, *, full: bool, dirty: list[int], new: list[int]) -> None:
        """Save the table.

        Parameters
        ----------
        full : bool
            Row order changed, so every row must be written.
        dirty : list of int
            Indexes of saved rows that changed.
        new : list of int
            Indexes of rows added since the last commit.
        """
        raise NotImplementedError
