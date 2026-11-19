# The database

Every backend stores the same 20 columns (schema v2). Columns are found by
**name**, so their order does not matter, and extra columns you add yourself
are left untouched.

| Column | Meaning |
|---|---|
| `uid` | Unique id; the screenshot is filed as `IMG_<uid>.PNG`. Blank for a seeded gym that was never scanned. |
| `title` | The gym's name, lowercase. |
| `model` | The phone profile the badge was scanned on (`iSE`, `i11`, `i15`). |
| `style` | `gold`, or `100+ days` from 100 days defended. |
| `victories`, `days`, `hours`, `minutes` | From the badge. |
| `defended` | Time defended in fractional days (4 decimals). |
| `treats` | From the badge. |
| `latitude`, `longitude` | Decimal degrees, stored as numbers. |
| `city`, `county`, `state`, `country` | Lowercase, in English. |
| `status` | Review flags, comma separated; blank means clean. See [](workflow.md). |
| `scanned_at` | The date of the screenshot (`YYYY-MM-DD`). |
| `notes` | Free text for you. |
| `image_sha256` | The screenshot's hash, used to avoid adding it twice. |

`style` and `defended` are always recomputed from the statistics, so a
hand-edited value cannot disagree with them.

## Choosing a backend

| Backend | Good for | Notes |
|---|---|---|
| `csv` | Getting started; easy to open anywhere | The whole file is rewritten, atomically, after each screenshot. |
| `sqlite` | A fast single-file database | Always read in geographic order. |
| `sheets` | Sharing, editing by hand, Google My Maps | See [](google-sheets.md). |

All three behave identically; the same tests run against each.

## Order

`pogo scan` finishes by sorting the database by state, county, city and
title, ignoring case, with blank values last.

## Upgrading a version 1 database

Version 1 stored coordinates in one `latlon` column. Version 2 uses two
numeric columns. `pogo upgrade` converts a CSV file or a Google Sheet:

```bash
pogo upgrade --dry-run     # show the plan, change nothing
pogo upgrade               # back up, ask, then upgrade
```

It writes a timestamped backup to `backups/` first, asks for confirmation,
re-reads the result and checks the number of gyms. It:

- splits `latlon` into `latitude` and `longitude`;
- adds the new columns (`country`, `status`, `scanned_at`, `notes`,
  `image_sha256`, and `model` if missing);
- drops an unnamed index column left by some CSV exports;
- keeps any extra columns you added;
- flags a row whose coordinates cannot be read `NO_COORDS` instead of losing
  it.

Running it twice is harmless. Try it on a copy of your sheet first. See
[](migrating-from-v1.md).

## Moving between backends

```bash
pogo migrate --from sheets --to sqlite --db-path gyms.db
```

copies every gym, seeded or scanned. The target must be empty, so two
databases can never be mixed.

## Google My Maps

```bash
pogo export my-maps maps.csv            # scanned gyms with coordinates
pogo export my-maps maps.csv --include-seeded
```

writes `title, latitude, longitude, style, days, defended, victories,
treats, city, county, state, country`. In My Maps choose **Import**, pick
`latitude` and `longitude` as the position columns and `title` as the
marker title.

:::{note}
My Maps limits the number of places per layer (about 2,000 at the time of
writing). Check the current limit if your collection grows toward it.
:::
