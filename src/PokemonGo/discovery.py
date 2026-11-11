"""Find the screenshots to scan.

``pogo scan`` accepts any mix of files and folders. Files are matched on
``.png`` ignoring case, folders are searched one level deep unless asked
to recurse, and the same file is never returned twice even when it is
named two ways (on macOS ``IMG_1.png`` and ``IMG_1.PNG`` are one file).
"""

from __future__ import annotations

import os
from collections.abc import Iterator, Sequence
from pathlib import Path

from PokemonGo.errors import ConfigError


def _is_screenshot(path: Path) -> bool:
    """Return whether a path looks like a PNG screenshot.

    Names starting with ``._`` are skipped: macOS writes those resource
    files next to real ones on some drives.
    """
    name = path.name
    return (
        name.lower().endswith(".png")
        and not name.startswith("._")
        and path.is_file()
    )


def _in_folder(folder: Path, *, recursive: bool) -> list[Path]:
    """List the screenshots in a folder, oldest first, then by name."""
    candidates: Iterator[Path] = (
        folder.rglob("*") if recursive else folder.iterdir()
    )
    found = [p for p in candidates if _is_screenshot(p)]
    return sorted(found, key=lambda p: (p.stat().st_mtime_ns, p.name))


def discover(
    paths: Sequence[Path], default: Path, *, recursive: bool = False
) -> list[Path]:
    """Collect the screenshots named by the command line.

    Parameters
    ----------
    paths : sequence of pathlib.Path
        Files and folders. Explicit files keep the order given; the
        screenshots inside a folder are ordered by modification time,
        then name. If empty, ``default`` is searched.
    default : pathlib.Path
        The folder to search when no path is given.
    recursive : bool, optional
        Search inside sub-folders too.

    Returns
    -------
    list of pathlib.Path
        The screenshots, without duplicates, in processing order. Empty
        if there are none.

    Raises
    ------
    ConfigError
        If a path does not exist, or a named file is not a PNG. This is
        raised before anything is processed.
    """
    chosen = [p.expanduser() for p in paths] or [default.expanduser()]
    for path in chosen:
        if not path.exists():
            msg = f"path not found: {path}"
            raise ConfigError(msg)
        if path.is_file() and not path.name.lower().endswith(".png"):
            msg = f"only PNG screenshots are supported: {path}"
            raise ConfigError(msg)

    result: list[Path] = []
    seen: set[tuple[int, int]] = set()
    for path in chosen:
        found = (
            [path] if path.is_file() else _in_folder(path, recursive=recursive)
        )
        for screenshot in found:
            info = os.stat(screenshot)
            identity = (info.st_dev, info.st_ino)
            if identity not in seen:
                seen.add(identity)
                result.append(screenshot)
    return result
