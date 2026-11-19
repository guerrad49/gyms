"""Where the title and statistics sit on each supported iPhone.

A :class:`DeviceProfile` is plain data, so supporting another phone means
adding one entry to :data:`PROFILES`; nothing else changes.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Final

from PokemonGo.errors import UnsupportedDeviceError

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class DeviceProfile:
    """Crop geometry for one iPhone screen size.

    Parameters
    ----------
    name : str
        Profile name such as ``"i15"``; also written to the ``model``
        column.
    size : tuple of int
        Reference ``(height, width)`` of a screenshot, in pixels.
    scale : float
        Factor by which a crop is enlarged before OCR. Smaller screens
        need more enlargement.
    title_rows : tuple of int
        First and last pixel row of the title area.
    activity_rows : tuple of int
        First and last pixel row of the victories/time/treats area.
    """

    name: str
    size: tuple[int, int]
    scale: float
    title_rows: tuple[int, int]
    activity_rows: tuple[int, int]

    def scaled_to(self, size: tuple[int, int]) -> DeviceProfile:
        """Adapt the profile to an image of a different size.

        Row positions are scaled by the height ratio, and the OCR scale
        by the inverse width ratio, so the enlarged crop keeps the same
        pixel width. This is an approximation: it assumes the layout
        grows in proportion.

        Parameters
        ----------
        size : tuple of int
            The ``(height, width)`` of the actual image.

        Returns
        -------
        DeviceProfile
            ``self`` when the size already matches, otherwise a rescaled
            copy with the same name.

        Examples
        --------
        >>> profile = PROFILES["i15"]
        >>> profile.scaled_to((1278, 590)).title_rows
        (55, 105)
        >>> profile.scaled_to(profile.size) is profile
        True
        """
        if size == self.size:
            return self
        height, width = size
        ref_height, ref_width = self.size
        ratio = height / ref_height

        def rows(pair: tuple[int, int]) -> tuple[int, int]:
            return round(pair[0] * ratio), round(pair[1] * ratio)

        return replace(
            self,
            size=size,
            scale=round(self.scale * ref_width / width, 4),
            title_rows=rows(self.title_rows),
            activity_rows=rows(self.activity_rows),
        )


PROFILES: Final[Mapping[str, DeviceProfile]] = {
    profile.name: profile
    for profile in (
        DeviceProfile("iSE", (1334, 750), 1.75, (50, 140), (975, 1100)),
        DeviceProfile("i11", (1792, 828), 1.5, (60, 150), (1075, 1225)),
        DeviceProfile("i15", (2556, 1179), 1.0, (110, 210), (1550, 1800)),
    )
}
"""The supported phones, keyed by profile name."""


def profile_names() -> tuple[str, ...]:
    """Return the names of all supported profiles.

    Returns
    -------
    tuple of str
        For example ``("iSE", "i11", "i15")``.
    """
    return tuple(PROFILES)


def get_profile(name: str) -> DeviceProfile:
    """Look a profile up by name, ignoring case.

    Parameters
    ----------
    name : str
        A profile name such as ``"i15"`` or ``"I15"``.

    Returns
    -------
    DeviceProfile
        The profile.

    Raises
    ------
    UnsupportedDeviceError
        If there is no such profile; the message lists the choices.

    Examples
    --------
    >>> get_profile("ISE").name
    'iSE'
    """
    for profile in PROFILES.values():
        if profile.name.lower() == name.strip().lower():
            return profile
    choices = ", ".join(profile_names())
    msg = f"unknown phone model {name!r}; choose one of: {choices}"
    raise UnsupportedDeviceError(msg)


def detect_profile(size: tuple[int, int]) -> DeviceProfile:
    """Find the profile whose reference size equals an image's size.

    Parameters
    ----------
    size : tuple of int
        The image ``(height, width)``.

    Returns
    -------
    DeviceProfile
        The matching profile.

    Raises
    ------
    UnsupportedDeviceError
        If no profile has this size. The message names the profile with
        the closest aspect ratio, so ``--model`` can be suggested.

    Examples
    --------
    >>> detect_profile((1792, 828)).name
    'i11'
    """
    for profile in PROFILES.values():
        if profile.size == size:
            return profile
    height, width = size
    closest = min(
        PROFILES.values(),
        key=lambda p: abs(p.size[0] / p.size[1] - height / width),
    )
    msg = (
        f"image size {width}x{height} matches no known phone; "
        f"the closest profile is {closest.name!r} "
        f"(force it with --model {closest.name})"
    )
    raise UnsupportedDeviceError(msg)


def select_profile(
    size: tuple[int, int], forced: str | None = None
) -> DeviceProfile:
    """Choose the profile for an image.

    Parameters
    ----------
    size : tuple of int
        The image ``(height, width)``.
    forced : str, optional
        A profile name to use instead of detecting one. If the image is
        a different size than that profile expects, the profile is
        rescaled (see :meth:`DeviceProfile.scaled_to`) and a warning is
        logged.

    Returns
    -------
    DeviceProfile
        A profile whose geometry fits ``size``.

    Raises
    ------
    UnsupportedDeviceError
        If ``forced`` is unknown, or nothing is forced and the size is
        not recognized.
    """
    if forced is None:
        return detect_profile(size)
    profile = get_profile(forced)
    if profile.size != size:
        logger.warning(
            "image is %dx%d but profile %s expects %dx%d; scaling crops",
            size[1],
            size[0],
            profile.name,
            profile.size[1],
            profile.size[0],
        )
    return profile.scaled_to(size)
