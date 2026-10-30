"""Run the new parsers on real Tesseract output for the six fixtures."""

import pytest

from PokemonGo.matching import find_matches
from PokemonGo.models import Activity, Gym
from PokemonGo.parsing import parse_activity
from tests.support import legacy
from tests.support.expected import ALL, Expected

pytestmark = pytest.mark.ocr


@pytest.mark.parametrize("case", ALL, ids=lambda c: c.file)
def test_activity_is_parsed_for_every_fixture(case: Expected) -> None:
    """D1: includes IMG_1305, which the v1 regex could not parse."""
    text = legacy.activity_text(case.path)
    assert parse_activity(text) == Activity(**case.activity)


@pytest.mark.parametrize("case", ALL, ids=lambda c: c.file)
def test_a_title_read_matches_without_asking(case: Expected) -> None:
    """D6/D10: no read needs a prompt; matching is pure and tolerant."""
    gyms = [Gym(None, case.title), Gym(None, "unrelated place")]
    reads = legacy.title_passes(case.path)
    assert any(find_matches(text, gyms) for text in reads)
