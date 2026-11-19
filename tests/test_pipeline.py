"""The scan pipeline, unattended: what is saved, skipped and filed."""

import hashlib
from datetime import datetime
from pathlib import Path

import pytest

from PokemonGo.errors import (
    GeocodingError,
    ImageReadError,
    StoreError,
    UnsupportedDeviceError,
)
from PokemonGo.geo import Address
from PokemonGo.matching import similarity
from PokemonGo.models import Activity, Coordinates, Flag, Gym
from PokemonGo.pipeline import (
    Outcome,
    SafeGeocoder,
    Scanner,
)
from tests.support.geo import FakeGeocoder
from tests.support.pipeline import (
    STATS,
    make_reading,
    make_shot,
)
from tests.support.scan_env import AMES, HERE, Env, seed

# --- a seeded gym is filled in ---


def test_an_exact_title_fills_in_the_seeded_gym(tmp_path: Path) -> None:
    env = Env(tmp_path, {"a.PNG": make_reading("maple park")}, seeds=[seed()])
    shot = env.shot("a.PNG", mtime=1_700_000_000)
    [result] = env.run(shot).results
    assert result.outcome is Outcome.MATCHED
    assert result.stored_as == "IMG_0001.PNG"
    [gym] = env.saved()
    assert gym.row == 2  # filled in place, not added as a second row
    assert (gym.uid, gym.title, gym.model, gym.activity) == (
        1,
        "maple park",
        "i15",
        STATS,
    )
    assert (gym.city, gym.state, gym.country) == (
        "ames",
        "iowa",
        "united states",
    )
    assert gym.image_sha256 == hashlib.sha256(b"a.PNG").hexdigest()
    assert gym.scanned_at == datetime.fromtimestamp(1_700_000_000).date()
    assert gym.status == (Flag.COUNTY,) or gym.status == ()
    assert (env.badges / "IMG_0001.PNG").read_bytes() == b"a.PNG"
    assert not shot.exists()


def test_only_seeded_titles_are_given_to_the_reader_as_hints(
    tmp_path: Path,
) -> None:
    scanned = Gym(7, "already done", HERE, activity=Activity(1, 1, 1, 1, 1))
    env = Env(
        tmp_path,
        {"a.PNG": make_reading("maple park")},
        seeds=[scanned, seed("maple park"), seed("other seed")],
    )
    env.run(env.shot("a.PNG"))
    assert env.reader.calls == [("a.PNG", ("maple park", "other seed"))]


def test_new_ids_continue_from_the_largest_in_processing_order(
    tmp_path: Path,
) -> None:
    existing = Gym(41, "old", HERE, activity=Activity(1, 1, 1, 1, 1))
    readings = {"a.PNG": make_reading("alpha"), "b.PNG": make_reading("beta")}
    env = Env(tmp_path, readings, seeds=[existing])
    summary = env.run(env.shot("a.PNG"), env.shot("b.PNG"))
    assert [r.gym.uid for r in summary.results if r.gym] == [42, 43]
    assert env.filed() == ["IMG_0042.PNG", "IMG_0043.PNG"]


def test_a_seed_is_used_once_even_if_two_screenshots_match_it(
    tmp_path: Path,
) -> None:
    readings = {
        "a.PNG": make_reading("maple park"),
        "b.PNG": make_reading("maple park"),
    }
    env = Env(tmp_path, readings, seeds=[seed()])
    summary = env.run(env.shot("a.PNG"), env.shot("b.PNG"))
    assert [r.outcome for r in summary.results] == [
        Outcome.MATCHED,
        Outcome.ADDED,
    ]
    assert len(env.saved()) == 2


# --- unattended: new gyms and uncertain titles ---


def test_a_new_gym_is_added_flagged_for_its_missing_coordinates(
    tmp_path: Path,
) -> None:
    env = Env(tmp_path, {"a.PNG": make_reading("new place")})
    [result] = env.run(env.shot("a.PNG")).results
    assert result.outcome is Outcome.ADDED
    [gym] = env.saved()
    assert (gym.uid, gym.title, gym.coordinates) == (1, "new place", None)
    assert gym.status == (Flag.NO_COORDS,)
    assert env.geocoder.calls == []  # nowhere to look up
    assert env.filed() == ["IMG_0001.PNG"]


def test_a_similar_title_is_accepted_only_above_the_threshold(
    tmp_path: Path,
) -> None:
    stored = "portland head light museum"
    sure, unsure = "portland head light museun", "portlond head light musuem"
    assert (
        similarity(stored, sure)
        > 0.95
        > 0.9
        <= similarity(stored, unsure)
        < 0.95
    )

    env = Env(tmp_path, {"a.PNG": make_reading(sure)}, seeds=[seed(stored)])
    assert env.run(env.shot("a.PNG")).results[0].outcome is Outcome.MATCHED

    env = Env(
        tmp_path / "x", {"a.PNG": make_reading(unsure)}, seeds=[seed(stored)]
    )
    shot = env.shot("a.PNG")
    [result] = env.run(shot).results
    assert result.outcome is Outcome.SKIPPED
    assert "needs a person" in result.reason
    assert shot.exists()
    assert env.saved()[0].is_seeded  # nothing was saved
    assert env.filed() == []


def test_the_threshold_can_be_changed(tmp_path: Path) -> None:
    env = Env(
        tmp_path,
        {"a.PNG": make_reading("portlond head light musuem")},
        seeds=[seed("portland head light museum")],
        auto_accept=0.9,
    )
    assert env.run(env.shot("a.PNG")).results[0].outcome is Outcome.MATCHED


def test_several_gyms_with_the_same_title_need_a_person(tmp_path: Path) -> None:
    env = Env(
        tmp_path,
        {"a.PNG": make_reading("verizon")},
        seeds=[seed("verizon", HERE), seed("verizon", Coordinates(41, -76))],
    )
    shot = env.shot("a.PNG")
    [result] = env.run(shot).results
    assert result.outcome is Outcome.SKIPPED
    assert shot.exists()
    assert all(g.is_seeded for g in env.saved())


def test_unreadable_statistics_leave_the_screenshot_alone(
    tmp_path: Path,
) -> None:
    env = Env(
        tmp_path,
        {"a.PNG": make_reading("maple park", activity=None)},
        seeds=[seed()],
    )
    shot = env.shot("a.PNG")
    [result] = env.run(shot).results
    assert result.outcome is Outcome.SKIPPED
    assert "statistics" in result.reason
    assert shot.exists()


def test_a_screenshot_with_no_readable_title_is_skipped(tmp_path: Path) -> None:
    env = Env(tmp_path, {"a.PNG": make_reading()})
    [result] = env.run(env.shot("a.PNG")).results
    assert result.outcome is Outcome.SKIPPED
    assert result.reason == "no title could be read"


# --- problems with one screenshot do not stop the others ---


def test_a_bad_screenshot_is_reported_and_the_scan_goes_on(
    tmp_path: Path,
) -> None:
    readings = {
        "bad.PNG": ImageReadError("not a readable image"),
        "odd.PNG": UnsupportedDeviceError(
            "image size 1x1 matches no known phone"
        ),
        "ok.PNG": make_reading("fine"),
    }
    env = Env(tmp_path, readings)
    summary = env.run(
        env.shot("bad.PNG"), env.shot("odd.PNG"), env.shot("ok.PNG")
    )
    assert [r.outcome for r in summary.results] == [
        Outcome.ERROR,
        Outcome.ERROR,
        Outcome.ADDED,
    ]
    assert "not a readable image" in summary.results[0].reason
    assert [r.path.name for r in summary.needs_attention] == [
        "bad.PNG",
        "odd.PNG",
    ]


def test_a_failing_database_stops_the_scan(tmp_path: Path) -> None:
    env = Env(
        tmp_path, {"a.PNG": make_reading("x"), "b.PNG": make_reading("y")}
    )

    def fail() -> None:
        raise StoreError("the sheet is unreachable")

    env.store.commit = fail  # type: ignore[method-assign]
    shot_a, shot_b = env.shot("a.PNG"), env.shot("b.PNG")
    with pytest.raises(StoreError, match="unreachable"):
        env.run(shot_a, shot_b)
    assert shot_a.exists()  # never filed away without its row
    assert shot_b.exists()


# --- screenshots that were already scanned ---


def test_scanning_the_same_screenshot_twice_adds_nothing(
    tmp_path: Path,
) -> None:
    env = Env(
        tmp_path,
        {"a.PNG": make_reading("alpha"), "copy.PNG": make_reading("alpha")},
    )
    env.run(env.shot("a.PNG", b"same pixels"))
    [result] = env.run(env.shot("copy.PNG", b"same pixels")).results
    assert result.outcome is Outcome.ALREADY
    assert "already in the database as #1" in result.reason
    assert len(env.saved()) == 1


def test_an_interrupted_run_is_finished_by_running_it_again(
    tmp_path: Path,
) -> None:
    done = Gym(
        5,
        "alpha",
        HERE,
        activity=Activity(1, 1, 1, 1, 1),
        image_sha256=hashlib.sha256(b"pixels").hexdigest(),
    )
    env = Env(tmp_path, {}, seeds=[done])
    shot = env.shot("a.PNG", b"pixels")
    [result] = env.run(shot).results
    assert result.outcome is Outcome.ALREADY
    assert "filed as IMG_0005.PNG" in result.reason
    assert env.filed() == ["IMG_0005.PNG"]
    assert not shot.exists()


def test_a_duplicate_is_left_where_it_is_when_the_original_is_filed(
    tmp_path: Path,
) -> None:
    done = Gym(
        5,
        "alpha",
        HERE,
        activity=Activity(1, 1, 1, 1, 1),
        image_sha256=hashlib.sha256(b"pixels").hexdigest(),
    )
    env = Env(tmp_path, {}, seeds=[done])
    make_shot(env.badges, "IMG_0005.PNG", b"pixels")
    shot = env.shot("again.PNG", b"pixels")
    [result] = env.run(shot).results
    assert "left where it is" in result.reason
    assert shot.exists()


# --- filing ---


def test_copy_keeps_the_original(tmp_path: Path) -> None:
    env = Env(tmp_path, {"a.PNG": make_reading("alpha")}, copy=True)
    shot = env.shot("a.PNG")
    env.run(shot)
    assert shot.exists()
    assert env.filed() == ["IMG_0001.PNG"]


def test_an_existing_file_is_never_overwritten(tmp_path: Path) -> None:
    env = Env(tmp_path, {"a.PNG": make_reading("alpha")})
    make_shot(env.badges, "IMG_0001.PNG", b"someone else's file")
    shot = env.shot("a.PNG")
    [result] = env.run(shot).results
    assert result.outcome is Outcome.ERROR
    assert "already exists" in result.reason
    assert env.saved() == []
    assert (env.badges / "IMG_0001.PNG").read_bytes() == b"someone else's file"


def test_a_filing_failure_is_reported_but_the_row_is_kept(
    tmp_path: Path,
) -> None:
    env = Env(tmp_path, {"a.PNG": make_reading("alpha")})
    env.badges.write_text("a file where the folder should be", encoding="utf-8")
    shot = env.shot("a.PNG")
    [result] = env.run(shot).results
    assert result.outcome is Outcome.ERROR
    assert (
        "saved in the database, but the screenshot was not filed"
        in result.reason
    )
    assert len(env.saved()) == 1
    assert shot.exists()


# --- dry run ---


def test_a_dry_run_changes_nothing(tmp_path: Path) -> None:
    env = Env(
        tmp_path,
        {
            "a.PNG": make_reading("maple park"),
            "b.PNG": make_reading("brand new"),
        },
        seeds=[seed()],
        dry_run=True,
    )
    shots = [env.shot("a.PNG"), env.shot("b.PNG")]
    before = env.db.read_bytes()
    summary = env.run(*shots)
    assert [r.outcome for r in summary.results] == [
        Outcome.MATCHED,
        Outcome.ADDED,
    ]
    assert [r.stored_as for r in summary.results] == [
        "IMG_0001.PNG",
        "IMG_0002.PNG",
    ]
    assert [r.gym.uid for r in summary.results if r.gym] == [1, 2]
    assert env.db.read_bytes() == before
    assert not env.badges.exists()
    assert all(s.exists() for s in shots)
    assert summary.sorted is False


def test_a_dry_run_still_notices_repeats_within_the_batch(
    tmp_path: Path,
) -> None:
    readings = {"a.PNG": make_reading("alpha"), "b.PNG": make_reading("alpha")}
    env = Env(tmp_path, readings, dry_run=True)
    summary = env.run(env.shot("a.PNG", b"same"), env.shot("b.PNG", b"same"))
    assert [r.outcome for r in summary.results] == [
        Outcome.ADDED,
        Outcome.ALREADY,
    ]


# --- sorting ---


def test_the_database_is_sorted_at_the_end(tmp_path: Path) -> None:
    readings = {"a.PNG": make_reading("zebra"), "b.PNG": make_reading("apple")}
    env = Env(tmp_path, readings, geocoder=FakeGeocoder(default=AMES))
    summary = env.run(env.shot("a.PNG"), env.shot("b.PNG"))
    assert summary.sorted is True
    # both have no coordinates, so no state: sorted by title
    assert [g.title for g in env.saved()] == ["apple", "zebra"]


def test_nothing_is_sorted_when_nothing_was_written(tmp_path: Path) -> None:
    env = Env(tmp_path, {"a.PNG": make_reading("x", activity=None)})
    assert env.run(env.shot("a.PNG")).sorted is False


def test_sorting_can_be_turned_off(tmp_path: Path) -> None:
    readings = {"a.PNG": make_reading("zebra"), "b.PNG": make_reading("apple")}
    env = Env(tmp_path, readings, sort=False)
    summary = env.run(env.shot("a.PNG"), env.shot("b.PNG"))
    assert summary.sorted is False
    assert [g.title for g in env.saved()] == ["zebra", "apple"]


# --- addresses ---


def test_missing_address_parts_are_flagged(tmp_path: Path) -> None:
    geocoder = FakeGeocoder(default=Address(state="cusco"))
    env = Env(
        tmp_path,
        {"a.PNG": make_reading("maple park")},
        seeds=[seed()],
        geocoder=geocoder,
    )
    env.run(env.shot("a.PNG"))
    [gym] = env.saved()
    assert gym.state == "cusco"
    assert gym.status == (Flag.CITY, Flag.COUNTY)


def test_a_failed_lookup_flags_the_gym_but_still_saves_it(
    tmp_path: Path,
) -> None:
    geocoder = FakeGeocoder(default=AMES, fail_on=[str(HERE)])
    env = Env(
        tmp_path,
        {"a.PNG": make_reading("maple park")},
        seeds=[seed()],
        geocoder=geocoder,
    )
    [result] = env.run(env.shot("a.PNG")).results
    assert result.outcome is Outcome.MATCHED
    assert env.saved()[0].status == (Flag.ADDRESS,)


def test_lookups_are_switched_off_after_repeated_failures(
    tmp_path: Path,
) -> None:
    seeds = [seed(f"gym {i}", Coordinates(i + 1, i + 1)) for i in range(5)]
    readings = {f"{i}.PNG": make_reading(f"gym {i}") for i in range(5)}
    geocoder = FakeGeocoder(
        default=AMES, fail_on=[str(s.coordinates) for s in seeds]
    )
    env = Env(tmp_path, readings, seeds=seeds, geocoder=geocoder)
    summary = env.run(*[env.shot(f"{i}.PNG") for i in range(5)])
    assert len(geocoder.calls) == 3  # the last two were never tried
    assert "switched off after 3 failures" in summary.geocoding_problem
    assert "pogo resolve" in summary.geocoding_problem
    assert all(g.has_flag(Flag.ADDRESS) for g in env.saved())
    assert summary.count(Outcome.MATCHED) == 5


# --- the pieces ---


def test_the_safe_geocoder_recovers_after_a_success() -> None:
    inner = FakeGeocoder(default=AMES, fail_on=["1.0,1.0", "2.0,2.0"])
    safe = SafeGeocoder(inner, max_failures=3)
    assert safe.reverse(Coordinates(1, 1)) is None
    assert safe.reverse(Coordinates(2, 2)) is None
    assert safe.reverse(HERE) == AMES  # a success resets the count
    assert safe.reverse(Coordinates(1, 1)) is None
    assert safe.disabled_reason == ""


def test_the_safe_geocoder_turns_off_and_stays_off() -> None:
    inner = FakeGeocoder(default=AMES, fail_on=["1.0,1.0"])
    safe = SafeGeocoder(inner, max_failures=2)
    for _ in range(2):
        safe.reverse(Coordinates(1, 1))
    assert "switched off" in safe.disabled_reason
    assert safe.reverse(HERE) is None
    assert inner.calls == ["1.0,1.0", "1.0,1.0"]


def test_the_summary_counts_and_lists_what_needs_attention(
    tmp_path: Path,
) -> None:
    readings = {
        "ok.PNG": make_reading("fine"),
        "skip.PNG": make_reading("x", activity=None),
    }
    env = Env(tmp_path, readings)
    summary = env.run(env.shot("ok.PNG"), env.shot("skip.PNG"))
    assert summary.count(Outcome.ADDED) == 1
    assert summary.count(Outcome.SKIPPED) == 1
    assert [r.path.name for r in summary.needs_attention] == ["skip.PNG"]
    assert [g.title for g in summary.flagged] == ["fine"]  # NO_COORDS


def test_results_are_reported_as_they_happen(tmp_path: Path) -> None:
    env = Env(
        tmp_path, {"a.PNG": make_reading("a"), "b.PNG": make_reading("b")}
    )
    seen: list[str] = []
    scanner = Scanner(
        reader=env.reader,
        store=env.store,
        geocoder=env.geocoder,
        prompter=env.prompter,
        options=env.options,
    )
    scanner.run(
        [env.shot("a.PNG"), env.shot("b.PNG")],
        on_result=lambda r: seen.append(r.path.name),
    )
    assert seen == ["a.PNG", "b.PNG"]


def test_geocoding_errors_from_the_geocoder_never_escape(
    tmp_path: Path,
) -> None:
    class Exploding:
        def reverse(self, coordinates: Coordinates) -> Address | None:
            raise GeocodingError("boom")

    env = Env(tmp_path, {"a.PNG": make_reading("maple park")}, seeds=[seed()])
    scanner = Scanner(
        reader=env.reader,
        store=env.store,
        geocoder=Exploding(),
        prompter=env.prompter,
        options=env.options,
    )
    [result] = scanner.run([env.shot("a.PNG")]).results
    assert result.outcome is Outcome.MATCHED
