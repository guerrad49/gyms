"""Ground truth for the six reference screenshots.

The values live in ``tests/fixtures/expected.json``. They were read by
eye from the screenshots, so they do not depend on any OCR engine.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Final

FIXTURES_DIR: Final = Path(__file__).resolve().parents[1] / "fixtures"
IMAGES_DIR: Final = FIXTURES_DIR / "images"
EXPECTED_JSON: Final = FIXTURES_DIR / "expected.json"


@dataclass(frozen=True, slots=True)
class Expected:
    """Ground truth for one reference screenshot.

    Attributes
    ----------
    file : str
        File name inside ``tests/fixtures/images``.
    model : str
        Phone profile name (``iSE``, ``i11`` or ``i15``).
    title : str
        The gym title, lowercase, on a single line.
    victories, days, hours, minutes, treats : int
        The badge statistics.
    defended : float
        Time defended in fractional days, rounded to 4 decimals.
    style : str
        ``"gold"`` or ``"100+ days"``.
    known_defects : dict of str to str
        Maps a check name to the defect id (see ``PLAN.md`` section 3)
        that makes the *v1* code fail it.
    """

    file: str
    model: str
    title: str
    victories: int
    days: int
    hours: int
    minutes: int
    treats: int
    defended: float
    style: str
    known_defects: dict[str, str]

    @property
    def path(self) -> Path:
        """Return the absolute path of the screenshot."""
        return IMAGES_DIR / self.file

    @property
    def activity(self) -> dict[str, int]:
        """Return the badge statistics as a dictionary."""
        return {
            "victories": self.victories,
            "days": self.days,
            "hours": self.hours,
            "minutes": self.minutes,
            "treats": self.treats,
        }


def load_expected() -> tuple[Expected, ...]:
    """Load every reference screenshot's ground truth.

    Returns
    -------
    tuple of Expected
        One entry per screenshot, in file-name order.
    """
    raw: dict[str, dict[str, object]] = json.loads(
        EXPECTED_JSON.read_text(encoding="utf-8")
    )
    return tuple(
        Expected(file=name, **values)  # type: ignore[arg-type]
        for name, values in sorted(raw.items())
    )


ALL: Final = load_expected()


def write_truth_csv(path: Path) -> Path:
    """Write the reference screenshots' values as a truth CSV.

    The ``uid`` of each row is taken from the file name (``IMG_1131.PNG``
    is gym 1131), so the screenshot folder doubles as the badges folder.
    Titles are quoted properly: some contain commas.

    Parameters
    ----------
    path : pathlib.Path
        The CSV file to create.

    Returns
    -------
    pathlib.Path
        ``path``, for chaining.
    """
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            ["uid", "title", "victories", "days", "hours", "minutes", "treats"]
        )
        for case in ALL:
            writer.writerow(
                [
                    int(case.file[4:8]),
                    case.title,
                    case.victories,
                    case.days,
                    case.hours,
                    case.minutes,
                    case.treats,
                ]
            )
    return path
