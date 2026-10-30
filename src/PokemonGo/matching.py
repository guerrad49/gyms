"""Find gyms by title, and detect likely duplicates by location.

Matching never prompts. It returns ranked candidates, and the caller
(the pipeline, through a ``Prompter``) decides what to do with them.
This replaces v1's ``are_similar``, which called ``input()`` from inside
a pandas ``apply``.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import Enum
from typing import Final

from PokemonGo.models import Coordinates, Gym
from PokemonGo.parsing import normalize_title

SIMILARITY_MIN: Final = 0.9
"""Minimum :func:`similarity` for a candidate (same as v1)."""

AUTO_ACCEPT: Final = 0.95
"""Default score for accepting a unique match without asking."""

NEARBY_RADIUS_M: Final = 100.0
"""Default radius, in metres, for :func:`nearby_duplicates`."""

EARTH_RADIUS_M: Final = 6_371_008.8


class MatchKind(str, Enum):
    """How a candidate matched the title."""

    EXACT = "exact"
    SIMILAR = "similar"


@dataclass(frozen=True, slots=True)
class Match:
    """A candidate gym for a scanned title.

    Attributes
    ----------
    gym : Gym
        The candidate.
    score : float
        ``1.0`` for an exact match, otherwise the similarity ratio.
    kind : MatchKind
        Whether the normalized titles are identical or only similar.
    """

    gym: Gym
    score: float
    kind: MatchKind


def _numbers(text: str) -> list[str]:
    """Return the digit runs in a title, in order."""
    return re.findall(r"\d+", text)


def similarity(a: str, b: str) -> float:
    """Measure how alike two titles are, from 0 to 1.

    Both titles are normalized first (see
    :func:`PokemonGo.parsing.normalize_title`).

    Parameters
    ----------
    a, b : str
        The titles to compare.

    Returns
    -------
    float
        ``1.0`` for identical titles after normalization.

    Examples
    --------
    >>> similarity("Starbucks", "starbucks")
    1.0
    >>> round(similarity("starbucks", "starbuck5"), 2)
    0.89
    """
    matcher = SequenceMatcher(
        None, normalize_title(a), normalize_title(b), autojunk=False
    )
    return matcher.ratio()


def find_matches(
    title: str,
    gyms: Iterable[Gym],
    *,
    threshold: float = SIMILARITY_MIN,
) -> list[Match]:
    """Find the gyms a scanned title may refer to.

    If any gym has exactly the same normalized title, only those are
    returned (several when names repeat, which is common). Otherwise the
    gyms at or above ``threshold`` similarity are returned, best first.

    A similar title is **rejected** when its numbers differ, because
    ``"building 10"`` and ``"building 11"`` are 91% similar but are
    different gyms.

    Parameters
    ----------
    title : str
        The scanned title.
    gyms : iterable of Gym
        The candidates, for example only the seeded rows.
    threshold : float, optional
        Minimum similarity for a non-exact match.

    Returns
    -------
    list of Match
        Empty when nothing matches.

    Examples
    --------
    >>> rows = [Gym(None, "starbucks"), Gym(None, "building 11")]
    >>> [m.kind.value for m in find_matches("Starbucks", rows)]
    ['exact']
    >>> find_matches("building 10", rows)
    []
    """
    target = normalize_title(title)
    if not target:
        return []

    exact: list[Match] = []
    similar: list[Match] = []
    for gym in gyms:
        candidate = normalize_title(gym.title)
        if candidate == target:
            exact.append(Match(gym, 1.0, MatchKind.EXACT))
        elif _numbers(candidate) == _numbers(target):
            score = similarity(candidate, target)
            if score >= threshold:
                similar.append(Match(gym, score, MatchKind.SIMILAR))

    if exact:
        return exact
    return sorted(similar, key=lambda match: match.score, reverse=True)


def unique_confident_match(
    matches: Sequence[Match], *, auto_accept: float = AUTO_ACCEPT
) -> Match | None:
    """Pick a match that is safe to accept without asking.

    This is the rule for non-interactive runs: accept only when there is
    exactly one candidate and it is exact or scores at least
    ``auto_accept``.

    Parameters
    ----------
    matches : sequence of Match
        The output of :func:`find_matches`.
    auto_accept : float, optional
        Minimum score for a similar (non-exact) match.

    Returns
    -------
    Match or None
        The match, or ``None`` when a person needs to decide.

    Examples
    --------
    >>> gym = Gym(None, "starbucks")
    >>> unique_confident_match([Match(gym, 1.0, MatchKind.EXACT)]) is None
    False
    >>> unique_confident_match([Match(gym, 0.93, MatchKind.SIMILAR)]) is None
    True
    """
    if len(matches) != 1:
        return None
    match = matches[0]
    if match.kind is MatchKind.EXACT or match.score >= auto_accept:
        return match
    return None


def distance_m(a: Coordinates, b: Coordinates) -> float:
    """Return the great-circle distance between two points in metres.

    Parameters
    ----------
    a, b : Coordinates
        The two points.

    Returns
    -------
    float
        The haversine distance.

    Examples
    --------
    >>> point = Coordinates(40.0, -75.0)
    >>> distance_m(point, point)
    0.0
    >>> round(distance_m(Coordinates(0, 0), Coordinates(0, 1)) / 1000)
    111
    """
    lat_a, lat_b = math.radians(a.latitude), math.radians(b.latitude)
    d_lat = lat_b - lat_a
    d_lon = math.radians(b.longitude - a.longitude)
    h = (
        math.sin(d_lat / 2) ** 2
        + math.cos(lat_a) * math.cos(lat_b) * math.sin(d_lon / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def nearby_duplicates(
    title: str,
    coordinates: Coordinates,
    gyms: Iterable[Gym],
    *,
    radius_m: float = NEARBY_RADIUS_M,
) -> list[Gym]:
    """Find gyms with the same title close to a point.

    Used to warn that a "new" gym is probably a re-scan of a gym already
    in the database.

    Parameters
    ----------
    title : str
        The title of the gym about to be added.
    coordinates : Coordinates
        Where it is.
    gyms : iterable of Gym
        The existing gyms.
    radius_m : float, optional
        How close counts as nearby, in metres.

    Returns
    -------
    list of Gym
        Existing gyms with an identical normalized title within the radius.
        Gyms without coordinates are never reported.

    Examples
    --------
    >>> here = Coordinates(40.0, -75.0)
    >>> rows = [Gym(1, "starbucks", here), Gym(2, "starbucks")]
    >>> [g.uid for g in nearby_duplicates("Starbucks", here, rows)]
    [1]
    """
    target = normalize_title(title)
    return [
        gym
        for gym in gyms
        if gym.coordinates is not None
        and normalize_title(gym.title) == target
        and distance_m(coordinates, gym.coordinates) <= radius_m
    ]
