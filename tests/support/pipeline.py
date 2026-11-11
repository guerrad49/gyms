"""Fakes for testing the scan pipeline without OCR or a terminal."""

import os
from collections.abc import Sequence
from pathlib import Path

from PokemonGo.models import Activity, Gym
from PokemonGo.vision.devices import PROFILES
from PokemonGo.vision.reader import BadgeReading, TitleCandidate

STATS = Activity(27, 18, 0, 56, 16)


def make_reading(
    *titles: str,
    activity: Activity | None = STATS,
    model: str = "i15",
    text: str = "27 18d 0h 56m 16",
) -> BadgeReading:
    """Build what the badge reader would return for a screenshot."""
    candidates = tuple(
        TitleCandidate(t, 95.0 - i, "default") for i, t in enumerate(titles)
    )
    return BadgeReading(PROFILES[model], candidates, text, activity)


def make_shot(
    folder: Path,
    name: str,
    content: bytes | None = None,
    mtime: int | None = None,
) -> Path:
    """Create a fake screenshot file (its bytes are what gets hashed)."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / name
    path.write_bytes(content if content is not None else name.encode())
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


class FakeReader:
    """Returns a prepared reading (or raises) for each file name."""

    def __init__(
        self, readings: dict[str, BadgeReading | BaseException]
    ) -> None:
        self.readings = readings
        self.calls: list[tuple[str, tuple[str, ...]]] = []

    def read(
        self, path: Path, known_titles: Sequence[str] = ()
    ) -> BadgeReading:
        self.calls.append((path.name, tuple(known_titles)))
        item = self.readings[path.name]
        if isinstance(item, BaseException):
            raise item
        return item


class ScriptedPrompter:
    """A person who answers from a script, and fails on surprises.

    Each kind of question has its own queue. Asking when the queue is
    empty raises, so a test proves exactly which questions are asked.
    Like the terminal prompter, an empty text answer means the default.
    """

    interactive = True

    def __init__(
        self,
        asks: Sequence[str | None] = (),
        confirms: Sequence[bool] = (),
        chooses: Sequence[int | None] = (),
    ) -> None:
        self.asks = list(asks)
        self.confirms = list(confirms)
        self.chooses = list(chooses)
        self.said: list[str] = []
        self.questions: list[str] = []
        self.defaults: list[str] = []
        self.options: list[list[str]] = []

    def say(self, message: str) -> None:
        self.said.append(message)

    def ask(self, message: str, default: str = "") -> str | None:
        self.questions.append(message)
        self.defaults.append(default)
        if not self.asks:
            msg = f"unexpected question: {message}"
            raise AssertionError(msg)
        answer = self.asks.pop(0)
        return answer if answer is None or answer else default

    def confirm(self, message: str, default: bool = False) -> bool:
        self.questions.append(message)
        if not self.confirms:
            msg = f"unexpected question: {message}"
            raise AssertionError(msg)
        return self.confirms.pop(0)

    def choose(self, message: str, options: Sequence[str]) -> int | None:
        self.questions.append(message)
        self.options.append(list(options))
        if not self.chooses:
            msg = f"unexpected question: {message}"
            raise AssertionError(msg)
        return self.chooses.pop(0)

    def finished(self) -> bool:
        """Whether every scripted answer was used."""
        return not (self.asks or self.confirms or self.chooses)


def titles_of(gyms: Sequence[Gym]) -> list[str]:
    return [g.title for g in gyms]
