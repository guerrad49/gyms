import builtins
import csv
from pathlib import Path

import pytest

from PokemonGo import store as store_module
from PokemonGo.cli import main
from PokemonGo.store.csv_store import CsvStore, read_csv_table
from PokemonGo.store.schema import COLUMNS, LEGACY_COLUMNS
from tests.support.sheets import FakeWorksheet

V1_ROWS = [
    "1186,agricultural laboratory,i15,gold,2,22,1,2,22.0431,20,"
    '"-13.329799,-72.195433",huarocondo,,cusco',
    "931,looking north,i11,gold,0,21,17,0,21.7083,81,"
    '"43.623893,-70.211253",cape elizabeth,cumberland,maine',
]


def _v1(path: Path) -> Path:
    path.write_text(
        ",".join(LEGACY_COLUMNS) + "\n" + "\n".join(V1_ROWS) + "\n",
        encoding="utf-8",
    )
    return path


def test_upgrade_dry_run_shows_the_plan_and_changes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _v1(tmp_path / "gyms.csv")
    before = path.read_bytes()
    status = main(
        [
            "upgrade",
            "--backend",
            "csv",
            "--csv-path",
            str(path),
            "--dry-run",
            "--backups",
            str(tmp_path / "bk"),
        ]
    )
    out = capsys.readouterr().out
    assert status == 0
    assert "2 gyms" in out
    assert "remove columns : latlon" in out
    assert "add columns" in out
    assert "Dry run" in out
    assert path.read_bytes() == before
    assert not (tmp_path / "bk").exists()


def test_upgrade_writes_a_backup_then_upgrades(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _v1(tmp_path / "gyms.csv")
    original = read_csv_table(path)
    status = main(
        [
            "upgrade",
            "--backend",
            "csv",
            "--csv-path",
            str(path),
            "--yes",
            "--backups",
            str(tmp_path / "bk"),
        ]
    )
    assert status == 0
    assert "Done. 2 gyms verified." in capsys.readouterr().out
    [backup] = list((tmp_path / "bk").iterdir())
    assert read_csv_table(backup) == original  # the backup is the old file
    assert read_csv_table(path).header[:12] == list(COLUMNS)[:12]
    assert [g.uid for g in CsvStore(path).all()] == [1186, 931]


@pytest.mark.parametrize(("answer", "status"), [("y", 0), ("n", 1), ("", 1)])
def test_upgrade_asks_before_changing_anything(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    answer: str,
    status: int,
) -> None:
    path = _v1(tmp_path / "gyms.csv")
    before = path.read_bytes()
    monkeypatch.setattr(builtins, "input", lambda _prompt: answer)
    code = main(
        [
            "upgrade",
            "--backend",
            "csv",
            "--csv-path",
            str(path),
            "--backups",
            str(tmp_path / "bk"),
        ]
    )
    assert code == status
    if status:
        assert "Cancelled" in capsys.readouterr().out
        assert path.read_bytes() == before
    else:
        assert "latitude" in path.read_text(encoding="utf-8")


def test_upgrading_twice_is_harmless(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _v1(tmp_path / "gyms.csv")
    args = [
        "upgrade",
        "--backend",
        "csv",
        "--csv-path",
        str(path),
        "--yes",
        "--backups",
        str(tmp_path / "bk"),
    ]
    assert main(args) == 0
    capsys.readouterr()
    assert main(args) == 0
    assert "Already on schema v2 (2 gyms)" in capsys.readouterr().out
    assert len(list((tmp_path / "bk").iterdir())) == 1


def test_upgrade_of_an_empty_file_and_of_sqlite(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    empty = tmp_path / "empty.csv"
    empty.write_text("", encoding="utf-8")
    assert main(["upgrade", "--backend", "csv", "--csv-path", str(empty)]) == 0
    assert "nothing to upgrade" in capsys.readouterr().out
    assert main(["upgrade", "--backend", "sqlite", "--db-path", "x.db"]) == 0
    assert "current schema" in capsys.readouterr().out


def test_settings_come_from_an_env_file(tmp_path: Path) -> None:
    path = _v1(tmp_path / "gyms.csv")
    env = tmp_path / "variables.env"
    env.write_text("BACKEND=csv\nCSV_PATH=gyms.csv\n", encoding="utf-8")
    args = [
        "upgrade",
        "--env-file",
        str(env),
        "--yes",
        "--backups",
        str(tmp_path / "bk"),
    ]
    assert main(args) == 0
    assert "latitude" in path.read_text(encoding="utf-8")


def test_a_full_upgrade_of_a_google_sheet(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    rows: list[list[object]] = [list(LEGACY_COLUMNS)]
    rows.extend(list(next(csv.reader([line]))) for line in V1_ROWS)
    sheet = FakeWorksheet(rows, col_count=14)
    monkeypatch.setattr(store_module, "open_worksheet", lambda key, name: sheet)
    env = tmp_path / "variables.env"
    env.write_text(
        f"SHEET_NAME=gym_data\nJSON_KEY={tmp_path}/k.json\n", encoding="utf-8"
    )
    status = main(
        [
            "upgrade",
            "--env-file",
            str(env),
            "--yes",
            "--backups",
            str(tmp_path / "bk"),
        ]
    )
    assert status == 0
    assert "Done. 2 gyms verified." in capsys.readouterr().out
    header = sheet.values[0]
    assert header[: len(COLUMNS)] == list(COLUMNS)
    assert "latlon" not in header
    assert sheet.values[1][COLUMNS.index("latitude")] == -13.329799
    assert sheet.col_count >= len(COLUMNS)
    assert len(list((tmp_path / "bk").iterdir())) == 1


def test_other_commands_tell_you_to_upgrade_first(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _v1(tmp_path / "gyms.csv")
    status = main(
        [
            "migrate",
            "--from",
            "csv",
            "--to",
            "sqlite",
            "--csv-path",
            str(path),
            "--db-path",
            str(tmp_path / "g.db"),
        ]
    )
    assert status == 1
    assert "pogo upgrade" in capsys.readouterr().err


def test_migrate_copies_to_another_backend(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _v1(tmp_path / "gyms.csv")
    main(
        [
            "upgrade",
            "--backend",
            "csv",
            "--csv-path",
            str(path),
            "--yes",
            "--backups",
            str(tmp_path / "bk"),
        ]
    )
    capsys.readouterr()
    db = tmp_path / "g.db"
    status = main(
        [
            "migrate",
            "--from",
            "csv",
            "--to",
            "sqlite",
            "--csv-path",
            str(path),
            "--db-path",
            str(db),
        ]
    )
    assert status == 0
    assert "Copied 2 gyms from csv to sqlite." in capsys.readouterr().out
    again = main(
        [
            "migrate",
            "--from",
            "csv",
            "--to",
            "sqlite",
            "--csv-path",
            str(path),
            "--db-path",
            str(db),
        ]
    )
    assert again == 1
    assert "not empty" in capsys.readouterr().err


def test_migrate_needs_two_different_backends(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["migrate", "--from", "csv", "--to", "csv"]) == 1
    assert "must be different" in capsys.readouterr().err


def test_export_my_maps(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _v1(tmp_path / "gyms.csv")
    main(
        [
            "upgrade",
            "--backend",
            "csv",
            "--csv-path",
            str(path),
            "--yes",
            "--backups",
            str(tmp_path / "bk"),
        ]
    )
    capsys.readouterr()
    out = tmp_path / "maps.csv"
    status = main(
        [
            "export",
            "my-maps",
            str(out),
            "--backend",
            "csv",
            "--csv-path",
            str(path),
        ]
    )
    assert status == 0
    assert "Wrote 2 gyms" in capsys.readouterr().out
    assert out.read_text(encoding="utf-8").startswith(
        "title,latitude,longitude"
    )


def test_a_missing_setting_is_reported(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.chdir(tmp_path)
    assert main(["export", "my-maps", "out.csv", "--backend", "csv"]) == 1
    assert "CSV_PATH is required" in capsys.readouterr().err


def test_variables_env_in_the_working_folder_is_found_automatically(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _v1(tmp_path / "gyms.csv")
    (tmp_path / "variables.env").write_text(
        "BACKEND=csv\nCSV_PATH=gyms.csv\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    assert main(["upgrade", "--dry-run"]) == 0
    assert "Upgrading the csv database (2 gyms)" in capsys.readouterr().out


def test_unreadable_coordinates_are_listed_in_the_plan(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "gyms.csv"
    row = V1_ROWS[0].replace('"-13.329799,-72.195433"', "nowhere")
    path.write_text(
        ",".join(LEGACY_COLUMNS) + "\n" + row + "\n", encoding="utf-8"
    )
    args = ["upgrade", "--backend", "csv", "--csv-path", str(path), "--dry-run"]
    assert main(args) == 0
    assert "row 2: unreadable coordinates 'nowhere' (flagged)" in (
        capsys.readouterr().out
    )


def test_an_upgrade_that_loses_gyms_is_reported(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = _v1(tmp_path / "gyms.csv")

    class Empty:
        def all(self) -> list[object]:
            return []

    monkeypatch.setattr(store_module, "open_store", lambda *_a: Empty())
    status = main(
        [
            "upgrade",
            "--backend",
            "csv",
            "--csv-path",
            str(path),
            "--yes",
            "--backups",
            str(tmp_path / "bk"),
        ]
    )
    assert status == 1
    assert "upgrade check failed: 0 gyms found, expected 2" in (
        capsys.readouterr().err
    )
    assert len(list((tmp_path / "bk").iterdir())) == 1  # the backup remains
