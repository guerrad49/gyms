"""`pogo scan` with the real OCR reader on the six reference screenshots.

Only the network is faked. These tests read real pixels, run the real
matching, and write a real database and real files.
"""

import os
import shutil
from pathlib import Path

import pytest

from PokemonGo import geo
from PokemonGo.cli import main
from PokemonGo.geo import Address
from PokemonGo.models import Activity, Coordinates, Flag, Gym
from PokemonGo.store.csv_store import CsvStore
from tests.support.expected import ALL, IMAGES_DIR
from tests.support.geo import FakeGeocoder

pytestmark = pytest.mark.ocr

AMES = Address("ames", "story", "iowa", "united states")


@pytest.fixture
def geocoder(monkeypatch: pytest.MonkeyPatch) -> FakeGeocoder:
    fake = FakeGeocoder(default=AMES)
    monkeypatch.setattr(geo, "build_geocoder", lambda email, cache=None: fake)
    return fake


class Install:
    """Settings, a source folder holding the six screenshots, no database."""

    def __init__(self, tmp_path: Path) -> None:
        self.downloads = tmp_path / "downloads"
        self.downloads.mkdir()
        for position, case in enumerate(ALL):
            target = self.downloads / case.file
            shutil.copy(IMAGES_DIR / case.file, target)
            os.utime(target, (1000 + position, 1000 + position))
        self.badges = tmp_path / "badges"
        self.db = tmp_path / "gyms.csv"
        self.env = tmp_path / "variables.env"
        self.env.write_text(
            "EMAIL=me@example.com\nBACKEND=csv\nCSV_PATH=gyms.csv\n"
            "SOURCE=downloads\nBADGES=badges\n",
            encoding="utf-8",
        )

    def scan(self, *args: str) -> int:
        return main(["scan", "--env-file", str(self.env), "--no-cache", *args])

    def saved(self) -> list[Gym]:
        return CsvStore(self.db).all()


@pytest.fixture
def install(tmp_path: Path) -> Install:
    return Install(tmp_path)


def test_all_six_screenshots_are_read_into_the_database(
    install: Install, geocoder: FakeGeocoder, capsys: pytest.CaptureFixture[str]
) -> None:
    assert install.scan("--non-interactive") == 0
    out = capsys.readouterr().out
    assert "Scanned 6 screenshots: 6 added" in out

    saved = {g.uid: g for g in install.saved() if g.uid is not None}
    assert sorted(saved) == [1, 2, 3, 4, 5, 6]
    for uid, case in enumerate(ALL, start=1):
        gym = saved[uid]
        assert gym.title == case.title
        assert gym.activity == Activity(**case.activity)
        assert gym.model == case.model
        assert gym.status == (Flag.NO_COORDS,)  # no coordinates were given
    assert sorted(p.name for p in install.badges.iterdir()) == [
        f"IMG_{n:04d}.PNG" for n in range(1, 7)
    ]
    assert list(install.downloads.iterdir()) == []  # all of them were filed


def test_screenshots_are_filed_in_processing_order(
    install: Install, geocoder: FakeGeocoder
) -> None:
    install.scan("--non-interactive", "--copy")
    for uid, case in enumerate(ALL, start=1):
        filed = install.badges / f"IMG_{uid:04d}.PNG"
        assert filed.read_bytes() == (IMAGES_DIR / case.file).read_bytes()


def test_seeded_gyms_are_filled_in_with_their_addresses(
    install: Install, geocoder: FakeGeocoder
) -> None:
    store = CsvStore(install.db)
    store.add(Gym(None, ALL[0].title, Coordinates(40.0, -75.0)))
    store.add(Gym(None, ALL[2].title, Coordinates(41.0, -76.0)))
    store.commit()
    assert install.scan("--non-interactive") == 0
    gyms = {g.title: g for g in install.saved()}
    assert len(gyms) == 6  # the two seeds were filled in, not duplicated
    for case in (ALL[0], ALL[2]):
        gym = gyms[case.title]
        assert gym.coordinates is not None
        assert (gym.city, gym.state) == ("ames", "iowa")
        assert gym.status == ()
    assert gyms[ALL[1].title].status == (Flag.NO_COORDS,)


def test_a_dry_run_reads_everything_and_changes_nothing(
    install: Install, geocoder: FakeGeocoder, capsys: pytest.CaptureFixture[str]
) -> None:
    before = sorted(p.name for p in install.downloads.iterdir())
    assert install.scan("--non-interactive", "--dry-run") == 0
    out = capsys.readouterr().out
    assert out.count("would add") == 6
    assert "Dry run: nothing was saved, moved or created." in out
    assert not install.db.exists()
    assert not install.badges.exists()
    assert sorted(p.name for p in install.downloads.iterdir()) == before


def test_scanning_again_adds_nothing(
    install: Install,
    geocoder: FakeGeocoder,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    install.scan("--non-interactive", "--copy")
    capsys.readouterr()
    assert install.scan("--non-interactive") == 0
    out = capsys.readouterr().out
    assert (
        "Scanned 6 screenshots: 0 added, 0 filled in, 6 already scanned" in out
    )
    assert len(install.saved()) == 6
    assert len(list(install.badges.iterdir())) == 6


def test_a_single_file_can_be_scanned_with_verbose_output(
    install: Install, geocoder: FakeGeocoder, capsys: pytest.CaptureFixture[str]
) -> None:
    case = ALL[3]  # the two-line title with a status bar over it
    code = install.scan(
        str(install.downloads / case.file),
        "--non-interactive",
        "-v",
        "--model",
        case.model,
    )
    assert code == 0
    out = capsys.readouterr().out
    assert f"read on {case.model}:" in out
    assert case.title in out
    assert [g.title for g in install.saved()] == [case.title]
    assert len(list(install.downloads.iterdir())) == 5  # only that one was used
