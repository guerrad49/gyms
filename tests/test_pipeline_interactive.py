"""The scan pipeline with a person answering questions."""

from pathlib import Path

from PokemonGo.geo import Address
from PokemonGo.models import Activity, Coordinates, Flag, Gym
from PokemonGo.pipeline import Outcome
from tests.support.geo import FakeGeocoder
from tests.support.pipeline import STATS, ScriptedPrompter, make_reading
from tests.support.scan_env import HERE, Env, seed

STORED = "portland head light museum"
SIMILAR = "portlond head light musuem"  # 92% alike: needs confirming


def _scan(
    tmp_path: Path,
    reading_title: str,
    prompter: ScriptedPrompter,
    *,
    seeds: list[Gym] | None = None,
    geocoder: FakeGeocoder | None = None,
    activity: Activity | None = STATS,
) -> tuple[Env, Outcome]:
    env = Env(
        tmp_path,
        {"a.PNG": make_reading(reading_title, activity=activity)},
        seeds=seeds,
        geocoder=geocoder,
        prompter=prompter,
    )
    [result] = env.run(env.shot("a.PNG")).results
    assert prompter.finished()
    return env, result.outcome


# --- no questions when nothing is in doubt ---


def test_an_exact_match_asks_nothing(tmp_path: Path) -> None:
    prompter = ScriptedPrompter()
    env, outcome = _scan(tmp_path, "maple park", prompter, seeds=[seed()])
    assert outcome is Outcome.MATCHED
    assert prompter.questions == []
    assert env.saved()[0].uid == 1


# --- a similar title ---


def test_a_similar_title_is_confirmed(tmp_path: Path) -> None:
    prompter = ScriptedPrompter(confirms=[True])
    env, outcome = _scan(tmp_path, SIMILAR, prompter, seeds=[seed(STORED)])
    assert outcome is Outcome.MATCHED
    [question] = prompter.questions
    assert SIMILAR in question
    assert STORED in question
    assert "92%" in question
    assert env.saved()[0].title == STORED  # the stored spelling is kept


def test_refusing_a_similar_title_creates_a_new_gym_instead(
    tmp_path: Path,
) -> None:
    prompter = ScriptedPrompter(confirms=[False], asks=["", ""])
    env, outcome = _scan(tmp_path, SIMILAR, prompter, seeds=[seed(STORED)])
    assert outcome is Outcome.ADDED
    gyms = {g.title: g for g in env.saved()}
    assert gyms[STORED].is_seeded  # the seed is untouched
    assert gyms[SIMILAR].uid == 1
    assert gyms[SIMILAR].status == (Flag.NO_COORDS,)


# --- several gyms with the same title ---


def _twins() -> list[Gym]:
    return [
        Gym(None, "verizon", HERE, city="newark", state="new jersey"),
        Gym(None, "verizon", Coordinates(41.0, -76.0)),
    ]


def test_the_person_picks_among_gyms_with_the_same_title(
    tmp_path: Path,
) -> None:
    prompter = ScriptedPrompter(chooses=[1])
    env, outcome = _scan(tmp_path, "verizon", prompter, seeds=_twins())
    assert outcome is Outcome.MATCHED
    [options] = prompter.options
    assert options[0] == "verizon - newark, new jersey (40.0,-75.0)"
    assert options[1] == "verizon - unknown place (41.0,-76.0)"
    assert options[2].startswith("none of these")
    by_place = {g.coordinates: g for g in env.saved()}
    assert by_place[HERE].is_seeded  # the first twin was left alone
    assert by_place[Coordinates(41.0, -76.0)].uid == 1  # the second was chosen


def test_declining_to_pick_leaves_the_screenshot(tmp_path: Path) -> None:
    prompter = ScriptedPrompter(chooses=[None])
    env, outcome = _scan(tmp_path, "verizon", prompter, seeds=_twins())
    assert outcome is Outcome.SKIPPED
    assert all(g.is_seeded for g in env.saved())


def test_none_of_these_creates_a_new_gym(tmp_path: Path) -> None:
    prompter = ScriptedPrompter(chooses=[2], asks=["", "40.5,-74.5"])
    env, outcome = _scan(tmp_path, "verizon", prompter, seeds=_twins())
    assert outcome is Outcome.ADDED
    assert len(env.saved()) == 3


# --- a new gym ---


def test_a_new_gym_gets_its_title_and_coordinates(tmp_path: Path) -> None:
    prompter = ScriptedPrompter(asks=["", "40.7, -74.0"])
    env, outcome = _scan(tmp_path, "new place", prompter)
    assert outcome is Outcome.ADDED
    assert "no seeded gym matches" in prompter.questions[0]
    assert prompter.defaults[0] == "new place"  # Enter accepts the read title
    [gym] = env.saved()
    assert gym.title == "new place"
    assert gym.coordinates == Coordinates(40.7, -74.0)
    assert (gym.city, gym.state) == ("ames", "iowa")  # looked up
    assert gym.status == ()


def test_the_title_can_be_corrected_when_it_is_created(tmp_path: Path) -> None:
    prompter = ScriptedPrompter(asks=["  The  Right\nTitle ", ""])
    env, _ = _scan(tmp_path, "the rite title", prompter)
    assert env.saved()[0].title == "the right title"


def test_pasted_coordinate_forms_are_understood(tmp_path: Path) -> None:
    prompter = ScriptedPrompter(asks=["", "(40.7, -74.0)"])
    env, _ = _scan(tmp_path, "new place", prompter)
    assert env.saved()[0].coordinates == Coordinates(40.7, -74.0)


def test_unusable_coordinates_are_asked_again(tmp_path: Path) -> None:
    prompter = ScriptedPrompter(asks=["", "somewhere", "40.7,-74.0"])
    env, outcome = _scan(tmp_path, "new place", prompter)
    assert outcome is Outcome.ADDED
    assert any("not usable" in line for line in prompter.said)
    assert env.saved()[0].coordinates == Coordinates(40.7, -74.0)


def test_giving_up_on_coordinates_flags_the_gym(tmp_path: Path) -> None:
    prompter = ScriptedPrompter(asks=["", "x", "y", "z"])
    env, outcome = _scan(tmp_path, "new place", prompter)
    assert outcome is Outcome.ADDED
    assert env.saved()[0].status == (Flag.NO_COORDS,)
    assert len(prompter.said) == 3


def test_enter_means_the_coordinates_are_not_known_yet(tmp_path: Path) -> None:
    prompter = ScriptedPrompter(asks=["", ""])
    env, outcome = _scan(tmp_path, "new place", prompter)
    assert outcome is Outcome.ADDED
    assert env.saved()[0].status == (Flag.NO_COORDS,)
    assert env.geocoder.calls == []


def test_skip_at_the_title_or_coordinates_leaves_the_screenshot(
    tmp_path: Path,
) -> None:
    for answers in (["skip"], ["", "SKIP"], [None], [" skip "]):
        env, outcome = _scan(
            tmp_path / str(answers), "new place", ScriptedPrompter(asks=answers)
        )
        assert outcome is Outcome.SKIPPED
        assert env.saved() == []
        assert (env.downloads / "a.PNG").exists()


def test_an_empty_title_is_skipped(tmp_path: Path) -> None:
    prompter = ScriptedPrompter(asks=["_ |"])
    _, outcome = _scan(tmp_path, "new place", prompter)
    assert outcome is Outcome.SKIPPED


# --- a gym that may already be in the database ---


def _existing() -> Gym:
    return Gym(9, "new place", HERE, activity=Activity(1, 1, 1, 1, 1))


def test_a_nearby_gym_with_the_same_title_is_questioned(tmp_path: Path) -> None:
    prompter = ScriptedPrompter(asks=["", "40.0003,-75.0"], confirms=[False])
    env, outcome = _scan(tmp_path, "new place", prompter, seeds=[_existing()])
    assert outcome is Outcome.SKIPPED
    assert "gym #9" in prompter.questions[-1]
    assert len(env.saved()) == 1


def test_the_person_can_add_it_anyway(tmp_path: Path) -> None:
    prompter = ScriptedPrompter(asks=["", "40.0003,-75.0"], confirms=[True])
    env, outcome = _scan(tmp_path, "new place", prompter, seeds=[_existing()])
    assert outcome is Outcome.ADDED
    assert len(env.saved()) == 2


def test_a_same_titled_gym_far_away_is_not_questioned(tmp_path: Path) -> None:
    prompter = ScriptedPrompter(asks=["", "41.0,-75.0"])
    _, outcome = _scan(tmp_path, "new place", prompter, seeds=[_existing()])
    assert outcome is Outcome.ADDED


def test_gyms_planned_in_a_dry_run_count_as_existing(tmp_path: Path) -> None:
    prompter = ScriptedPrompter(
        asks=["", "40.0,-75.0", "", "40.0001,-75.0"], confirms=[False]
    )
    readings = {
        "a.PNG": make_reading("new place"),
        "b.PNG": make_reading("new place"),
    }
    env = Env(tmp_path, readings, prompter=prompter, dry_run=True)
    first, second = env.run(
        env.shot("a.PNG", b"1"), env.shot("b.PNG", b"2")
    ).results
    assert (first.outcome, second.outcome) == (Outcome.ADDED, Outcome.SKIPPED)


# --- statistics that could not be read ---


def test_statistics_can_be_typed_in(tmp_path: Path) -> None:
    prompter = ScriptedPrompter(asks=["27 18d 0h 56m 16"])
    env, outcome = _scan(
        tmp_path, "maple park", prompter, seeds=[seed()], activity=None
    )
    assert outcome is Outcome.MATCHED
    assert env.saved()[0].activity == STATS
    assert "27 18d 0h 56m 16" in prompter.questions[0]


def test_statistics_are_asked_again_when_not_understood(tmp_path: Path) -> None:
    prompter = ScriptedPrompter(asks=["rubbish", "27 18d 0h 56m 16"])
    _, outcome = _scan(
        tmp_path, "maple park", prompter, seeds=[seed()], activity=None
    )
    assert outcome is Outcome.MATCHED
    assert prompter.said == ["That was not understood; try again."]


def test_statistics_can_be_skipped_or_given_up_on(tmp_path: Path) -> None:
    for answers in (["skip"], [""], [None], ["a", "b", "c"]):
        prompter = ScriptedPrompter(asks=answers)
        env, outcome = _scan(
            tmp_path / str(answers),
            "maple park",
            prompter,
            seeds=[seed()],
            activity=None,
        )
        assert outcome is Outcome.SKIPPED
        assert env.saved()[0].is_seeded


# --- filling in a missing city or state ---


def test_a_missing_city_and_state_are_asked_for(tmp_path: Path) -> None:
    geocoder = FakeGeocoder(default=Address(county="story", country="peru"))
    prompter = ScriptedPrompter(asks=["  Huarocondo ", "CUSCO"])
    env, _ = _scan(
        tmp_path, "maple park", prompter, seeds=[seed()], geocoder=geocoder
    )
    [gym] = env.saved()
    assert (gym.city, gym.state) == ("huarocondo", "cusco")
    assert gym.status == ()
    assert "City for 'maple park'" in prompter.questions[0]
    assert "State for 'maple park'" in prompter.questions[1]


def test_a_blank_answer_leaves_the_field_flagged(tmp_path: Path) -> None:
    geocoder = FakeGeocoder(default=Address(state="cusco", county="x"))
    prompter = ScriptedPrompter(asks=[""])
    env, _ = _scan(
        tmp_path, "maple park", prompter, seeds=[seed()], geocoder=geocoder
    )
    assert env.saved()[0].status == (Flag.CITY,)


def test_the_county_is_never_asked_for(tmp_path: Path) -> None:
    geocoder = FakeGeocoder(default=Address(city="cusco", state="cusco"))
    prompter = ScriptedPrompter()  # any question would fail the test
    env, _ = _scan(
        tmp_path, "maple park", prompter, seeds=[seed()], geocoder=geocoder
    )
    assert env.saved()[0].status == (Flag.COUNTY,)


def test_nothing_is_asked_about_an_address_without_coordinates(
    tmp_path: Path,
) -> None:
    prompter = ScriptedPrompter(asks=["", ""])
    env, _ = _scan(tmp_path, "new place", prompter)
    assert len(prompter.questions) == 2  # title and coordinates only
    assert env.saved()[0].city == ""


# --- several screenshots in one run ---


def test_questions_are_asked_in_screenshot_order(tmp_path: Path) -> None:
    prompter = ScriptedPrompter(asks=["", "", "", "40.0,-75.0"])
    readings = {"a.PNG": make_reading("first"), "b.PNG": make_reading("second")}
    env = Env(tmp_path, readings, prompter=prompter)
    summary = env.run(env.shot("a.PNG"), env.shot("b.PNG"))
    assert [r.outcome for r in summary.results] == [
        Outcome.ADDED,
        Outcome.ADDED,
    ]
    assert "a.PNG" in prompter.questions[0]
    assert "b.PNG" in prompter.questions[2]
    assert prompter.defaults[0] == "first"  # the read title is offered
    assert prompter.defaults[2] == "second"
    assert prompter.finished()
