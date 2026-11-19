"""The interface every storage backend implements."""

from __future__ import annotations

from typing import Protocol

from PokemonGo.models import Gym


class GymStore(Protocol):
    """A gym database: Google Sheets, SQLite, or a CSV file.

    Changes are kept in memory (or in an open transaction) until
    :meth:`commit`; closing without committing discards them.

    Each :class:`~PokemonGo.models.Gym` returned by :meth:`all` carries a
    ``row``. Pass the same gym back to :meth:`update` to change it in
    place, whether or not it has a ``uid`` yet. Rows are only valid until
    :meth:`sort`; call :meth:`all` again afterwards.
    """

    def all(self) -> list[Gym]:
        """Return every gym, seeded or scanned.

        Returns
        -------
        list of Gym
            In storage order, each with ``row`` set.

        Raises
        ------
        StoreError
            If a row cannot be read; the message names the row.
        """

    def add(self, gym: Gym) -> None:
        """Append a gym and set its ``row``.

        Parameters
        ----------
        gym : Gym
            The gym to add.

        Raises
        ------
        StoreError
            If its ``uid`` is already taken.
        """

    def update(self, gym: Gym) -> None:
        """Overwrite the stored gym at ``gym.row``.

        Parameters
        ----------
        gym : Gym
            A gym previously returned by :meth:`all` or :meth:`add`.

        Raises
        ------
        StoreError
            If ``gym.row`` is unset or does not exist, or the new ``uid``
            belongs to another gym.
        """

    def sort(self) -> None:
        """Order the gyms by state, county, city and title.

        Case is ignored and blank values come last. Invalidates the
        ``row`` of gyms obtained earlier.
        """

    def commit(self) -> None:
        """Save every change made since the last commit."""

    def close(self) -> None:
        """Release the database. Uncommitted changes are discarded."""
