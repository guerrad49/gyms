"""Benchmark an OCR setup against badges whose values are already known.

Your database is a labeled dataset: each row holds the correct title and
statistics, and the matching screenshot is stored as ``IMG_####.PNG``
under that row's ``uid``. :func:`evaluate` reads every screenshot with no
hints and reports how often the result agrees with the database, so a
change to the preprocessing, the engine, or the selection rule can be
judged by numbers instead of by feel.

Two cautions when reading the numbers. The stored title is what was typed
into the sheet (often copied from another map), so it can differ from the
in-game title; look at the listed mismatches before trusting a low title
score. And the statistics were read from the screenshot when the row was
written, so they are a fair, but not perfect, ground truth.
"""

from __future__ import annotations

import csv
from collections.abc import Callable, Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Final

from PokemonGo.errors import ConfigError, ParseError, PogoError
from PokemonGo.matching import SIMILARITY_MIN, similarity
from PokemonGo.models import Activity
from PokemonGo.parsing import normalize_title
from PokemonGo.vision.reader import BadgeReader, TitleCandidate

TRUTH_COLUMNS: Final = (
    "uid",
    "title",
    "victories",
    "days",
    "hours",
    "minutes",
    "treats",
)
"""Columns the truth CSV must have; others are ignored."""

_STATS: Final = ("victories", "days", "hours", "minutes", "treats")


@dataclass(frozen=True, slots=True)
class TruthRow:
    """The known-correct values for one badge.

    Attributes
    ----------
    uid : int
        The gym id; the screenshot is ``IMG_{uid:04d}.PNG``.
    title : str
        The stored title, normalized.
    activity : Activity
        The stored statistics.
    """

    uid: int
    title: str
    activity: Activity


@dataclass(frozen=True, slots=True)
class RowResult:
    """How one screenshot compared with its known values.

    Attributes
    ----------
    uid : int
        The gym id.
    truth_title : str
        The stored title.
    read_title : str
        The title the reader ranked first; empty if none was read.
    title_exact : bool
        Whether ``read_title`` equals the stored title.
    title_close : bool
        Whether it is at least 90% similar (v1 would ask "Accept?").
    title_reachable : bool
        Whether *any* variant read a close title. If this is true but
        ``title_close`` is not, the ranking rule is at fault; if both are
        false, the reading itself is.
    stats_ok : dict
        Per-field agreement (``True``/``False``) for the five statistics.
    all_stats_ok : bool
        Whether every statistic agrees.
    error : str
        Why the row could not be read (missing or unreadable image, ...).
    activity_text : str
        The raw text read from the statistics area, to see why parsing
        failed.
    candidates : tuple of TitleCandidate
        Every distinct title reading, best first.
    """

    uid: int
    truth_title: str
    read_title: str = ""
    title_exact: bool = False
    title_close: bool = False
    title_reachable: bool = False
    stats_ok: dict[str, bool] | None = None
    all_stats_ok: bool = False
    error: str = ""
    activity_text: str = ""
    candidates: tuple[TitleCandidate, ...] = ()

    @property
    def needs_help(self) -> bool:
        """Whether v1 would have prompted a person for this badge."""
        return bool(self.error) or not (self.title_close and self.all_stats_ok)


@dataclass(frozen=True, slots=True)
class EvalReport:
    """The outcome of a benchmark run.

    Attributes
    ----------
    rows : tuple of RowResult
        One result per truth row, in order.
    """

    rows: tuple[RowResult, ...]

    @property
    def readable(self) -> tuple[RowResult, ...]:
        """The rows whose screenshot could be read."""
        return tuple(row for row in self.rows if not row.error)

    def rate(self, predicate: Callable[[RowResult], bool]) -> float:
        """Return the share of readable rows satisfying a condition.

        Parameters
        ----------
        predicate : callable
            Called with each readable :class:`RowResult`.

        Returns
        -------
        float
            A fraction from 0 to 1; ``0.0`` when nothing was readable.
        """
        rows = self.readable
        if not rows:
            return 0.0
        return sum(1 for row in rows if predicate(row)) / len(rows)

    @property
    def ranking_misses(self) -> int:
        """Rows where a variant read the title well but another won."""
        return sum(
            1 for r in self.readable if r.title_reachable and not r.title_close
        )

    @property
    def unreachable(self) -> int:
        """Rows where no variant read a close title."""
        return sum(1 for r in self.readable if not r.title_reachable)

    @property
    def near_misses(self) -> int:
        """Rows with a close but not identical title."""
        return sum(
            1 for r in self.readable if r.title_close and not r.title_exact
        )

    @property
    def help_rate(self) -> float:
        """Share of all rows that would need manual input."""
        if not self.rows:
            return 0.0
        return sum(row.needs_help for row in self.rows) / len(self.rows)


def load_truth(path: Path) -> list[TruthRow]:
    """Read the known values from a CSV export of the database.

    Parameters
    ----------
    path : pathlib.Path
        A CSV with at least the columns in :data:`TRUTH_COLUMNS`. Rows
        with a blank ``uid`` (seeded, never scanned) are skipped, and
        extra columns are ignored.

    Returns
    -------
    list of TruthRow
        The rows in file order.

    Raises
    ------
    ConfigError
        If the file does not exist.
    ParseError
        If a required column is missing or a value is not valid.
    """
    if not path.is_file():
        msg = f"truth file not found: {path}"
        raise ConfigError(msg)
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        missing = [
            c for c in TRUTH_COLUMNS if c not in (reader.fieldnames or [])
        ]
        if missing:
            msg = f"{path.name} is missing column(s): {', '.join(missing)}"
            raise ParseError(msg)
        rows: list[TruthRow] = []
        for number, record in enumerate(reader, start=2):
            if not (record["uid"] or "").strip():
                continue
            try:
                rows.append(
                    TruthRow(
                        uid=int(record["uid"]),
                        title=normalize_title(record["title"] or ""),
                        activity=Activity(
                            **{name: int(record[name]) for name in _STATS}
                        ),
                    )
                )
            except (TypeError, ValueError) as error:
                msg = f"{path.name} line {number}: {error}"
                raise ParseError(msg) from error
    return rows


def find_image(badges: Path, uid: int) -> Path | None:
    """Locate the stored screenshot for a gym id.

    Parameters
    ----------
    badges : pathlib.Path
        The folder of processed screenshots.
    uid : int
        The gym id.

    Returns
    -------
    pathlib.Path or None
        ``IMG_####.PNG`` (or ``.png``), or ``None`` if absent.
    """
    for suffix in ("PNG", "png"):
        candidate = badges / f"IMG_{uid:04d}.{suffix}"
        if candidate.is_file():
            return candidate
    return None


def _evaluate_row(
    row: TruthRow, badges: Path, reader: BadgeReader
) -> RowResult:
    """Read one screenshot and compare it with the known values."""
    path = find_image(badges, row.uid)
    if path is None:
        return RowResult(row.uid, row.title, error="image not found")
    try:
        reading = reader.read(path)
    except PogoError as error:
        return RowResult(row.uid, row.title, error=str(error))

    best = reading.title.text if reading.title else ""
    stats = {
        name: reading.activity is not None
        and getattr(reading.activity, name) == getattr(row.activity, name)
        for name in _STATS
    }
    return RowResult(
        uid=row.uid,
        truth_title=row.title,
        read_title=best,
        title_exact=best == row.title,
        title_close=similarity(best, row.title) >= SIMILARITY_MIN,
        title_reachable=any(
            similarity(c.text, row.title) >= SIMILARITY_MIN
            for c in reading.titles
        ),
        stats_ok=stats,
        all_stats_ok=all(stats.values()),
        activity_text=reading.activity_text,
        candidates=reading.titles,
    )


def evaluate(
    reader: BadgeReader,
    badges: Path,
    truth: Iterable[TruthRow],
    *,
    jobs: int = 1,
    progress: Callable[[int, int], None] | None = None,
) -> EvalReport:
    """Read every screenshot and compare it with the known values.

    Parameters
    ----------
    reader : BadgeReader
        The reader (and so the engine and phone model) under test.
    badges : pathlib.Path
        The folder of ``IMG_####.PNG`` screenshots.
    truth : iterable of TruthRow
        The known values.
    jobs : int, optional
        Screenshots to read at the same time. OCR runs in separate
        Tesseract processes, so a few jobs speed things up.
    progress : callable, optional
        Called as ``progress(done, total)`` after each screenshot.

    Returns
    -------
    EvalReport
        The per-row results.
    """
    rows = list(truth)
    results: list[RowResult] = []
    with ThreadPoolExecutor(max_workers=max(jobs, 1)) as pool:
        futures = [
            pool.submit(_evaluate_row, row, badges, reader) for row in rows
        ]
        for done, future in enumerate(futures, start=1):
            results.append(future.result())
            if progress is not None:
                progress(done, len(rows))
    return EvalReport(tuple(results))


def _line(label: str, share: float) -> str:
    """Format one report line: a label and a percentage."""
    return f"  {label:<26}{share * 100:5.1f}%"


def _stat_ok(row: RowResult, name: str) -> bool:
    """Return whether one statistic of a row was read correctly."""
    return bool((row.stats_ok or {}).get(name))


def format_report(report: EvalReport, *, show: int = 15) -> str:
    """Render a report as text.

    Parameters
    ----------
    report : EvalReport
        The results.
    show : int, optional
        Maximum number of problem rows to list.

    Returns
    -------
    str
        A multi-line summary followed by the problem rows.
    """
    rows = report.rows
    unread = len(rows) - len(report.readable)
    lines = [
        f"Screenshots checked: {len(rows)} ({unread} unreadable or missing)",
        "",
        "Title",
        _line("exact match", report.rate(lambda r: r.title_exact)),
        _line("close (>= 90% similar)", report.rate(lambda r: r.title_close)),
        _line(
            "reachable, any variant", report.rate(lambda r: r.title_reachable)
        ),
        f"  close but not exact       {report.near_misses} rows",
        f"  ranking picked wrong      {report.ranking_misses} rows",
        f"  no variant read it        {report.unreachable} rows",
        "",
        "Statistics",
    ]
    for name in _STATS:
        lines.append(_line(name, report.rate(partial(_stat_ok, name=name))))
    lines += [
        _line("all five", report.rate(lambda r: r.all_stats_ok)),
        "",
        _line("would need manual input", report.help_rate),
    ]

    problems = [row for row in rows if row.needs_help]
    if problems:
        lines += ["", f"Problem rows (showing {min(show, len(problems))}):"]
        for row in problems[:show]:
            if row.error:
                lines.append(f"  {row.uid:>5}  {row.error}")
                continue
            bad = [n for n, ok in (row.stats_ok or {}).items() if not ok]
            note = f"stats: {', '.join(bad)}" if bad else ""
            lines.append(
                f"  {row.uid:>5}  read {row.read_title!r} "
                f"expected {row.truth_title!r} {note}".rstrip()
            )
    return "\n".join(lines)


def _flat(text: str) -> str:
    """Put multi-line OCR text on one line for a CSV cell."""
    return " / ".join(part for part in text.splitlines() if part.strip())


def _candidates(row: RowResult) -> str:
    """Describe every title reading of a row, best first."""
    return " || ".join(
        f"{c.text} [{c.variant} {c.confidence:.0f}]" for c in row.candidates
    )


def write_problems(report: EvalReport, path: Path) -> int:
    """Write the rows that needed help to a CSV file.

    Parameters
    ----------
    report : EvalReport
        The results.
    path : pathlib.Path
        The CSV to create.

    Returns
    -------
    int
        The number of rows written.
    """
    problems = [row for row in report.rows if row.needs_help]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "uid",
                "problem",
                "expected_title",
                "read_title",
                "activity_text",
                "candidates",
            ]
        )
        for row in problems:
            if row.error:
                problem = row.error
            else:
                bad = [n for n, ok in (row.stats_ok or {}).items() if not ok]
                parts = [] if row.title_close else ["title"]
                problem = ",".join(parts + bad)
            writer.writerow(
                [
                    row.uid,
                    problem,
                    row.truth_title,
                    row.read_title,
                    _flat(row.activity_text),
                    _candidates(row),
                ]
            )
    return len(problems)


def write_near_misses(report: EvalReport, path: Path) -> int:
    """Write rows whose title was close but not identical to a CSV file.

    These are not failures, but each one would have asked a person to
    confirm a similar match. Looking at them shows whether the cause is
    OCR slips or stored titles that differ from the in-game text.

    Parameters
    ----------
    report : EvalReport
        The results.
    path : pathlib.Path
        The CSV to create.

    Returns
    -------
    int
        The number of rows written.
    """
    rows = [r for r in report.readable if r.title_close and not r.title_exact]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["uid", "similarity", "expected_title", "read_title", "candidates"]
        )
        for row in rows:
            score = similarity(row.read_title, row.truth_title)
            writer.writerow(
                [
                    row.uid,
                    f"{score:.3f}",
                    row.truth_title,
                    row.read_title,
                    _candidates(row),
                ]
            )
    return len(rows)
