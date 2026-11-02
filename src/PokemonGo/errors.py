"""Exceptions raised by PokemonGo.

Every error the package raises on purpose derives from
:class:`PogoError`, so callers can catch the whole family at once.
"""

from __future__ import annotations


class PogoError(Exception):
    """Base class for all errors raised by PokemonGo."""


class ParseError(PogoError, ValueError):
    """Text could not be turned into a value.

    Raised, for example, when pasted coordinates are not a ``lat,lon``
    pair or when a status string contains an unknown flag.
    """


class ConfigError(PogoError):
    """The configuration is missing, malformed, or inconsistent."""


class UnsupportedDeviceError(PogoError):
    """The image size matches no known phone profile.

    Pass the phone model explicitly (``--model``) to force a profile.
    """


class ImageReadError(PogoError):
    """An image file is missing, unreadable, or not an image."""


class OcrError(PogoError):
    """The OCR engine is missing or failed."""


class StoreError(PogoError):
    """A gym database could not be read or written."""


class SchemaError(StoreError):
    """A database does not have the current column layout.

    The message says what to do, usually "run ``pogo upgrade``".
    """
