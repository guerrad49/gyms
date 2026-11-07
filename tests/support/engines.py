"""Fake OCR engines for tests that must not need Tesseract."""

from collections.abc import Sequence

from PokemonGo.vision.engines import OcrResult, OcrWord
from PokemonGo.vision.preprocess import Image


def result(*words: tuple[str, float], line: int = 0) -> OcrResult:
    """Build an :class:`OcrResult` of words on one line."""
    return OcrResult(tuple(OcrWord(t, c, line) for t, c in words))


def lines(*texts: str, confidence: float = 90.0) -> OcrResult:
    """Build an :class:`OcrResult` with one text per line."""
    return OcrResult(
        tuple(
            OcrWord(word, confidence, number)
            for number, text in enumerate(texts)
            for word in text.split()
        )
    )


class ScriptedEngine:
    """An engine that returns prepared results in order.

    The images it is given are recorded in :attr:`images`, so tests can
    check the crop geometry. When the script runs out, an empty result
    is returned.
    """

    def __init__(self, script: Sequence[OcrResult]) -> None:
        self._script = list(script)
        self.images: list[Image] = []

    def read(self, image: Image) -> OcrResult:
        self.images.append(image)
        index = len(self.images) - 1
        if index < len(self._script):
            return self._script[index]
        return OcrResult(())
