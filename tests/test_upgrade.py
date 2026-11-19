from pathlib import Path

from PokemonGo.models import Flag
from PokemonGo.store.csv_store import CsvStore, read_csv_table, write_csv_table
from PokemonGo.store.schema import COLUMNS, LEGACY_COLUMNS
from PokemonGo.store.table import RawTable
from PokemonGo.store.upgrade import backup_table, needs_upgrade, upgrade_table

V1 = [
    [
        "1186",
        "agricultural laboratory",
        "i15",
        "gold",
        "2",
        "22",
        "1",
        "2",
        "22.0431",
        "20",
        "-13.329799,-72.195433",
        "huarocondo",
        "",
        "cusco",
    ],
    [
        "931",
        "looking north",
        "i11",
        "gold",
        "0",
        "21",
        "17",
        "0",
        "21.7083",
        "81",
        "43.623893,-70.211253",
        "cape elizabeth",
        "cumberland",
        "maine",
    ],
]


def _v1(rows: list[list[str]] | None = None) -> RawTable:
    return RawTable(list(LEGACY_COLUMNS), [list(r) for r in (rows or V1)])


def _cell(table: RawTable, row: int, name: str) -> object:
    return table.rows[row][table.header.index(name)]


def test_needs_upgrade() -> None:
    assert needs_upgrade(LEGACY_COLUMNS)
    assert needs_upgrade(["uid", "title"])
    assert not needs_upgrade(COLUMNS)
    assert not needs_upgrade([*COLUMNS, "extra"])


def test_latlon_is_split_into_numbers() -> None:
    new, plan = upgrade_table(_v1())
    assert new.header == list(COLUMNS)
    assert _cell(new, 0, "latitude") == -13.329799
    assert _cell(new, 0, "longitude") == -72.195433
    assert "latlon" not in new.header
    assert plan.rows == 2
    assert plan.dropped == ("latlon",)
    assert plan.added == (
        "latitude",
        "longitude",
        "country",
        "status",
        "scanned_at",
        "notes",
        "image_sha256",
    )
    assert plan.bad_coordinates == ()


def test_existing_values_are_untouched() -> None:
    new, _ = upgrade_table(_v1())
    for name in ("uid", "title", "model", "style", "defended", "city", "state"):
        old = V1[0][LEGACY_COLUMNS.index(name)]
        assert _cell(new, 0, name) == old


def test_the_result_loads_as_a_valid_database(tmp_path: Path) -> None:
    new, _ = upgrade_table(_v1())
    path = tmp_path / "v2.csv"
    write_csv_table(path, new)
    gyms = CsvStore(path).all()
    assert [g.uid for g in gyms] == [1186, 931]
    assert gyms[0].coordinates is not None
    assert gyms[0].coordinates.latitude == -13.329799
    assert gyms[1].county == "cumberland"
    assert gyms[1].model == "i11"


def test_a_pandas_index_column_and_a_missing_model_are_handled() -> None:
    header = ["", *(c for c in LEGACY_COLUMNS if c != "model")]
    rows: list[list[object]] = [
        ["0", *(v for i, v in enumerate(V1[0]) if LEGACY_COLUMNS[i] != "model")]
    ]
    new, plan = upgrade_table(RawTable(header, rows))
    assert plan.dropped == ("(unnamed index column)", "latlon")
    assert "model" in plan.added
    assert _cell(new, 0, "uid") == "1186"
    assert _cell(new, 0, "model") == ""


def test_unreadable_coordinates_are_flagged_not_lost() -> None:
    rows = [list(V1[0]), list(V1[1])]
    rows[1][LEGACY_COLUMNS.index("latlon")] = "somewhere over the rainbow"
    new, plan = upgrade_table(_v1(rows))
    assert plan.bad_coordinates == ((3, "somewhere over the rainbow"),)
    assert _cell(new, 1, "latitude") == ""
    assert _cell(new, 1, "status") == "NO_COORDS"
    assert _cell(new, 1, "title") == "looking north"  # nothing else is lost


def test_blank_coordinates_on_a_real_row_are_flagged() -> None:
    rows = [list(V1[0])]
    rows[0][LEGACY_COLUMNS.index("latlon")] = ""
    new, plan = upgrade_table(_v1(rows))
    assert plan.bad_coordinates == ((2, ""),)
    assert Flag.NO_COORDS.value == _cell(new, 0, "status")


def test_blank_rows_stay_blank_and_are_not_counted() -> None:
    blank = [""] * len(LEGACY_COLUMNS)
    new, plan = upgrade_table(_v1([V1[0], blank]))
    assert plan.rows == 1
    assert _cell(new, 1, "status") == ""
    assert plan.bad_coordinates == ()


def test_extra_columns_are_kept_after_the_canonical_ones() -> None:
    table = RawTable([*LEGACY_COLUMNS, "my notes"], [[*V1[0], "keep me"]])
    new, _ = upgrade_table(table)
    assert new.header == [*COLUMNS, "my notes"]
    assert _cell(new, 0, "my notes") == "keep me"


def test_a_short_row_is_padded() -> None:
    new, _ = upgrade_table(_v1([["7", "short"]]))
    assert _cell(new, 0, "title") == "short"
    assert _cell(new, 0, "latitude") == ""


def test_a_current_table_comes_back_unchanged() -> None:
    table = RawTable(list(COLUMNS), [[""] * len(COLUMNS)])
    new, plan = upgrade_table(table)
    assert new is table
    assert not plan.changes_anything


def test_a_partly_upgraded_table_gets_only_the_missing_columns() -> None:
    header = [c for c in COLUMNS if c not in ("country", "notes")]
    row: list[object] = ["5", "x", *[""] * (len(header) - 2)]
    new, plan = upgrade_table(RawTable(header, [row]))
    assert plan.added == ("country", "notes")
    assert plan.dropped == ()
    assert new.header == list(COLUMNS)


def test_upgrading_twice_changes_nothing_the_second_time() -> None:
    once, _ = upgrade_table(_v1())
    twice, plan = upgrade_table(once)
    assert twice is once
    assert not plan.changes_anything


def test_a_backup_is_written_with_the_original_content(tmp_path: Path) -> None:
    table = _v1()
    path = backup_table(table, tmp_path / "backups", "csv")
    assert path.parent == tmp_path / "backups"
    assert path.name.startswith("csv-")
    assert read_csv_table(path) == table
