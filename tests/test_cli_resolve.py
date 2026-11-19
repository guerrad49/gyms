import json
from pathlib import Path

import pytest

from PokemonGo import geo
from PokemonGo.cli import main
from PokemonGo.geo import Address, CachedGeocoder
from PokemonGo.models import Coordinates, Gym
from PokemonGo.store.csv_store import CsvStore
from tests.support.geo import FakeGeocoder

AMES = Address("ames", "story", "iowa", "united states")


def _db(tmp_path: Path) -> Path:
    path = tmp_path / "gyms.csv"
    if path.exists():
        return path
    store = CsvStore(path)
    store.add(Gym(1, "needs one", Coordinates(1, 1)))
    store.add(Gym(2, "needs two", Coordinates(2, 2)))
    store.add(Gym(3, "already", Coordinates(3, 3), city="x", state="y"))
    store.commit()
    return path


def _args(tmp_path: Path, *extra: str) -> list[str]:
    return [
        "resolve",
        "--backend",
        "csv",
        "--csv-path",
        str(_db(tmp_path)),
        *extra,
    ]


@pytest.fixture
def fake_geocoder(monkeypatch: pytest.MonkeyPatch) -> FakeGeocoder:
    """Replace the network geocoder; remember how it was asked to be built."""
    fake = FakeGeocoder(default=AMES)
    built: list[tuple[str, Path | None]] = []

    def build(email: str, cache: Path | None = None) -> FakeGeocoder:
        built.append((email, cache))
        return fake

    monkeypatch.setattr(geo, "build_geocoder", build)
    fake.built = built  # type: ignore[attr-defined]
    return fake


def _env(tmp_path: Path, email: str = "me@example.com") -> Path:
    env = tmp_path / "variables.env"
    env.write_text(f"EMAIL={email}\n", encoding="utf-8")
    return env


def test_resolve_fills_addresses_and_saves(
    tmp_path: Path,
    fake_geocoder: FakeGeocoder,
    capsys: pytest.CaptureFixture[str],
) -> None:
    env = _env(tmp_path)
    args = _args(tmp_path, "--env-file", str(env))
    assert main(args) == 0
    out = capsys.readouterr()
    assert "Looked up 2 gyms; 2 changed." in out.out
    assert "2/2" in out.err
    cities = {g.title: g.city for g in CsvStore(tmp_path / "gyms.csv").all()}
    assert cities == {"needs one": "ames", "needs two": "ames", "already": "x"}


def test_the_email_and_default_cache_come_from_the_settings(
    tmp_path: Path, fake_geocoder: FakeGeocoder
) -> None:
    main(_args(tmp_path, "--env-file", str(_env(tmp_path))))
    assert fake_geocoder.built == [  # type: ignore[attr-defined]
        ("me@example.com", Path("geocode_cache.json"))
    ]


def test_cache_options(tmp_path: Path, fake_geocoder: FakeGeocoder) -> None:
    env = str(_env(tmp_path))
    main(
        _args(tmp_path, "--env-file", env, "--cache", str(tmp_path / "c.json"))
    )
    main(_args(tmp_path, "--env-file", env, "--no-cache"))
    built = fake_geocoder.built  # type: ignore[attr-defined]
    assert built[0][1] == tmp_path / "c.json"
    assert built[1][1] is None


def test_a_dry_run_saves_nothing(
    tmp_path: Path,
    fake_geocoder: FakeGeocoder,
    capsys: pytest.CaptureFixture[str],
) -> None:
    env = _env(tmp_path)
    assert main(_args(tmp_path, "--env-file", str(env), "--dry-run")) == 0
    assert "Dry run: nothing was saved." in capsys.readouterr().out
    assert all(g.city != "ames" for g in CsvStore(tmp_path / "gyms.csv").all())


def test_the_limit_option(tmp_path: Path, fake_geocoder: FakeGeocoder) -> None:
    env = _env(tmp_path)
    assert main(_args(tmp_path, "--env-file", str(env), "--limit", "1")) == 0
    assert len(fake_geocoder.calls) == 1


def test_a_failed_lookup_exits_with_an_error_but_keeps_progress(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    fake = FakeGeocoder(default=AMES, fail_on=["2.0,2.0"])
    monkeypatch.setattr(geo, "build_geocoder", lambda email, cache=None: fake)
    env = _env(tmp_path)
    assert main(_args(tmp_path, "--env-file", str(env))) == 1
    assert "Stopped early" in capsys.readouterr().out
    cities = {g.title: g.city for g in CsvStore(tmp_path / "gyms.csv").all()}
    assert cities["needs one"] == "ames"
    assert cities["needs two"] == ""


def test_the_cache_is_saved_even_when_the_run_stops(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    fake = FakeGeocoder(default=AMES, fail_on=["2.0,2.0"])
    cache_path = tmp_path / "c.json"
    monkeypatch.setattr(
        geo,
        "build_geocoder",
        lambda email, cache=None: CachedGeocoder(fake, cache_path),
    )
    main(_args(tmp_path, "--env-file", str(_env(tmp_path))))
    entries = json.loads(cache_path.read_text(encoding="utf-8"))["entries"]
    assert list(entries) == ["1.000000,1.000000"]


def test_a_missing_email_is_reported(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    args = _args(
        tmp_path, "--env-file", str(_env(tmp_path, email="")), "--no-cache"
    )
    assert main(args) == 1
    assert "EMAIL must be a valid contact address" in capsys.readouterr().err
