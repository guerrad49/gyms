"""An in-memory stand-in for a gspread worksheet."""

import re
from datetime import date

_A1 = re.compile(r"^([A-Z]+)(\d+)(?::([A-Z]+)(\d+))?$")


def _column_number(letters: str) -> int:
    number = 0
    for char in letters:
        number = number * 26 + ord(char) - 64
    return number


class FakeWorksheet:
    """Implements the part of a worksheet that the Sheets store uses.

    Like the real API, :meth:`get_all_values` returns every cell as text.
    Every write is recorded in :attr:`calls`, so tests can check that only
    the rows that changed were sent.
    """

    def __init__(
        self, values: list[list[object]] | None = None, col_count: int = 26
    ) -> None:
        self.values: list[list[object]] = [list(r) for r in values or []]
        self.col_count = col_count
        self.calls: list[tuple[str, object]] = []

    def get_all_values(self) -> list[list[object]]:
        self.calls.append(("get_all_values", None))
        return [
            ["" if cell is None else str(cell) for cell in row]
            for row in self.values
        ]

    def _write(self, range_name: str, block: list[list[object]]) -> None:
        match = _A1.match(range_name)
        assert match, range_name
        col = _column_number(match.group(1))
        row = int(match.group(2))
        for r, cells in enumerate(block):
            while len(self.values) < row + r:
                self.values.append([])
            target = self.values[row + r - 1]
            while len(target) < col - 1 + len(cells):
                target.append("")
            for c, cell in enumerate(cells):
                target[col - 1 + c] = cell

    def update(self, *, range_name: str, values: list[list[object]]) -> None:
        self.calls.append(("update", range_name))
        self._write(range_name, values)

    def batch_update(self, data: list[dict[str, object]]) -> None:
        self.calls.append(("batch_update", [d["range"] for d in data]))
        for item in data:
            self._write(str(item["range"]), item["values"])  # type: ignore[arg-type]

    def append_rows(self, values: list[list[object]]) -> None:
        self.calls.append(("append_rows", len(values)))
        self.values.extend(list(row) for row in values)

    def add_cols(self, cols: int) -> None:
        self.calls.append(("add_cols", cols))
        self.col_count += cols

    def sort(self, *specs: tuple[int, str], range: str) -> None:
        self.calls.append(("sort", range))
        match = _A1.match(range)
        assert match
        first, last = int(match.group(2)), int(match.group(4))
        block = self.values[first - 1 : last]

        def key(row: list[object]) -> list[tuple[bool, str]]:
            out = []
            for number, _order in specs:
                cell = row[number - 1] if number - 1 < len(row) else ""
                text = "" if cell is None else str(cell)
                out.append((text == "", text.lower()))
            return out

        block.sort(key=key)
        self.values[first - 1 : last] = block


def today() -> date:
    return date(2026, 11, 2)
