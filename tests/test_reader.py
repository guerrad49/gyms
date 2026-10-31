"""BadgeReader with scripted OCR results: deterministic, no Tesseract."""

from pathlib import Path

import numpy as np
import pytest

from PokemonGo.errors import ImageReadError, UnsupportedDeviceError
from PokemonGo.models import Activity
from PokemonGo.vision.preprocess import Image, load_image
from PokemonGo.vision.reader import (
    TITLE_VARIANTS,
    BadgeReader,
    TitleCandidate,
    rank_titles,
)
from tests.support.engines import ScriptedEngine, lines, result
from tests.support.expected import ALL, Expected

I15 = next(c for c in ALL if c.file == "IMG_1305.PNG")  # 1179 x 2556
I11 = next(c for c in ALL if c.file == "IMG_0002.PNG")  # 828 x 1792
ACTIVITY = lines("victories time defended treats", "27 18d 0h 56m 16")


def _image(case: Expected) -> Image:
    return load_image(case.path)


def test_variants_are_tried_cheapest_first() -> None:
    assert [v.name for v in TITLE_VARIANTS] == [
        "default",
        "tall",
        "tall-inpaint",
        "default-inpaint",
    ]


def test_blind_ranking_drops_noise_and_prefers_confidence() -> None:
    engine = ScriptedEngine(
        [
            result(("_", 5), ("Starbucks", 96)),
            result(
                ("st", 60), ("Verizon", 70), ("17:57", 70), ("Starbucks", 90)
            ),
            result(("Starbucks", 96)),
            result(),  # nothing readable
            ACTIVITY,
        ]
    )
    reading = BadgeReader(engine).read_image(_image(I15))
    assert [t.text for t in reading.titles] == [
        "starbucks",
        "st verizon 17:57 starbucks",
    ]
    assert reading.title is not None
    assert reading.title.variant == "default"  # the earlier of equal reads
    assert reading.title.confidence == 96.0
    assert reading.activity == Activity(27, 18, 0, 56, 16)
    assert len(engine.images) == 5  # four title variants + the statistics


def test_known_titles_outrank_a_more_confident_wrong_reading() -> None:
    engine = ScriptedEngine(
        [
            result(("Something", 99), ("else", 99)),
            result(("Starbuck", 70)),
            result(),
            result(),
            ACTIVITY,
        ]
    )
    reading = BadgeReader(engine).read_image(
        _image(I15), known_titles=["Starbucks", ""]
    )
    assert reading.titles[0].text == "starbuck"


def test_an_exact_known_title_stops_the_search_early() -> None:
    engine = ScriptedEngine([result(("Starbucks", 80)), ACTIVITY])
    reading = BadgeReader(engine).read_image(
        _image(I15), known_titles=["starbucks"]
    )
    assert reading.title is not None
    assert reading.title.text == "starbucks"
    assert len(engine.images) == 2  # one title variant + the statistics


def test_nothing_readable_gives_no_title_and_no_activity() -> None:
    engine = ScriptedEngine([])
    reading = BadgeReader(engine).read_image(_image(I15))
    assert reading.titles == ()
    assert reading.title is None
    assert reading.activity is None
    assert reading.activity_text == ""


def test_unparseable_statistics_keep_the_raw_text() -> None:
    engine = ScriptedEngine(
        [
            result(("Starbucks", 90)),
            result(),
            result(),
            result(),
            lines("Victories", "27 18d 7n 16"),
        ]
    )
    reading = BadgeReader(engine).read_image(_image(I15))
    assert reading.activity is None
    assert reading.activity_text == "victories\n27 18d 7n 16"


def test_crop_geometry_follows_the_profile() -> None:
    engine = ScriptedEngine([])
    BadgeReader(engine).read_image(_image(I15))  # i15: scale 1.0
    default, tall, _, _, activity = engine.images
    assert default.shape == (100, 1179)  # rows 110-210
    assert tall.shape == (140, 1179)  # 40 rows taller
    assert activity.shape == (250, 1179)  # rows 1550-1800

    engine = ScriptedEngine([])
    BadgeReader(engine).read_image(_image(I11))  # i11: scale 1.5
    assert engine.images[0].shape == (135, 1242)  # 90 rows * 1.5


def test_a_forced_model_rescales_the_crops() -> None:
    engine = ScriptedEngine([])
    reading = BadgeReader(engine, model="i15").read_image(_image(I11))
    assert reading.profile.name == "i15"
    assert reading.profile.size == (1792, 828)
    # i15 rows 110-210 scaled by 1792/2556, then enlarged to 1179 wide.
    assert engine.images[0].shape == (100, 1179)


def test_an_unknown_size_needs_a_forced_model() -> None:
    odd = np.zeros((1000, 500, 3), dtype=np.uint8)
    with pytest.raises(UnsupportedDeviceError, match="--model"):
        BadgeReader(ScriptedEngine([])).read_image(odd)
    reading = BadgeReader(ScriptedEngine([]), model="i11").read_image(odd)
    assert reading.profile.size == (1000, 500)


def test_a_missing_file_is_reported(tmp_path: Path) -> None:
    with pytest.raises(ImageReadError):
        BadgeReader(ScriptedEngine([])).read(tmp_path / "nope.PNG")


def test_read_loads_the_file() -> None:
    engine = ScriptedEngine([result(("Ashford", 90)), ACTIVITY])
    reading = BadgeReader(engine).read(I15.path, known_titles=["ashford"])
    assert reading.profile.name == "i15"
    assert reading.title is not None
    assert reading.title.text == "ashford"


def test_rank_titles_breaks_ties_by_variant_order() -> None:
    first = TitleCandidate("a", 90.0, "default")
    second = TitleCandidate("b", 90.0, "tall")
    assert rank_titles([first, second]) == (first, second)
    assert rank_titles([second, first]) == (second, first)


def test_rank_titles_with_known_titles_uses_closeness_first() -> None:
    near = TitleCandidate("portland head light", 50.0, "tall")
    far = TitleCandidate("something", 99.0, "default")
    ranked = rank_titles([far, near], ["Portland Head Light"])
    assert ranked == (near, far)


def test_rank_titles_of_nothing_is_empty() -> None:
    assert rank_titles([]) == ()
