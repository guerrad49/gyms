"""Asking the person questions, without the rest of the code knowing how.

Only the command line talks to a terminal. Everything else receives a
:class:`Prompter`, so the same pipeline can run with a person
(:class:`TerminalPrompter`), unattended (:class:`NonInteractivePrompter`),
or scripted in a test.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import Protocol

logger = logging.getLogger(__name__)


class Prompter(Protocol):
    """How the pipeline asks questions and shows messages."""

    @property
    def interactive(self) -> bool:
        """Whether a person is answering.

        When ``False`` the pipeline applies its unattended rules instead
        of asking.
        """

    def say(self, message: str) -> None:
        """Show a message that needs no answer."""

    def ask(self, message: str, default: str = "") -> str | None:
        """Ask for a line of text.

        Parameters
        ----------
        message : str
            The question.
        default : str, optional
            What an empty answer means.

        Returns
        -------
        str or None
            The answer, or ``default`` if it was empty. ``None`` means no
            answer is possible (unattended, or the input ended).
        """

    def confirm(self, message: str, default: bool = False) -> bool:
        """Ask a yes/no question; ``default`` is what Enter means."""

    def choose(self, message: str, options: Sequence[str]) -> int | None:
        """Ask the person to pick one of several options.

        Returns
        -------
        int or None
            The zero-based index of the chosen option, or ``None`` if
            they declined to choose.
        """


class NonInteractivePrompter:
    """Answers every question with "no answer", and logs what it was asked.

    This is how unattended runs work: the pipeline sees ``None`` and
    ``False`` and falls back to its automatic rules.
    """

    interactive = False

    def say(self, message: str) -> None:
        """Log the message at info level."""
        logger.info(message)

    def ask(self, message: str, default: str = "") -> str | None:
        """Decline to answer."""
        logger.info("needs an answer (skipped): %s", message)
        return None

    def confirm(self, message: str, default: bool = False) -> bool:
        """Answer no."""
        logger.info("needs a decision (declined): %s", message)
        return False

    def choose(self, message: str, options: Sequence[str]) -> int | None:
        """Decline to choose."""
        logger.info("needs a choice (skipped): %s", message)
        return None


class TerminalPrompter:
    """Asks questions on the terminal.

    Parameters
    ----------
    input_fn : callable, optional
        Reads a line; injectable for tests. Defaults to ``input``,
        looked up each time so it can be replaced.
    print_fn : callable, optional
        Shows a line; injectable for tests. Defaults to ``print``.
    """

    interactive = True

    def __init__(
        self,
        input_fn: Callable[[str], str] | None = None,
        print_fn: Callable[[str], None] = print,
    ) -> None:
        self._input = input_fn
        self._print = print_fn

    def say(self, message: str) -> None:
        """Print a message."""
        self._print(message)

    def _read(self, prompt: str) -> str | None:
        try:
            return (self._input or input)(prompt).strip()
        except EOFError:
            return None

    def ask(self, message: str, default: str = "") -> str | None:
        """Ask for text; an empty answer gives ``default``."""
        shown = f"{message} [{default}] " if default else f"{message} "
        answer = self._read(shown)
        if answer is None:
            return None
        return answer or default

    def confirm(self, message: str, default: bool = False) -> bool:
        """Ask y or n until the answer is clear; Enter gives ``default``."""
        hint = "[Y/n]" if default else "[y/N]"
        while True:
            answer = self._read(f"{message} {hint} ")
            if answer is None:
                return False
            if not answer:
                return default
            if answer.lower() in {"y", "yes"}:
                return True
            if answer.lower() in {"n", "no"}:
                return False
            self._print("Please answer y or n.")

    def choose(self, message: str, options: Sequence[str]) -> int | None:
        """List the options and ask for a number; Enter declines."""
        self._print(message)
        for number, option in enumerate(options, start=1):
            self._print(f"  {number}. {option}")
        while True:
            answer = self._read(f"Number (1-{len(options)}, Enter to skip): ")
            if not answer:
                return None
            if answer.isdigit() and 1 <= int(answer) <= len(options):
                return int(answer) - 1
            self._print(f"Please enter a number from 1 to {len(options)}.")
