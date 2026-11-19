"""A gym database in a plain CSV file."""

from __future__ import annotations

import csv
import os
import tempfile
from pathlib import Path

from PokemonGo.errors import StoreError
from PokemonGo.store.schema import COLUMNS, Cell
from PokemonGo.store.table import RawTable, TableStore


def format_cell(value: Cell) -> str:
    """Format a cell for a CSV file.

    Floats use their shortest exact form, so coordinates survive a round
    trip.

    Examples
    --------
    >>> format_cell(None), format_cell(448), format_cell(22.0431)
    ('', '448', '22.0431')
    """
    if value is None:
        return ""
    if isinstance(value, float):
        return repr(value)
    return str(value)


def read_csv_table(path: Path) -> RawTable:
    """Read a CSV file as a table without interpreting it.

    Parameters
    ----------
    path : pathlib.Path
        The file. A UTF-8 byte-order mark is accepted.

    Returns
    -------
    RawTable
        The header and rows; empty for an empty file.

    Raises
    ------
    StoreError
        If the file cannot be read.
    """
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            rows = [list(row) for row in csv.reader(handle)]
    except (OSError, UnicodeDecodeError, csv.Error) as error:
        msg = f"cannot read {path}: {error}"
        raise StoreError(msg) from error
    if not rows:
        return RawTable([])
    return RawTable(rows[0], [list(row) for row in rows[1:]])


def write_csv_table(path: Path, table: RawTable) -> None:
    """Write a table to a CSV file atomically.

    The data goes to a temporary file in the same folder, which then
    replaces the target, so a crash never leaves a half-written file.

    Parameters
    ----------
    path : pathlib.Path
        The file to create or replace.
    table : RawTable
        The table to write.

    Raises
    ------
    StoreError
        If the file cannot be written.
    """
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(
            dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
        )
        try:
            with os.fdopen(descriptor, "w", newline="", encoding="utf-8") as fh:
                writer = csv.writer(fh)
                writer.writerow(table.header)
                for row in table.rows:
                    writer.writerow([format_cell(cell) for cell in row])
            os.replace(name, path)
        except BaseException:
            Path(name).unlink(missing_ok=True)
            raise
    except OSError as error:
        msg = f"cannot write {path}: {error}"
        raise StoreError(msg) from error


class CsvStore(TableStore):
    """A gym database stored as a CSV file.

    The file is created, with the schema v2 header, on the first commit if
    it does not exist. The whole file is rewritten atomically on commit.

    Parameters
    ----------
    path : pathlib.Path
        The CSV file.

    Raises
    ------
    SchemaError
        If the file uses the old layout; run ``pogo upgrade``.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        exists = path.is_file() and path.stat().st_size > 0
        table = read_csv_table(path) if exists else RawTable(list(COLUMNS))
        super().__init__(table)
        self._force = not exists

    def _flush(self, *, full: bool, dirty: list[int], new: list[int]) -> None:
        write_csv_table(self.path, RawTable(self._header, self._rows))
