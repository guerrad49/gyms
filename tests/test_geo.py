import json
from pathlib import Path

import pytest
from geopy.exc import (
    ConfigurationError,
    GeocoderInsufficientPrivileges,
    GeocoderQueryError,
    GeocoderRateLimited,
    GeocoderTimedOut,
    GeocoderUnavailable,
)

from PokemonGo import geo
from PokemonGo.errors import ConfigError, GeocodingError
from PokemonGo.geo import (
    Address,
    CachedGeocoder,
    NominatimGeocoder,
    RateLimiter,
    ResolveSummary,
    address_from_nominatim,
    fill_address,
    format_resolve_summary,
    make_nominatim,
    needs_address,
    resolve_addresses,
)
from PokemonGo.models import Coordinates, Flag, Gym
from PokemonGo.store.csv_store import CsvStore
from tests.support.geo import FakeClock, FakeGeocoder, ScriptedClient, location

HERE = Coordinates(40.0, -75.0)
AMES = Address("ames", "story", "iowa", "united states")


# --- turning Nominatim's answer into an Address ---


def test_the_address_is_lowercased_and_the_county_suffix_removed() -> None:
    raw = {
        "city": "Ames",
        "county": "Story County",
        "state": "Iowa",
        "country": "United States",
    }
    assert address_from_nominatim(raw) == AMES


def test_the_first_city_key_wins_not_the_last() -> None:
    """D5: v1 let a township beat a city."""
    raw = {"township": "Hanover", "city": "Newark", "village": "Roseland"}
    assert address_from_nominatim(raw).city == "newark"


@pytest.mark.parametrize(
    ("raw", "city"),
    [
        ({"town": "Ames"}, "ames"),
        ({"village": "Moray", "township": "East"}, "moray"),
        ({"township": "Hanover"}, "hanover"),
        ({"hamlet": "Tiny"}, "tiny"),  # a fallback v1 did not have
        ({"municipality": "Cusco"}, "cusco"),
        ({"borough": "East Rutherford", "hamlet": "x"}, "east rutherford"),
        ({"city": "  ", "town": "Ames"}, "ames"),  # blank is skipped
        ({"suburb": "Somewhere"}, ""),
        ({}, ""),
    ],
)
def test_city_keys(raw: dict[str, str], city: str) -> None:
    assert address_from_nominatim(raw).city == city


def test_non_text_values_are_ignored() -> None:
    assert address_from_nominatim({"city": 5, "state": None}) == Address()


def test_missing_flags() -> None:
    assert Address().missing == (Flag.CITY, Flag.COUNTY, Flag.STATE)
    assert AMES.missing == ()
    assert Address(city="x", state="y").missing == (Flag.COUNTY,)


# --- rate limiting ---


def test_requests_are_spaced_one_second_apart() -> None:
    clock = FakeClock()
    limiter = RateLimiter(1.0, clock=clock, sleep=clock.sleep)
    limiter.wait()  # the first request never waits
    assert clock.slept == []
    clock.now += 0.25
    limiter.wait()
    assert clock.slept == [pytest.approx(0.75)]
    clock.now += 5
    limiter.wait()  # long enough ago: no wait
    assert len(clock.slept) == 1


# --- the Nominatim adapter ---


def _geocoder(
    script: list[object], clock: FakeClock | None = None, **options: object
) -> tuple[NominatimGeocoder, ScriptedClient, FakeClock]:
    clock = clock or FakeClock()
    client = ScriptedClient(script)
    limiter = RateLimiter(1.0, clock=clock, sleep=clock.sleep)
    geocoder = NominatimGeocoder(
        client,
        limiter=limiter,
        sleep=clock.sleep,
        **options,  # type: ignore[arg-type]
    )
    return geocoder, client, clock


def test_a_lookup_returns_an_address_and_sends_the_right_request() -> None:
    geocoder, client, _ = _geocoder(
        [location({"city": "Ames", "county": "Story County", "state": "Iowa"})]
    )
    assert geocoder.reverse(HERE) == Address("ames", "story", "iowa", "")
    assert client.calls == [
        {"query": (40.0, -75.0), "language": "en", "timeout": 5}
    ]


def test_nothing_found_is_none_not_an_error() -> None:
    geocoder, _, _ = _geocoder([None, location(None)])
    assert geocoder.reverse(HERE) is None
    assert geocoder.reverse(HERE) is None  # a result with no address object


def test_lookups_are_rate_limited() -> None:
    geocoder, _, clock = _geocoder([location({"city": "a"})] * 3)
    for _ in range(3):
        geocoder.reverse(HERE)
    assert clock.slept == [pytest.approx(1.0), pytest.approx(1.0)]


@pytest.mark.parametrize(
    "error",
    [
        GeocoderTimedOut("slow"),
        GeocoderUnavailable("503"),
        GeocoderRateLimited("429"),
    ],
)
def test_brief_failures_are_retried_with_growing_waits(
    error: Exception,
) -> None:
    geocoder, client, clock = _geocoder(
        [error, error, location({"city": "ok"})], backoff=2.0
    )
    assert geocoder.reverse(HERE) == Address(city="ok")
    assert len(client.calls) == 3
    assert 2.0 in clock.slept
    assert 4.0 in clock.slept


def test_giving_up_after_the_last_attempt() -> None:
    geocoder, client, _ = _geocoder([GeocoderTimedOut("slow")] * 3)
    with pytest.raises(GeocodingError, match="failed after 3 tries: slow"):
        geocoder.reverse(HERE)
    assert len(client.calls) == 3


@pytest.mark.parametrize(
    "error",
    [
        GeocoderQueryError("bad"),
        GeocoderInsufficientPrivileges("blocked"),
        ConfigurationError("no agent"),
    ],
)
def test_errors_that_retrying_cannot_fix_fail_at_once(error: Exception) -> None:
    geocoder, client, _ = _geocoder([error])
    with pytest.raises(GeocodingError, match="address lookup failed"):
        geocoder.reverse(HERE)
    assert len(client.calls) == 1


def test_make_nominatim_identifies_you_and_never_calls_the_network(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    class FakeNominatim:
        def __init__(self, user_agent: str, timeout: int) -> None:
            seen.update(user_agent=user_agent, timeout=timeout)

        def reverse(self, query: object, **options: object) -> None:
            seen.update(query=query, options=options)

    monkeypatch.setattr(geo, "Nominatim", FakeNominatim)
    geocoder = make_nominatim(
        "me@example.com", timeout=9, sleep=lambda _s: None
    )
    assert geocoder.reverse(HERE) is None
    assert seen["user_agent"] == "me@example.com"
    assert seen["timeout"] == 9
    assert seen["query"] == (40.0, -75.0)
    assert seen["options"] == {"language": "en", "timeout": 9}


@pytest.mark.parametrize("email", ["", "nobody"])
def test_make_nominatim_needs_a_contact_address(email: str) -> None:
    with pytest.raises(ConfigError, match="contact address"):
        make_nominatim(email)


def test_a_missing_language_uses_the_service_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    geocoder, client, _ = _geocoder([None], language=None)
    geocoder.reverse(HERE)
    assert client.calls[0]["language"] is None


# --- the cache ---


def test_each_place_is_looked_up_once(tmp_path: Path) -> None:
    inner = FakeGeocoder(default=AMES)
    cache = CachedGeocoder(inner, tmp_path / "c.json")
    assert cache.reverse(HERE) == AMES
    assert cache.reverse(HERE) == AMES
    assert inner.calls == [str(HERE)]
    assert (cache.hits, cache.misses) == (1, 1)


def test_no_address_is_remembered_too(tmp_path: Path) -> None:
    inner = FakeGeocoder(default=None)
    cache = CachedGeocoder(inner, tmp_path / "c.json")
    assert cache.reverse(HERE) is None
    assert cache.reverse(HERE) is None
    assert len(inner.calls) == 1


def test_failures_are_not_remembered(tmp_path: Path) -> None:
    inner = FakeGeocoder(default=AMES, fail_on=[str(HERE)])
    cache = CachedGeocoder(inner, tmp_path / "c.json")
    with pytest.raises(GeocodingError):
        cache.reverse(HERE)
    inner.fail_on.clear()
    assert cache.reverse(HERE) == AMES  # tried again


def test_the_cache_survives_between_runs(tmp_path: Path) -> None:
    path = tmp_path / "sub" / "c.json"
    first = CachedGeocoder(FakeGeocoder(default=AMES), path)
    first.reverse(HERE)
    first.reverse(Coordinates(1, 2))
    first.flush()
    inner = FakeGeocoder(default=Address(city="wrong"))
    second = CachedGeocoder(inner, path)
    assert second.reverse(HERE) == AMES
    assert inner.calls == []
    assert [p.name for p in path.parent.iterdir()] == ["c.json"]


def test_nearby_spellings_of_a_point_share_an_entry(tmp_path: Path) -> None:
    inner = FakeGeocoder(default=AMES)
    cache = CachedGeocoder(inner, tmp_path / "c.json")
    cache.reverse(Coordinates(40.0, -75.0))
    cache.reverse(Coordinates(40.00000004, -75.0))  # below six decimals
    assert len(inner.calls) == 1


def test_flush_writes_nothing_when_nothing_changed(tmp_path: Path) -> None:
    path = tmp_path / "c.json"
    CachedGeocoder(FakeGeocoder(), path).flush()
    assert not path.exists()


@pytest.mark.parametrize(
    "content",
    ["not json", "[]", '{"version": 99, "entries": {}}', '{"version": 1}', ""],
)
def test_an_unreadable_cache_is_ignored(tmp_path: Path, content: str) -> None:
    path = tmp_path / "c.json"
    path.write_text(content, encoding="utf-8")
    inner = FakeGeocoder(default=AMES)
    cache = CachedGeocoder(inner, path)
    assert cache.reverse(HERE) == AMES
    cache.flush()
    assert json.loads(path.read_text(encoding="utf-8"))["version"] == 1


def test_a_failed_flush_leaves_the_old_cache_and_no_temp_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "c.json"
    first = CachedGeocoder(FakeGeocoder(default=AMES), path)
    first.reverse(HERE)
    first.flush()
    before = path.read_bytes()
    second = CachedGeocoder(FakeGeocoder(default=AMES), path)
    second.reverse(Coordinates(1, 2))

    def fail(*_a: object, **_k: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr("os.replace", fail)
    with pytest.raises(OSError, match="disk full"):
        second.flush()
    assert path.read_bytes() == before
    assert [p.name for p in tmp_path.iterdir()] == ["c.json"]


# --- deciding who needs a lookup, and filling a gym in ---


@pytest.mark.parametrize(
    ("gym", "expected"),
    [
        (Gym(1, "a", HERE), True),  # no city, no state
        (Gym(1, "a", HERE, city="x"), True),  # no state
        (Gym(1, "a", HERE, city="x", state="y"), False),
        (Gym(1, "a", HERE, city="x", state="y", status=(Flag.COUNTY,)), False),
        (Gym(1, "a", HERE, city="x", state="y", status=(Flag.ADDRESS,)), True),
        (
            Gym(1, "a", HERE, city="x", state="y", status=(Flag.NO_COORDS,)),
            True,
        ),
        (Gym(1, "a"), False),  # nowhere to look
    ],
)
def test_needs_address(gym: Gym, expected: bool) -> None:
    assert needs_address(gym) is expected


def test_a_new_gym_gets_every_field() -> None:
    gym = Gym(None, "x", HERE)
    assert fill_address(gym, FakeGeocoder(default=AMES)) == AMES
    assert (gym.city, gym.county, gym.state, gym.country) == (
        "ames",
        "story",
        "iowa",
        "united states",
    )
    assert gym.status == ()


def test_existing_values_are_never_overwritten() -> None:
    gym = Gym(1, "x", HERE, city="my own spelling", status=(Flag.CITY,))
    fill_address(gym, FakeGeocoder(default=AMES))
    assert gym.city == "my own spelling"
    assert gym.state == "iowa"
    assert not gym.has_flag(Flag.CITY)  # filled, so no longer flagged


def test_fields_the_service_lacks_are_flagged() -> None:
    gym = Gym(1, "x", HERE)
    fill_address(gym, FakeGeocoder(default=Address(state="cusco")))
    assert gym.state == "cusco"
    assert gym.status == (Flag.CITY, Flag.COUNTY)


def test_no_address_found_sets_the_address_flag() -> None:
    gym = Gym(1, "x", HERE)
    assert fill_address(gym, FakeGeocoder(default=None)) is None
    assert gym.status == (Flag.ADDRESS,)


def test_a_found_address_clears_the_address_flag() -> None:
    gym = Gym(1, "x", HERE, status=(Flag.ADDRESS,))
    fill_address(gym, FakeGeocoder(default=AMES))
    assert gym.status == ()


def test_coordinates_typed_in_later_clear_no_coords() -> None:
    gym = Gym(1, "x", HERE, status=(Flag.NO_COORDS,))
    fill_address(gym, FakeGeocoder(default=AMES))
    assert gym.status == ()


def test_without_coordinates_nothing_is_looked_up() -> None:
    geocoder = FakeGeocoder(default=AMES)
    gym = Gym(1, "x")
    assert fill_address(gym, geocoder) is None
    assert gym.status == (Flag.NO_COORDS,)
    assert geocoder.calls == []


# --- resolving a whole database ---


def _store_with(tmp_path: Path, *gyms: Gym) -> CsvStore:
    store = CsvStore(tmp_path / "gyms.csv")
    for gym in gyms:
        store.add(gym)
    store.commit()
    return store


def test_resolve_fills_the_gyms_that_need_it_and_skips_the_rest(
    tmp_path: Path,
) -> None:
    done = Gym(1, "done", HERE, city="x", state="y")
    needs = Gym(2, "needs", Coordinates(1, 2))
    nowhere = Gym(3, "nowhere")
    store = _store_with(tmp_path, done, needs, nowhere)
    geocoder = FakeGeocoder(default=AMES)
    summary = resolve_addresses(store, geocoder)
    assert geocoder.calls == ["1.0,2.0"]  # only the one that needed it
    assert (summary.checked, summary.changed, summary.error) == (1, 1, "")
    assert summary.still_missing == []
    store.commit()
    found = {g.title: g for g in CsvStore(tmp_path / "gyms.csv").all()}
    assert found["needs"].city == "ames"
    assert found["done"].city == "x"  # untouched
    assert found["nowhere"].city == ""


def test_a_dry_run_looks_up_but_changes_nothing(tmp_path: Path) -> None:
    store = _store_with(tmp_path, Gym(1, "needs", HERE))
    summary = resolve_addresses(store, FakeGeocoder(default=AMES), dry_run=True)
    assert summary.changed == 1
    store.commit()
    assert CsvStore(tmp_path / "gyms.csv").all()[0].city == ""


def test_the_limit_caps_the_lookups(tmp_path: Path) -> None:
    gyms = [Gym(i, f"g{i}", Coordinates(i, i)) for i in range(1, 6)]
    store = _store_with(tmp_path, *gyms)
    geocoder = FakeGeocoder(default=AMES)
    summary = resolve_addresses(store, geocoder, limit=2)
    assert summary.checked == 2
    assert len(geocoder.calls) == 2


def test_gyms_the_service_cannot_place_are_reported(tmp_path: Path) -> None:
    store = _store_with(tmp_path, Gym(1, "at sea", HERE))
    summary = resolve_addresses(store, FakeGeocoder(default=None))
    assert summary.still_missing == [(2, "at sea", (Flag.ADDRESS,))]
    store.commit()
    assert CsvStore(tmp_path / "gyms.csv").all()[0].status == (Flag.ADDRESS,)


def test_a_failed_lookup_stops_the_run_but_keeps_earlier_work(
    tmp_path: Path,
) -> None:
    store = _store_with(
        tmp_path,
        Gym(1, "first", Coordinates(1, 1)),
        Gym(2, "second", Coordinates(2, 2)),
        Gym(3, "third", Coordinates(3, 3)),
    )
    geocoder = FakeGeocoder(default=AMES, fail_on=["2.0,2.0"])
    summary = resolve_addresses(store, geocoder)
    assert summary.checked == 1
    assert "service is down" in summary.error
    assert len(geocoder.calls) == 2  # the third was never tried
    store.commit()
    cities = {g.title: g.city for g in CsvStore(tmp_path / "gyms.csv").all()}
    assert cities == {"first": "ames", "second": "", "third": ""}


def test_progress_is_reported(tmp_path: Path) -> None:
    store = _store_with(
        tmp_path, Gym(1, "a", Coordinates(1, 1)), Gym(2, "b", Coordinates(2, 2))
    )
    seen: list[tuple[int, int]] = []
    resolve_addresses(
        store,
        FakeGeocoder(default=AMES),
        progress=lambda done, total: seen.append((done, total)),
    )
    assert seen == [(1, 2), (2, 2)]


def test_the_summary_text() -> None:
    summary = ResolveSummary(
        checked=3,
        changed=2,
        still_missing=[(5, f"gym {i}", (Flag.CITY,)) for i in range(4)],
        error="boom",
    )
    text = format_resolve_summary(summary, dry_run=True, show=2)
    assert "Looked up 3 gyms; 2 changed." in text
    assert "Still without a city or state: 4" in text
    assert "  row 5  gym 0  [CITY]" in text
    assert "... and 2 more" in text
    assert "Stopped early: boom" in text
    assert "Dry run: nothing was saved." in text
    assert (
        format_resolve_summary(ResolveSummary())
        == "Looked up 0 gyms; 0 changed."
    )
