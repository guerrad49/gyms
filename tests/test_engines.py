from typing import Any

import numpy as np
import pytesseract
import pytest

from PokemonGo.errors import OcrError
from PokemonGo.vision.engines import (
    ENGINES,
    OcrResult,
    OcrWord,
    TesseractEngine,
    make_engine,
    tesseract_available,
)
from PokemonGo.vision.preprocess import binarize, crop_rows, load_image
from tests.support.engines import lines, result
from tests.support.expected import ALL


@pytest.mark.parametrize(
    ("text", "junk"),
    [
        ("_", True),
        ("«©", True),
        ("|", True),
        ("a", False),
        ("17:57", False),
        # Real title punctuation is not noise (it appears in 34 titles).
        ("&", False),
        ("-", False),
        ("\u2013", False),
        ("\u2014", False),
        (":", False),
        ("+", False),
        ("/", False),
    ],
)
def test_words_without_letters_or_digits_are_junk(
    text: str, junk: bool
) -> None:
    assert OcrWord(text, 50.0).is_junk is junk


def test_result_text_keeps_line_structure() -> None:
    ocr = lines("victories time", "27 18d")
    assert ocr.text == "victories time\n27 18d"


def test_result_confidence_is_the_mean_and_zero_when_empty() -> None:
    assert result(("a", 80), ("b", 100)).confidence == 90.0
    assert OcrResult(()).confidence == 0.0
    assert OcrResult(()).text == ""


def test_without_junk_stops_noise_dragging_confidence_down() -> None:
    noisy = result(("_", 0), ("Starbucks", 96))
    assert noisy.confidence == 48.0
    clean = noisy.without_junk()
    assert clean.text == "Starbucks"
    assert clean.confidence == 96.0


def test_without_junk_keeps_ampersands_and_dashes() -> None:
    noisy = result(
        ("_", 3), ("MSU", 90), ("-", 80), ("Bird", 90), ("House", 90)
    )
    assert noisy.without_junk().text == "MSU - Bird House"
    assert result(
        ("Paws", 90), ("&", 70), ("Claws", 90)
    ).without_junk().text == ("Paws & Claws")


def _fake_data(**overrides: list[Any]) -> dict[str, list[Any]]:
    data: dict[str, list[Any]] = {
        "text": ["", "Greater", "Washington", "", "Temple"],
        "conf": ["-1", "96", "95.5", "-1", "90"],
        "block_num": [1, 1, 1, 1, 1],
        "par_num": [1, 1, 1, 1, 1],
        "line_num": [0, 1, 1, 0, 2],
    }
    data.update(overrides)
    return data


def test_tesseract_engine_builds_words_and_lines(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    def fake(image: object, **options: object) -> dict[str, list[Any]]:
        seen.update(options)
        return _fake_data()

    monkeypatch.setattr(pytesseract, "image_to_data", fake)
    engine = TesseractEngine(lang="eng", config="--psm 6")
    ocr = engine.read(np.zeros((4, 4), dtype=np.uint8))
    assert ocr.text == "Greater Washington\nTemple"
    assert [w.confidence for w in ocr.words] == [96.0, 95.5, 90.0]
    assert seen["lang"] == "eng"
    assert seen["config"] == "--psm 6"


def test_a_missing_tesseract_becomes_an_ocr_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake(*_args: object, **_kwargs: object) -> None:
        raise pytesseract.TesseractNotFoundError

    monkeypatch.setattr(pytesseract, "image_to_data", fake)
    with pytest.raises(OcrError, match="brew install tesseract"):
        TesseractEngine().read(np.zeros((4, 4), dtype=np.uint8))


def test_tesseract_available_follows_the_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("shutil.which", lambda _name: None)
    assert tesseract_available() is False
    monkeypatch.setattr("shutil.which", lambda _name: "/usr/bin/tesseract")
    assert tesseract_available() is True


def test_make_engine_by_name_and_unknown_name() -> None:
    assert isinstance(make_engine("Tesseract"), TesseractEngine)
    assert "tesseract" in ENGINES
    with pytest.raises(OcrError, match="choose one of: tesseract"):
        make_engine("magic")


@pytest.mark.ocr
def test_real_tesseract_reads_a_title_crop() -> None:
    case = next(c for c in ALL if c.file == "IMG_0001.PNG")
    crop = crop_rows(load_image(case.path), 50, 140)
    text = TesseractEngine().read(binarize(crop, 1.75)).text
    assert text.strip().lower() == "starbucks"


def test_a_bar_between_words_is_a_capital_i() -> None:
    """From the benchmark: the game's capital I is read as ``|``."""
    ocr = result(
        ("edgemont", 90),
        ("world", 90),
        ("war", 90),
        ("|", 60),
        ("memorial", 90),
    )
    assert ocr.without_junk().text == "edgemont world war i memorial"
    assert ocr.junk() == ()


@pytest.mark.parametrize(
    "words",
    [
        [("|", 50), ("reserve", 90), ("the", 90)],  # could be the border
        [("church", 90), ("of", 90), ("|", 50)],
        [("|", 50), ("_", 20), ("|", 40)],  # nothing real around them
        [("|", 50)],
    ],
)
def test_a_bar_at_the_edge_stays_noise(words: list[tuple[str, float]]) -> None:
    ocr = result(*words)
    assert "i" not in ocr.without_junk().text.split()
    assert "|" in ocr.junk()


def test_junk_lists_only_what_was_actually_discarded() -> None:
    ocr = result(("_", 5), ("world", 90), ("|", 60), ("war", 90), ("\u00ab", 3))
    assert ocr.without_junk().text == "world i war"
    assert ocr.junk() == ("_", "\u00ab")
