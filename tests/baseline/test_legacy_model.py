"""Baseline: v1 behavior that needs no OCR engine.

Passing tests describe behavior the rewrite must keep. Tests marked
``xfail(strict=True)`` document a known defect; they will start failing
(as unexpected passes) once the defect is fixed, which is the signal to
delete the marker.
"""

from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
import pytesseract
import pytest

from tests.support import legacy
from tests.support.expected import ALL, Expected

FIRST = ALL[0]


@pytest.mark.parametrize("case", ALL, ids=lambda c: c.file)
def test_device_model_is_detected_from_size(case: Expected) -> None:
    assert legacy.detect_model(case.path) == case.model


def test_unsupported_size_is_rejected(tmp_path: Path) -> None:
    odd = tmp_path / "odd.PNG"
    cv2.imwrite(str(odd), np.zeros((100, 50, 3), dtype=np.uint8))
    error = legacy.load("exceptions").UnsupportedPhoneModel
    with pytest.raises(error):
        legacy.badge_image(odd)


@pytest.mark.parametrize("case", ALL, ids=lambda c: c.file)
def test_defended_and_style_match_ground_truth(case: Expected) -> None:
    defended, style = legacy.gym_values(case.activity)
    assert defended == case.defended
    assert style == case.style


@pytest.mark.parametrize(("days", "style"), [(99, "gold"), (100, "100+ days")])
def test_long_term_threshold_is_one_hundred_days(days: int, style: str) -> None:
    activity = {
        "victories": 0,
        "days": days,
        "hours": 0,
        "minutes": 0,
        "treats": 0,
    }
    assert legacy.gym_values(activity)[1] == style


@pytest.mark.xfail(
    strict=True, reason="D1: region compared to an int, cleanup is dead code"
)
def test_title_newlines_are_collapsed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pytesseract, "image_to_string", lambda *_a, **_k: "line one\nline two"
    )
    img = legacy.badge_image(FIRST.path)
    img.set_title_crop()
    assert img.get_text(region="title") == "line one line two"


@pytest.mark.xfail(
    strict=True, reason="D1: region compared to an int, cleanup is dead code"
)
def test_activity_letter_o_becomes_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pytesseract, "image_to_string", lambda *_a, **_k: "27 18d Oh 56m 16"
    )
    img = legacy.badge_image(FIRST.path)
    img.set_activity_crop()
    assert img.get_text(region="activity") == "27 18d 0h 56m 16"


@pytest.mark.xfail(
    strict=True,
    raises=TypeError,
    reason="D2: scanner.py passes offset=, the parameter is northOffset",
)
def test_title_crop_accepts_the_keyword_scanner_uses() -> None:
    img = legacy.badge_image(FIRST.path)
    img.set_title_crop(offset=40)
