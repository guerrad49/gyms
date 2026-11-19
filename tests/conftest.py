"""Shared pytest configuration."""

from __future__ import annotations

import shutil
import socket
from collections.abc import Iterator

import pytest


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Skip tests marked ``ocr`` when Tesseract is not installed.

    Parameters
    ----------
    config : pytest.Config
        The pytest configuration (unused).
    items : list of pytest.Item
        The collected tests.
    """
    if shutil.which("tesseract") is not None:
        return
    skip = pytest.mark.skip(reason="the tesseract executable is missing")
    for item in items:
        if "ocr" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def no_network(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[None]:
    """Fail any test that tries to open a network connection.

    Address lookups, Google Sheets and everything else must be faked. Only
    tests marked ``live`` may reach a real service.
    """
    if "live" in request.keywords:
        yield
        return

    def blocked(*_args: object, **_kwargs: object) -> None:
        msg = "network access is not allowed in tests (mark it 'live')"
        raise RuntimeError(msg)

    monkeypatch.setattr(socket.socket, "connect", blocked)
    monkeypatch.setattr(socket, "create_connection", blocked)
    yield
