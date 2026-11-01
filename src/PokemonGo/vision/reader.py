"""Read a badge screenshot: phone, title candidates, and statistics.

The title is the hard part. Where it sits depends on whether it wraps to
two lines, and the phone's status bar may overlap it. Instead of trusting
one crop, :class:`BadgeReader` reads several variants, drops OCR noise,
and ranks the results. When the caller knows which titles to expect (the
seeded rows of the database), similarity to them decides; otherwise the
engine's confidence does.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from PokemonGo.matching import similarity
from PokemonGo.models import Activity
from PokemonGo.parsing import normalize_title, parse_activity
from PokemonGo.vision.devices import DeviceProfile, select_profile
from PokemonGo.vision.engines import OcrEngine, TesseractEngine
from PokemonGo.vision.preprocess import (
    Image,
    binarize,
    crop_rows,
    inpaint_status_bar,
    load_image,
)


@dataclass(frozen=True, slots=True)
class TitleVariant:
    """One way of cropping and cleaning the title area.

    Attributes
    ----------
    name : str
        Short label, shown in verbose output.
    north_offset : int
        Pixels to extend the crop upwards, to include a wrapped first
        line.
    inpaint : bool
        Whether to paint over the status-bar marks.
    """

    name: str
    north_offset: int
    inpaint: bool


TITLE_VARIANTS: Final = (
    TitleVariant("default", 0, False),
    TitleVariant("tall", 40, False),
    TitleVariant("tall-inpaint", 40, True),
    TitleVariant("default-inpaint", 0, True),
)
"""The title reads tried, cheapest and most common first."""


@dataclass(frozen=True, slots=True)
class TitleCandidate:
    """One reading of the title.

    Attributes
    ----------
    text : str
        The normalized title.
    confidence : float
        Mean word confidence from 0 to 100, OCR noise excluded.
    variant : str
        Name of the :class:`TitleVariant` that produced it.
    dropped : tuple of str
        Words the OCR engine returned that were discarded as noise. Kept
        for diagnostics: if a title is missing a character, this shows
        whether the engine saw it.
    """

    text: str
    confidence: float
    variant: str
    dropped: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class BadgeReading:
    """Everything read from one screenshot.

    Attributes
    ----------
    profile : DeviceProfile
        The phone profile used (rescaled if it was forced).
    titles : tuple of TitleCandidate
        The distinct title readings, best first.
    activity_text : str
        The raw text of the statistics area, for showing to a person when
        parsing fails.
    activity : Activity or None
        The parsed statistics, or ``None`` if they could not be parsed.
    """

    profile: DeviceProfile
    titles: tuple[TitleCandidate, ...]
    activity_text: str
    activity: Activity | None

    @property
    def title(self) -> TitleCandidate | None:
        """The best title reading, or ``None`` if nothing was read."""
        return self.titles[0] if self.titles else None


_CLOCK: Final = re.compile(r"^\d{1,2}:\d{2}$")
_BATTERY: Final = re.compile(r"^\d{1,3}%$")


def _is_status_token(token: str) -> bool:
    """Return whether a word looks like a clock or battery reading."""
    return bool(_CLOCK.match(token) or _BATTERY.match(token))


def has_status_bar(text: str) -> bool:
    """Return whether a reading includes the phone's clock or battery.

    A gym title essentially never contains ``17:57`` or ``85%``, so
    these words mean the crop caught the status bar.

    Parameters
    ----------
    text : str
        A normalized title reading.

    Returns
    -------
    bool
        ``True`` if any word is a clock time or a percentage.

    Examples
    --------
    >>> has_status_bar("17:16 7 al horace ashenfelter")
    True
    >>> has_status_bar("horace ashenfelter")
    False
    """
    return any(_is_status_token(token) for token in text.split())


def _content_words(text: str) -> frozenset[str]:
    """Return the words of three or more characters, minus status text."""
    return frozenset(
        token
        for token in text.split()
        if len(token) >= 3 and not _is_status_token(token)
    )


def drop_contaminated(
    candidates: Sequence[TitleCandidate],
) -> list[TitleCandidate]:
    """Drop readings that are a clean reading plus status-bar text.

    A "tall" crop sometimes reads ``"17:16 7 al horace ashenfelter
    commemorative plaque"`` a point or two more confidently than the clean
    ``"horace ashenfelter commemorative plaque"``. A contaminated reading
    is dropped only when a clean one has the same words (at most one
    fewer), so a clean reading that is merely a *truncated* title never
    displaces a contaminated reading that has the whole title.

    Parameters
    ----------
    candidates : sequence of TitleCandidate
        The readings, in variant order.

    Returns
    -------
    list of TitleCandidate
        The readings that remain, in the same order.

    Examples
    --------
    >>> clean = TitleCandidate("njit", 91.0, "default")
    >>> noisy = TitleCandidate("11:58 njit", 92.0, "tall")
    >>> drop_contaminated([noisy, clean]) == [clean]
    True
    """
    clean_words = [
        words
        for c in candidates
        if not has_status_bar(c.text) and (words := _content_words(c.text))
    ]
    kept: list[TitleCandidate] = []
    for candidate in candidates:
        if has_status_bar(candidate.text):
            words = _content_words(candidate.text)
            if any(
                clean <= words and len(clean) >= len(words) - 1
                for clean in clean_words
            ):
                continue
        kept.append(candidate)
    return kept


def rank_titles(
    candidates: Iterable[TitleCandidate], known_titles: Sequence[str] = ()
) -> tuple[TitleCandidate, ...]:
    """Order title readings from most to least likely.

    Parameters
    ----------
    candidates : iterable of TitleCandidate
        The readings, in the order the variants were tried. That order
        breaks ties, so earlier (cheaper) variants win.
    known_titles : sequence of str, optional
        Titles expected in the database. When given, closeness to the
        nearest known title ranks first and confidence second.

    Returns
    -------
    tuple of TitleCandidate
        The readings, best first.

    Examples
    --------
    >>> a = TitleCandidate("st verizon 17:57 starbucks", 66.7, "tall")
    >>> b = TitleCandidate("starbucks", 96.0, "default")
    >>> [c.variant for c in rank_titles([a, b])]
    ['default', 'tall']
    """
    known = [normalize_title(title) for title in known_titles]

    def key(item: tuple[int, TitleCandidate]) -> tuple[float, float, int]:
        index, candidate = item
        closeness = max(
            (similarity(candidate.text, title) for title in known if title),
            default=0.0,
        )
        return (-closeness, -candidate.confidence, index)

    return tuple(c for _, c in sorted(enumerate(candidates), key=key))


class BadgeReader:
    """Reads badge screenshots with an OCR engine.

    Parameters
    ----------
    engine : OcrEngine, optional
        The OCR engine. Defaults to Tesseract.
    model : str, optional
        Force a phone profile by name (for example ``"i15"``) instead of
        detecting it from the image size.

    Examples
    --------
    >>> reader = BadgeReader(model="i15")
    >>> reader.model
    'i15'
    """

    def __init__(
        self, engine: OcrEngine | None = None, *, model: str | None = None
    ) -> None:
        self._engine: OcrEngine = engine or TesseractEngine()
        self.model = model

    def read(
        self, path: Path, known_titles: Sequence[str] = ()
    ) -> BadgeReading:
        """Read a screenshot file.

        Parameters
        ----------
        path : pathlib.Path
            The screenshot.
        known_titles : sequence of str, optional
            Titles expected in the database; see :func:`rank_titles`.

        Returns
        -------
        BadgeReading
            The title candidates and the statistics.

        Raises
        ------
        ImageReadError
            If the file is missing or not an image.
        UnsupportedDeviceError
            If the image size is unknown and no model is forced.
        OcrError
            If the OCR engine is unavailable.
        """
        return self.read_image(load_image(path), known_titles)

    def read_image(
        self, image: Image, known_titles: Sequence[str] = ()
    ) -> BadgeReading:
        """Read an already loaded screenshot.

        Parameters
        ----------
        image : numpy.ndarray
            The screenshot, BGR.
        known_titles : sequence of str, optional
            Titles expected in the database; see :func:`rank_titles`.

        Returns
        -------
        BadgeReading
            The title candidates and the statistics.
        """
        profile = select_profile(image.shape[:2], self.model)
        known = {normalize_title(t) for t in known_titles} - {""}

        found: dict[str, TitleCandidate] = {}
        for variant in TITLE_VARIANTS:
            candidate = self._read_title(image, profile, variant)
            if candidate is None:
                continue
            previous = found.get(candidate.text)
            if previous is None or candidate.confidence > previous.confidence:
                found[candidate.text] = candidate
            if candidate.text in known:
                break  # an exact known title cannot be improved on

        activity_text = self._read_activity_text(image, profile)
        return BadgeReading(
            profile=profile,
            titles=rank_titles(
                drop_contaminated(list(found.values())), known_titles
            ),
            activity_text=activity_text,
            activity=parse_activity(activity_text),
        )

    def _read_title(
        self, image: Image, profile: DeviceProfile, variant: TitleVariant
    ) -> TitleCandidate | None:
        """Read the title with one variant; ``None`` if nothing usable."""
        start, end = profile.title_rows
        crop = crop_rows(image, start - variant.north_offset, end)
        if variant.inpaint:
            crop = inpaint_status_bar(crop)
        raw = self._engine.read(binarize(crop, profile.scale))
        result = raw.without_junk()
        text = normalize_title(result.text)
        if not text:
            return None
        dropped = tuple(w.text for w in raw.words if w.is_junk)
        return TitleCandidate(text, result.confidence, variant.name, dropped)

    def _read_activity_text(self, image: Image, profile: DeviceProfile) -> str:
        """Return the raw text of the statistics area."""
        start, end = profile.activity_rows
        crop = crop_rows(image, start, end)
        result = self._engine.read(binarize(crop, profile.scale))
        return result.text.strip().lower()
