# Scanning screenshots

`pogo scan` turns badge screenshots into database rows. This page explains
what it does with each screenshot and what it does when it is unsure.

## What happens to each screenshot

1. **Identify.** Its SHA-256 is checked against the database, so the same
   screenshot is never added twice.
2. **Read.** The title and the statistics are read with OCR.
3. **Match.** The title is compared with gyms that have no `uid` yet
   ("seeded" gyms, see below).
4. **Complete.** The address is looked up from the coordinates.
5. **Save.** The row is written and committed.
6. **File.** Only then is the screenshot moved to `badges/IMG_####.PNG`,
   where `####` is the gym's `uid`.

A problem with one screenshot is reported and the scan carries on with the
rest. A failure of the *database* stops the scan, so a screenshot is never
filed away without its row.

## Choosing what to scan

```bash
pogo scan                       # the source folder (default ~/Downloads)
pogo scan ~/Pictures/pogo       # a folder
pogo scan IMG_1305.PNG          # one file
pogo scan a.PNG b.PNG c.PNG     # several, in this order
pogo scan --recursive ~/Pictures
```

- Only `.png` files (any capitalisation) are used.
- Files inside a folder are processed oldest first, then by name. Files you
  name are processed in the order given.
- A file named twice, or under two names (on macOS `IMG.png` and `IMG.PNG`
  are one file), is processed once.
- A path that does not exist is an error before anything is scanned.

## Seeded gyms and new gyms

You can **seed** the database by adding rows that have a title and
coordinates but no `uid`. When a screenshot's title matches a seed, that row
is filled in (its stored title is kept). This is optional: a screenshot that
matches no seed simply creates a new gym.

Matching ignores case, punctuation noise and the letters `i`/`l` (the game's
capital I is often read as a lowercase l). Titles that differ in a *number*
never match each other, so `building 10` is never mistaken for `building 11`.

## When it asks you

With a person at the keyboard, `pogo scan` asks when it is not sure:

| Situation | Question |
|---|---|
| One similar (not identical) seeded title | Use it? |
| Several seeded gyms with the same title | Which one? (the list shows city and coordinates, with "none of these") |
| No seeded gym matches | The title (Enter accepts the one it read), then the coordinates as `lat,lon` |
| A same-titled gym is within 100 m | Add it as a new gym anyway? |
| The statistics could not be read | Type them like `27 18d 0h 56m 16` |
| City or state still missing after the lookup | The city, the state |

Typing `skip` at a text question leaves the screenshot where it is for a
later run. Coordinates can be pasted in any common form: `40.75,-73.98`,
`40.75, -73.98` or `(40.75, -73.98)`. Pressing Enter at the coordinates
question means "not yet".

The county is never asked for, because many places have none.

## Running unattended

```bash
pogo scan --non-interactive
```

Nothing is asked. It accepts only what is safe, and leaves everything else
for a later run:

| Situation | What happens |
|---|---|
| Exact title match | Used. |
| One similar title | Used only if it is at least 95% alike (`--auto-accept`). |
| Several gyms with the same title | Skipped. |
| Statistics unreadable | Skipped. |
| No seeded gym matches | A new gym is added with the read title and flagged `NO_COORDS`. |
| City or state missing | Left blank and flagged. |

Skipped screenshots are never moved, so you can run `pogo scan` again
interactively to deal with them.

## Review flags

The `status` column lists reasons a person should look at a row. A blank
status means the row is clean.

| Flag | Meaning |
|---|---|
| `NO_COORDS` | The gym has no coordinates yet. |
| `ADDRESS` | The address lookup found nothing, or failed. |
| `CITY`, `STATE` | That part of the address is still blank. |
| `COUNTY` | The county is blank. Many places have none, so this is often fine. |

`pogo resolve` clears the flags it can. The flags `TITLE` and `STATS` are
accepted in the column (version 1 logged them) but are not set by this
version.

## Previewing and safety

```bash
pogo scan --dry-run
```

reads everything, matches, looks up addresses and asks its questions, then
prints the row and file name each screenshot *would* get. It saves nothing,
moves nothing and creates no folders. Ids shown are provisional.

- `--copy` copies screenshots into `badges/` and leaves the originals.
- A file already in `badges/` is never overwritten.
- If a run is interrupted, run it again. A screenshot that was saved but not
  yet filed is filed; one that is a duplicate of a filed screenshot is
  reported and left alone.

## Other options

| Option | Meaning |
|---|---|
| `--model NAME` | Force a phone profile (`iSE`, `i11`, `i15`) instead of detecting it from the image size. |
| `--badges DIR` | File screenshots into this folder instead. |
| `--auto-accept RATIO` | The similarity needed to accept a title unattended (default 0.95). |
| `--no-sort` | Do not sort the database at the end. |
| `--cache FILE`, `--no-cache` | Use another address cache, or none. |
| `-v` | Show what was read from each screenshot and which reading variant won. |

At the end, the database is sorted by state, county, city and title
(blank values last).

## Exit status

| Status | Meaning |
|---|---|
| 0 | Every screenshot was done, or had already been done. |
| 2 | Some screenshots were skipped or failed; they are listed. |
| 1 | A fatal error (bad settings, database unreachable, ...). |
| 130 | You interrupted it. Everything finished so far is saved. |

## After scanning

If addresses are missing (for example you entered coordinates later), run:

```bash
pogo resolve
```

It looks up gyms that have coordinates but no city or state. It never
overwrites a value that is already there. See [](cli.md) for its options.
