from pathlib import Path

import pytest

from PokemonGo import doctor
from PokemonGo.cli import main
from PokemonGo.config import Settings
from PokemonGo.doctor import Check


def _env(tmp_path: Path) -> Path:
    (tmp_path / "downloads").mkdir()
    env = tmp_path / "variables.env"
    env.write_text(
        "EMAIL=me@example.com\nBACKEND=csv\nCSV_PATH=gyms.csv\n"
        "SOURCE=downloads\nBADGES=badges\n",
        encoding="utf-8",
    )
    return env


def _fake_checks(monkeypatch: pytest.MonkeyPatch, checks: list[Check]) -> None:
    def run(settings: Settings) -> list[Check]:
        return checks

    monkeypatch.setattr(doctor, "run_checks", run)


def test_doctor_reports_success(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _fake_checks(monkeypatch, [Check("tesseract", True, "5.5.0")])
    assert main(["doctor", "--env-file", str(_env(tmp_path))]) == 0
    out = capsys.readouterr().out
    assert "[ok]   tesseract: 5.5.0" in out
    assert "Everything is in place." in out


def test_doctor_lists_every_failure_and_exits_with_an_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _fake_checks(
        monkeypatch,
        [
            Check("tesseract", False, "not found"),
            Check("settings", True, "backend: csv"),
            Check("database", False, "old layout"),
        ],
    )
    assert main(["doctor", "--env-file", str(_env(tmp_path))]) == 1
    out = capsys.readouterr().out
    assert "[FAIL] tesseract: not found" in out
    assert "[ok]   settings: backend: csv" in out
    assert "[FAIL] database: old layout" in out
    assert "2 problem(s) to fix before scanning." in out


@pytest.mark.ocr
def test_doctor_with_the_real_checks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["doctor", "--env-file", str(_env(tmp_path))]) == 0
    out = capsys.readouterr().out
    for name in (
        "python",
        "tesseract",
        "settings",
        "database",
        "badges folder",
    ):
        assert f"[ok]   {name}:" in out
    assert "0 gyms (0 scanned, 0 seeded)" in out
