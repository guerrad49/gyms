# PokemonGo

Build and maintain a database of your Pokémon GO **gold gyms** from iPhone
screenshots of the gym badges. The in-game list of gyms is capped at the
1,000 most recent; this keeps a permanent record beyond that.

For each screenshot it:

1. reads the title and the badge statistics (victories, time defended,
   treats) with OCR;
2. finds the gym, or creates it;
3. looks up the city, county, state and country from the coordinates;
4. saves the row to **Google Sheets**, **SQLite** or a **CSV** file;
5. files the screenshot as `IMG_####.PNG`.

The database can be imported into **Google My Maps**.

## Install

You need Python 3.10 or newer and the Tesseract OCR program.

```bash
brew install tesseract                       # macOS; Debian: apt install tesseract-ocr
git clone <repository-url> pogo && cd pogo
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[sheets]"                   # leave out [sheets] for CSV or SQLite
pogo doctor                                  # checks everything
```

## Quick start

Create `variables.env`:

```
EMAIL=you@example.com
BACKEND=csv
CSV_PATH=gyms.csv
```

AirDrop some badge screenshots to `~/Downloads`, then:

```bash
pogo scan --dry-run      # preview: changes nothing
pogo scan                # scan for real; it asks when unsure
pogo resolve             # fill in missing addresses
pogo export my-maps maps.csv
```

## Commands

| Command | Purpose |
|---|---|
| `pogo scan [PATH ...]` | Read screenshots (files or folders) into the database. |
| `pogo resolve` | Fill in missing addresses from coordinates. |
| `pogo upgrade` | Upgrade a version 1 database (with a backup). |
| `pogo migrate` | Copy the database to another backend. |
| `pogo export my-maps FILE` | Write a CSV for Google My Maps. |
| `pogo doctor` | Check that everything is in place. |
| `pogo eval` | Measure OCR accuracy against your own database. |

Useful `scan` options: `--non-interactive` (never ask; leave anything
uncertain for later), `--dry-run`, `--copy`, `--model`, `--recursive`.

## Documentation

The full guide is in the `docs/` folder and is published with GitHub Pages:
installation, configuration, the scanning workflow, the database layout,
Google Sheets setup, troubleshooting, and how the reading and matching work.
Build it locally with:

```bash
pip install -e ".[docs]"
sphinx-build -b html docs docs/_build/html
```

## Upgrading from version 1

Your settings file and your data carry over. See the migration guide in the
documentation; the short version is `pogo upgrade`.

## Accuracy

On the author's 1,191 screenshots, 98.2% of titles were read exactly and
99.6% closely enough to match, and the statistics were read correctly
essentially every time. About 0.4% needed a person.

## Notes

- iPhone screenshots only (three screen sizes so far).
- For personal use. Address lookups use OpenStreetMap's Nominatim service
  under its usage policy: one request per second, identified by your email.
- Keep `variables.env`, your Google key, `badges/` and your database out of
  version control: gym coordinates reveal where you have been.

## Contributing

See `CONTRIBUTING.md`. The code is typed, tested and documented, and the
checks are the same ones CI runs.

## License

MIT. See `LICENSE`.
