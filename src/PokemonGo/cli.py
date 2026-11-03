"""Command-line entry point for the ``pogo`` tool.

Implemented so far: ``pogo eval`` (the OCR benchmark) and ``--version``.
The remaining sub-commands described in ``PLAN.md`` section 9 arrive in
later phases.
"""

from __future__ import annotations

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from PokemonGo import __version__
from PokemonGo.config import Backend, Settings
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
    upgrade = commands.add_parser(
        "upgrade",
        help="upgrade a v1 database to the current layout",
        description=(
            "Split 'latlon' into latitude and longitude and add the new "
            "columns. A backup is written first."
        ),
    )
    _add_store_options(upgrade)
    upgrade.add_argument(
        "--backups",
        type=Path,
        default=Path("backups"),
        help="folder for the backup (default: %(default)s)",
    )
    upgrade.add_argument(
        "--dry-run", action="store_true", help="show the changes only"
    )
    upgrade.add_argument(
        "--yes", action="store_true", help="do not ask for confirmation"
    )

    migrate = commands.add_parser(
        "migrate", help="copy the database to another backend"
    )
    _add_store_options(migrate)
    migrate.add_argument(
        "--from",
        dest="source",
        required=True,
        choices=[b.value for b in Backend],
    )
    migrate.add_argument(
        "--to",
        dest="target",
        required=True,
        choices=[b.value for b in Backend],
    )

    export = commands.add_parser("export", help="export the database")
    formats = export.add_subparsers(dest="format", metavar="FORMAT")
    my_maps = formats.add_parser(
        "my-maps", help="a CSV that Google My Maps can import"
    )
    _add_store_options(my_maps)
    my_maps.add_argument("output", type=Path, help="CSV file to write")
    my_maps.add_argument(
        "--include-seeded",
        action="store_true",
        help="also export gyms that were never scanned",
    )
    return parser


def _add_store_options(parser: argparse.ArgumentParser) -> None:
    """Add the options that say where the database is."""
    parser.add_argument(
        "--env-file",
        type=Path,
        help="settings file (default: variables.env, then "
        "requirements/variables.env)",
    )
    parser.add_argument(
        "--backend",
        choices=[b.value for b in Backend],
        help="where the database is stored",
    )
    parser.add_argument("--csv-path", type=Path, help="CSV database file")
    parser.add_argument("--db-path", type=Path, help="SQLite database file")


def _settings(args: argparse.Namespace) -> Settings:
    """Combine the settings file, environment and command-line options."""
    env_file = args.env_file
    if env_file is None:
        for candidate in (
            Path("variables.env"),
            Path("requirements") / "variables.env",
        ):
            if candidate.is_file():
                env_file = candidate
                break
    overrides = {
        "backend": args.backend,
        "csv_path": None if args.csv_path is None else str(args.csv_path),
        "db_path": None if args.db_path is None else str(args.db_path),
    }
    return Settings.load(
        env_file=env_file, environ=os.environ, overrides=overrides
    )


def _run_upgrade(args: argparse.Namespace) -> int:
    """Upgrade a database to schema v2, with a backup and a confirmation."""
    from PokemonGo.store import open_store, read_table, write_table
    from PokemonGo.store.upgrade import backup_table, upgrade_table

    settings = _settings(args)
    backend = settings.backend
    if backend is Backend.SQLITE:
        print("SQLite databases are created with the current schema.")
        return 0
    table = read_table(settings, backend)
    if not table.header:
        print("The database is empty; nothing to upgrade.")
        return 0
    new, plan = upgrade_table(table)
    if not plan.changes_anything:
        print(f"Already on schema v2 ({plan.rows} gyms). Nothing to do.")
        return 0

    print(f"Upgrading the {backend.value} database ({plan.rows} gyms):")
    if plan.dropped:
        print(f"  remove columns : {', '.join(plan.dropped)}")
    if plan.added:
        print(f"  add columns    : {', '.join(plan.added)}")
    if "latlon" in plan.dropped:
        print("  split 'latlon' into numeric latitude and longitude")
    for number, value in plan.bad_coordinates:
        print(f"  row {number}: unreadable coordinates {value!r} (flagged)")
    if args.dry_run:
        print("Dry run: nothing was changed.")
        return 0

    backup = backup_table(table, args.backups, backend.value)
    print(f"Backup written to {backup}")
    if not args.yes and input("Apply the upgrade? [y/N] ").strip() != "y":
        print("Cancelled; nothing was changed.")
        return 1
    write_table(settings, backend, new)
    stored = len(open_store(settings, backend).all())
    if stored != plan.rows:
        msg = f"upgrade check failed: {stored} gyms found, expected {plan.rows}"
        raise PogoError(msg)
    print(f"Done. {stored} gyms verified.")
    return 0


def _run_migrate(args: argparse.Namespace) -> int:
    """Copy a database to another backend."""
    from PokemonGo.store import open_store
    from PokemonGo.store.migrate import copy_gyms

    source_kind, target_kind = Backend(args.source), Backend(args.target)
    if source_kind is target_kind:
        msg = "--from and --to must be different backends"
        raise ConfigError(msg)
    settings = _settings(args)
    source = open_store(settings, source_kind)
    target = open_store(settings, target_kind)
    count = copy_gyms(source, target)
    print(
        f"Copied {count} gyms from {source_kind.value} to {target_kind.value}."
    )
    return 0


def _run_export(args: argparse.Namespace) -> int:
    """Write a CSV for Google My Maps."""
    from PokemonGo.export import write_my_maps_csv
    from PokemonGo.store import open_store

    store = open_store(_settings(args))
    count = write_my_maps_csv(
        store.all(), args.output, include_seeded=args.include_seeded
    )
    print(f"Wrote {count} gyms to {args.output}")
    return 0


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
        if args.command == "upgrade":
            return _run_upgrade(args)
        if args.command == "migrate":
            return _run_migrate(args)
        if args.command == "export" and args.format == "my-maps":
            return _run_export(args)
    except PogoError as error:
        print(f"pogo: error: {error}", file=sys.stderr)
        return 1
    parser.print_help()
    return 0
