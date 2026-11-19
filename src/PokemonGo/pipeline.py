"""Scan screenshots into the gym database.

For each screenshot the pipeline reads the badge, finds or creates the
gym, fills in its address, saves it, and only then files the screenshot
away as ``IMG_####.PNG``. It never talks to a terminal, a phone, or a
network service directly: the reader, the store, the geocoder and the
:class:`~PokemonGo.prompts.Prompter` are all passed in, so every
decision can be tested.

Two policies decide what happens when the pipeline is unsure:

* **Interactive** (a person is answering): it asks.
* **Unattended** (``pogo scan --non-interactive``): it accepts only what is
  safe, and otherwise leaves the screenshot in place for a later run.
  Nothing is ever guessed and silently saved.
"""

from __future__ import annotations

import hashlib
import shutil
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Protocol

from PokemonGo.errors import GeocodingError, ParseError, PogoError, StoreError
from PokemonGo.geo import Address, Geocoder, fill_address
from PokemonGo.matching import (
    AUTO_ACCEPT,
    Match,
    MatchKind,
    find_matches,
    nearby_duplicates,
    unique_confident_match,
)
from PokemonGo.models import Activity, Coordinates, Flag, Gym
from PokemonGo.parsing import (
    format_status,
    normalize_title,
    parse_activity,
    parse_coordinates,
)
from PokemonGo.prompts import Prompter
from PokemonGo.store.base import GymStore
from PokemonGo.store.schema import next_uid
from PokemonGo.vision.reader import BadgeReading

MAX_TRIES = 3
"""How many times a person is asked again after an unusable answer."""

SKIP_WORD = "skip"
"""Typed at a free-text question to leave the screenshot for later."""


class Reader(Protocol):
    """Reads a screenshot; :class:`~PokemonGo.vision.reader.BadgeReader`."""

    def read(
        self, path: Path, known_titles: Sequence[str] = ()
    ) -> BadgeReading:
        """Read the title candidates and statistics of a screenshot."""


class Outcome(str, Enum):
    """What happened to one screenshot."""

    ADDED = "added"
    MATCHED = "matched"
    ALREADY = "already"
    SKIPPED = "skipped"
    ERROR = "error"


@dataclass(frozen=True, slots=True)
class ScanOptions:
    """How a scan behaves.

    Attributes
    ----------
    badges : pathlib.Path
        The folder that processed screenshots are filed into.
    auto_accept : float
        Unattended runs accept one similar title only at this score or
        above.
    dry_run : bool
        Do everything except write: no store changes, no files moved,
        no folders created.
    copy : bool
        Copy screenshots into ``badges`` instead of moving them.
    sort : bool
        Sort the database geographically at the end.
    """

    badges: Path
    auto_accept: float = AUTO_ACCEPT
    dry_run: bool = False
    copy: bool = False
    sort: bool = True


@dataclass(slots=True)
class ScanResult:
    """The outcome for one screenshot.

    Attributes
    ----------
    path : pathlib.Path
        The screenshot.
    outcome : Outcome
        What happened.
    reason : str
        Why it was skipped or failed, or a note on what was done.
    gym : Gym or None
        The gym written (or, in a dry run, that would be written). Its
        ``uid`` is provisional in a dry run.
    stored_as : str
        The name the screenshot was (or would be) filed under.
    reading : BadgeReading or None
        What was read, for verbose output.
    """

    path: Path
    outcome: Outcome
    reason: str = ""
    gym: Gym | None = None
    stored_as: str = ""
    reading: BadgeReading | None = None


@dataclass(slots=True)
class ScanSummary:
    """The outcome of a whole scan.

    Attributes
    ----------
    results : list of ScanResult
        One per screenshot, in order.
    sorted : bool
        Whether the database was sorted at the end.
    geocoding_problem : str
        Why address lookups were switched off part-way, if they were.
    """

    results: list[ScanResult] = field(default_factory=list)
    sorted: bool = False
    geocoding_problem: str = ""

    def count(self, outcome: Outcome) -> int:
        """Return how many screenshots had an outcome."""
        return sum(1 for r in self.results if r.outcome is outcome)

    @property
    def needs_attention(self) -> list[ScanResult]:
        """The screenshots that were skipped or failed."""
        bad = (Outcome.SKIPPED, Outcome.ERROR)
        return [r for r in self.results if r.outcome in bad]

    @property
    def flagged(self) -> list[Gym]:
        """Gyms written with review flags (missing city, coordinates, ...)."""
        done = (Outcome.ADDED, Outcome.MATCHED)
        return [
            r.gym
            for r in self.results
            if r.outcome in done and r.gym is not None and r.gym.status
        ]


class SafeGeocoder:
    """Wraps a geocoder so a service outage cannot stop a scan.

    A failed lookup becomes "no address found" (the gym is flagged
    ``ADDRESS`` and can be completed later with ``pogo resolve``). After
    several failures in a row, lookups are switched off for the rest of
    the run, so a dead network does not add minutes of retries per image.

    Parameters
    ----------
    inner : Geocoder
        The real geocoder.
    max_failures : int, optional
        Consecutive failures before lookups are switched off.
    """

    def __init__(self, inner: Geocoder, *, max_failures: int = 3) -> None:
        self._inner = inner
        self._max = max_failures
        self._failures = 0
        self.disabled_reason = ""

    def reverse(self, coordinates: Coordinates) -> Address | None:
        """Look up an address; failures give ``None`` instead of raising."""
        if self.disabled_reason:
            return None
        try:
            address = self._inner.reverse(coordinates)
        except GeocodingError as error:
            self._failures += 1
            if self._failures >= self._max:
                self.disabled_reason = (
                    f"address lookups were switched off after "
                    f"{self._failures} failures in a row ({error}); "
                    "run 'pogo resolve' later to fill them in"
                )
            return None
        self._failures = 0
        return address


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _screenshot_date(path: Path) -> date:
    """Return the date a screenshot was taken (its modification date)."""
    return datetime.fromtimestamp(path.stat().st_mtime).date()


def _skipped(
    path: Path, reason: str, reading: BadgeReading | None = None
) -> ScanResult:
    return ScanResult(path, Outcome.SKIPPED, reason, reading=reading)


class Scanner:
    """Scans screenshots into a database.

    Parameters
    ----------
    reader : Reader
        Reads screenshots.
    store : GymStore
        The database.
    geocoder : Geocoder
        Looks up addresses.
    prompter : Prompter
        Asks questions, or declines to (unattended).
    options : ScanOptions
        How to behave.
    """

    def __init__(
        self,
        *,
        reader: Reader,
        store: GymStore,
        geocoder: Geocoder,
        prompter: Prompter,
        options: ScanOptions,
    ) -> None:
        self._reader = reader
        self._store = store
        self._geocoder = SafeGeocoder(geocoder)
        self._prompter = prompter
        self._options = options
        gyms = store.all()
        self._hashes = {g.image_sha256: g for g in gyms if g.image_sha256}
        self._next_uid = next_uid(gyms)
        self._claimed: set[int] = set()
        self._planned: list[Gym] = []  # gyms a dry run would have added

    # --- running ---------------------------------------------------------

    def run(
        self,
        paths: Sequence[Path],
        on_result: Callable[[ScanResult], None] | None = None,
    ) -> ScanSummary:
        """Scan screenshots in order.

        A problem with one screenshot is recorded and the scan goes on. A
        failure of the *database* stops the scan, because carrying on could
        leave screenshots filed away without their rows.

        Parameters
        ----------
        paths : sequence of pathlib.Path
            The screenshots, in processing order.
        on_result : callable, optional
            Called with each result as soon as it is known.

        Returns
        -------
        ScanSummary
            What happened.

        Raises
        ------
        StoreError
            If the database cannot be read or written.
        """
        summary = ScanSummary()
        for path in paths:
            try:
                result = self.scan_one(path)
            except StoreError:
                raise
            except (PogoError, OSError) as error:
                result = ScanResult(path, Outcome.ERROR, str(error))
            summary.results.append(result)
            if on_result is not None:
                on_result(result)

        wrote = any(
            r.outcome in (Outcome.ADDED, Outcome.MATCHED)
            for r in summary.results
        )
        if self._options.sort and wrote and not self._options.dry_run:
            self._store.sort()
            self._store.commit()
            summary.sorted = True
        summary.geocoding_problem = self._geocoder.disabled_reason
        return summary

    def scan_one(self, path: Path) -> ScanResult:
        """Scan one screenshot; see :meth:`run`."""
        digest = _sha256(path)
        if digest in self._hashes:
            return self._already_scanned(path, self._hashes[digest])

        seeds = [
            g
            for g in self._store.all()
            if g.is_seeded and g.row not in self._claimed
        ]
        reading = self._reader.read(path, [g.title for g in seeds])

        activity = reading.activity or self._ask_statistics(path, reading)
        if activity is None:
            return _skipped(path, "the statistics could not be read", reading)

        title = reading.title.text if reading.title else ""
        gym, why = self._find_or_create(path, title, seeds, reading)
        if gym is None:
            return _skipped(path, why, reading)
        matched = gym.row is not None

        uid = self._next_uid
        stored_as = f"IMG_{uid:04d}.PNG"
        destination = self._options.badges / stored_as
        if destination.exists() and not self._options.dry_run:
            reason = f"{destination} already exists; not overwriting it"
            return ScanResult(path, Outcome.ERROR, reason, reading=reading)

        gym.uid = uid
        gym.model = reading.profile.name
        gym.activity = activity
        gym.scanned_at = _screenshot_date(path)
        gym.image_sha256 = digest
        self._complete_address(gym)

        if not self._options.dry_run:
            if matched:
                self._store.update(gym)
            else:
                self._store.add(gym)
            self._store.commit()  # saved before the screenshot is filed
        problem = self._file_away(path, destination)

        self._hashes[digest] = gym
        self._next_uid += 1
        if matched and gym.row is not None:
            self._claimed.add(gym.row)
        elif self._options.dry_run:
            self._planned.append(gym)

        outcome = Outcome.MATCHED if matched else Outcome.ADDED
        if problem:
            return ScanResult(
                path, Outcome.ERROR, problem, gym, stored_as, reading
            )
        return ScanResult(path, outcome, "", gym, stored_as, reading)

    # --- already processed -------------------------------------------------

    def _already_scanned(self, path: Path, gym: Gym) -> ScanResult:
        """Handle a screenshot whose content is already in the database.

        If the run that saved it stopped before filing the screenshot, it
        is filed now, so an interrupted scan can simply be run again.
        """
        stored_as = f"IMG_{gym.uid:04d}.PNG" if gym.uid is not None else ""
        reason = f"already in the database as #{gym.uid}"
        destination = self._options.badges / stored_as
        if stored_as and not destination.exists() and not self._options.dry_run:
            problem = self._file_away(path, destination)
            reason += f"; {problem}" if problem else f"; filed as {stored_as}"
        elif stored_as:
            reason += "; left where it is"
        return ScanResult(path, Outcome.ALREADY, reason, gym, stored_as)

    # --- finding or creating the gym -----------------------------------------

    def _find_or_create(
        self,
        path: Path,
        title: str,
        seeds: Sequence[Gym],
        reading: BadgeReading,
    ) -> tuple[Gym | None, str]:
        """Return the gym to fill in, or ``(None, why it was skipped)``."""
        matches = find_matches(title, seeds) if title else []
        if matches:
            chosen, skip_reason, create = self._pick(path, title, matches)
            if chosen is not None or not create:
                return chosen, skip_reason
        return self._new_gym(path, title, reading)

    def _pick(
        self, path: Path, title: str, matches: Sequence[Match]
    ) -> tuple[Gym | None, str, bool]:
        """Choose among matching seeded gyms.

        Returns the gym, the reason if skipped, and whether to fall back
        to creating a new gym.
        """
        if not self._prompter.interactive:
            sure = unique_confident_match(
                matches, auto_accept=self._options.auto_accept
            )
            if sure is not None:
                return sure.gym, "", False
            why = "the title match needs a person to confirm it"
            return None, why, False

        if len(matches) == 1:
            only = matches[0]
            if only.kind is MatchKind.EXACT:
                return only.gym, "", False
            question = (
                f"{path.name}: read {title!r}. Use the similar gym "
                f"{only.gym.title!r} ({only.score:.0%})?"
            )
            if self._prompter.confirm(question, default=True):
                return only.gym, "", False
            return None, "", True  # not that one: make a new gym instead

        options = [_describe(m.gym) for m in matches]
        options.append("none of these: create a new gym")
        picked = self._prompter.choose(
            f"{path.name}: read {title!r}, which matches several gyms.", options
        )
        if picked is None:
            return None, "you chose not to pick a gym", False
        if picked == len(matches):
            return None, "", True
        return matches[picked].gym, "", False

    def _new_gym(
        self, path: Path, title: str, reading: BadgeReading
    ) -> tuple[Gym | None, str]:
        """Create a gym for a screenshot with no seeded match."""
        if not self._prompter.interactive:
            if not title:
                return None, "no title could be read"
            return Gym(None, title), ""

        say = self._prompter
        answer = say.ask(
            f"{path.name}: no seeded gym matches. Title (Enter to accept, "
            f"{SKIP_WORD!r} to leave it for later):",
            default=title,
        )
        if answer is None:
            return None, "no answer was given (the input ended)"
        if answer.strip().lower() == SKIP_WORD:
            return None, "you chose to leave it for later"
        new_title = normalize_title(answer)
        if not new_title:
            return None, "no title was given"

        coordinates, leave = self._ask_coordinates(new_title)
        if leave:
            return None, "you chose to leave it for later"
        gym = Gym(None, new_title, coordinates)
        if gym.coordinates is not None and not self._confirm_not_a_rescan(gym):
            return None, "it looks like a gym that is already in the database"
        return gym, ""

    def _ask_coordinates(self, title: str) -> tuple[Coordinates | None, bool]:
        """Ask for coordinates.

        Returns the coordinates (``None`` if unknown) and whether the
        person asked to leave the screenshot for later.
        """
        for _ in range(MAX_TRIES):
            answer = self._prompter.ask(
                f"Coordinates for {title!r} as lat,lon (Enter = not yet, "
                f"{SKIP_WORD!r} = leave the screenshot):"
            )
            if not answer:
                return None, False
            if answer.strip().lower() == SKIP_WORD:
                return None, True
            try:
                return parse_coordinates(answer), False
            except ParseError as error:
                self._prompter.say(f"That is not usable: {error}")
        return None, False

    def _confirm_not_a_rescan(self, gym: Gym) -> bool:
        """Warn when a same-titled gym is already close by."""
        assert gym.coordinates is not None
        existing = [*self._store.all(), *self._planned]
        close = nearby_duplicates(gym.title, gym.coordinates, existing)
        if not close:
            return True
        other = close[0]
        return self._prompter.confirm(
            f"{gym.title!r} is within a hundred metres of gym #{other.uid}, "
            "which has the same title. Add it as a new gym anyway?",
            default=False,
        )

    # --- statistics and address ---

    def _ask_statistics(
        self, path: Path, reading: BadgeReading
    ) -> Activity | None:
        """Ask for statistics that could not be read (interactive only)."""
        if not self._prompter.interactive:
            return None
        for _ in range(MAX_TRIES):
            answer = self._prompter.ask(
                f"{path.name}: could not read the statistics (saw "
                f"{reading.activity_text!r}). Type them like "
                f"'27 18d 0h 56m 16' (victories, time, treats), or "
                f"{SKIP_WORD!r}:"
            )
            if not answer or answer.strip().lower() == SKIP_WORD:
                return None
            activity = parse_activity(answer)
            if activity is not None:
                return activity
            self._prompter.say("That was not understood; try again.")
        return None

    def _complete_address(self, gym: Gym) -> None:
        """Look up the address, then ask for what is still missing."""
        fill_address(gym, self._geocoder)
        if not self._prompter.interactive or gym.coordinates is None:
            return
        for name, flag in (("city", Flag.CITY), ("state", Flag.STATE)):
            if getattr(gym, name):
                continue
            answer = self._prompter.ask(
                f"{name.title()} for {gym.title!r} ({gym.coordinates}) "
                "(Enter = leave blank):"
            )
            if answer:
                setattr(gym, name, answer.strip().lower())
                gym.remove_flag(flag)

    # --- filing the screenshot -----------------------------------------------

    def _file_away(self, path: Path, destination: Path) -> str:
        """Move (or copy) a screenshot; return a problem, or ``""``."""
        if self._options.dry_run:
            return ""
        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if self._options.copy:
                shutil.copy2(path, destination)
            else:
                shutil.move(path, destination)
        except OSError as error:
            return (
                "saved in the database, but the screenshot was not "
                f"filed: {error}"
            )
        return ""


def _describe(gym: Gym) -> str:
    """Describe a candidate gym for a menu."""
    place = ", ".join(p for p in (gym.city, gym.state) if p) or "unknown place"
    where = f" ({gym.coordinates})" if gym.coordinates else ""
    return f"{gym.title} - {place}{where}"


def describe_gym(gym: Gym) -> str:
    """Describe a gym on one line, as it will be stored.

    Examples
    --------
    >>> describe_gym(Gym(7, "maple park", Coordinates(40.0, -75.0)))
    '#7 maple park (40.0,-75.0)'
    """
    parts = [f"#{gym.uid} {gym.title}"]
    if gym.coordinates is not None:
        parts.append(f"({gym.coordinates})")
    if gym.activity is not None:
        a = gym.activity
        time = f"{a.days}d {a.hours}h {a.minutes}m"
        parts.append(f"{a.victories} wins, {time}, {a.treats} treats")
    place = ", ".join(
        p for p in (gym.city, gym.county, gym.state, gym.country) if p
    )
    if place:
        parts.append(f"- {place}")
    if gym.status:
        parts.append(f"[{format_status(gym.status)}]")
    return " ".join(parts)


def format_result(
    result: ScanResult, *, dry_run: bool = False, verbose: bool = False
) -> str:
    """Describe what happened to one screenshot.

    Parameters
    ----------
    result : ScanResult
        The outcome.
    dry_run : bool, optional
        Phrase it as what *would* happen.
    verbose : bool, optional
        Add what was read from the screenshot: each title candidate with
        the variant that produced it.

    Returns
    -------
    str
        One or more lines.
    """
    name = result.path.name
    gym = result.gym
    verbs = {
        Outcome.ADDED: ("would add", "added"),
        Outcome.MATCHED: ("would fill in", "filled in"),
    }
    if result.outcome in verbs and gym is not None:
        verb = verbs[result.outcome][0 if dry_run else 1]
        lines = [f"{name}: {verb} {describe_gym(gym)} -> {result.stored_as}"]
    elif result.outcome is Outcome.ALREADY:
        lines = [f"{name}: {result.reason}"]
    elif result.outcome is Outcome.SKIPPED:
        lines = [f"{name}: SKIPPED - {result.reason}"]
    else:
        lines = [f"{name}: ERROR - {result.reason}"]
    if verbose and result.reading is not None:
        seen = ", ".join(
            f"{c.text!r} ({c.variant} {c.confidence:.0f})"
            for c in result.reading.titles
        )
        lines.append(
            f"    read on {result.reading.profile.name}: {seen or 'no title'}"
        )
    return "\n".join(lines)


def format_summary(
    summary: ScanSummary, *, dry_run: bool = False, show: int = 15
) -> str:
    """Describe a whole scan.

    Parameters
    ----------
    summary : ScanSummary
        The outcome.
    dry_run : bool, optional
        Say that nothing was saved.
    show : int, optional
        Maximum number of items to list in each section.

    Returns
    -------
    str
        A few lines: counts, what needs attention, and flagged gyms.
    """
    counts = ", ".join(
        f"{summary.count(o)} {label}"
        for o, label in (
            (Outcome.ADDED, "added"),
            (Outcome.MATCHED, "filled in"),
            (Outcome.ALREADY, "already scanned"),
            (Outcome.SKIPPED, "skipped"),
            (Outcome.ERROR, "errors"),
        )
    )
    lines = [f"Scanned {len(summary.results)} screenshots: {counts}."]
    attention = summary.needs_attention
    if attention:
        lines.append("Needs attention (left where they are):")
        lines += [f"  {r.path.name}: {r.reason}" for r in attention[:show]]
        if len(attention) > show:
            lines.append(f"  ... and {len(attention) - show} more")
    flagged = summary.flagged
    if flagged:
        lines.append("Written with review flags:")
        lines += [f"  {describe_gym(g)}" for g in flagged[:show]]
        if len(flagged) > show:
            lines.append(f"  ... and {len(flagged) - show} more")
    if summary.geocoding_problem:
        lines.append(summary.geocoding_problem)
    if dry_run:
        lines.append("Dry run: nothing was saved, moved or created.")
    elif summary.sorted:
        lines.append("The database was sorted.")
    return "\n".join(lines)
