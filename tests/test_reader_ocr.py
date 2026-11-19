"""BadgeReader with real Tesseract on the six reference screenshots."""

import pytest

from PokemonGo.models import Activity
from PokemonGo.vision.reader import BadgeReader
from tests.support.expected import ALL, Expected

pytestmark = pytest.mark.ocr


@pytest.fixture(scope="module")
def reader() -> BadgeReader:
    return BadgeReader()


@pytest.mark.parametrize("case", ALL, ids=lambda c: c.file)
def test_every_fixture_reads_correctly_with_no_hints(
    case: Expected, reader: BadgeReader
) -> None:
    reading = reader.read(case.path)
    assert reading.profile.name == case.model
    assert reading.title is not None
    assert reading.title.text == case.title
    assert reading.activity == Activity(**case.activity)


@pytest.mark.parametrize("case", ALL, ids=lambda c: c.file)
def test_known_titles_give_the_same_answer(
    case: Expected, reader: BadgeReader
) -> None:
    reading = reader.read(case.path, known_titles=[case.title, "other"])
    assert reading.title is not None
    assert reading.title.text == case.title


def test_a_forced_model_still_reads_a_different_sized_image(
    reader: BadgeReader,
) -> None:
    case = next(c for c in ALL if c.file == "IMG_0002.PNG")  # i11
    forced = BadgeReader(model="i15").read(case.path)
    assert forced.profile.name == "i15"
    assert forced.title is not None
    assert forced.title.text == case.title
