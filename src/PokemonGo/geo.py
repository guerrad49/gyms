"""Find a gym's city, county, state and country from its coordinates.

Addresses come from OpenStreetMap's Nominatim service through ``geopy``.
That service allows one request per second and asks every user to
identify themselves, so lookups are rate limited, retried when the service
is briefly unavailable, and remembered in a cache so that each place is
only ever looked up once.

Only :class:`NominatimGeocoder` and :func:`make_nominatim` touch the
network. Everything else works with the small :class:`Geocoder` interface,
which is what the tests fake.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Protocol, cast

from geopy.exc import (
    GeocoderQuotaExceeded,
    GeocoderTimedOut,
    GeocoderUnavailable,
    GeopyError,
)
from geopy.geocoders import Nominatim

from PokemonGo.errors import ConfigError, GeocodingError
from PokemonGo.models import Coordinates, Flag, Gym
from PokemonGo.parsing import format_status
from PokemonGo.store.base import GymStore

logger = logging.getLogger(__name__)

CITY_KEYS: Final = (
    "city",
    "town",
    "village",
    "township",
    "borough",
    "municipality",
    "hamlet",
)
"""Nominatim address keys that name the city, in order of preference.

The first four are the keys v1 used. v1 let the *last* match win (so a
``township`` beat a ``city``); the first match wins here. The last three
are fallbacks that only apply where v1 would have asked you to type the
city.
"""

CACHE_VERSION: Final = 1

_FLAG_FOR: Final = {
    "city": Flag.CITY,
    "county": Flag.COUNTY,
    "state": Flag.STATE,
}


@dataclass(frozen=True, slots=True)
class Address:
    """The place a gym is in.

    Attributes
    ----------
    city, county, state, country : str
        Lowercase names; empty when the service did not provide one.
    """

    city: str = ""
    county: str = ""
    state: str = ""
    country: str = ""

    @property
    def missing(self) -> tuple[Flag, ...]:
        """The review flags for the city, county and state that are blank.

        Examples
        --------
        >>> [f.value for f in Address(city="ames", state="iowa").missing]
        ['COUNTY']
        """
        return tuple(
            flag for name, flag in _FLAG_FOR.items() if not getattr(self, name)
        )


def address_from_nominatim(raw: Mapping[str, object]) -> Address:
    """Convert Nominatim's address details to an :class:`Address`.

    Parameters
    ----------
    raw : mapping
        The ``address`` object of a Nominatim reverse-geocoding result.

    Returns
    -------
    Address
        Lowercase names. The city is the first present key of
        :data:`CITY_KEYS`, and a trailing " county" is removed from the
        county, as in v1.

    Examples
    --------
    >>> address_from_nominatim(
    ...     {"town": "Ames", "county": "Story County", "state": "Iowa"}
    ... )
    Address(city='ames', county='story', state='iowa', country='')
    >>> address_from_nominatim({"city": "Newark", "township": "Hanover"}).city
    'newark'
    """

    def pick(*keys: str) -> str:
        for key in keys:
            value = raw.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip().lower()
        return ""

    return Address(
        city=pick(*CITY_KEYS),
        county=pick("county").removesuffix(" county"),
        state=pick("state"),
        country=pick("country"),
    )


class Geocoder(Protocol):
    """Turns coordinates into an address."""

    def reverse(self, coordinates: Coordinates) -> Address | None:
        """Look up the address of a point.

        Parameters
        ----------
        coordinates : Coordinates
            Where to look.

        Returns
        -------
        Address or None
            ``None`` when there is no address there (open water, say).

        Raises
        ------
        GeocodingError
            If the lookup failed, as opposed to finding nothing.
        """


class RateLimiter:
    """Keeps requests at least ``min_interval`` seconds apart.

    Parameters
    ----------
    min_interval : float, optional
        Seconds between requests; Nominatim's policy is one per second.
    clock : callable, optional
        A monotonic clock; injectable for tests.
    sleep : callable, optional
        Waits for a number of seconds; injectable for tests.
    """

    def __init__(
        self,
        min_interval: float = 1.0,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.min_interval = min_interval
        self._clock = clock
        self._sleep = sleep
        self._last: float | None = None

    def wait(self) -> None:
        """Block until a request is allowed, then record it."""
        now = self._clock()
        if self._last is not None:
            remaining = self._last + self.min_interval - now
            if remaining > 0:
                self._sleep(remaining)
                now = self._clock()
        self._last = now


class LocationLike(Protocol):
    """The part of a ``geopy`` location this module reads."""

    @property
    def raw(self) -> Mapping[str, object]:
        """The service's raw response."""


class ReverseClient(Protocol):
    """The part of a ``geopy`` geocoder this module uses."""

    def reverse(
        self,
        query: tuple[float, float],
        *,
        language: str | None,
        timeout: int,
    ) -> LocationLike | None:
        """Look up the address of ``(latitude, longitude)``."""


class _NominatimClient:
    """Adapts :class:`geopy.geocoders.Nominatim` to :class:`ReverseClient`."""

    def __init__(self, email: str, timeout: int) -> None:
        self._nominatim = Nominatim(user_agent=email, timeout=timeout)

    def reverse(
        self,
        query: tuple[float, float],
        *,
        language: str | None,
        timeout: int,
    ) -> LocationLike | None:
        found = self._nominatim.reverse(
            query, language=language or False, timeout=timeout
        )
        return cast("LocationLike | None", found)


class NominatimGeocoder:
    """Reverse geocoding with OpenStreetMap's Nominatim service.

    Parameters
    ----------
    client : ReverseClient
        The ``geopy`` geocoder (see :func:`make_nominatim`); tests pass a
        fake.
    language : str, optional
        Language of the returned names. English keeps names consistent
        (``"japan"`` rather than ``"日本"``). ``None`` uses the service
        default.
    timeout : int, optional
        Seconds to wait for a response.
    attempts : int, optional
        Tries per lookup when the service is briefly unavailable, timed
        out, or rate limiting. Any other error fails at once.
    backoff : float, optional
        Seconds to wait before the second try; it grows with each try.
    limiter : RateLimiter, optional
        Spaces the requests; defaults to one per second.
    sleep : callable, optional
        Waits between retries; injectable for tests.
    """

    def __init__(
        self,
        client: ReverseClient,
        *,
        language: str | None = "en",
        timeout: int = 5,
        attempts: int = 3,
        backoff: float = 2.0,
        limiter: RateLimiter | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._client = client
        self.language = language
        self.timeout = timeout
        self.attempts = attempts
        self.backoff = backoff
        self._limiter = limiter or RateLimiter(sleep=sleep)
        self._sleep = sleep

    def reverse(self, coordinates: Coordinates) -> Address | None:
        """Look up an address; see :meth:`Geocoder.reverse`."""
        query = (coordinates.latitude, coordinates.longitude)
        for attempt in range(1, self.attempts + 1):
            self._limiter.wait()
            try:
                found = self._client.reverse(
                    query, language=self.language, timeout=self.timeout
                )
            except (
                GeocoderTimedOut,
                GeocoderUnavailable,
                GeocoderQuotaExceeded,
            ) as error:
                if attempt == self.attempts:
                    msg = (
                        f"address lookup failed after {attempt} tries: {error}"
                    )
                    raise GeocodingError(msg) from error
                logger.warning("lookup failed (%s); retrying", error)
                self._sleep(self.backoff * attempt)
                continue
            except GeopyError as error:
                msg = f"address lookup failed: {error}"
                raise GeocodingError(msg) from error
            if found is None:
                return None
            raw = found.raw.get("address")
            if not isinstance(raw, Mapping):
                return None
            return address_from_nominatim(raw)
        return None  # pragma: no cover - the loop always returns or raises


def make_nominatim(email: str, **options: object) -> NominatimGeocoder:
    """Create a rate-limited Nominatim geocoder that identifies you.

    Parameters
    ----------
    email : str
        Your contact address. Nominatim's usage policy requires it, and
        it is sent as the user agent.
    **options
        Passed to :class:`NominatimGeocoder`.

    Returns
    -------
    NominatimGeocoder
        A geocoder ready to use.

    Raises
    ------
    ConfigError
        If ``email`` is not a plausible address.
    """
    if "@" not in email:
        msg = "EMAIL must be a valid contact address (Nominatim usage policy)"
        raise ConfigError(msg)
    timeout = options.get("timeout", 5)
    client = _NominatimClient(email, int(cast("int", timeout)))
    return NominatimGeocoder(client, **options)  # type: ignore[arg-type]


def _key(coordinates: Coordinates) -> str:
    """Return the cache key: six decimals is about ten centimetres."""
    return f"{coordinates.latitude:.6f},{coordinates.longitude:.6f}"


class CachedGeocoder:
    """Remembers lookups in a JSON file so each place is looked up once.

    "No address here" is remembered too. Failures are not, so a lookup that
    failed because the network was down is tried again next time. An
    unreadable cache file is ignored and replaced, since it only holds
    things that can be looked up again.

    Parameters
    ----------
    inner : Geocoder
        The geocoder to ask on a cache miss.
    path : pathlib.Path
        The cache file.

    Attributes
    ----------
    hits, misses : int
        How many lookups were answered from the cache, and how many were
        passed on.
    """

    def __init__(self, inner: Geocoder, path: Path) -> None:
        self._inner = inner
        self.path = path
        self.hits = 0
        self.misses = 0
        self._dirty = False
        self._entries: dict[str, dict[str, str] | None] = self._load()

    def _load(self) -> dict[str, dict[str, str] | None]:
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if data.get("version") == CACHE_VERSION:
                return dict(data["entries"])
        except FileNotFoundError:
            pass
        except (
            OSError,
            ValueError,
            KeyError,
            AttributeError,
            TypeError,
        ) as error:
            logger.warning("ignoring unreadable cache %s: %s", self.path, error)
        return {}

    def reverse(self, coordinates: Coordinates) -> Address | None:
        """Look up an address, from the cache when possible."""
        key = _key(coordinates)
        if key in self._entries:
            self.hits += 1
            entry = self._entries[key]
            return None if entry is None else Address(**entry)
        self.misses += 1
        address = self._inner.reverse(coordinates)
        self._entries[key] = (
            None
            if address is None
            else {
                "city": address.city,
                "county": address.county,
                "state": address.state,
                "country": address.country,
            }
        )
        self._dirty = True
        return address

    def flush(self) -> None:
        """Write the cache to disk if it changed (atomically)."""
        if not self._dirty:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, name = tempfile.mkstemp(
            dir=self.path.parent, prefix=f".{self.path.name}.", suffix=".tmp"
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(
                    {"version": CACHE_VERSION, "entries": self._entries},
                    handle,
                    ensure_ascii=False,
                    indent=0,
                )
            os.replace(name, self.path)
        except BaseException:
            Path(name).unlink(missing_ok=True)
            raise
        self._dirty = False


def build_geocoder(
    email: str, cache: Path | None = None
) -> CachedGeocoder | NominatimGeocoder:
    """Create the geocoder the tool uses: Nominatim, plus a cache.

    Parameters
    ----------
    email : str
        Your contact address.
    cache : pathlib.Path, optional
        The cache file; ``None`` disables caching.

    Returns
    -------
    CachedGeocoder or NominatimGeocoder
        With a cache, call ``flush()`` when done.
    """
    nominatim = make_nominatim(email)
    return nominatim if cache is None else CachedGeocoder(nominatim, cache)


def needs_address(gym: Gym) -> bool:
    """Return whether a gym should have its address looked up.

    A gym needs it when it has coordinates and no city or no state, or is
    flagged ``ADDRESS`` or ``NO_COORDS`` (the person has since typed the
    coordinates in). A blank county alone does not count: many places have
    none, and asking again would not find one.

    Examples
    --------
    >>> from PokemonGo.models import Coordinates
    >>> here = Coordinates(1, 2)
    >>> needs_address(Gym(1, "a", here))
    True
    >>> needs_address(Gym(1, "a", here, city="x", state="y"))
    False
    >>> needs_address(Gym(1, "a"))
    False
    """
    if gym.coordinates is None:
        return False
    return (
        not gym.city
        or not gym.state
        or gym.has_flag(Flag.ADDRESS)
        or gym.has_flag(Flag.NO_COORDS)
    )


def fill_address(gym: Gym, geocoder: Geocoder) -> Address | None:
    """Look up a gym's address and fill in what is blank.

    Existing values are never overwritten, so a name you corrected by hand
    survives. Review flags are kept in step: ``CITY``, ``COUNTY`` and
    ``STATE`` are set when that field is still blank and cleared when it is
    filled; ``ADDRESS`` is set when the service found nothing and cleared
    when it did; ``NO_COORDS`` is cleared once the gym has coordinates.

    Parameters
    ----------
    gym : Gym
        The gym to complete; changed in place.
    geocoder : Geocoder
        Where addresses come from.

    Returns
    -------
    Address or None
        The address found, or ``None`` when there were no coordinates or
        the service had nothing.

    Raises
    ------
    GeocodingError
        If the lookup failed.
    """
    if gym.coordinates is None:
        gym.add_flag(Flag.NO_COORDS)
        return None
    _drop(gym, Flag.NO_COORDS)
    address = geocoder.reverse(gym.coordinates)
    if address is None:
        gym.add_flag(Flag.ADDRESS)
        return None
    _drop(gym, Flag.ADDRESS)
    for name in ("city", "county", "state", "country"):
        if not getattr(gym, name):
            setattr(gym, name, getattr(address, name))
    for name, flag in _FLAG_FOR.items():
        if getattr(gym, name):
            _drop(gym, flag)
        else:
            gym.add_flag(flag)
    return address


def _drop(gym: Gym, flag: Flag) -> None:
    gym.status = tuple(f for f in gym.status if f is not flag)


@dataclass(slots=True)
class ResolveSummary:
    """The outcome of :func:`resolve_addresses`.

    Attributes
    ----------
    checked : int
        Gyms looked at.
    changed : int
        Gyms whose fields or flags changed.
    still_missing : list of tuple
        ``(row, title, flags)`` for gyms still without a city or state.
    error : str
        Why the run stopped early, if it did.
    """

    checked: int = 0
    changed: int = 0
    still_missing: list[tuple[int, str, tuple[Flag, ...]]] = field(
        default_factory=list
    )
    error: str = ""


def resolve_addresses(
    store: GymStore,
    geocoder: Geocoder,
    *,
    limit: int | None = None,
    dry_run: bool = False,
    progress: Callable[[int, int], None] | None = None,
) -> ResolveSummary:
    """Fill in missing addresses for the gyms that need them.

    Gyms are updated in the store but **not committed**; the caller
    commits. If a lookup fails the run stops, keeping the gyms done so
    far, and the reason is in :attr:`ResolveSummary.error`.

    Parameters
    ----------
    store : GymStore
        The database.
    geocoder : Geocoder
        Where addresses come from.
    limit : int, optional
        Look up at most this many gyms.
    dry_run : bool, optional
        Look addresses up but do not update the store.
    progress : callable, optional
        Called as ``progress(done, total)`` after each gym.

    Returns
    -------
    ResolveSummary
        What happened.
    """
    todo: Sequence[Gym] = [g for g in store.all() if needs_address(g)]
    if limit is not None:
        todo = todo[:limit]
    summary = ResolveSummary()
    for done, gym in enumerate(todo, start=1):
        before = (gym.city, gym.county, gym.state, gym.country, gym.status)
        try:
            fill_address(gym, geocoder)
        except GeocodingError as error:
            summary.error = str(error)
            break
        summary.checked += 1
        if (gym.city, gym.county, gym.state, gym.country, gym.status) != before:
            summary.changed += 1
            if not dry_run:
                store.update(gym)
        if not gym.city or not gym.state:
            row = gym.row or 0
            summary.still_missing.append((row, gym.title, gym.status))
        if progress is not None:
            progress(done, len(todo))
    return summary


def format_resolve_summary(
    summary: ResolveSummary, *, dry_run: bool = False, show: int = 15
) -> str:
    """Describe the outcome of :func:`resolve_addresses` as text.

    Parameters
    ----------
    summary : ResolveSummary
        The outcome.
    dry_run : bool, optional
        Whether nothing was saved.
    show : int, optional
        Maximum number of unresolved gyms to list.

    Returns
    -------
    str
        A few lines for the terminal.
    """
    lines = [f"Looked up {summary.checked} gyms; {summary.changed} changed."]
    if summary.still_missing:
        total = len(summary.still_missing)
        lines.append(f"Still without a city or state: {total}")
        for row, title, flags in summary.still_missing[:show]:
            lines.append(f"  row {row}  {title}  [{format_status(flags)}]")
        if total > show:
            lines.append(f"  ... and {total - show} more")
    if summary.error:
        lines.append(f"Stopped early: {summary.error}")
    if dry_run:
        lines.append("Dry run: nothing was saved.")
    return "\n".join(lines)
