"""Build and maintain a database of Pokemon GO gold gyms.

The package reads iPhone screenshots of gym badges, extracts the title
and the badge statistics, resolves the location, and stores one row per
gym in Google Sheets, SQLite, or a CSV file.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

try:
    __version__: str = version("PokemonGo")
except PackageNotFoundError:  # pragma: no cover - uninstalled checkout
    __version__ = "0+unknown"

__all__ = ["__version__"]
