from pathlib import Path

import numpy as np
import pytest

from PokemonGo.errors import ImageReadError
from PokemonGo.vision.devices import PROFILES
from PokemonGo.vision.preprocess import (
    Image,
    binarize,
    crop_rows,
    inpaint_status_bar,
    load_image,
)
from tests.support.expected import ALL, Expected


def _blank(height: int = 10, width: int = 4) -> Image:
    return np.full((height, width, 3), 255, dtype=np.uint8)


@pytest.mark.parametrize("case", ALL, ids=lambda c: c.file)
def test_load_image_returns_bgr_pixels(case: Expected) -> None:
    image = load_image(case.path)
    assert image.dtype == np.uint8
    assert image.shape == (*PROFILES[case.model].size, 3)


def test_load_image_reports_a_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ImageReadError, match="not found"):
        load_image(tmp_path / "nope.PNG")


def test_load_image_reports_a_file_that_is_not_an_image(
    tmp_path: Path,
) -> None:
    fake = tmp_path / "fake.PNG"
    fake.write_text("not an image", encoding="utf-8")
    with pytest.raises(ImageReadError, match="not a readable image"):
        load_image(fake)


def test_crop_rows_takes_a_full_width_band() -> None:
    crop = crop_rows(_blank(), 2, 5)
    assert crop.shape == (3, 4, 3)


def test_crop_rows_clamps_to_the_image() -> None:
    assert crop_rows(_blank(), -5, 3).shape[0] == 3
    assert crop_rows(_blank(), 8, 99).shape[0] == 2


def test_crop_rows_returns_a_copy() -> None:
    image = _blank()
    crop_rows(image, 0, 3)[:] = 0
    assert np.min(image) == 255


@pytest.mark.parametrize(("start", "end"), [(5, 5), (7, 3), (20, 30)])
def test_crop_rows_rejects_an_empty_band(start: int, end: int) -> None:
    with pytest.raises(ValueError, match="empty crop"):
        crop_rows(_blank(), start, end)


def test_inpainting_removes_dark_marks_without_touching_the_input() -> None:
    crop = _blank(40, 80)
    crop[15:25, 30:50] = 0  # a black mark, like a clock digit
    repaired = inpaint_status_bar(crop)
    assert np.min(crop) == 0
    assert np.min(repaired) > 200
    assert repaired.shape == crop.shape


def test_binarize_scales_and_leaves_only_two_levels() -> None:
    gradient = np.tile(
        np.linspace(0, 255, 20, dtype=np.uint8)[:, None, None], (1, 30, 3)
    )
    binary = binarize(gradient, 2.0)
    assert binary.shape == (40, 60)
    assert binary.dtype == np.uint8
    assert set(np.unique(binary)) <= {0, 230}


def test_binarize_threshold_is_adjustable() -> None:
    gray = np.full((4, 4, 3), 150, dtype=np.uint8)
    assert np.max(binarize(gray, 1.0, threshold=200)) == 0
    assert np.min(binarize(gray, 1.0, threshold=100)) == 230
