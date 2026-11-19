import pytest

import PokemonGo
from PokemonGo.cli import build_parser, main


def test_version_is_a_non_empty_string() -> None:
    assert isinstance(PokemonGo.__version__, str)
    assert PokemonGo.__version__


def test_version_flag_prints_the_version(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exit_info:
        main(["--version"])
    assert exit_info.value.code == 0
    assert PokemonGo.__version__ in capsys.readouterr().out


def test_no_arguments_prints_help(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main([]) == 0
    assert "usage: pogo" in capsys.readouterr().out


def test_parser_program_name() -> None:
    assert build_parser().prog == "pogo"
