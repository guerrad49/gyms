import pytest

from PokemonGo.matching import (
    Match,
    MatchKind,
    distance_m,
    find_matches,
    nearby_duplicates,
    similarity,
    unique_confident_match,
)
from PokemonGo.models import Coordinates, Gym

HERE = Coordinates(40.0, -75.0)


def _gyms(*titles: str) -> list[Gym]:
    return [Gym(uid=None, title=title) for title in titles]


def test_similarity_normalizes_before_comparing() -> None:
    assert similarity("  Starbucks\n", "starbucks") == 1.0
    assert similarity("abc", "xyz") == 0.0


def test_exact_match_wins_over_similar_ones() -> None:
    gyms = _gyms("starbuck", "starbucks")
    matches = find_matches("Starbucks", gyms)
    assert [m.kind for m in matches] == [MatchKind.EXACT]
    assert matches[0].gym is gyms[1]
    assert matches[0].score == 1.0


def test_duplicate_names_are_all_returned() -> None:
    gyms = _gyms("verizon", "verizon", "other")
    matches = find_matches("verizon", gyms)
    assert [m.gym for m in matches] == gyms[:2]


def test_similar_matches_are_ranked_best_first() -> None:
    gyms = _gyms("the church of jesus christ of latter-day saint", "x")
    title = "the church of jesus christ of latter day saints"
    gyms.append(Gym(None, "the church of jesus christ of latter-day saints!"))
    matches = find_matches(title, gyms)
    assert all(m.kind is MatchKind.SIMILAR for m in matches)
    scores = [m.score for m in matches]
    assert len(matches) == 2
    assert scores == sorted(scores, reverse=True)
    assert all(score >= 0.9 for score in scores)


def test_threshold_is_adjustable() -> None:
    gyms = _gyms("portland head light")
    assert find_matches("portland head lite", gyms, threshold=0.99) == []
    assert len(find_matches("portland head lite", gyms, threshold=0.8)) == 1


def test_titles_with_different_numbers_are_never_similar() -> None:
    # 91% similar by letters alone, but they are different gyms.
    assert similarity("building 10", "building 11") > 0.9
    assert find_matches("building 10", _gyms("building 11")) == []
    assert len(find_matches("building 11", _gyms("building 11"))) == 1


@pytest.mark.parametrize("title", ["", "   ", "_ |"])
def test_blank_titles_match_nothing(title: str) -> None:
    assert find_matches(title, _gyms("", "starbucks")) == []


def test_no_candidates_means_no_matches() -> None:
    assert find_matches("starbucks", []) == []


def test_matching_accepts_any_iterable() -> None:
    assert len(find_matches("a", iter(_gyms("a")))) == 1


@pytest.mark.parametrize(
    ("kind", "score", "accepted"),
    [
        (MatchKind.EXACT, 1.0, True),
        (MatchKind.SIMILAR, 0.96, True),
        (MatchKind.SIMILAR, 0.95, True),
        (MatchKind.SIMILAR, 0.94, False),
    ],
)
def test_unique_confident_match(
    kind: MatchKind, score: float, accepted: bool
) -> None:
    match = Match(Gym(None, "x"), score, kind)
    assert (unique_confident_match([match]) is match) is accepted


def test_several_matches_always_need_a_person() -> None:
    gym = Gym(None, "x")
    exact = Match(gym, 1.0, MatchKind.EXACT)
    assert unique_confident_match([exact, exact]) is None
    assert unique_confident_match([]) is None


def test_auto_accept_threshold_is_adjustable() -> None:
    match = Match(Gym(None, "x"), 0.91, MatchKind.SIMILAR)
    assert unique_confident_match([match], auto_accept=0.9) is match


def test_distance_of_one_degree_of_latitude() -> None:
    d = distance_m(Coordinates(0, 0), Coordinates(1, 0))
    assert d == pytest.approx(111_195, rel=1e-3)


def test_distance_is_symmetric_and_zero_for_the_same_point() -> None:
    other = Coordinates(40.01, -75.02)
    assert distance_m(HERE, HERE) == 0.0
    assert distance_m(HERE, other) == pytest.approx(distance_m(other, HERE))


def test_nearby_duplicates_respects_radius_and_title() -> None:
    close = Coordinates(40.0004, -75.0)  # about 44 m north
    far = Coordinates(40.01, -75.0)  # about 1.1 km north
    gyms = [
        Gym(1, "starbucks", close),
        Gym(2, "starbucks", far),
        Gym(3, "dunkin", close),
        Gym(4, "starbucks"),  # no coordinates
    ]
    found = nearby_duplicates("Starbucks", HERE, gyms)
    assert [g.uid for g in found] == [1]
    wide = nearby_duplicates("Starbucks", HERE, gyms, radius_m=5_000)
    assert [g.uid for g in wide] == [1, 2]


@pytest.mark.parametrize(
    ("read", "stored"),
    [
        ("lrony", "irony"),
        ("ll w tower", "ii w tower"),
        ("il w tower", "ii w tower"),
    ],
)
def test_a_capital_i_read_as_l_still_matches(read: str, stored: str) -> None:
    """From the benchmark: OCR draws the game's capital I as a lowercase l."""
    assert similarity(read, stored) == 1.0
    matches = find_matches(read, _gyms(stored))
    assert [m.kind for m in matches] == [MatchKind.SIMILAR]


def test_the_i_l_fold_never_counts_as_an_exact_match() -> None:
    [match] = find_matches("lrony", _gyms("irony"))
    assert match.kind is MatchKind.SIMILAR
    assert find_matches("irony", _gyms("irony"))[0].kind is MatchKind.EXACT
