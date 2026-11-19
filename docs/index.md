# PokemonGo

Build and maintain a database of your Pokémon GO **gold gyms** from iPhone
screenshots of the gym badges.

Each badge screenshot is read with OCR (the title, victories, time defended
and treats), matched to a gym, given an address from its coordinates, and
saved to a database of your choice: **Google Sheets**, **SQLite** or a plain
**CSV** file. The database can be imported into Google My Maps.

The in-game list of gyms is capped at the 1,000 most recent. This tool keeps
a permanent record beyond that cap.

:::{note}
Only iPhone screenshots are supported (three screen sizes so far, see
[](how-it-works.md)). The tool is for personal use.
:::

```{toctree}
:maxdepth: 2
:caption: Getting started

installation
quickstart
configuration
```

```{toctree}
:maxdepth: 2
:caption: Using it

workflow
database
google-sheets
cli
troubleshooting
```

```{toctree}
:maxdepth: 2
:caption: Background

how-it-works
migrating-from-v1
```

```{toctree}
:maxdepth: 2
:caption: Project

contributing
api
changelog
```
