"""Sample gyms that exercise the awkward cases of every backend."""

from datetime import date

from PokemonGo.models import Activity, Coordinates, Flag, Gym


def seeded() -> Gym:
    """Return a gym with only a title and coordinates (a v1 seed row)."""
    return Gym(None, "maple park", Coordinates(40.758186, -73.985585))


def scanned() -> Gym:
    """Return a fully scanned gym with every field filled in."""
    return Gym(
        uid=7,
        title="the church of jesus christ of latter-day saints",
        coordinates=Coordinates(-13.329799, -72.195433),
        model="i15",
        activity=Activity(8, 21, 19, 0, 13),
        city="huarocondo",
        county="",
        state="cusco",
        country="peru",
        status=(Flag.CITY, Flag.COUNTY),
        scanned_at=date(2026, 11, 2),
        notes='line one, with a comma\nline two with "quotes"',
        image_sha256="ab" * 32,
    )


def unicode_gym() -> Gym:
    """Return a gym whose text is not ASCII."""
    return Gym(
        uid=12,
        title="\u5927\u962a\u57ce",
        coordinates=Coordinates(34.6873, 135.5262),
        activity=Activity(246, 2, 3, 40, 369),
        city="\u5927\u962a",
        state="\u5927\u962a\u5e9c",
        country="japan",
    )


def many() -> list[Gym]:
    """Return gyms in a non-geographic order, for the sort tests."""
    here = Coordinates(40.0, -75.0)
    return [
        Gym(
            3,
            "zebra",
            here,
            activity=Activity(1, 1, 1, 1, 1),
            city="b",
            county="y",
            state="maine",
        ),
        Gym(
            1,
            "Apple",
            here,
            activity=Activity(1, 1, 1, 1, 1),
            city="a",
            county="x",
            state="maine",
        ),
        Gym(
            2,
            "pear",
            here,
            activity=Activity(1, 1, 1, 1, 1),
            city="a",
            state="maine",
        ),  # no county
        Gym(None, "seed in ohio", here, state="ohio", city="c", county="z"),
        Gym(
            4,
            "banana",
            here,
            activity=Activity(1, 1, 1, 1, 1),
            city="a",
            county="x",
            state="iowa",
        ),
        Gym(5, "no state", here, activity=Activity(1, 1, 1, 1, 1)),
    ]


EXPECTED_ORDER = [
    "banana",  # iowa
    "Apple",  # maine / x / a
    "zebra",  # maine / y / b
    "pear",  # maine / (no county) -> blanks last
    "seed in ohio",  # ohio
    "no state",  # no state -> last
]
