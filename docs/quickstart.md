# Quick start

This walks through a first scan using a plain CSV file as the database. It
needs no Google account. See [](google-sheets.md) to use a spreadsheet
instead.

## 1. Settings

Create a file called `variables.env` in the folder where you will run
`pogo`:

```
EMAIL=you@example.com
BACKEND=csv
CSV_PATH=gyms.csv
SOURCE=~/Downloads
BADGES=badges
```

`EMAIL` is required. Addresses come from OpenStreetMap's Nominatim service,
whose usage policy asks every user to identify themselves. All the settings
are explained in [](configuration.md).

## 2. Check everything

```bash
pogo doctor
```

Every line should start with `[ok]`.

## 3. Take screenshots

In Pokémon GO, open a gym's **badge** screen (the one with the diamond and
*Total gym activity*) and take a screenshot. AirDrop them to your Mac. They
arrive in `~/Downloads`, which is where `pogo` looks by default.

## 4. Preview, then scan

A dry run shows exactly what would happen and changes nothing:

```bash
pogo scan --dry-run
```

Then scan for real:

```bash
pogo scan
```

For a gym it has not seen before, `pogo` asks for the title (press Enter to
accept the one it read) and the coordinates as `lat,lon`. Coordinates are not
on the screenshot; copy them from a map. Press Enter to leave them for later.

Each screenshot is saved to the database and then filed in `badges/` as
`IMG_0001.PNG`, `IMG_0002.PNG` and so on.

## 5. Fill in the rest

If you left coordinates blank, add them to the database later, then run:

```bash
pogo resolve
```

It fills in the city, county, state and country of every gym that has
coordinates but no address.

## 6. Use the data

```bash
pogo export my-maps maps.csv
```

writes a file you can import into Google My Maps. See [](database.md).

## Next steps

- [](workflow.md) explains the prompts and how to run unattended.
- [](troubleshooting.md) lists common problems.
