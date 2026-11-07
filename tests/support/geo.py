"""Fakes for address lookups: no test ever touches the network."""

from collections.abc import Mapping, Sequence
from types import SimpleNamespace

from PokemonGo.errors import GeocodingError
from PokemonGo.geo import Address, LocationLike
from PokemonGo.models import Coordinates


class FakeGeocoder:
    """Returns prepared addresses and records every lookup.

    Parameters
    ----------
    answers : mapping, optional
        ``"lat,lon"`` to an :class:`Address` (or ``None`` for "nothing
        there"). Unlisted points get ``default``.
    fail_on : sequence of str, optional
        Points that raise :class:`GeocodingError`.
    """

    def __init__(
        self,
        answers: Mapping[str, Address | None] | None = None,
        default: Address | None = None,
        fail_on: Sequence[str] = (),
    ) -> None:
        self.answers = dict(answers or {})
        self.default = default
        self.fail_on = set(fail_on)
        self.calls: list[str] = []

    def reverse(self, coordinates: Coordinates) -> Address | None:
        key = str(coordinates)
        self.calls.append(key)
        if key in self.fail_on:
            msg = "the service is down"
            raise GeocodingError(msg)
        return self.answers.get(key, self.default)


def location(address: Mapping[str, object] | None) -> LocationLike:
    """Build the part of a geopy location the code reads."""
    raw: dict[str, object] = (
        {} if address is None else {"address": dict(address)}
    )
    return SimpleNamespace(raw=raw)


class ScriptedClient:
    """A geopy-like client that returns or raises a prepared sequence."""

    def __init__(self, script: Sequence[object]) -> None:
        self.script = list(script)
        self.calls: list[dict[str, object]] = []

    def reverse(
        self, query: tuple[float, float], *, language: str | None, timeout: int
    ) -> LocationLike | None:
        self.calls.append(
            {"query": query, "language": language, "timeout": timeout}
        )
        item = self.script.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item  # type: ignore[return-value]


class FakeClock:
    """A clock that only moves when a test sleeps."""

    def __init__(self) -> None:
        self.now = 100.0
        self.slept: list[float] = []

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds
