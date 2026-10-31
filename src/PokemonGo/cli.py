"""Command-line entry point for the ``pogo`` tool.

Implemented so far: ``pogo eval`` (the OCR benchmark) and ``--version``.
The remaining sub-commands described in ``PLAN.md`` section 9 arrive in
later phases.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from PokemonGo import __version__
from PokemonGo.errors import ConfigError, PogoError


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
    from PokemonGo.vision.devices import profile_names
    from PokemonGo.vision.engines import ENGINES

    parser = argparse.ArgumentParser(
        prog="pogo",
        description="Build and maintain a database of gold gyms.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")

    evaluate = commands.add_parser(
        "eval",
        help="measure OCR accuracy against your existing database",
        description=(
            "Read every stored screenshot with no hints and compare the "
            "result with the values already in your database."
        ),
    )
    evaluate.add_argument(
        "--badges",
        type=Path,
        required=True,
        help="folder of IMG_####.PNG screenshots",
    )
    evaluate.add_argument(
        "--truth",
        type=Path,
        required=True,
        help="CSV export with uid,title,victories,days,hours,minutes,treats",
    )
    evaluate.add_argument(
        "--model",
        choices=profile_names(),
        help="force a phone profile instead of detecting it",
    )
    evaluate.add_argument(
        "--engine",
        choices=sorted(ENGINES),
        default="tesseract",
        help="OCR engine (default: %(default)s)",
    )
    evaluate.add_argument(
        "--limit", type=int, help="only check the first N rows"
    )
    evaluate.add_argument(
        "--jobs", type=int, default=4, help="parallel reads (default: 4)"
    )
    evaluate.add_argument(
        "--problems",
        type=Path,
        help="write the rows that needed help to this CSV file",
    )
    evaluate.add_argument(
        "--near-misses",
        type=Path,
        help="write rows with a close but not identical title to this CSV",
    )
    return parser


def _run_eval(args: argparse.Namespace) -> int:
    """Run the ``eval`` command and print its report."""
    from PokemonGo.evaluate import (
        evaluate,
        format_report,
        load_truth,
        write_near_misses,
        write_problems,
    )
    from PokemonGo.vision.engines import make_engine
    from PokemonGo.vision.reader import BadgeReader

    if not args.badges.is_dir():
        msg = f"badges folder not found: {args.badges}"
        raise ConfigError(msg)
    truth = load_truth(args.truth)
    if args.limit is not None:
        truth = truth[: args.limit]
    reader = BadgeReader(make_engine(args.engine), model=args.model)

    def progress(done: int, total: int) -> None:
        if done % 25 == 0 or done == total:
            print(f"  {done}/{total}", file=sys.stderr)

    report = evaluate(
        reader, args.badges, truth, jobs=args.jobs, progress=progress
    )
    print(format_report(report))
    if args.problems is not None:
        count = write_problems(report, args.problems)
        print(f"\nWrote {count} problem row(s) to {args.problems}")
    if args.near_misses is not None:
        count = write_near_misses(report, args.near_misses)
        print(f"Wrote {count} near-miss row(s) to {args.near_misses}")
    return 0


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
        The process exit status: 0 on success, 1 when a
        :class:`~PokemonGo.errors.PogoError` was reported.
    """
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "eval":
            return _run_eval(args)
    except PogoError as error:
        print(f"pogo: error: {error}", file=sys.stderr)
        return 1
    parser.print_help()
    return 0
