from pathlib import Path

from PokemonGo.models import Activity, Coordinates, Flag, Gym
from PokemonGo.pipeline import (
    Outcome,
    ScanResult,
    ScanSummary,
    describe_gym,
    format_result,
    format_summary,
)
from tests.support.pipeline import make_reading

SHOT = Path("/downloads/IMG_5.PNG")


def _gym(**changes: object) -> Gym:
    base = {
        "uid": 7,
        "title": "maple park",
        "coordinates": Coordinates(40.0, -75.0),
        "activity": Activity(27, 18, 0, 56, 16),
        "city": "ames",
        "state": "iowa",
    }
    return Gym(**{**base, **changes})  # type: ignore[arg-type]


def test_a_gym_is_described_on_one_line() -> None:
    assert describe_gym(_gym()) == (
        "#7 maple park (40.0,-75.0) 27 wins, 18d 0h 56m, 16 treats - ames, iowa"
    )


def test_missing_parts_are_left_out_and_flags_are_shown() -> None:
    gym = _gym(coordinates=None, activity=None, city="", state="")
    gym.add_flag(Flag.NO_COORDS)
    assert describe_gym(gym) == "#7 maple park [NO_COORDS]"


def test_every_place_part_is_listed() -> None:
    text = describe_gym(_gym(county="story", country="united states"))
    assert text.endswith("- ames, story, iowa, united states")


def _result(outcome: Outcome, **fields: object) -> ScanResult:
    return ScanResult(SHOT, outcome, **fields)  # type: ignore[arg-type]


def test_results_are_phrased_for_a_real_run_and_a_dry_run() -> None:
    added = _result(Outcome.ADDED, gym=_gym(), stored_as="IMG_0007.PNG")
    assert format_result(added).startswith("IMG_5.PNG: added #7 maple park")
    assert format_result(added).endswith("-> IMG_0007.PNG")
    assert "would add #7" in format_result(added, dry_run=True)
    matched = _result(Outcome.MATCHED, gym=_gym(), stored_as="IMG_0007.PNG")
    assert "filled in #7" in format_result(matched)
    assert "would fill in #7" in format_result(matched, dry_run=True)


def test_other_outcomes() -> None:
    assert format_result(
        _result(Outcome.ALREADY, reason="already in the database as #3")
    ) == ("IMG_5.PNG: already in the database as #3")
    assert format_result(_result(Outcome.SKIPPED, reason="needs a person")) == (
        "IMG_5.PNG: SKIPPED - needs a person"
    )
    assert format_result(_result(Outcome.ERROR, reason="boom")) == (
        "IMG_5.PNG: ERROR - boom"
    )


def test_verbose_shows_what_was_read() -> None:
    reading = make_reading("maple park", "st verizon maple park")
    result = _result(Outcome.SKIPPED, reason="x", reading=reading)
    text = format_result(result, verbose=True)
    assert (
        "read on i15: 'maple park' (default 95), 'st verizon maple park'"
        in text
    )
    nothing = _result(Outcome.SKIPPED, reason="x", reading=make_reading())
    assert "no title" in format_result(nothing, verbose=True)
    assert "read on" not in format_result(result)


def _summary() -> ScanSummary:
    flagged = _gym()
    flagged.add_flag(Flag.CITY)
    return ScanSummary(
        results=[
            _result(Outcome.ADDED, gym=flagged, stored_as="IMG_0007.PNG"),
            _result(Outcome.MATCHED, gym=_gym(uid=8), stored_as="IMG_0008.PNG"),
            _result(Outcome.SKIPPED, reason="needs a person"),
            _result(Outcome.ERROR, reason="boom"),
        ],
        sorted=True,
    )


def test_the_summary_counts_and_lists_what_needs_attention() -> None:
    text = format_summary(_summary())
    assert (
        "Scanned 4 screenshots: 1 added, 1 filled in, 0 already scanned, "
        "1 skipped, 1 errors." in text
    )
    assert "Needs attention (left where they are):" in text
    assert "  IMG_5.PNG: needs a person" in text
    assert "Written with review flags:" in text
    assert "[CITY]" in text
    assert "The database was sorted." in text
    assert "Dry run" not in text


def test_a_dry_run_summary_says_nothing_was_saved() -> None:
    text = format_summary(_summary(), dry_run=True)
    assert "Dry run: nothing was saved, moved or created." in text
    assert "was sorted" not in text


def test_long_lists_are_cut_off() -> None:
    summary = ScanSummary(
        results=[_result(Outcome.SKIPPED, reason=f"r{i}") for i in range(5)]
    )
    text = format_summary(summary, show=2)
    assert "... and 3 more" in text
    assert "r1" in text
    assert "r2" not in text


def test_a_geocoding_problem_is_reported() -> None:
    summary = ScanSummary(geocoding_problem="address lookups were switched off")
    assert "switched off" in format_summary(summary)
    assert (
        format_summary(ScanSummary())
        == "Scanned 0 screenshots: 0 added, 0 filled in, 0 already scanned, "
        "0 skipped, 0 errors."
    )
