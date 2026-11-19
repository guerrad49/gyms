from pathlib import Path

import pytest

from PokemonGo.config import Backend, Settings
from PokemonGo.doctor import Check, run_checks, tesseract_version
from PokemonGo.errors import PogoError, SchemaError
from PokemonGo.models import Activity, Coordinates, Gym
from PokemonGo.store.base import GymStore
from PokemonGo.store.csv_store import CsvStore


def _settings(tmp_path: Path, **changes: object) -> Settings:
    (tmp_path / "downloads").mkdir(exist_ok=True)
    base = {
        "backend": Backend.CSV,
        "csv_path": tmp_path / "gyms.csv",
        "email": "me@example.com",
        "source": tmp_path / "downloads",
        "badges": tmp_path / "badges",
    }
    return Settings(**{**base, **changes})  # type: ignore[arg-type]


def _ok_tesseract() -> str:
    return "5.5.0"


def _by_name(checks: list[Check]) -> dict[str, Check]:
    return {c.name: c for c in checks}


def test_everything_in_place(tmp_path: Path) -> None:
    store = CsvStore(tmp_path / "gyms.csv")
    store.add(Gym(1, "a", Coordinates(1, 2), activity=Activity(1, 1, 1, 1, 1)))
    store.add(Gym(None, "seed", Coordinates(3, 4)))
    store.commit()
    checks = _by_name(run_checks(_settings(tmp_path), tesseract=_ok_tesseract))
    assert all(c.ok for c in checks.values())
    assert checks["tesseract"].detail == "5.5.0"
    assert checks["settings"].detail == "backend: csv"
    assert checks["database"].detail == "2 gyms (1 scanned, 1 seeded)"
    assert "0 screenshots" in checks["source folder"].detail
    assert "will be created" in checks["badges folder"].detail


def test_a_missing_tesseract_is_reported_with_the_fix(tmp_path: Path) -> None:
    def missing() -> str:
        raise PogoError("not found; install it (macOS: brew install tesseract)")

    checks = _by_name(run_checks(_settings(tmp_path), tesseract=missing))
    assert not checks["tesseract"].ok
    assert "brew install tesseract" in checks["tesseract"].detail
    assert checks["settings"].ok  # one failure does not hide the others


def test_every_problem_is_listed_in_one_run(tmp_path: Path) -> None:
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    settings = _settings(
        tmp_path, email="", source=tmp_path / "nope", badges=blocker / "badges"
    )
    checks = _by_name(run_checks(settings, tesseract=_ok_tesseract))
    failed = sorted(name for name, c in checks.items() if not c.ok)
    assert failed == ["badges folder", "settings", "source folder"]
    assert "EMAIL" in checks["settings"].detail
    assert "path not found" in checks["source folder"].detail
    assert "not writable" in checks["badges folder"].detail


def test_a_database_that_needs_upgrading_is_reported(tmp_path: Path) -> None:
    def old(_settings: Settings) -> GymStore:
        raise SchemaError("old layout; run 'pogo upgrade' first")

    checks = _by_name(
        run_checks(_settings(tmp_path), tesseract=_ok_tesseract, opener=old)
    )
    assert not checks["database"].ok
    assert "pogo upgrade" in checks["database"].detail


def test_the_sheets_backend_checks_for_gspread_and_skips_an_unconfigured_sheet(
    tmp_path: Path,
) -> None:
    settings = _settings(tmp_path, backend=Backend.SHEETS, csv_path=None)
    checks = _by_name(run_checks(settings, tesseract=_ok_tesseract))
    assert "gspread" in checks
    assert not checks["settings"].ok
    assert "database" not in checks  # not opened: it is not configured


def test_the_real_tesseract_check_does_not_crash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pytesseract

    def missing() -> None:
        raise pytesseract.TesseractNotFoundError

    monkeypatch.setattr(pytesseract, "get_tesseract_version", missing)
    with pytest.raises(PogoError, match="brew install tesseract"):
        tesseract_version()
