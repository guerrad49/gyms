"""Shared pytest configuration."""

from __future__ import annotations

import shutil

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
