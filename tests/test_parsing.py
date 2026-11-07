import pytest

from PokemonGo.errors import ParseError
from PokemonGo.models import Activity, Coordinates, Flag
from PokemonGo.parsing import (
    format_status,
    normalize_title,
    parse_activity,
    parse_coordinates,
    parse_status,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        # Texts exactly as Tesseract returned them for the fixtures.
        (
            "victories time defended treats\n15 102d 5h 20",
            Activity(15, 102, 5, 0, 20),
        ),
        (
            "victories | time defended | treats\n1 20d 6h 58m 16",
            Activity(1, 20, 6, 58, 16),
        ),
        (
            "victories | time defended | treats\n8 21d 19h 13",
            Activity(8, 21, 19, 0, 13),
        ),
        # D1: the letter o read in place of a zero.
        (
            "victories | time defended | treats\n27 18d oh 56m 16",
            Activity(27, 18, 0, 56, 16),
        ),
        ("27 18d Oh 56m 16", Activity(27, 18, 0, 56, 16)),
        ("o 21d 18h 7m 104", Activity(0, 21, 18, 7, 104)),
        ("1 2d 3h 4m 5", Activity(1, 2, 3, 4, 5)),
        # Only some time components are shown.
        ("5 3d 12", Activity(5, 3, 0, 0, 12)),
        ("5 7m 12", Activity(5, 0, 0, 7, 12)),
        # Rare seconds are ignored.
        ("27 18d 1h 5m 3s 16", Activity(27, 18, 1, 5, 16)),
        # Digit look-alikes inside time values, from the benchmark of 1,191
        # screenshots: "1m" read as "im"/"lm", "51m" as "5im", "5h" as "sh".
        ("6 13d 11h im 43", Activity(6, 13, 11, 1, 43)),
        ("0 18d 18h im 62", Activity(0, 18, 18, 1, 62)),
        ("7 21d 5h lm 1", Activity(7, 21, 5, 1, 1)),
        ("176 17d 8h 5im 27", Activity(176, 17, 8, 51, 27)),
        ("11 19d sh 1m 17", Activity(11, 19, 5, 1, 17)),
        ("160 42d 4h im 10", Activity(160, 42, 4, 1, 10)),
        # Values may be split across lines or separated by bars.
        ("27\n18d 0h 56m\n16", Activity(27, 18, 0, 56, 16)),
        ("27 | 18d 0h 56m | 16", Activity(27, 18, 0, 56, 16)),
    ],
)
def test_parse_activity_reads_ocr_text(text: str, expected: Activity) -> None:
    assert parse_activity(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "victories time defended treats",
        "o 21d 18h 7n 104",  # "7n" is not a unit
        "15 20",  # no time component
        "5 3d 70m 12",  # minutes out of range
        "5 3d 25h 12",  # hours out of range
        "garbage",
    ],
)
def test_parse_activity_rejects_unreadable_text(text: str) -> None:
    assert parse_activity(text) is None


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Starbucks", "starbucks"),
        ("  The  Church\nof Jesus\n\nChrist ", "the church of jesus christ"),
        (
            "_ Paradise Avenue Gatehouse, Spring\n\nGrove",
            "paradise avenue gatehouse, spring grove",
        ),
        ("| ~ starbucks _", "starbucks"),
        ("Mary\u2019s Church", "mary's church"),
        ("Latter\u2014day Saints", "latter-day saints"),
        ("\uff33tarbucks", "starbucks"),  # full-width letter
        ("\u5927\u962a\u57ce", "\u5927\u962a\u57ce"),
        ("", ""),
        ("_ |", ""),
    ],
)
def test_normalize_title(text: str, expected: str) -> None:
    assert normalize_title(text) == expected


def test_normalize_title_is_idempotent() -> None:
    once = normalize_title("_ Mary\u2019s\nChurch ")
    assert normalize_title(once) == once


@pytest.mark.parametrize(
    ("text", "lat", "lon"),
    [
        ("40.758186,-73.985585", 40.758186, -73.985585),
        ("40.758186, -73.985585", 40.758186, -73.985585),
        ("(40.758186, -73.985585)", 40.758186, -73.985585),
        ("[40.75;-73.98]", 40.75, -73.98),
        ("40.75 -73.98", 40.75, -73.98),
        ("  +40.75\u00b0 , -73.98\u00b0 ", 40.75, -73.98),
        ("-12, 77", -12.0, 77.0),
        ("0,0", 0.0, 0.0),
    ],
)
def test_parse_coordinates_accepts_common_forms(
    text: str, lat: float, lon: float
) -> None:
    assert parse_coordinates(text) == Coordinates(lat, lon)


@pytest.mark.parametrize(
    ("text", "message"),
    [
        ("", "not a latitude,longitude pair"),
        ("somewhere", "not a latitude,longitude pair"),
        ("40.75", "not a latitude,longitude pair"),
        ("1,2,3", "not a latitude,longitude pair"),
        ("40.75N 73.98W", "not a latitude,longitude pair"),
        ("91, 0", "latitude must be within"),
        ("0, -181", "longitude must be within"),
    ],
)
def test_parse_coordinates_rejects_bad_input(text: str, message: str) -> None:
    with pytest.raises(ParseError, match=message):
        parse_coordinates(text)


def test_parse_status_and_format_round_trip() -> None:
    flags = parse_status("city, STATE  title,CITY")
    assert flags == (Flag.CITY, Flag.STATE, Flag.TITLE)
    assert format_status(flags) == "CITY,STATE,TITLE"
    assert parse_status(format_status(flags)) == flags


def test_parse_status_blank_means_clean() -> None:
    assert parse_status("") == ()
    assert parse_status("  ,  ") == ()
    assert format_status(()) == ""


def test_parse_status_rejects_unknown_flags() -> None:
    with pytest.raises(ParseError, match="unknown status flag: 'BOGUS'"):
        parse_status("CITY,BOGUS")
