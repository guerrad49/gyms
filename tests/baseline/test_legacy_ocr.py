"""Baseline: v1 behavior that depends on Tesseract.

OCR output varies between Tesseract versions, so these checks use
similarity thresholds, and defect markers are *not* strict: an
unexpected pass is tolerated rather than failing the build.
"""

from __future__ import annotations

from difflib import SequenceMatcher

import pytest

from tests.support import legacy
from tests.support.expected import ALL, Expected

pytestmark = pytest.mark.ocr

SIMILARITY_MIN = 0.9  # the same threshold v1 uses in utils.are_similar


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def _expect_defect(
    request: pytest.FixtureRequest, case: Expected, check: str
) -> None:
    defect = case.known_defects.get(check)
    if defect is not None:
        request.applymarker(
            pytest.mark.xfail(strict=False, reason=f"{defect}: see PLAN.md")
        )


@pytest.mark.parametrize("case", ALL, ids=lambda c: c.file)
def test_two_pass_title_is_close_enough_to_match(case: Expected) -> None:
    """Characterizes how v1 finds titles: similar, then confirmed by you."""
    passes = legacy.title_passes(case.path)
    best = max(
        (legacy.squash(text) for text in passes),
        key=lambda text: _ratio(text, case.title),
    )
    assert _ratio(best, case.title) >= SIMILARITY_MIN


@pytest.mark.parametrize("case", ALL, ids=lambda c: c.file)
def test_single_pass_title_is_exact(
    case: Expected, request: pytest.FixtureRequest
) -> None:
    _expect_defect(request, case, "title_single_pass")
    first, _second = legacy.title_passes(case.path)
    assert legacy.squash(first) == case.title


@pytest.mark.parametrize("case", ALL, ids=lambda c: c.file)
def test_title_text_has_no_line_breaks(
    case: Expected, request: pytest.FixtureRequest
) -> None:
    _expect_defect(request, case, "title_newlines")
    _first, second = legacy.title_passes(case.path)
    assert "\n" not in second


@pytest.mark.parametrize("case", ALL, ids=lambda c: c.file)
def test_activity_is_parsed(
    case: Expected, request: pytest.FixtureRequest
) -> None:
    _expect_defect(request, case, "activity")
    text = legacy.activity_text(case.path)
    assert legacy.parse_activity(text) == case.activity
