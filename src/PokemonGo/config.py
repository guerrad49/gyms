"""Configuration: where files live, which backend to use, who you are.

Values come from four places. From lowest to highest precedence:

1. built-in defaults;
2. a ``variables.env`` file (the same keys v1 used);
3. environment variables, each prefixed with ``POGO_``
   (``POGO_BACKEND``, ``POGO_EMAIL``, ...), so they cannot collide with
   unrelated variables such as a system-wide ``EMAIL``;
4. overrides, which the command line passes for the options it received.

A relative path inside ``variables.env`` is resolved against the folder
that contains the file, as in v1. Relative paths from the environment or
the command line are left relative to the working directory.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from enum import Enum
from pathlib import Path
from typing import Final

from dotenv import dotenv_values

from PokemonGo.errors import ConfigError

ENV_PREFIX: Final = "POGO_"

# Key in variables.env -> name of the Settings field.
_KEYS: Final = {
    "BACKEND": "backend",
    "EMAIL": "email",
    "SOURCE": "source",
    "BADGES": "badges",
    "SHEET_NAME": "sheet_name",
    "JSON_KEY": "json_key",
    "DB_PATH": "db_path",
    "CSV_PATH": "csv_path",
    "PHONE_MODEL": "phone_model",
}
_PATH_FIELDS: Final = frozenset(
    {"source", "badges", "json_key", "db_path", "csv_path"}
)


class Backend(str, Enum):
    """Where the gym database is stored."""

    SHEETS = "sheets"
    CSV = "csv"
    SQLITE = "sqlite"


def _default_source() -> Path:
    """Return the default folder to scan, ``~/Downloads``."""
    return Path.home() / "Downloads"


@dataclass(frozen=True, slots=True)
class Settings:
    """Resolved configuration, passed explicitly instead of via globals.

    Parameters
    ----------
    backend : Backend, optional
        Where the database lives. Defaults to Google Sheets, as in v1.
    email : str, optional
        Contact address required by the Nominatim usage policy.
    source : pathlib.Path, optional
        Default folder of screenshots to scan.
    badges : pathlib.Path, optional
        Folder where processed screenshots are stored.
    sheet_name : str, optional
        Spreadsheet name (sheets backend).
    json_key : pathlib.Path, optional
        Google service-account key file (sheets backend).
    db_path : pathlib.Path, optional
        SQLite database file (sqlite backend).
    csv_path : pathlib.Path, optional
        CSV database file (csv backend).
    phone_model : str, optional
        Force a phone profile instead of detecting it from the image.

    Examples
    --------
    >>> settings = Settings.load(
    ...     environ={"POGO_BACKEND": "csv", "POGO_CSV_PATH": "gyms.csv"}
    ... )
    >>> settings.backend
    <Backend.CSV: 'csv'>
    >>> str(settings.csv_path)
    'gyms.csv'
    """

    backend: Backend = Backend.SHEETS
    email: str = ""
    source: Path = field(default_factory=_default_source)
    badges: Path = Path("badges")
    sheet_name: str = ""
    json_key: Path | None = None
    db_path: Path | None = None
    csv_path: Path | None = None
    phone_model: str | None = None

    @classmethod
    def load(
        cls,
        *,
        env_file: Path | None = None,
        environ: Mapping[str, str] | None = None,
        overrides: Mapping[str, str | None] | None = None,
    ) -> Settings:
        """Build settings from all sources.

        Parameters
        ----------
        env_file : pathlib.Path, optional
            A ``variables.env`` file. It must exist if given.
        environ : mapping of str to str, optional
            The environment, normally ``os.environ``. Only keys starting
            with ``POGO_`` are read.
        overrides : mapping of str to str or None, optional
            Highest precedence, keyed by field name (``"badges"``,
            ``"phone_model"``). ``None`` and empty values are ignored,
            so unset command-line options can be passed straight through.

        Returns
        -------
        Settings
            The resolved settings. Call :meth:`validate` before use.

        Raises
        ------
        ConfigError
            If ``env_file`` does not exist or the backend is unknown.
        """
        raw: dict[str, str] = {}
        if env_file is not None:
            raw.update(_read_env_file(env_file))
        for key, name in _KEYS.items():
            value = (environ or {}).get(ENV_PREFIX + key)
            if value:
                raw[name] = value
        for name, value in (overrides or {}).items():
            if value:
                raw[name] = value
        return cls._from_raw(raw)

    @classmethod
    def _from_raw(cls, raw: Mapping[str, str]) -> Settings:
        """Convert text values into typed fields."""
        changes: dict[str, object] = {}
        for name, value in raw.items():
            if name == "backend":
                changes[name] = _parse_backend(value)
            elif name in _PATH_FIELDS:
                changes[name] = Path(value).expanduser()
            elif name in _KEYS.values():
                changes[name] = value.strip()
        return replace(cls(), **changes)  # type: ignore[arg-type]

    def validate(self, *, need_email: bool = True) -> Settings:
        """Check that everything the chosen backend needs is present.

        Parameters
        ----------
        need_email : bool, optional
            Whether a contact email is required (it is whenever addresses
            are looked up).

        Returns
        -------
        Settings
            ``self``, so calls can be chained.

        Raises
        ------
        ConfigError
            Listing every problem found, not just the first.

        Examples
        --------
        >>> Settings(backend=Backend.CSV).validate(need_email=False)
        Traceback (most recent call last):
            ...
        PokemonGo.errors.ConfigError: CSV_PATH is required for the csv backend
        """
        problems: list[str] = []
        if self.backend is Backend.SHEETS:
            if not self.sheet_name:
                problems.append("SHEET_NAME is required for sheets")
            if self.json_key is None:
                problems.append("JSON_KEY is required for sheets")
            elif not self.json_key.is_file():
                problems.append(f"JSON_KEY file not found: {self.json_key}")
        elif self.backend is Backend.CSV and self.csv_path is None:
            problems.append("CSV_PATH is required for the csv backend")
        elif self.backend is Backend.SQLITE and self.db_path is None:
            problems.append("DB_PATH is required for the sqlite backend")
        if need_email and "@" not in self.email:
            problems.append("EMAIL must be a valid contact address")
        if problems:
            msg = "; ".join(problems)
            raise ConfigError(msg)
        return self


def _parse_backend(value: str) -> Backend:
    """Convert text to a :class:`Backend`, listing the choices on error."""
    try:
        return Backend(value.strip().lower())
    except ValueError:
        choices = ", ".join(backend.value for backend in Backend)
        msg = f"unknown backend {value!r}; choose one of: {choices}"
        raise ConfigError(msg) from None


def _read_env_file(path: Path) -> dict[str, str]:
    """Read ``variables.env`` into ``{field name: text}``.

    Empty values count as unset, and unknown keys are ignored (the old
    ``LOG_FILE`` key, for instance).
    """
    if not path.is_file():
        msg = f"configuration file not found: {path}"
        raise ConfigError(msg)
    values: dict[str, str] = {}
    for key, value in dotenv_values(path).items():
        name = _KEYS.get(key)
        if name is None or not value or not value.strip():
            continue
        if name in _PATH_FIELDS:
            value = str(path.parent / Path(value).expanduser())
        values[name] = value
    return values
