"""Command-line entry point for the ``pogo`` tool.

Only ``--version`` is implemented so far. The sub-commands described in
``PLAN.md`` section 9 arrive in later phases.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from PokemonGo import __version__


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser for ``pogo``.

    Returns
    -------
    argparse.ArgumentParser
        The configured parser.

    Examples
    --------
    >>> build_parser().prog
    'pogo'
    """
    parser = argparse.ArgumentParser(
        prog="pogo",
        description="Build and maintain a database of gold gyms.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command-line interface.

    Parameters
    ----------
    argv : sequence of str, optional
        Command-line arguments, without the program name. Defaults to
        ``sys.argv[1:]``.

    Returns
    -------
    int
        The process exit status.
    """
    parser = build_parser()
    parser.parse_args(argv)
    parser.print_help()
    return 0
