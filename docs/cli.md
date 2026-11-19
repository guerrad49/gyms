# Command reference

Every command is run as `pogo COMMAND`. `pogo --help` lists them and
`pogo COMMAND --help` shows one command's options. Options that say where
the database is (`--env-file`, `--backend`, `--csv-path`, `--db-path`) work
on every command that uses it; see [](configuration.md).

| Command | Purpose |
|---|---|
| `scan` | Read screenshots into the database. See [](workflow.md). |
| `resolve` | Fill in missing addresses from coordinates. |
| `upgrade` | Upgrade a version 1 database. See [](database.md). |
| `migrate` | Copy the database to another backend. |
| `export` | Write a file for Google My Maps. |
| `doctor` | Check that everything is in place. |
| `eval` | Measure OCR accuracy against your own database. |

## Full reference

This section is generated from the program itself, so it always matches the
installed version.

```{argparse}
:module: PokemonGo.cli
:func: build_parser
:prog: pogo
```

## Measuring accuracy

`pogo eval` reads every stored screenshot with no hints and compares the
result with your database. It is how the reading was tuned, and it can find
rows in an older database that were misread when they were first scanned.

```bash
pogo eval --badges badges --truth export.csv --problems problems.csv \
          --near-misses near_misses.csv
```

`export.csv` needs the columns `uid`, `title`, `victories`, `days`,
`hours`, `minutes` and `treats`; screenshots are found as `IMG_####.PNG`
by `uid`. Use `--limit N` for a quick look and `--jobs N` to read several
screenshots at once.
