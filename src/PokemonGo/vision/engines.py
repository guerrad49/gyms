"""OCR engines: turn a prepared image into words with confidences.

An engine is anything with a ``read`` method (see :class:`OcrEngine`).
Tesseract is the default; the benchmark in :mod:`PokemonGo.evaluate`
exists so other engines can be compared before being adopted.
"""

from __future__ import annotations

import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, Protocol

import pytesseract

from PokemonGo.errors import OcrError
from PokemonGo.vision.preprocess import Image

PUNCTUATION_WORDS: Final = frozenset(
    {"&", "-", "\u2013", "\u2014", "+", "/", ":"}
)
"""Words made only of punctuation that are nonetheless part of titles.

Dropping them made ``"paws & claws"`` read as ``"paws claws"`` and
``"msu - bird house"`` as ``"msu bird house"``.
"""


@dataclass(frozen=True, slots=True)
class OcrWord:
    """One word read from an image.

    Parameters
    ----------
    text : str
        The word.
    confidence : float
        The engine's confidence, from 0 to 100.
    line : int, optional
        Words with the same line number are on the same line of text.

    Examples
    --------
    >>> OcrWord("_", 12.0).is_junk
    True
    >>> OcrWord("17:57", 90.0).is_junk
    False
    >>> OcrWord("&", 90.0).is_junk
    False
    """

    text: str
    confidence: float
    line: int = 0

    @property
    def is_junk(self) -> bool:
        """Whether the word is OCR noise.

        A word is noise when it has no letters or digits, unless it is
        one of the punctuation marks in :data:`PUNCTUATION_WORDS`.
        """
        if self.text in PUNCTUATION_WORDS:
            return False
        return not any(char.isalnum() for char in self.text)


@dataclass(frozen=True, slots=True)
class OcrResult:
    """Everything an engine read from one image.

    Parameters
    ----------
    words : tuple of OcrWord
        The words in reading order.

    Examples
    --------
    >>> result = OcrResult((OcrWord("_", 5), OcrWord("Starbucks", 96)))
    >>> result.text
    '_ Starbucks'
    >>> result.without_junk().text
    'Starbucks'
    >>> result.without_junk().confidence
    96.0
    """

    words: tuple[OcrWord, ...]

    @property
    def text(self) -> str:
        """The words, spaces within a line and newlines between lines."""
        lines: dict[int, list[str]] = {}
        for word in self.words:
            lines.setdefault(word.line, []).append(word.text)
        return "\n".join(" ".join(line) for line in lines.values())

    @property
    def confidence(self) -> float:
        """Mean word confidence from 0 to 100; ``0.0`` with no words."""
        if not self.words:
            return 0.0
        return sum(w.confidence for w in self.words) / len(self.words)

    def without_junk(self) -> OcrResult:
        """Drop words that contain no letters or digits.

        Stray marks such as ``_`` or ``«©`` come from the phone's status
        bar. Removing them before scoring stops one junk word from
        dragging an otherwise perfect reading down. Real title
        punctuation (``&``, ``-``, ``:``) is kept.

        Returns
        -------
        OcrResult
            A result with only the meaningful words.
        """
        return OcrResult(tuple(w for w in self.words if not w.is_junk))


class OcrEngine(Protocol):
    """Reads text from a preprocessed image."""

    def read(self, image: Image) -> OcrResult:
        """Read all words from an image.

        Parameters
        ----------
        image : numpy.ndarray
            A prepared (typically binarized) image.

        Returns
        -------
        OcrResult
            The words, in reading order.
        """


class TesseractEngine:
    """OCR with the Tesseract executable, through ``pytesseract``.

    Parameters
    ----------
    lang : str, optional
        Tesseract language code.
    config : str, optional
        Extra command-line options, for example ``"--psm 6"``.
    """

    def __init__(self, lang: str = "eng", config: str = "") -> None:
        self.lang = lang
        self.config = config

    def read(self, image: Image) -> OcrResult:
        """Read all words from an image.

        Parameters
        ----------
        image : numpy.ndarray
            A prepared (typically binarized) image.

        Returns
        -------
        OcrResult
            The words with Tesseract's confidences.

        Raises
        ------
        OcrError
            If the ``tesseract`` executable cannot be found.
        """
        try:
            data = pytesseract.image_to_data(
                image,
                lang=self.lang,
                config=self.config,
                output_type=pytesseract.Output.DICT,
            )
        except pytesseract.TesseractNotFoundError as error:
            msg = "tesseract not found; install it (brew install tesseract)"
            raise OcrError(msg) from error

        line_ids: dict[tuple[int, int, int], int] = {}
        words: list[OcrWord] = []
        for index, text in enumerate(data["text"]):
            if not text.strip():
                continue
            key = (
                int(data["block_num"][index]),
                int(data["par_num"][index]),
                int(data["line_num"][index]),
            )
            line = line_ids.setdefault(key, len(line_ids))
            words.append(OcrWord(text, float(data["conf"][index]), line))
        return OcrResult(tuple(words))


def tesseract_available() -> bool:
    """Return whether the ``tesseract`` executable is on the path.

    Returns
    -------
    bool
        ``True`` if Tesseract can be run.
    """
    return shutil.which("tesseract") is not None


ENGINES: Final[Mapping[str, type[TesseractEngine]]] = {
    "tesseract": TesseractEngine,
}
"""Engines selectable by name (``pogo eval --engine``)."""


def make_engine(name: str) -> OcrEngine:
    """Create an engine by name.

    Parameters
    ----------
    name : str
        A key of :data:`ENGINES`.

    Returns
    -------
    OcrEngine
        A new engine with default settings.

    Raises
    ------
    OcrError
        If the name is unknown; the message lists the choices.
    """
    try:
        return ENGINES[name.lower()]()
    except KeyError:
        choices = ", ".join(ENGINES)
        msg = f"unknown OCR engine {name!r}; choose one of: {choices}"
        raise OcrError(msg) from None
