"""`pogo scan` end to end, with the OCR reader and the network faked."""

import builtins
from pathlib import Path

import pytest

from PokemonGo import geo
from PokemonGo.cli import main
from PokemonGo.geo import Address, CachedGeocoder
from PokemonGo.models import Coordinates, Gym
from PokemonGo.store.csv_store import CsvStore
from PokemonGo.vision import reader as reader_module
from tests.support.geo import FakeGeocoder
from tests.support.pipeline import FakeReader, make_reading, make_shot

AMES = Address("ames", "story", "iowa", "united states")


class Fakes:
    """What the CLI is given instead of OCR and the network."""

    def __init__(self) -> None:
        self.readings: dict[str, object] = {}
        self.geocoder = FakeGeocoder(default=AMES)
        self.models: list[str | None] = []
        self.built: list[tuple[str, Path | None]] = []


@pytest.fixture
def fakes(monkeypatch: pytest.MonkeyPatch) -> Fakes:
    fake = Fakes()

    def make_reader(
        engine: object = None, *, model: str | None = None
    ) -> FakeReader:
        fake.models.append(model)
        return FakeReader(fake.readings)  # type: ignore[arg-type]

    def build(email: str, cache: Path | None = None) -> object:
        fake.built.append((email, cache))
        return CachedGeocoder(fake.geocoder, cache) if cache else fake.geocoder

    monkeypatch.setattr(reader_module, "BadgeReader", make_reader)
    monkeypatch.setattr(geo, "build_geocoder", build)
    return fake


class World:
    """A temporary installation: settings, source folder, database."""

    def __init__(self, tmp_path: Path, extra_env: str = "") -> None:
        self.root = tmp_path
        self.downloads = tmp_path / "downloads"
        self.downloads.mkdir()
        self.badges = tmp_path / "badges"
        self.db = tmp_path / "gyms.csv"
        self.env = tmp_path / "variables.env"
        self.env.write_text(
            "EMAIL=me@example.com\nBACKEND=csv\nCSV_PATH=gyms.csv\n"
            "SOURCE=downloads\nBADGES=badges\n" + extra_env,
            encoding="utf-8",
        )

    def shot(
        self, name: str, content: bytes | None = None, mtime: int | None = None
    ) -> Path:
        return make_shot(self.downloads, name, content, mtime)

    def scan(self, *args: str) -> int:
        return main(["scan", "--env-file", str(self.env), "--no-cache", *args])

    def saved(self) -> list[Gym]:
        return CsvStore(self.db).all()

    def seed(self, *gyms: Gym) -> None:
        store = CsvStore(self.db)
        for gym in gyms:
            store.add(gym)
        store.commit()


@pytest.fixture
def world(tmp_path: Path) -> World:
    return World(tmp_path)


def test_a_folder_is_scanned_unattended(
    world: World, fakes: Fakes, capsys: pytest.CaptureFixture[str]
) -> None:
    fakes.readings = {
        "a.PNG": make_reading("alpha"),
        "b.PNG": make_reading("beta"),
    }
    world.shot("a.PNG", mtime=100)
    world.shot("b.PNG", mtime=200)
    assert world.scan("--non-interactive") == 0
    out = capsys.readouterr().out
    assert "Found 2 screenshot(s)." in out
    assert "a.PNG: added #1 alpha" in out
    assert "b.PNG: added #2 beta" in out
    assert "Scanned 2 screenshots: 2 added" in out
    assert [g.title for g in world.saved()] == ["alpha", "beta"]
    assert sorted(p.name for p in world.badges.iterdir()) == [
        "IMG_0001.PNG",
        "IMG_0002.PNG",
    ]


def test_the_source_and_badges_folders_come_from_the_settings(
    world: World, fakes: Fakes
) -> None:
    fakes.readings = {"a.PNG": make_reading("alpha")}
    world.shot("a.PNG")
    assert world.scan("--non-interactive") == 0
    assert (world.badges / "IMG_0001.PNG").exists()
    assert not (world.downloads / "a.PNG").exists()


def test_paths_and_options_override_the_settings(
    world: World, fakes: Fakes, tmp_path: Path
) -> None:
    fakes.readings = {"a.PNG": make_reading("alpha")}
    elsewhere = make_shot(tmp_path / "elsewhere", "a.PNG")
    other_badges = tmp_path / "other"
    code = world.scan(
        str(elsewhere), "--non-interactive", "--badges", str(other_badges)
    )
    assert code == 0
    assert (other_badges / "IMG_0001.PNG").exists()
    assert not world.badges.exists()


def test_nothing_to_scan(
    world: World, fakes: Fakes, capsys: pytest.CaptureFixture[str]
) -> None:
    assert world.scan("--non-interactive") == 0
    assert capsys.readouterr().out.strip() == "No screenshots found."
    assert not world.db.exists()


def test_recursive_searches_subfolders(world: World, fakes: Fakes) -> None:
    fakes.readings = {"deep.PNG": make_reading("deep")}
    make_shot(world.downloads / "sub", "deep.PNG")
    world.scan("--non-interactive")
    assert world.saved() == []
    world.scan("--non-interactive", "--recursive")
    assert [g.title for g in world.saved()] == ["deep"]


def test_a_skipped_screenshot_gives_exit_status_two(
    world: World, fakes: Fakes, capsys: pytest.CaptureFixture[str]
) -> None:
    fakes.readings = {"a.PNG": make_reading("x", activity=None)}
    shot = world.shot("a.PNG")
    assert world.scan("--non-interactive") == 2
    out = capsys.readouterr().out
    assert "a.PNG: SKIPPED - the statistics could not be read" in out
    assert "Needs attention (left where they are):" in out
    assert shot.exists()


def test_a_dry_run_shows_the_plan_and_changes_nothing(
    world: World, fakes: Fakes, capsys: pytest.CaptureFixture[str]
) -> None:
    fakes.readings = {"a.PNG": make_reading("alpha")}
    shot = world.shot("a.PNG")
    assert world.scan("--non-interactive", "--dry-run") == 0
    out = capsys.readouterr().out
    assert "a.PNG: would add #1 alpha" in out
    assert "-> IMG_0001.PNG" in out
    assert "Dry run: nothing was saved, moved or created." in out
    assert shot.exists()
    assert not world.db.exists()
    assert not world.badges.exists()


def test_copy_keeps_the_originals(world: World, fakes: Fakes) -> None:
    fakes.readings = {"a.PNG": make_reading("alpha")}
    shot = world.shot("a.PNG")
    world.scan("--non-interactive", "--copy")
    assert shot.exists()
    assert (world.badges / "IMG_0001.PNG").exists()


def test_no_sort_leaves_the_order_alone(world: World, fakes: Fakes) -> None:
    fakes.readings = {
        "a.PNG": make_reading("zebra"),
        "b.PNG": make_reading("apple"),
    }
    world.shot("a.PNG", mtime=1)
    world.shot("b.PNG", mtime=2)
    world.scan("--non-interactive", "--no-sort")
    assert [g.title for g in world.saved()] == ["zebra", "apple"]


def test_seeded_gyms_are_filled_in_and_given_as_hints(
    world: World, fakes: Fakes, capsys: pytest.CaptureFixture[str]
) -> None:
    world.seed(Gym(None, "maple park", Coordinates(40.0, -75.0)))
    fakes.readings = {"a.PNG": make_reading("maple park")}
    world.shot("a.PNG")
    world.scan("--non-interactive")
    assert "a.PNG: filled in #1 maple park" in capsys.readouterr().out
    [gym] = world.saved()
    assert (gym.uid, gym.city) == (1, "ames")


def test_verbose_shows_what_was_read(
    world: World, fakes: Fakes, capsys: pytest.CaptureFixture[str]
) -> None:
    fakes.readings = {"a.PNG": make_reading("alpha")}
    world.shot("a.PNG")
    world.scan("--non-interactive", "-v")
    assert "read on i15: 'alpha' (default 95)" in capsys.readouterr().out


# --- questions on the terminal ---


def _typing(monkeypatch: pytest.MonkeyPatch, *answers: str) -> list[str]:
    prompts: list[str] = []
    queue = list(answers)

    def fake_input(prompt: str = "") -> str:
        prompts.append(prompt)
        return queue.pop(0)

    monkeypatch.setattr(builtins, "input", fake_input)
    return prompts


def test_a_new_gym_is_created_with_typed_answers(
    world: World, fakes: Fakes, monkeypatch: pytest.MonkeyPatch
) -> None:
    prompts = _typing(monkeypatch, "", "40.7, -74.0")
    fakes.readings = {"a.PNG": make_reading("new place")}
    world.shot("a.PNG")
    assert world.scan() == 0
    assert "a.PNG: no seeded gym matches" in prompts[0]
    assert "[new place]" in prompts[0]  # Enter accepts the read title
    [gym] = world.saved()
    assert gym.coordinates == Coordinates(40.7, -74.0)
    assert gym.city == "ames"


def test_non_interactive_never_reads_the_keyboard(
    world: World, fakes: Fakes, monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(prompt: str = "") -> str:
        raise AssertionError("asked a question")

    monkeypatch.setattr(builtins, "input", forbidden)
    fakes.readings = {"a.PNG": make_reading("new place")}
    world.shot("a.PNG")
    assert world.scan("--non-interactive") == 0


# --- options and errors ---


def test_the_model_option_and_setting(world: World, fakes: Fakes) -> None:
    fakes.readings = {"a.PNG": make_reading("alpha")}
    world.shot("a.PNG")
    world.scan("--non-interactive", "--model", "i11")
    assert fakes.models == ["i11"]


def test_the_model_can_be_set_in_the_settings_file(
    tmp_path: Path, fakes: Fakes
) -> None:
    world = World(tmp_path, extra_env="PHONE_MODEL=i15\n")
    fakes.readings = {"a.PNG": make_reading("alpha")}
    world.shot("a.PNG")
    world.scan("--non-interactive")
    assert fakes.models == ["i15"]


def test_an_unknown_model_in_the_settings_fails_before_scanning(
    tmp_path: Path, fakes: Fakes, capsys: pytest.CaptureFixture[str]
) -> None:
    world = World(tmp_path, extra_env="PHONE_MODEL=i99\n")
    world.shot("a.PNG")
    assert world.scan("--non-interactive") == 1
    assert "unknown phone model 'i99'" in capsys.readouterr().err
    assert world.saved() == []


@pytest.mark.parametrize("value", ["0", "1.5", "abc", "-1"])
def test_auto_accept_must_be_a_ratio(value: str, world: World) -> None:
    with pytest.raises(SystemExit) as info:
        world.scan("--auto-accept", value)
    assert info.value.code == 2


def test_the_auto_accept_option_is_passed_on(
    world: World, fakes: Fakes
) -> None:
    stored = "portland head light museum"
    world.seed(Gym(None, stored, Coordinates(1.0, 1.0)))
    fakes.readings = {"a.PNG": make_reading("portlond head light musuem")}
    world.shot("a.PNG")
    assert world.scan("--non-interactive") == 2  # 92% is not enough by default
    assert world.scan("--non-interactive", "--auto-accept", "0.9") == 0


def test_a_missing_path_is_reported(
    world: World, fakes: Fakes, capsys: pytest.CaptureFixture[str]
) -> None:
    assert world.scan(str(world.root / "nope.PNG"), "--non-interactive") == 1
    assert "path not found" in capsys.readouterr().err


def test_a_missing_email_stops_before_anything_happens(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    world = World(tmp_path)
    world.env.write_text(
        "BACKEND=csv\nCSV_PATH=gyms.csv\nSOURCE=downloads\n", encoding="utf-8"
    )
    world.shot("a.PNG")
    assert world.scan("--non-interactive") == 1
    assert "EMAIL must be a valid contact address" in capsys.readouterr().err


def test_the_geocoding_cache_is_used_and_saved(
    world: World, fakes: Fakes, tmp_path: Path
) -> None:
    world.seed(Gym(None, "maple park", Coordinates(40.0, -75.0)))
    fakes.readings = {"a.PNG": make_reading("maple park")}
    world.shot("a.PNG")
    cache = tmp_path / "places.json"
    code = main(
        [
            "scan",
            "--env-file",
            str(world.env),
            "--non-interactive",
            "--cache",
            str(cache),
        ]
    )
    assert code == 0
    assert cache.exists()
    assert fakes.built[-1] == ("me@example.com", cache)


def test_interrupting_keeps_what_was_finished(
    world: World, fakes: Fakes, capsys: pytest.CaptureFixture[str]
) -> None:
    fakes.readings = {
        "a.PNG": make_reading("alpha"),
        "b.PNG": KeyboardInterrupt(),
    }
    world.shot("a.PNG", mtime=1)
    second = world.shot("b.PNG", mtime=2)
    assert world.scan("--non-interactive") == 130
    assert (
        "Interrupted. Everything finished so far has been saved."
        in capsys.readouterr().err
    )
    assert [g.title for g in world.saved()] == ["alpha"]
    assert second.exists()


def test_the_screenshot_filed_name_is_in_the_output(
    world: World, fakes: Fakes, capsys: pytest.CaptureFixture[str]
) -> None:
    fakes.readings = {"a.PNG": make_reading("alpha")}
    world.shot("a.PNG")
    world.scan("--non-interactive")
    assert "-> IMG_0001.PNG" in capsys.readouterr().out
