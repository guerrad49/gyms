"""Turn text into values: badge statistics, titles, coordinates, flags.

Everything here is pure. OCR engines and people both produce text with
small mistakes, so the parsers are tolerant where a mistake is
unambiguous (a letter ``o`` where a ``0`` belongs) and strict otherwise.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable
from typing import Final

from PokemonGo.errors import ParseError
from PokemonGo.models import Activity, Coordinates, Flag

# A digit, or the letter "o" that OCR often reads in place of a zero.
_NUM: Final = r"[0-9o]"

# Inside a time value (before d, h or m) Tesseract also reads the digit 1
# as the letter i or l ("1m" -> "im"), and the digit 5 as s ("5h" -> "sh").
_TIME: Final = r"[0-9oils]"
_LOOKALIKES: Final = str.maketrans("oils", "0115")

_ACTIVITY_RE: Final = re.compile(
    rf"""
    (?<![0-9a-z])                           # not inside a longer word
    (?P<victories>{_NUM}{{1,4}})
    [\s|]+
    (?:(?P<days>{_TIME}{{1,3}})d[\s|]*)?
    (?:(?P<hours>{_TIME}{{1,2}})h[\s|]*)?
    (?:(?P<minutes>{_TIME}{{1,2}})m[\s|]*)?
    (?:{_NUM}{{1,2}}s[\s|]*)?               # seconds: shown rarely, ignored
    (?P<treats>{_NUM}{{1,4}})
    (?![0-9a-z])
    """,
    re.VERBOSE,
)

_COORDINATES_RE: Final = re.compile(
    r"""
    ^\s*[(\[]?\s*
    (?P<lat>[-+]?\d+(?:\.\d+)?)\s*°?
    (?:\s*[,;]\s*|\s+)
    (?P<lon>[-+]?\d+(?:\.\d+)?)\s*°?
    \s*[)\]]?\s*$
    """,
    re.VERBOSE,
)

_QUOTES: Final = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "\u2013": "-",
        "\u2014": "-",
    }
)

_TITLE_EDGE_JUNK: Final = " _|~"


def _to_int(digits: str | None) -> int:
    """Convert matched text, reading look-alike letters as digits."""
    if digits is None:
        return 0
    return int(digits.translate(_LOOKALIKES))


def parse_activity(text: str) -> Activity | None:
    r"""Parse badge statistics from OCR text.

    The text normally has a row of labels followed by a row of values,
    such as ``"victories time defended treats\n27 18d 0h 56m 16"``. The
    labels are ignored. OCR look-alikes are read as digits: ``o`` is
    zero everywhere, and inside a time value ``i`` and ``l`` are one and
    ``s`` is five, so ``18d oh 56m`` and ``13d 11h im`` both parse.

    Parameters
    ----------
    text : str
        Raw text read from the activity region of a badge.

    Returns
    -------
    Activity or None
        The statistics, or ``None`` if the text does not contain victories,
        at least one time component, and treats, or if a value is out of
        range (for example 70 minutes).

    Examples
    --------
    >>> parse_activity("27 18d Oh 56m 16")
    Activity(victories=27, days=18, hours=0, minutes=56, treats=16)
    >>> parse_activity("victories | time defended | treats\n8 21d 19h 13")
    Activity(victories=8, days=21, hours=19, minutes=0, treats=13)
    >>> parse_activity("o 21d 18h 7m 104")
    Activity(victories=0, days=21, hours=18, minutes=7, treats=104)
    >>> parse_activity("6 13d 11h im 43")
    Activity(victories=6, days=13, hours=11, minutes=1, treats=43)
    >>> parse_activity("o 21d 18h 7n 104") is None
    True
    """
    match = _ACTIVITY_RE.search(text.lower())
    if match is None:
        return None
    if not any(match[unit] for unit in ("days", "hours", "minutes")):
        return None
    try:
        return Activity(
            victories=_to_int(match["victories"]),
            days=_to_int(match["days"]),
            hours=_to_int(match["hours"]),
            minutes=_to_int(match["minutes"]),
            treats=_to_int(match["treats"]),
        )
    except ValueError:
        return None


def normalize_title(text: str) -> str:
    r"""Normalize a gym title for storing and comparing.

    The result is lowercase, on one line, with single spaces, curly
    quotes and long dashes replaced by plain ones, and stray ``_``, ``|``
    or ``~`` characters removed from both ends (typical OCR noise from the
    phone status bar).

    Parameters
    ----------
    text : str
        A title as read by OCR or typed by a person.

    Returns
    -------
    str
        The normalized title; empty if nothing usable remains.

    Examples
    --------
    >>> normalize_title("_ Paradise Avenue Gatehouse, Spring\n\nGrove")
    'paradise avenue gatehouse, spring grove'
    >>> normalize_title("Mary\u2019s Church")
    "mary's church"
    """
    text = unicodedata.normalize("NFKC", text).translate(_QUOTES)
    text = " ".join(text.lower().split())
    return text.strip(_TITLE_EDGE_JUNK)


def parse_coordinates(text: str) -> Coordinates:
    """Parse a latitude and longitude typed or pasted by a person.

    Accepted forms include ``40.75,-73.98``, ``40.75, -73.98``,
    ``(40.75, -73.98)``, ``40.75 -73.98`` and values followed by a degree
    sign. Hemisphere letters (``N``, ``W``) are not supported.

    Parameters
    ----------
    text : str
        The text to parse.

    Returns
    -------
    Coordinates
        The validated coordinates.

    Raises
    ------
    ParseError
        If the text is not a pair of numbers, or the values are out of
        range.

    Examples
    --------
    >>> parse_coordinates("(40.758186, -73.985585)")
    Coordinates(latitude=40.758186, longitude=-73.985585)
    >>> parse_coordinates("40.7 -74")
    Coordinates(latitude=40.7, longitude=-74.0)
    >>> parse_coordinates("somewhere")
    Traceback (most recent call last):
        ...
    PokemonGo.errors.ParseError: not a latitude,longitude pair: 'somewhere'
    """
    match = _COORDINATES_RE.match(text)
    if match is None:
        msg = f"not a latitude,longitude pair: {text[:40]!r}"
        raise ParseError(msg)
    try:
        return Coordinates(float(match["lat"]), float(match["lon"]))
    except ValueError as error:
        raise ParseError(str(error)) from error


def parse_status(text: str) -> tuple[Flag, ...]:
    """Parse the ``status`` column into flags.

    Parameters
    ----------
    text : str
        Flags separated by commas or spaces; blank means no flags.

    Returns
    -------
    tuple of Flag
        The flags in the order given, without duplicates.

    Raises
    ------
    ParseError
        If a token is not a known flag.

    Examples
    --------
    >>> [flag.value for flag in parse_status("city, STATE")]
    ['CITY', 'STATE']
    >>> parse_status("")
    ()
    """
    flags: list[Flag] = []
    for token in re.split(r"[,\s]+", text.strip()):
        if not token:
            continue
        try:
            flag = Flag(token.upper())
        except ValueError:
            msg = f"unknown status flag: {token!r}"
            raise ParseError(msg) from None
        if flag not in flags:
            flags.append(flag)
    return tuple(flags)


def format_status(flags: Iterable[Flag]) -> str:
    """Format flags for the ``status`` column.

    Parameters
    ----------
    flags : iterable of Flag
        The flags to write.

    Returns
    -------
    str
        The flag names joined with commas; empty when there are none.

    Examples
    --------
    >>> format_status([Flag.CITY, Flag.STATE])
    'CITY,STATE'
    """
    return ",".join(flag.value for flag in flags)
