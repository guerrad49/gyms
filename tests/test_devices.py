import logging

import pytest

from PokemonGo.errors import UnsupportedDeviceError
from PokemonGo.vision.devices import (
    PROFILES,
    DeviceProfile,
    detect_profile,
    get_profile,
    profile_names,
    select_profile,
)


def test_profiles_keep_the_v1_geometry() -> None:
    assert PROFILES["iSE"] == DeviceProfile(
        "iSE", (1334, 750), 1.75, (50, 140), (975, 1100)
    )
    assert PROFILES["i11"] == DeviceProfile(
        "i11", (1792, 828), 1.5, (60, 150), (1075, 1225)
    )
    assert PROFILES["i15"] == DeviceProfile(
        "i15", (2556, 1179), 1.0, (110, 210), (1550, 1800)
    )


def test_profile_names_come_from_the_registry() -> None:
    assert profile_names() == ("iSE", "i11", "i15")


@pytest.mark.parametrize("name", list(PROFILES))
def test_detect_profile_by_exact_size(name: str) -> None:
    assert detect_profile(PROFILES[name].size).name == name


def test_unknown_size_names_the_closest_profile() -> None:
    with pytest.raises(UnsupportedDeviceError) as info:
        detect_profile((2400, 1100))
    message = str(info.value)
    assert "1100x2400" in message
    assert "closest profile is 'i15'" in message
    assert "--model i15" in message


@pytest.mark.parametrize("name", ["i15", "I15", " i15 ", "ISE"])
def test_get_profile_ignores_case_and_spaces(name: str) -> None:
    assert get_profile(name).name.lower() == name.strip().lower()


def test_get_profile_lists_the_choices_on_error() -> None:
    with pytest.raises(UnsupportedDeviceError, match="iSE, i11, i15"):
        get_profile("i99")


def test_scaling_to_the_same_size_returns_the_same_profile() -> None:
    profile = PROFILES["i11"]
    assert profile.scaled_to(profile.size) is profile


def test_scaling_moves_rows_by_height_and_scale_by_width() -> None:
    scaled = PROFILES["i15"].scaled_to((1278, 590))  # half size
    assert scaled.name == "i15"
    assert scaled.size == (1278, 590)
    assert scaled.title_rows == (55, 105)
    assert scaled.activity_rows == (775, 900)
    assert scaled.scale == pytest.approx(1179 / 590, abs=1e-4)


def test_select_without_forcing_detects() -> None:
    assert select_profile((1334, 750)).name == "iSE"


def test_select_with_a_matching_forced_model_is_silent(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        profile = select_profile((2556, 1179), "i15")
    assert profile is PROFILES["i15"]
    assert not caplog.records


def test_select_with_a_mismatched_forced_model_scales_and_warns(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING):
        profile = select_profile((1792, 828), "i15")
    assert profile.name == "i15"
    assert profile.size == (1792, 828)
    assert "scaling crops" in caplog.text


def test_select_rejects_an_unknown_forced_model() -> None:
    with pytest.raises(UnsupportedDeviceError, match="unknown phone model"):
        select_profile((1792, 828), "nope")
