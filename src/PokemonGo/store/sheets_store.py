"""A gym database in a Google Sheet.

Only :func:`open_worksheet` touches the ``gspread`` library. Everything
else works through the small :class:`Worksheet` interface, which is what
the tests fake, so the logic here is tested without a network.
"""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from PokemonGo.errors import ConfigError, StoreError
from PokemonGo.store.schema import COLUMNS, Cell, text
from PokemonGo.store.table import RawTable, TableStore

BATCH = 200
"""Rows written per API request."""


class Worksheet(Protocol):
    """The part of a ``gspread`` worksheet this module uses."""

    col_count: int

    def get_all_values(self) -> list[list[object]]:
        """Return every row of the sheet, including the header."""

    def update(self, *, range_name: str, values: list[list[object]]) -> object:
        """Write a block of values starting at a range."""

    def batch_update(self, data: list[dict[str, object]]) -> object:
        """Write several ranges in one request."""

    def append_rows(self, values: list[list[object]]) -> object:
        """Add rows after the last row that has data."""

    def add_cols(self, cols: int) -> object:
        """Add empty columns to the right."""

    def sort(self, *specs: tuple[int, str], range: str) -> object:
        """Sort a range by columns, given as ``(column number, "asc")``."""


def column_letter(number: int) -> str:
    """Convert a 1-based column number to its letter, as in A1 notation.

    Examples
    --------
    >>> column_letter(1), column_letter(26), column_letter(27)
    ('A', 'Z', 'AA')
    """
    letters = ""
    while number > 0:
        number, remainder = divmod(number - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def open_worksheet(key_path: Path, sheet_name: str) -> Worksheet:
    """Open the first sheet of a spreadsheet with a service-account key.

    Parameters
    ----------
    key_path : pathlib.Path
        The service-account JSON key (see the gspread authentication guide).
    sheet_name : str
        The spreadsheet's name.

    Returns
    -------
    Worksheet
        Its first sheet, where the database lives.

    Raises
    ------
    ConfigError
        If ``gspread`` is not installed.
    StoreError
        If the key or spreadsheet cannot be used.
    """
    try:
        import gspread
    except ImportError as error:
        msg = (
            "Google Sheets support is not installed: "
            "pip install 'PokemonGo[sheets]'"
        )
        raise ConfigError(msg) from error
    try:
        client = gspread.service_account(filename=str(key_path))
        sheet: Worksheet = client.open(sheet_name).sheet1
    except (OSError, ValueError, gspread.exceptions.GSpreadException) as error:
        msg = f"cannot open spreadsheet {sheet_name!r}: {error!r}"
        raise StoreError(msg) from error
    return sheet


def read_sheet_table(sheet: Worksheet) -> RawTable:
    """Read a worksheet as a table without interpreting it.

    Parameters
    ----------
    sheet : Worksheet
        The worksheet.

    Returns
    -------
    RawTable
        The header and rows; empty for an empty sheet.
    """
    values = sheet.get_all_values()
    if not values:
        return RawTable([])
    return RawTable([text(c) for c in values[0]], [list(r) for r in values[1:]])


def write_sheet_table(sheet: Worksheet, table: RawTable) -> None:
    """Replace the whole sheet with a table, adding columns if needed.

    Parameters
    ----------
    sheet : Worksheet
        The worksheet.
    table : RawTable
        The header and rows to write.
    """
    everything: list[list[object]] = [list(table.header)]
    everything.extend(list(row) for row in table.rows)
    width = max(len(row) for row in everything)
    if width > sheet.col_count:
        sheet.add_cols(width - sheet.col_count)
    last = column_letter(width)
    for start in range(0, len(everything), BATCH):
        block = [
            row + [""] * (width - len(row))
            for row in everything[start : start + BATCH]
        ]
        first = start + 1
        sheet.update(
            range_name=f"A{first}:{last}{first + len(block) - 1}",
            values=block,
        )


class SheetsStore(TableStore):
    """A gym database stored in a Google Sheet.

    Changed rows are written in batches on commit, touching only the
    rows that changed. Columns a person added are left alone.

    Parameters
    ----------
    sheet : Worksheet
        The worksheet, from :func:`open_worksheet`. An empty sheet gets
        the schema v2 header on the first commit.

    Raises
    ------
    SchemaError
        If the sheet uses the old layout; run ``pogo upgrade``.
    """

    def __init__(self, sheet: Worksheet) -> None:
        self._sheet = sheet
        table = read_sheet_table(sheet)
        empty = not table.header
        super().__init__(RawTable(list(COLUMNS)) if empty else table)
        self._force = empty

    def sort(self) -> None:
        """Sort the sheet by state, county, city and title.

        Saves pending changes first, sorts in the sheet (so formatting
        moves with its rows), and reloads.
        """
        self.commit()
        last = column_letter(len(self._header))
        specs = tuple(
            (self._col[name] + 1, "asc")
            for name in ("state", "county", "city", "title")
        )
        self._sheet.sort(*specs, range=f"A2:{last}{len(self._rows) + 1}")
        reloaded = read_sheet_table(self._sheet)
        self._rows = [self._pad(list(row)) for row in reloaded.rows]
        self._uids = {
            uid: i
            for i, row in enumerate(self._rows)
            if (uid := _uid(row[self._col["uid"]])) is not None
        }
        self._saved = len(self._rows)

    def _flush(self, *, full: bool, dirty: list[int], new: list[int]) -> None:
        width = len(self._header)
        if width > self._sheet.col_count:
            self._sheet.add_cols(width - self._sheet.col_count)
        last = column_letter(width)
        if self._force:
            self._sheet.update(
                range_name=f"A1:{last}1", values=[list(self._header)]
            )
        rows = list(dirty) if not full else list(range(self._saved))
        for start in range(0, len(rows), BATCH):
            data: list[dict[str, object]] = [
                {"range": f"A{i + 2}:{last}{i + 2}", "values": [self._rows[i]]}
                for i in rows[start : start + BATCH]
            ]
            self._sheet.batch_update(data)
        added = [self._rows[i] for i in new]
        for start in range(0, len(added), BATCH):
            self._sheet.append_rows(
                [list(r) for r in added[start : start + BATCH]]
            )


def _uid(value: Cell) -> int | None:
    """Read a uid cell, ignoring cells that are not whole numbers."""
    try:
        raw = text(value)
        return int(float(raw)) if raw else None
    except ValueError:
        return None


__all__ = [
    "SheetsStore",
    "Worksheet",
    "column_letter",
    "open_worksheet",
    "read_sheet_table",
    "write_sheet_table",
]
