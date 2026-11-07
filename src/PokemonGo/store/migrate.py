"""Copy a database from one backend to another."""

from __future__ import annotations

from dataclasses import replace

from PokemonGo.errors import StoreError
from PokemonGo.store.base import GymStore


def copy_gyms(source: GymStore, target: GymStore) -> int:
    """Copy every gym, seeded or scanned, into an empty database.

    The target is committed before returning.

    Parameters
    ----------
    source : GymStore
        The database to read.
    target : GymStore
        The database to fill. It must be empty, so a migration can never
        mix two databases or overwrite one.

    Returns
    -------
    int
        The number of gyms copied.

    Raises
    ------
    StoreError
        If the target already holds gyms.
    """
    if target.all():
        msg = "the target database is not empty; refusing to mix databases"
        raise StoreError(msg)
    count = 0
    for gym in source.all():
        target.add(replace(gym, row=None))
        count += 1
    target.commit()
    return count
