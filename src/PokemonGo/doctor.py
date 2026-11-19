"""Check that everything ``pogo scan`` needs is in place.

Each check says what it looked at and, when it fails, what to do about
it, so a new installation can be diagnosed in one command.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pytesseract

from PokemonGo.config import Backend, Settings
from PokemonGo.discovery import discover
from PokemonGo.errors import PogoError
from PokemonGo.store import open_store
from PokemonGo.store.base import GymStore


@dataclass(frozen=True, slots=True)
class Check:
    """The result of one check.

    Attributes
    ----------
    name : str
        What was checked.
    ok : bool
        Whether it passed.
    detail : str
        What was found, or what to do about a failure.
    """

    name: str
    ok: bool
    detail: str


def tesseract_version() -> str:
    """Return the installed Tesseract version.

    Returns
    -------
    str
        For example ``"5.5.0"``.

    Raises
    ------
    PogoError
        If Tesseract is not installed.
    """
    try:
        return str(pytesseract.get_tesseract_version())
    except pytesseract.TesseractNotFoundError as error:
        msg = "not found; install it (macOS: brew install tesseract)"
        raise PogoError(msg) from error


def _writable_folder(folder: Path) -> Check:
    """Check that a folder exists and can be written, or can be created."""
    target = folder
    while not target.exists() and target != target.parent:
        target = target.parent
    usable = target.is_dir() and os.access(target, os.W_OK)
    state = "exists" if folder.exists() else "will be created"
    detail = f"{folder} ({state})" if usable else f"{folder} is not writable"
    return Check("badges folder", usable, detail)


def run_checks(
    settings: Settings,
    *,
    tesseract: Callable[[], str] = tesseract_version,
    opener: Callable[[Settings], GymStore] = open_store,
) -> list[Check]:
    """Run every check.

    Parameters
    ----------
    settings : Settings
        The configuration to check.
    tesseract : callable, optional
        Returns the Tesseract version or raises; injectable for tests.
    opener : callable, optional
        Opens the database; injectable for tests.

    Returns
    -------
    list of Check
        One per check, in a sensible order. Failures do not stop later
        checks, so one run lists every problem.
    """
    checks = [
        Check("python", True, sys.version.split()[0]),
    ]
    try:
        checks.append(Check("tesseract", True, tesseract()))
    except PogoError as error:
        checks.append(Check("tesseract", False, str(error)))

    try:
        settings.validate()
        checks.append(
            Check("settings", True, f"backend: {settings.backend.value}")
        )
        configured = True
    except PogoError as error:
        checks.append(Check("settings", False, str(error)))
        configured = False

    if settings.backend is Backend.SHEETS:
        found = importlib.util.find_spec("gspread") is not None
        hint = "ok" if found else "missing; pip install 'PokemonGo[sheets]'"
        checks.append(Check("gspread", found, hint))

    if configured or settings.backend is not Backend.SHEETS:
        checks.append(_database(settings, opener))

    checks.append(_source(settings))
    checks.append(_writable_folder(settings.badges))
    return checks


def _database(
    settings: Settings, opener: Callable[[Settings], GymStore]
) -> Check:
    try:
        store = opener(settings)
        gyms = store.all()
        store.close()
    except PogoError as error:
        return Check("database", False, str(error))
    seeded = sum(1 for g in gyms if g.is_seeded)
    detail = f"{len(gyms)} gyms ({len(gyms) - seeded} scanned, {seeded} seeded)"
    return Check("database", True, detail)


def _source(settings: Settings) -> Check:
    try:
        found = discover([], settings.source)
    except PogoError as error:
        return Check("source folder", False, str(error))
    return Check(
        "source folder", True, f"{settings.source} ({len(found)} screenshots)"
    )
