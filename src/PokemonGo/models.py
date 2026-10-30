"""Domain models for gyms and their badge statistics.

The classes here hold values and enforce their invariants; they do no
input or output. Reading and writing them is the job of the store
backends, and extracting them from screenshots is the job of the vision
layer.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from enum import Enum
from typing import Final

LONG_TERM_DAYS: Final = 100
"""Days defended at which a gym counts as long term."""

HOURS_PER_DAY: Final = 24
MINUTES_PER_HOUR: Final = 60
MINUTES_PER_DAY: Final = 1440


class Style(str, Enum):
    """The gym style written to the ``style`` column."""

    GOLD = "gold"
    LONG_TERM = "100+ days"


class Flag(str, Enum):
    """A review flag recorded in the ``status`` column.

    A flag means "a person should look at this". Blank means clean.
    """

    TITLE = "TITLE"
    STATS = "STATS"
    CITY = "CITY"
    COUNTY = "COUNTY"
    STATE = "STATE"
    ADDRESS = "ADDRESS"
    NO_COORDS = "NO_COORDS"


@dataclass(frozen=True, slots=True)
class Activity:
    """Statistics read from a badge screenshot.

    Parameters
    ----------
    victories : int
        Total gym victories.
    days, hours, minutes : int
        Time defended. ``hours`` must be below 24 and ``minutes`` below 60.
    treats : int
        Total treats given.

    Raises
    ------
    TypeError
        If a value is not an ``int``.
    ValueError
        If a value is negative or a time component is out of range.

    Examples
    --------
    >>> activity = Activity(27, 18, 0, 56, 16)
    >>> activity.defended
    18.0389
    >>> activity.style.value
    'gold'
    >>> Activity(1, 0, 24, 0, 1)
    Traceback (most recent call last):
        ...
    ValueError: hours must be below 24, got 24
    """

    victories: int
    days: int
    hours: int
    minutes: int
    treats: int

    def __post_init__(self) -> None:
        """Validate the fields."""
        values = {
            "victories": self.victories,
            "days": self.days,
            "hours": self.hours,
            "minutes": self.minutes,
            "treats": self.treats,
        }
        for name, value in values.items():
            if isinstance(value, bool) or not isinstance(value, int):
                msg = f"{name} must be an int, got {value!r}"
                raise TypeError(msg)
            if value < 0:
                msg = f"{name} must not be negative, got {value}"
                raise ValueError(msg)
        if self.hours >= HOURS_PER_DAY:
            msg = f"hours must be below 24, got {self.hours}"
            raise ValueError(msg)
        if self.minutes >= MINUTES_PER_HOUR:
            msg = f"minutes must be below 60, got {self.minutes}"
            raise ValueError(msg)

    @property
    def defended(self) -> float:
        """Time defended in fractional days, rounded to 4 decimals."""
        total: float = self.days
        total += self.hours / HOURS_PER_DAY
        total += self.minutes / MINUTES_PER_DAY
        return round(total, 4)

    @property
    def style(self) -> Style:
        """The gym style, gold or long term (from 100 days)."""
        if self.days < LONG_TERM_DAYS:
            return Style.GOLD
        return Style.LONG_TERM


@dataclass(frozen=True, slots=True)
class Coordinates:
    """A validated latitude and longitude in decimal degrees.

    Parameters
    ----------
    latitude : float
        Degrees north, from -90 to 90.
    longitude : float
        Degrees east, from -180 to 180.

    Raises
    ------
    ValueError
        If a value is not finite or is out of range.

    Examples
    --------
    >>> str(Coordinates(40.758186, -73.985585))
    '40.758186,-73.985585'
    >>> Coordinates(91, 0)
    Traceback (most recent call last):
        ...
    ValueError: latitude must be within -90 and 90, got 91
    """

    latitude: float
    longitude: float

    def __post_init__(self) -> None:
        """Validate the ranges."""
        for name, value, limit in (
            ("latitude", self.latitude, 90),
            ("longitude", self.longitude, 180),
        ):
            if not math.isfinite(value) or abs(value) > limit:
                msg = f"{name} must be within -{limit} and {limit}, "
                msg += f"got {value:g}"
                raise ValueError(msg)

    def __str__(self) -> str:
        """Format as ``lat,lon`` with no space, as in the old sheet."""
        return f"{self.latitude},{self.longitude}"


@dataclass(slots=True)
class Gym:
    """One gym row, whether seeded or fully scanned.

    Parameters
    ----------
    uid : int or None
        The unique id. ``None`` while the gym is seeded but not yet
        scanned.
    title : str
        The gym title, lowercase.
    coordinates : Coordinates, optional
        Where the gym is, if known.
    model : str, optional
        The phone profile the badge was scanned on.
    activity : Activity, optional
        The badge statistics, once scanned.
    city, county, state, country : str, optional
        Address fields, lowercase.
    status : tuple of Flag, optional
        Review flags. Empty means clean.
    scanned_at : datetime.date, optional
        The date of the screenshot.
    notes : str, optional
        Free text.
    image_sha256 : str, optional
        SHA-256 of the screenshot, used to skip images already processed.

    Examples
    --------
    >>> gym = Gym(uid=None, title="starbucks")
    >>> gym.is_seeded
    True
    >>> gym.add_flag(Flag.CITY)
    >>> gym.has_flag(Flag.CITY)
    True
    """

    uid: int | None
    title: str
    coordinates: Coordinates | None = None
    model: str = ""
    activity: Activity | None = None
    city: str = ""
    county: str = ""
    state: str = ""
    country: str = ""
    status: tuple[Flag, ...] = ()
    scanned_at: date | None = None
    notes: str = ""
    image_sha256: str = ""

    @property
    def is_seeded(self) -> bool:
        """Whether the gym has no ``uid`` yet, i.e. was not scanned."""
        return self.uid is None

    @property
    def latitude(self) -> float | None:
        """The latitude, or ``None`` when the coordinates are unknown."""
        return None if self.coordinates is None else self.coordinates.latitude

    @property
    def longitude(self) -> float | None:
        """The longitude, or ``None`` when the coordinates are unknown."""
        if self.coordinates is None:
            return None
        return self.coordinates.longitude

    def has_flag(self, flag: Flag) -> bool:
        """Return whether a review flag is set.

        Parameters
        ----------
        flag : Flag
            The flag to look for.

        Returns
        -------
        bool
            ``True`` if the flag is in ``status``.
        """
        return flag in self.status

    def add_flag(self, flag: Flag) -> None:
        """Set a review flag, keeping ``status`` free of duplicates.

        Parameters
        ----------
        flag : Flag
            The flag to add.
        """
        if flag not in self.status:
            self.status = (*self.status, flag)
