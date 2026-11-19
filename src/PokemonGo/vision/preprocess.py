"""Prepare image regions for OCR.

All functions take and return BGR or grayscale ``uint8`` arrays and do
not modify their input.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

import cv2
import numpy as np
from numpy.typing import NDArray

from PokemonGo.errors import ImageReadError

Image = NDArray[np.uint8]
# A BGR (or grayscale) 8-bit image. Deliberately has no docstring: Sphinx
# shows the short name ``Image`` (see ``autodoc_type_aliases`` in
# docs/conf.py) instead of expanding numpy's internal array types.

THRESHOLD: Final = 200
"""Pixels brighter than this become foreground (text is light-on-dark
after the game's own contrast; this is v1's tuned value)."""

_DARKEST: Final = 100


def load_image(path: Path) -> Image:
    """Read an image file as BGR.

    Parameters
    ----------
    path : pathlib.Path
        The image file.

    Returns
    -------
    numpy.ndarray
        The image, height by width by 3, any alpha channel dropped.

    Raises
    ------
    ImageReadError
        If the file is missing or is not a readable image.
    """
    if not path.is_file():
        msg = f"image file not found: {path}"
        raise ImageReadError(msg)
    image = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if image is None:
        msg = f"not a readable image: {path}"
        raise ImageReadError(msg)
    return np.asarray(image, dtype=np.uint8)


def crop_rows(image: Image, start: int, end: int) -> Image:
    """Cut a band of full-width pixel rows out of an image.

    Parameters
    ----------
    image : numpy.ndarray
        The source image.
    start, end : int
        First row (inclusive) and last row (exclusive). Values outside
        the image are clamped to its edges.

    Returns
    -------
    numpy.ndarray
        A copy of the band.

    Raises
    ------
    ValueError
        If the band is empty after clamping.

    Examples
    --------
    >>> import numpy as np
    >>> crop_rows(np.zeros((10, 4, 3), dtype=np.uint8), -5, 3).shape
    (3, 4, 3)
    """
    start = max(start, 0)
    end = min(end, image.shape[0])
    if start >= end:
        msg = f"empty crop: rows {start} to {end} of {image.shape[0]}"
        raise ValueError(msg)
    return np.array(image[start:end, :], dtype=np.uint8)


def inpaint_status_bar(crop: Image) -> Image:
    """Paint over the phone's dark status-bar marks inside a crop.

    On two-line titles the clock and signal icons overlap the first line.
    The darkest pixels are treated as damage and reconstructed from their
    surroundings, which usually makes the title readable.

    Parameters
    ----------
    crop : numpy.ndarray
        A BGR crop containing the title.

    Returns
    -------
    numpy.ndarray
        The repaired crop.

    Notes
    -----
    Uses OpenCV's Telea inpainting; see the OpenCV tutorial at
    https://docs.opencv.org/3.4/df/d3d/tutorial_py_inpainting.html
    """
    lower = np.array([0, 0, 0], dtype=np.uint8)
    upper = np.array([_DARKEST] * 3, dtype=np.uint8)
    mask = cv2.inRange(crop, lower, upper)
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
    mask = cv2.dilate(mask, kernel, iterations=1)
    repaired = cv2.inpaint(crop, mask, 3, cv2.INPAINT_TELEA)
    return np.asarray(repaired, dtype=np.uint8)


def binarize(crop: Image, scale: float, threshold: int = THRESHOLD) -> Image:
    """Enlarge a crop and reduce it to black and white for OCR.

    Parameters
    ----------
    crop : numpy.ndarray
        A BGR crop.
    scale : float
        Enlargement factor.
    threshold : int, optional
        Gray level above which a pixel becomes foreground.

    Returns
    -------
    numpy.ndarray
        A single-channel image containing only 0 and 230.
    """
    height = round(crop.shape[0] * scale)
    width = round(crop.shape[1] * scale)
    resized = cv2.resize(crop, (width, height))
    gray = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, threshold, 230, cv2.THRESH_BINARY)
    return np.asarray(binary, dtype=np.uint8)
