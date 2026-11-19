# How it works

This page explains the reading and matching rules, so you know what to
expect and why a screenshot might need your attention.

## Supported phones

The badge screen's layout depends on the phone's screen. The tool knows
three screenshot sizes:

| Profile | Size in pixels (width × height) |
|---|---|
| `iSE` | 750 × 1334 |
| `i11` | 828 × 1792 |
| `i15` | 1179 × 2556 |

The size is detected from the image. A screenshot of any other size is
rejected with a message that names the closest profile; `--model` forces a
profile and scales the crops to fit. Adding a phone means adding one entry
to the profile table (see [](contributing.md)).

## Reading the title

The title sits near the top, but where exactly depends on whether it wraps
onto two lines, and the phone's clock and battery icons may overlap it. So
the tool does not trust a single crop. It reads four **variants**:

| Variant | Crop | Status bar |
|---|---|---|
| `default` | the usual title area | left as is |
| `tall` | extended upwards, to catch a wrapped first line | left as is |
| `tall-inpaint` | extended upwards | painted over |
| `default-inpaint` | the usual title area | painted over |

Each reading then goes through cleaning and ranking:

- **Noise is dropped.** Words with no letters or digits (stray marks such as
  `_`) are removed, but real title punctuation (`&`, `-`, `:`) is kept. A bar
  `|` between two words is read as the letter `i`: the game's capital I is
  drawn as a bar.
- **Status-bar text is discarded.** A reading that is a clean reading plus a
  clock or battery (`17:16 7 al horace ashenfelter ...`) is dropped when a
  clean reading with the same words exists.
- **Ranking.** If there are seeded titles to compare with, the reading
  closest to one of them wins; otherwise the engine's confidence decides.
  Ties go to the earlier, cheaper variant, and the search stops early on an
  exact match.

## Reading the statistics

The victories, time defended and treats are read from the lower part of the
screen and parsed tolerantly. OCR often reads a `0` as the letter `o`, a `1`
as `i` or `l`, and a `5` as `s`, so `18d oh 56m`, `13d 11h im` and `19d sh`
all parse. The parser is strict about structure: it needs victories, at
least one time part, and treats, and rejects impossible values such as 70
minutes. If it cannot be sure, it asks you (or skips the screenshot when
unattended).

## Matching titles

A title is normalised (lowercase, one line, curly quotes straightened) and
compared with the seeded gyms:

- identical after normalisation: an **exact** match;
- at least 90% alike: a **similar** match, which you confirm (or, unattended,
  accept at 95% and above);
- different **numbers** never match, however alike the rest is;
- the letters `i` and `l` are treated as the same.

When creating a gym, a same-titled gym within 100 metres is flagged as a
probable duplicate.

## Addresses

City, county, state and country come from OpenStreetMap's Nominatim service.
The tool follows its usage policy: at most one request per second, your
email as the user agent, retries when the service is briefly unavailable.
Names are requested in English. Results are cached in `geocode_cache.json`,
so each place is only ever looked up once. The city is the first available of
`city`, `town`, `village`, `township` (then `borough`, `municipality`,
`hamlet`).

## How accurate is it?

On the author's 1,191 screenshots, read with no hints:

- **98.2%** of titles were read exactly, and **99.6%** closely enough to
  match;
- the statistics were read correctly for essentially every screenshot;
- about **0.4%** needed a person: titles of three or more lines (which do
  not fit the crop) and a few genuine misreads.

These are figures for one person's data. `pogo eval` measures yours (see
[](cli.md)).

## Limits

- iPhone screenshots only, in PNG format, at the three sizes above.
- Titles of three or more lines may not be read completely.
- An already scanned gym is not re-read to update its statistics.
- A gym scanned from two different screenshots is only recognised as a
  duplicate when its coordinates are given and the title matches closely.
