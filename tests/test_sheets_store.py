import sys
import types
from pathlib import Path

import pytest

from PokemonGo.errors import ConfigError, SchemaError, StoreError
from PokemonGo.models import Gym
from PokemonGo.store import sheets_store
from PokemonGo.store.schema import COLUMNS
from PokemonGo.store.sheets_store import (
    SheetsStore,
    column_letter,
    open_worksheet,
    read_sheet_table,
    write_sheet_table,
)
from PokemonGo.store.table import RawTable
from tests.support.gyms import many, scanned, seeded
from tests.support.sheets import FakeWorksheet

LAST = column_letter(len(COLUMNS))  # "T"


def _filled() -> tuple[FakeWorksheet, SheetsStore]:
    sheet = FakeWorksheet()
    store = SheetsStore(sheet)
    for gym in (scanned(), seeded()):
        store.add(gym)
    store.commit()
    sheet.calls.clear()
    return sheet, SheetsStore(sheet)


@pytest.mark.parametrize(
    ("number", "letters"),
    [(1, "A"), (20, "T"), (26, "Z"), (27, "AA"), (52, "AZ"), (703, "AAA")],
)
def test_column_letters(number: int, letters: str) -> None:
    assert column_letter(number) == letters


def test_an_empty_sheet_gets_the_header_on_the_first_commit() -> None:
    sheet = FakeWorksheet()
    store = SheetsStore(sheet)
    assert sheet.values == []
    store.commit()
    assert sheet.values == [list(COLUMNS)]
    assert ("update", f"A1:{LAST}1") in sheet.calls


def test_only_changed_rows_are_sent() -> None:
    sheet, store = _filled()
    gyms = store.all()
    gyms[1].city = "somewhere"
    store.update(gyms[1])
    store.commit()
    assert sheet.calls[-1] == ("batch_update", [f"A3:{LAST}3"])
    assert [c for c, _ in sheet.calls if c != "get_all_values"] == [
        "batch_update"
    ]


def test_new_rows_are_appended_not_rewritten() -> None:
    sheet, store = _filled()
    store.add(Gym(9, "new one"))
    store.commit()
    calls = [c for c in sheet.calls if c[0] != "get_all_values"]
    assert calls == [("append_rows", 1)]
    assert len(sheet.values) == 4


def test_nothing_is_sent_when_nothing_changed() -> None:
    sheet, store = _filled()
    store.commit()
    assert [c for c, _ in sheet.calls if c != "get_all_values"] == []


def test_a_narrow_sheet_gets_columns_added() -> None:
    sheet = FakeWorksheet(col_count=10)
    store = SheetsStore(sheet)
    store.add(scanned())
    store.commit()
    assert sheet.col_count == len(COLUMNS)
    assert ("add_cols", len(COLUMNS) - 10) in sheet.calls


def test_the_old_layout_asks_for_an_upgrade() -> None:
    sheet = FakeWorksheet([["uid", "title", "latlon"], ["1", "a", "1,2"]])
    with pytest.raises(SchemaError, match="pogo upgrade"):
        SheetsStore(sheet)


def test_numbers_typed_into_the_sheet_are_read_back() -> None:
    sheet = FakeWorksheet()
    store = SheetsStore(sheet)
    store.add(scanned())
    store.commit()
    row = sheet.values[1]
    assert isinstance(row[COLUMNS.index("victories")], int)
    assert isinstance(row[COLUMNS.index("latitude")], float)
    assert SheetsStore(sheet).all()[0].activity == scanned().activity


def test_sorting_uses_the_sheet_and_reloads() -> None:
    sheet = FakeWorksheet()
    store = SheetsStore(sheet)
    for gym in many():
        store.add(gym)
    store.sort()
    assert any(call[0] == "sort" for call in sheet.calls)
    assert store.all()[0].title == "banana"
    # the uid index was rebuilt, so duplicates are still caught
    with pytest.raises(StoreError, match="already used"):
        store.add(Gym(4, "dup"))


def test_columns_a_person_added_are_left_alone() -> None:
    header: list[object] = [*COLUMNS, "my own notes"]
    row: list[object] = [""] * len(header)
    row[0], row[1], row[-1] = "5", "real", "keep me"
    sheet = FakeWorksheet([header, row])
    store = SheetsStore(sheet)
    gym = store.all()[0]
    gym.notes = "changed"
    store.update(gym)
    store.commit()
    assert sheet.values[1][-1] == "keep me"
    assert sheet.values[1][COLUMNS.index("notes")] == "changed"


def test_reading_and_writing_whole_tables_in_batches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sheets_store, "BATCH", 3)
    sheet = FakeWorksheet(col_count=2)
    rows: list[list[object]] = [[str(i), f"gym {i}", "x"] for i in range(7)]
    write_sheet_table(sheet, RawTable(["uid", "title", "extra"], rows))
    updates = [c for c in sheet.calls if c[0] == "update"]
    assert [c[1] for c in updates] == ["A1:C3", "A4:C6", "A7:C8"]
    assert sheet.col_count == 3
    table = read_sheet_table(sheet)
    assert table.header == ["uid", "title", "extra"]
    assert len(table.rows) == 7
    assert read_sheet_table(FakeWorksheet()).header == []


def test_open_worksheet_without_gspread(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "gspread", None)
    with pytest.raises(ConfigError, match=r"PokemonGo\[sheets\]"):
        open_worksheet(Path("key.json"), "gyms")


class RecordingSheet:
    """Stands in for a real ``gspread`` worksheet, recording every call.

    It has gspread's shape on purpose: ``col_count`` is a plain value read
    by the adapter, and ``get_all_values`` returns lists of strings.
    """

    col_count = 14

    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []

    def get_all_values(self) -> list[list[str]]:
        self.calls.append(("get_all_values", None))
        return [["uid", "title"], ["1", "a"]]

    def update(self, **kwargs: object) -> str:
        self.calls.append(("update", kwargs))
        return "updated"

    def batch_update(self, data: object) -> str:
        self.calls.append(("batch_update", data))
        return "batched"

    def append_rows(self, values: object) -> str:
        self.calls.append(("append_rows", values))
        return "appended"

    def add_cols(self, cols: int) -> None:
        self.calls.append(("add_cols", cols))

    def sort(self, *specs: object, **kwargs: object) -> str:
        self.calls.append(("sort", (specs, kwargs)))
        return "sorted"


def _fake_gspread(
    monkeypatch: pytest.MonkeyPatch, *, fail: bool, sheet: object = None
) -> list[object]:
    seen: list[object] = []
    module = types.ModuleType("gspread")

    class GSpreadError(Exception):
        pass

    module.exceptions = types.SimpleNamespace(GSpreadException=GSpreadError)  # type: ignore[attr-defined]

    def service_account(filename: str) -> object:
        seen.append(filename)
        if fail:
            raise GSpreadError("denied")

        def open_sheet(name: str) -> object:
            seen.append(name)
            return types.SimpleNamespace(sheet1=sheet)

        return types.SimpleNamespace(open=open_sheet)

    module.service_account = service_account  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "gspread", module)
    return seen


def test_open_worksheet_opens_the_first_sheet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = RecordingSheet()
    seen = _fake_gspread(monkeypatch, fail=False, sheet=real)
    worksheet = open_worksheet(Path("key.json"), "gym_data")
    assert seen == ["key.json", "gym_data"]
    assert worksheet.col_count == 14
    assert real.calls == []  # opening does not read the sheet


def test_the_adapter_passes_every_call_to_the_real_worksheet(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real = RecordingSheet()
    _fake_gspread(monkeypatch, fail=False, sheet=real)
    worksheet = open_worksheet(Path("key.json"), "gym_data")

    assert worksheet.get_all_values() == [["uid", "title"], ["1", "a"]]
    worksheet.update(range_name="A1:B1", values=[["x", 1]])
    worksheet.batch_update([{"range": "A2:B2", "values": [["y", 2.5]]}])
    worksheet.append_rows([["z", 3]])
    worksheet.add_cols(6)
    worksheet.sort((4, "asc"), (3, "asc"), range="A2:T9")

    assert real.calls == [
        ("get_all_values", None),
        ("update", {"values": [["x", 1]], "range_name": "A1:B1"}),
        ("batch_update", [{"range": "A2:B2", "values": [["y", 2.5]]}]),
        ("append_rows", [["z", 3]]),
        ("add_cols", 6),
        ("sort", (((4, "asc"), (3, "asc")), {"range": "A2:T9"})),
    ]


def test_open_worksheet_reports_a_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _fake_gspread(monkeypatch, fail=True)
    with pytest.raises(StoreError, match="cannot open spreadsheet 'gym_data'"):
        open_worksheet(Path("key.json"), "gym_data")


def test_a_store_works_through_the_adapter(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole path: real-shaped worksheet, adapter, store."""
    real = RecordingSheet()
    real.get_all_values = lambda: [list(COLUMNS)]  # type: ignore[method-assign]
    _fake_gspread(monkeypatch, fail=False, sheet=real)
    store = SheetsStore(open_worksheet(Path("key.json"), "gym_data"))
    store.add(scanned())
    store.commit()
    # the fake sheet has 14 columns; the store needs 20, so it adds 6 first
    assert [kind for kind, _ in real.calls] == ["add_cols", "append_rows"]
    assert real.calls[0] == ("add_cols", len(COLUMNS) - 14)
