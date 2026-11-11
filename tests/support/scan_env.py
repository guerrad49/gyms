"""A complete scan environment inside a temporary folder, for tests."""

from collections.abc import Mapping
from pathlib import Path

from PokemonGo.geo import Address
from PokemonGo.models import Coordinates, Gym
from PokemonGo.pipeline import Scanner, ScanOptions, ScanSummary
from PokemonGo.prompts import NonInteractivePrompter, Prompter
from PokemonGo.store.csv_store import CsvStore
from tests.support.geo import FakeGeocoder
from tests.support.pipeline import FakeReader, make_shot

HERE = Coordinates(40.0, -75.0)
AMES = Address("ames", "story", "iowa", "united states")


def seed(title: str = "maple park", at: Coordinates | None = HERE) -> Gym:
    return Gym(None, title, at)


class Env:
    """Everything a scan needs, inside a temporary folder."""

    def __init__(
        self,
        tmp_path: Path,
        readings: Mapping[str, object],
        *,
        seeds: list[Gym] | None = None,
        geocoder: FakeGeocoder | None = None,
        prompter: Prompter | None = None,
        **options: object,
    ) -> None:
        self.downloads = tmp_path / "downloads"
        self.badges = tmp_path / "badges"
        self.db = tmp_path / "gyms.csv"
        self.store = CsvStore(self.db)
        for gym in seeds or []:
            self.store.add(gym)
        self.store.commit()
        self.reader = FakeReader(readings)  # type: ignore[arg-type]
        self.geocoder = geocoder or FakeGeocoder(default=AMES)
        self.prompter = prompter or NonInteractivePrompter()
        self.options = ScanOptions(badges=self.badges, **options)  # type: ignore[arg-type]

    def shot(
        self, name: str, content: bytes | None = None, mtime: int | None = None
    ) -> Path:
        return make_shot(self.downloads, name, content, mtime)

    def run(self, *paths: Path) -> ScanSummary:
        scanner = Scanner(
            reader=self.reader,
            store=self.store,
            geocoder=self.geocoder,
            prompter=self.prompter,
            options=self.options,
        )
        return scanner.run(list(paths))

    def saved(self) -> list[Gym]:
        return CsvStore(self.db).all()

    def filed(self) -> list[str]:
        if not self.badges.exists():
            return []
        return sorted(p.name for p in self.badges.iterdir())
