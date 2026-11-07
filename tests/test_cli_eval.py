from pathlib import Path

import pytest

from PokemonGo.cli import main
from tests.support.expected import IMAGES_DIR, write_truth_csv


def test_eval_requires_its_options() -> None:
    with pytest.raises(SystemExit) as info:
        main(["eval"])
    assert info.value.code == 2


def test_eval_rejects_an_unknown_model(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as info:
        main(
            ["eval", "--badges", str(tmp_path), "--truth", "x", "--model", "i1"]
        )
    assert info.value.code == 2


def test_eval_reports_a_missing_badges_folder(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    status = main(["eval", "--badges", str(tmp_path / "nope"), "--truth", "x"])
    assert status == 1
    assert "badges folder not found" in capsys.readouterr().err


def test_eval_reports_a_bad_truth_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    truth = tmp_path / "truth.csv"
    truth.write_text("uid,title\n1,x\n", encoding="utf-8")
    status = main(["eval", "--badges", str(tmp_path), "--truth", str(truth)])
    assert status == 1
    assert "missing column" in capsys.readouterr().err


@pytest.mark.ocr
def test_eval_runs_end_to_end(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    problems = tmp_path / "problems.csv"
    status = main(
        [
            "eval",
            "--badges",
            str(IMAGES_DIR),
            "--truth",
            str(write_truth_csv(tmp_path / "truth.csv")),
            "--jobs",
            "2",
            "--problems",
            str(problems),
            "--near-misses",
            str(tmp_path / "near.csv"),
        ]
    )
    captured = capsys.readouterr()
    assert status == 0
    assert "Screenshots checked: 6 (0 unreadable or missing)" in captured.out
    assert "would need manual input" in captured.out
    assert "Wrote 0 problem row(s)" in captured.out
    assert "Wrote 0 near-miss row(s)" in captured.out
    assert "close but not exact       0 rows" in captured.out
    assert "6/6" in captured.err


@pytest.mark.ocr
def test_eval_honors_limit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    status = main(
        [
            "eval",
            "--badges",
            str(IMAGES_DIR),
            "--truth",
            str(write_truth_csv(tmp_path / "truth.csv")),
            "--limit",
            "2",
            "--model",
            "i15",
        ]
    )
    assert status == 0
    assert "Screenshots checked: 2" in capsys.readouterr().out
