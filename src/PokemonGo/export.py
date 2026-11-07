"""Export gyms for Google My Maps.

My Maps imports a CSV (or a sheet) and asks which columns hold the
position and the title. A file with separate numeric ``latitude`` and
``longitude`` columns is the easiest for it to read.
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from pathlib import Path
from typing import Final

from PokemonGo.models import Gym

MY_MAPS_COLUMNS: Final = (
    "title",
    "latitude",
    "longitude",
    "style",
    "days",
    "defended",
    "victories",
    "treats",
    "city",
    "county",
    "state",
    "country",
)
"""The columns of the My Maps export, position first."""


def write_my_maps_csv(
    gyms: Iterable[Gym], path: Path, *, include_seeded: bool = False
) -> int:
    """Write a CSV that Google My Maps can import.

    Parameters
    ----------
    gyms : iterable of Gym
        The gyms to export.
    path : pathlib.Path
        The CSV to create.
    include_seeded : bool, optional
        Also export gyms that were never scanned. By default only
        scanned gyms are written.

    Returns
    -------
    int
        The number of gyms written. Gyms without coordinates cannot be
        placed on a map and are skipped.
    """
    count = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(MY_MAPS_COLUMNS)
        for gym in gyms:
            if gym.coordinates is None:
                continue
            if gym.is_seeded and not include_seeded:
                continue
            activity = gym.activity
            writer.writerow(
                [
                    gym.title,
                    gym.coordinates.latitude,
                    gym.coordinates.longitude,
                    "" if activity is None else activity.style.value,
                    "" if activity is None else activity.days,
                    "" if activity is None else activity.defended,
                    "" if activity is None else activity.victories,
                    "" if activity is None else activity.treats,
                    gym.city,
                    gym.county,
                    gym.state,
                    gym.country,
                ]
            )
            count += 1
    return count
