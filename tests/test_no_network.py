import socket

import pytest


def test_real_connections_are_blocked() -> None:
    with pytest.raises(RuntimeError, match="network access is not allowed"):
        socket.create_connection(("example.com", 80))
    with (
        pytest.raises(RuntimeError, match="network access is not allowed"),
        socket.socket() as sock,
    ):
        sock.connect(("example.com", 80))


def test_the_real_geocoder_cannot_reach_nominatim() -> None:
    """A safety net: building the real client must not lead to a request."""
    from PokemonGo.errors import GeocodingError
    from PokemonGo.geo import make_nominatim
    from PokemonGo.models import Coordinates

    geocoder = make_nominatim("me@example.com", attempts=1)
    with pytest.raises((GeocodingError, RuntimeError)):
        geocoder.reverse(Coordinates(1, 2))
