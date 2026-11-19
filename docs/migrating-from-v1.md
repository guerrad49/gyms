# Migrating from version 1

Version 2 keeps your data and your settings file. The steps below take
about ten minutes.

## 1. Make a backup

Before anything else:

- In Google Sheets, choose **File → Make a copy** and keep the copy.
- Copy your `badges/` folder.

`pogo upgrade` writes its own backup too, but a second copy costs nothing.

## 2. Install version 2

Follow [](installation.md). Version 2 needs the **Tesseract** program (as
version 1 did) and Python 3.10 or newer. There is no `setup.sh`: use
`pip install -e ".[sheets]"`.

## 3. Your settings

Your existing `variables.env` works as it is, including when it is in
`requirements/`. The same keys apply (`SHEET_NAME`, `JSON_KEY`, `EMAIL`).
`LOG_FILE` is ignored. Relative paths are relative to the settings file,
as before. See [](configuration.md).

## 4. Check, then upgrade

```bash
pogo doctor                # reports that the database needs upgrading
pogo upgrade --dry-run     # shows what will change
pogo upgrade               # backs up, asks, then upgrades
```

The upgrade splits the `latlon` column into numeric `latitude` and
`longitude`, adds the new columns, and keeps everything else, including any
columns you added. See [](database.md).

## What changed

| Version 1 | Version 2 |
|---|---|
| `./scanner.py` | `pogo scan` |
| Every gym had to be seeded with a title and coordinates | Seeding is optional; a new gym can be created while scanning |
| `latlon` column | `latitude` and `longitude` columns |
| A log file of errors | A `status` column on each row |
| Only the first `city` key found was last-wins | The first available city key wins |
| Names in the service's default language | Names in English |
| `-u` update mode (it did not work reliably) | Not available |
| No preview | `pogo scan --dry-run` |
| Prompts always | Prompts, or `--non-interactive` |

New columns: `country`, `status`, `scanned_at`, `notes`, `image_sha256`.

## 5. Optional: audit your old data

Version 1's reader could silently misread a time. When `1m` was read as
`im`, it kept the hours as the *treats* and set hours and minutes to 0,
without asking. `pogo eval` compares every stored screenshot with your
database and lists the rows that disagree:

```bash
pogo eval --badges badges --truth export.csv --problems problems.csv
```

Look for rows where the database has `hours = 0`, `minutes = 0` and `treats`
equal to the hours shown on the screenshot. See [](cli.md) for the export
format.

## Going back

Restore the copy you made in step 1, and keep using version 1's
`scanner.py` from your earlier checkout.
