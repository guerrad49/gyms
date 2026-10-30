from pathlib import Path

import pytest

from PokemonGo.config import Backend, Settings
from PokemonGo.errors import ConfigError


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


def test_defaults(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    settings = Settings.load()
    assert settings.backend is Backend.SHEETS
    assert settings.source == tmp_path / "Downloads"
    assert settings.badges == Path("badges")
    assert settings.phone_model is None


def test_env_file_uses_the_v1_keys(tmp_path: Path) -> None:
    (tmp_path / "key.json").write_text("{}", encoding="utf-8")
    env = _write(
        tmp_path / "variables.env",
        "SHEET_NAME=gym_data\n"
        "JSON_KEY=key.json\n"
        "EMAIL=me@example.com\n"
        "LOG_FILE=pogo.log\n"  # retired key: ignored
        "UNKNOWN=1\n",
    )
    settings = Settings.load(env_file=env).validate()
    assert settings.sheet_name == "gym_data"
    assert settings.email == "me@example.com"
    # Relative paths in the file are relative to the file, as in v1.
    assert settings.json_key == tmp_path / "key.json"


def test_precedence_is_file_then_environment_then_overrides(
    tmp_path: Path,
) -> None:
    env = _write(tmp_path / "v.env", "BACKEND=csv\nCSV_PATH=a.csv\n")
    environ = {"POGO_BACKEND": "sqlite", "POGO_DB_PATH": "b.db"}
    overrides = {"backend": "sheets", "phone_model": "i15"}
    settings = Settings.load(env_file=env, environ=environ, overrides=overrides)
    assert settings.backend is Backend.SHEETS
    assert settings.db_path == Path("b.db")
    assert settings.csv_path == tmp_path / "a.csv"
    assert settings.phone_model == "i15"


def test_only_prefixed_environment_variables_are_read() -> None:
    settings = Settings.load(
        environ={"EMAIL": "stray@example.com", "BACKEND": "csv"}
    )
    assert settings.email == ""
    assert settings.backend is Backend.SHEETS


def test_unset_overrides_and_empty_values_are_ignored(
    tmp_path: Path,
) -> None:
    env = _write(tmp_path / "v.env", "BACKEND=csv\nEMAIL=\nSHEET_NAME=  \n")
    settings = Settings.load(
        env_file=env,
        environ={"POGO_BADGES": ""},
        overrides={"backend": None, "badges": ""},
    )
    assert settings.backend is Backend.CSV
    assert settings.email == ""
    assert settings.sheet_name == ""
    assert settings.badges == Path("badges")


def test_home_directory_is_expanded(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    settings = Settings.load(overrides={"source": "~/Pictures"})
    assert settings.source == tmp_path / "Pictures"


def test_unknown_backend_lists_the_choices() -> None:
    with pytest.raises(ConfigError, match="choose one of: sheets, csv, sql"):
        Settings.load(overrides={"backend": "excel"})


def test_missing_env_file_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="configuration file not found"):
        Settings.load(env_file=tmp_path / "nope.env")


def test_sheets_validation_reports_every_problem(tmp_path: Path) -> None:
    settings = Settings(json_key=tmp_path / "missing.json")
    with pytest.raises(ConfigError) as info:
        settings.validate()
    message = str(info.value)
    assert "SHEET_NAME is required" in message
    assert "JSON_KEY file not found" in message
    assert "EMAIL must be a valid contact address" in message


def test_sheets_validation_requires_a_key() -> None:
    settings = Settings(sheet_name="x", email="me@example.com")
    with pytest.raises(ConfigError, match="JSON_KEY is required"):
        settings.validate()


@pytest.mark.parametrize(
    ("backend", "needed"),
    [(Backend.CSV, "CSV_PATH"), (Backend.SQLITE, "DB_PATH")],
)
def test_local_backends_need_a_path(backend: Backend, needed: str) -> None:
    with pytest.raises(ConfigError, match=needed):
        Settings(backend=backend).validate(need_email=False)


def test_validation_passes_for_a_complete_local_setup() -> None:
    settings = Settings(
        backend=Backend.CSV,
        csv_path=Path("gyms.csv"),
        email="me@example.com",
    )
    assert settings.validate() is settings


def test_email_can_be_waived() -> None:
    settings = Settings(backend=Backend.SQLITE, db_path=Path("g.db"))
    assert settings.validate(need_email=False) is settings
