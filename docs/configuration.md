# Configuration

Settings come from four places. From lowest to highest precedence:

1. built-in defaults;
2. a settings file, `variables.env`;
3. environment variables, each starting with `POGO_`;
4. command-line options.

## The settings file

`pogo` looks for the file in this order and uses the first it finds:

1. the path given with `--env-file`;
2. `variables.env` in the current folder;
3. `requirements/variables.env`, where version 1 kept it.

It contains `KEY=value` lines. Relative paths in the file are relative to
the folder that holds the file. A leading `~` means your home folder. A
blank value counts as unset, and unknown keys are ignored.

| Key | Meaning | Default |
|---|---|---|
| `EMAIL` | Your contact address, sent to Nominatim as the user agent. **Required.** | |
| `BACKEND` | `sheets`, `csv` or `sqlite`. | `sheets` |
| `CSV_PATH` | The CSV file (csv backend). | |
| `DB_PATH` | The SQLite file (sqlite backend). | |
| `SHEET_NAME` | The spreadsheet's name (sheets backend). | |
| `JSON_KEY` | The Google service-account key file (sheets backend). | |
| `SOURCE` | The folder of screenshots to scan when none is named. | `~/Downloads` |
| `BADGES` | The folder where processed screenshots are filed. | `badges` |
| `PHONE_MODEL` | Force a phone profile (`iSE`, `i11`, `i15`) instead of detecting it. | detect |
| `GEOCODE_CACHE` | The file that remembers address lookups. | `geocode_cache.json` |

The old `LOG_FILE` key from version 1 is ignored: the database's `status`
column replaces the log.

## Environment variables

Every key can also be set in the environment with a `POGO_` prefix, for
example `POGO_BACKEND=csv` or `POGO_EMAIL=you@example.com`. The prefix keeps
them from clashing with unrelated variables such as a system-wide `EMAIL`.
Relative paths in environment variables are relative to the current folder.

## Command-line options

The options that say where the database is work on every command:

| Option | Meaning |
|---|---|
| `--env-file FILE` | Use this settings file. |
| `--backend NAME` | `sheets`, `csv` or `sqlite`. |
| `--csv-path FILE` | The CSV database. |
| `--db-path FILE` | The SQLite database. |

Other options belong to individual commands; see [](cli.md).

## Keep secrets out of git

`variables.env`, your Google key file, `badges/`, `backups/` and the
geocoding cache are listed in the repository's `.gitignore`. Keep them out
of version control: the repository is public, and gym coordinates reveal
where you have been.
