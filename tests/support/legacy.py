"""Typed access to the frozen v1 code in ``legacy/pogo_legacy``.

The v1 package is loaded under the name ``pogo_legacy`` without running
its ``__init__.py``, so only the modules a test asks for are imported.
This keeps the baseline tests independent of pandas and gspread.
"""

from __future__ import annotations

import importlib
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Final, Protocol, cast

LEGACY_DIR: Final = (
    Path(__file__).resolve().parents[2] / "legacy" / "pogo_legacy"
)


class _Params(Protocol):
    """The part of v1's ``ModelParams`` the tests read."""

    model: str


class LegacyBadgeImage(Protocol):
    """The part of v1's ``BadgeImage`` the tests use."""

    params: _Params

    def set_title_crop(self, **kwargs: int) -> None:
        """Crop the title region (``northOffset`` is the only option)."""

    def soften_title_overlay(self) -> None:
        """Inpaint the phone status bar out of the title crop."""

    def set_activity_crop(self) -> None:
        """Crop the activity region."""

    def get_text(self, region: str = "all") -> str:
        """Return the OCR text of a region."""


def load(name: str) -> ModuleType:
    """Import a module from the v1 package.

    Parameters
    ----------
    name : str
        Module name inside the package, for example ``"image"``.

    Returns
    -------
    types.ModuleType
        The imported module.
    """
    if "pogo_legacy" not in sys.modules:
        package = ModuleType("pogo_legacy")
        package.__path__ = [str(LEGACY_DIR)]
        sys.modules["pogo_legacy"] = package
    return importlib.import_module(f"pogo_legacy.{name}")


def squash(text: str) -> str:
    r"""Collapse all runs of whitespace into single spaces.

    Parameters
    ----------
    text : str
        The text to normalize.

    Returns
    -------
    str
        The text on one line, without leading or trailing spaces.

    Examples
    --------
    >>> squash("spring\n\ngrove")
    'spring grove'
    """
    return " ".join(text.split())


def badge_image(path: Path) -> LegacyBadgeImage:
    """Open a screenshot with the v1 ``BadgeImage`` class.

    Parameters
    ----------
    path : pathlib.Path
        Path of the screenshot.

    Returns
    -------
    LegacyBadgeImage
        A v1 ``BadgeImage`` instance.
    """
    return cast("LegacyBadgeImage", load("image").BadgeImage(str(path)))


def detect_model(path: Path) -> str:
    """Return the phone model v1 detects from the image size.

    Parameters
    ----------
    path : pathlib.Path
        Path of the screenshot.

    Returns
    -------
    str
        The profile name, for example ``"i15"``.
    """
    return str(badge_image(path).params.model)


def title_passes(path: Path) -> tuple[str, str]:
    """Run both of v1's title reads.

    The first pass uses the default crop. The second uses a taller crop
    with the status bar inpainted, exactly as ``scanner.py`` does after
    a failed match.

    Parameters
    ----------
    path : pathlib.Path
        Path of the screenshot.

    Returns
    -------
    tuple of str
        The raw text of the first and second pass.
    """
    img = badge_image(path)
    img.set_title_crop()
    first = str(img.get_text(region="title"))
    img.set_title_crop(northOffset=40)
    img.soften_title_overlay()
    second = str(img.get_text(region="title"))
    return first, second


def activity_text(path: Path) -> str:
    """Return the text v1 reads from the activity region.

    Parameters
    ----------
    path : pathlib.Path
        Path of the screenshot.

    Returns
    -------
    str
        The OCR text, lowercase.
    """
    img = badge_image(path)
    img.set_activity_crop()
    return str(img.get_text(region="activity"))


def parse_activity(text: str) -> dict[str, int] | None:
    """Apply v1's activity regex without ever prompting the user.

    Parameters
    ----------
    text : str
        Text from :func:`activity_text`.

    Returns
    -------
    dict of str to int or None
        The statistics, or ``None`` when the regex does not match
        (v1 would call ``input()`` here).
    """
    pattern = cast("re.Pattern[str]", load("image").TOTAL_ACTIVITY_RE)
    match = pattern.search(text)
    if match is None:
        return None
    return {k: int(v) for k, v in match.groupdict(default="0").items()}


def gym_values(activity: dict[str, int]) -> tuple[float, str]:
    """Compute ``defended`` and ``style`` with v1's ``GoldGym``.

    Parameters
    ----------
    activity : dict of str to int
        Keys ``victories``, ``days``, ``hours``, ``minutes``, ``treats``.

    Returns
    -------
    tuple
        Time defended in fractional days, and the gym style.
    """
    gym = load("gym").GoldGym(title="", **activity)
    gym.set_time_defended()
    gym.set_style()
    return float(gym.defended), str(gym.style)
