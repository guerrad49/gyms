import logging

import pytest

from PokemonGo.prompts import NonInteractivePrompter, TerminalPrompter


class Terminal:
    """Feeds scripted answers to a TerminalPrompter and records its output."""

    def __init__(self, *answers: str | type[EOFError]) -> None:
        self.answers = list(answers)
        self.prompts: list[str] = []
        self.printed: list[str] = []
        self.prompter = TerminalPrompter(self._input, self.printed.append)

    def _input(self, prompt: str) -> str:
        self.prompts.append(prompt)
        answer = self.answers.pop(0)
        if isinstance(answer, type):
            raise answer
        return answer


def test_unattended_answers_nothing(caplog: pytest.LogCaptureFixture) -> None:
    prompter = NonInteractivePrompter()
    with caplog.at_level(logging.INFO):
        assert prompter.interactive is False
        assert prompter.ask("title?", "x") is None
        assert prompter.confirm("sure?", default=True) is False
        assert prompter.choose("which?", ["a", "b"]) is None
        prompter.say("fyi")
    assert "title?" in caplog.text
    assert "which?" in caplog.text
    assert "fyi" in caplog.text


def test_ask_returns_the_answer_or_the_default() -> None:
    term = Terminal("  typed  ", "")
    assert term.prompter.ask("Title?", "default") == "typed"
    assert term.prompter.ask("Title?", "default") == "default"
    assert term.prompts[0] == "Title? [default] "


def test_ask_without_a_default_shows_no_brackets() -> None:
    term = Terminal("")
    assert term.prompter.ask("City?") == ""
    assert term.prompts == ["City? "]


def test_ask_gives_none_when_the_input_ends() -> None:
    assert Terminal(EOFError).prompter.ask("Title?") is None


@pytest.mark.parametrize(
    ("answer", "expected"),
    [("y", True), ("YES", True), ("n", False), ("No", False)],
)
def test_confirm_understands_yes_and_no(answer: str, expected: bool) -> None:
    assert Terminal(answer).prompter.confirm("ok?") is expected


def test_confirm_uses_the_default_for_enter() -> None:
    assert Terminal("").prompter.confirm("ok?", default=True) is True
    assert Terminal("").prompter.confirm("ok?", default=False) is False
    assert Terminal("").prompts == []
    term = Terminal("")
    term.prompter.confirm("ok?", default=True)
    assert term.prompts == ["ok? [Y/n] "]


def test_confirm_asks_again_until_clear() -> None:
    term = Terminal("maybe", "y")
    assert term.prompter.confirm("ok?") is True
    assert term.printed == ["Please answer y or n."]


def test_confirm_is_no_when_the_input_ends() -> None:
    assert Terminal(EOFError).prompter.confirm("ok?", default=True) is False


def test_choose_lists_the_options_and_returns_an_index() -> None:
    term = Terminal("2")
    assert term.prompter.choose("Which?", ["first", "second"]) == 1
    assert term.printed == ["Which?", "  1. first", "  2. second"]


@pytest.mark.parametrize("answer", ["", EOFError])
def test_choose_can_be_declined(answer: str | type[EOFError]) -> None:
    assert Terminal(answer).prompter.choose("Which?", ["a"]) is None


def test_choose_rejects_bad_numbers() -> None:
    term = Terminal("0", "3", "abc", "1")
    assert term.prompter.choose("Which?", ["a", "b"]) == 0
    assert term.printed.count("Please enter a number from 1 to 2.") == 3


def test_say_prints() -> None:
    term = Terminal()
    term.prompter.say("hello")
    assert term.printed == ["hello"]
