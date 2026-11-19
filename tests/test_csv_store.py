import csv
from pathlib import Path

import pytest

from PokemonGo.errors import SchemaError, StoreError
from PokemonGo.store.csv_store import CsvStore, format_cell, read_csv_table
from PokemonGo.store.schema import COLUMNS
from tests.support.gyms import scanned, seeded

HEADER = ",".join(COLUMNS)


def _write(path: Path, *lines: str, header: str = HEADER) -> Path:
    path.write_text("\n".join([header, *lines]) + "\n", encoding="utf-8")
    return path


def test_the_file_is_created_on_the_first_commit(tmp_path: Path) -> None:
    path = tmp_path / "new" / "gyms.csv"
    store = CsvStore(path)
    assert not path.exists()
    store.commit()
    assert path.read_text(encoding="utf-8").strip() == HEADER


def test_an_empty_file_is_treated_as_new(tmp_path: Path) -> None:
    path = tmp_path / "gyms.csv"
    path.write_text("", encoding="utf-8")
    store = CsvStore(path)
    store.add(scanned())
    store.commit()
    assert len(CsvStore(path).all()) == 1


def test_nothing_is_written_when_nothing_changed(tmp_path: Path) -> None:
    path = _write(tmp_path / "gyms.csv")
    before = path.stat().st_mtime_ns
    CsvStore(path).commit()
    assert path.stat().st_mtime_ns == before


def test_the_old_layout_asks_for_an_upgrade(tmp_path: Path) -> None:
    path = tmp_path / "v1.csv"
    path.write_text('uid,title,latlon\n1,a,"1,2"\n', encoding="utf-8")
    with pytest.raises(SchemaError, match="pogo upgrade"):
        CsvStore(path)


def test_a_missing_column_is_named(tmp_path: Path) -> None:
    header = HEADER.replace(",notes", "")
    with pytest.raises(SchemaError, match="notes"):
        CsvStore(_write(tmp_path / "x.csv", header=header))


def test_writing_leaves_no_temporary_files(tmp_path: Path) -> None:
    path = tmp_path / "gyms.csv"
    store = CsvStore(path)
    store.add(scanned())
    store.commit()
    assert [p.name for p in tmp_path.iterdir()] == ["gyms.csv"]


def test_text_with_commas_quotes_and_newlines_round_trips(
    tmp_path: Path,
) -> None:
    path = tmp_path / "gyms.csv"
    store = CsvStore(path)
    store.add(scanned())
    store.commit()
    with path.open(newline="", encoding="utf-8") as handle:
        [row] = list(csv.DictReader(handle))
    assert row["notes"] == 'line one, with a comma\nline two with "quotes"'
    assert row["latitude"] == "-13.329799"


def test_coordinates_keep_their_exact_digits(tmp_path: Path) -> None:
    path = tmp_path / "gyms.csv"
    store = CsvStore(path)
    gym = seeded()
    store.add(gym)
    store.commit()
    again = CsvStore(path).all()[0]
    assert again.coordinates == gym.coordinates


def test_duplicate_uids_in_a_file_are_reported(tmp_path: Path) -> None:
    row = ["1", "a"] + [""] * (len(COLUMNS) - 2)
    path = _write(tmp_path / "x.csv", ",".join(row), ",".join(row))
    with pytest.raises(StoreError, match="uid 1 is already used by row 2"):
        CsvStore(path)


@pytest.mark.parametrize(
    ("column", "value", "message"),
    [
        ("victories", "abc", "row 2: victories must be a whole number"),
        ("latitude", "x", "row 2: latitude must be a number"),
        ("scanned_at", "someday", "row 2: scanned_at must be a date"),
        ("status", "BOGUS", "row 2: unknown status flag"),
        ("uid", "1.5", "row 2: uid must be a whole number"),
    ],
)
def test_a_bad_cell_names_its_row(
    tmp_path: Path, column: str, value: str, message: str
) -> None:
    cells = dict.fromkeys(COLUMNS, "")
    cells.update(title="x", latitude="1", longitude="2")
    cells[column] = value
    path = _write(tmp_path / "x.csv", ",".join(cells.values()))
    with pytest.raises(StoreError, match=message):
        CsvStore(path).all()


def test_partly_filled_statistics_are_an_error(tmp_path: Path) -> None:
    cells = dict.fromkeys(COLUMNS, "")
    cells.update(title="x", victories="1", days="2")
    path = _write(tmp_path / "x.csv", ",".join(cells.values()))
    with pytest.raises(StoreError, match="only partly filled"):
        CsvStore(path).all()


def test_one_coordinate_without_the_other_is_an_error(tmp_path: Path) -> None:
    cells = dict.fromkeys(COLUMNS, "")
    cells.update(title="x", latitude="1")
    path = _write(tmp_path / "x.csv", ",".join(cells.values()))
    with pytest.raises(StoreError, match="both be set or both blank"):
        CsvStore(path).all()


def test_blank_rows_are_skipped_but_keep_their_numbers(tmp_path: Path) -> None:
    blank = "," * (len(COLUMNS) - 1)
    full = dict.fromkeys(COLUMNS, "")
    full.update(uid="5", title="real")
    path = _write(tmp_path / "x.csv", blank, ",".join(full.values()))
    [gym] = CsvStore(path).all()
    assert (gym.uid, gym.row) == (5, 3)


def test_extra_columns_and_short_rows_are_preserved(tmp_path: Path) -> None:
    header = HEADER + ",my own notes"
    full = dict.fromkeys(COLUMNS, "")
    full.update(uid="5", title="real")
    path = _write(
        tmp_path / "x.csv",
        ",".join(full.values()) + ",keep me",
        "6,short",
        header=header,
    )
    store = CsvStore(path)
    gyms = store.all()
    gyms[0].notes = "changed"
    store.update(gyms[0])
    store.commit()
    rows = list(csv.DictReader(path.open(encoding="utf-8")))
    assert rows[0]["my own notes"] == "keep me"
    assert rows[0]["notes"] == "changed"
    assert rows[1]["title"] == "short"


def test_a_byte_order_mark_is_accepted(tmp_path: Path) -> None:
    path = tmp_path / "x.csv"
    path.write_text("\ufeff" + HEADER + "\n", encoding="utf-8")
    assert read_csv_table(path).header[0] == "uid"


def test_an_unreadable_file_is_a_store_error(tmp_path: Path) -> None:
    path = tmp_path / "x.csv"
    path.write_bytes(b"\xff\xfe\x00bad")
    with pytest.raises(StoreError, match="cannot read"):
        read_csv_table(path)


def test_format_cell() -> None:
    assert format_cell(None) == ""
    assert format_cell(7) == "7"
    assert format_cell(22.0431) == "22.0431"
    assert format_cell("text") == "text"


def test_a_failed_write_keeps_the_original_and_leaves_no_temp_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _write(tmp_path / "gyms.csv")
    original = path.read_bytes()
    store = CsvStore(path)
    store.add(scanned())

    def fail(*_args: object, **_kwargs: object) -> None:
        msg = "disk full"
        raise OSError(msg)

    monkeypatch.setattr("os.replace", fail)
    with pytest.raises(StoreError, match=r"cannot write.*disk full"):
        store.commit()
    assert path.read_bytes() == original
    assert [p.name for p in tmp_path.iterdir()] == ["gyms.csv"]
