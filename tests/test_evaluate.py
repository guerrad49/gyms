import csv
from pathlib import Path

import pytest

from PokemonGo.errors import ConfigError, ParseError
from PokemonGo.evaluate import (
    EvalReport,
    RowResult,
    TruthRow,
    evaluate,
    find_image,
    format_report,
    load_truth,
    write_problems,
)
from PokemonGo.models import Activity
from PokemonGo.vision.reader import BadgeReader
from tests.support.engines import ScriptedEngine, lines, result
from tests.support.expected import ALL, IMAGES_DIR, write_truth_csv

HEADER = "uid,title,victories,days,hours,minutes,treats"


def _csv(tmp_path: Path, *rows: str, header: str = HEADER) -> Path:
    path = tmp_path / "truth.csv"
    path.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")
    return path


def test_load_truth_reads_rows_and_normalizes_titles(tmp_path: Path) -> None:
    path = _csv(
        tmp_path,
        "1,Starbucks ,448,23,6,16,121",
        ",seeded but never scanned,0,0,0,0,0",
        "2,portland head light,0,21,18,7,104",
    )
    assert load_truth(path) == [
        TruthRow(1, "starbucks", Activity(448, 23, 6, 16, 121)),
        TruthRow(2, "portland head light", Activity(0, 21, 18, 7, 104)),
    ]


def test_load_truth_ignores_extra_columns_and_a_bom(tmp_path: Path) -> None:
    path = tmp_path / "export.csv"
    path.write_text(
        "\ufeff,uid,title,victories,days,hours,minutes,treats,city\n"
        "0,5,x,1,2,3,4,5,somewhere\n",
        encoding="utf-8",
    )
    assert load_truth(path)[0].uid == 5


def test_load_truth_requires_the_columns(tmp_path: Path) -> None:
    path = _csv(tmp_path, "1,x,1", header="uid,title,victories")
    with pytest.raises(ParseError, match=r"missing column.*days"):
        load_truth(path)


@pytest.mark.parametrize(
    "row", ["1,x,abc,2,3,4,5", "1,x,1,2,30,4,5", "1,x,-1,2,3,4,5"]
)
def test_load_truth_reports_bad_values_with_the_line(
    tmp_path: Path, row: str
) -> None:
    with pytest.raises(ParseError, match=r"truth\.csv line 2"):
        load_truth(_csv(tmp_path, row))


def test_load_truth_needs_an_existing_file(tmp_path: Path) -> None:
    with pytest.raises(ConfigError, match="truth file not found"):
        load_truth(tmp_path / "nope.csv")


def test_find_image_accepts_either_extension_case(tmp_path: Path) -> None:
    on_disk = {7: "IMG_0007.PNG", 8: "IMG_0008.png"}
    for name in on_disk.values():
        (tmp_path / name).touch()
    # Compare files, not spellings: macOS filesystems ignore case, so the
    # path found may be spelled differently from the name on disk.
    for uid, name in on_disk.items():
        found = find_image(tmp_path, uid)
        assert found is not None
        assert found.samefile(tmp_path / name)
    assert find_image(tmp_path, 9) is None


def test_evaluate_compares_readings_with_the_truth() -> None:
    truth = [
        TruthRow(1, "starbucks", Activity(448, 23, 6, 16, 121)),
        TruthRow(2, "portland head light", Activity(0, 21, 18, 7, 104)),
        TruthRow(99, "no screenshot", Activity(1, 1, 1, 1, 1)),
    ]
    good = ("victories", "448 23d 6h 16m 121")
    flawed = ("victories", "0 21d 18h 7m 105")  # treats read wrong
    script = [
        result(("Starbucks", 96)),
        result(),
        result(),
        result(),
        lines(*good),
        result(("Portland", 90), ("Head", 90), ("Ligt", 80)),
        result(),
        result(),
        result(),
        lines(*flawed),
    ]
    seen: list[tuple[int, int]] = []
    report = evaluate(
        BadgeReader(ScriptedEngine(script)),
        IMAGES_DIR,
        truth,
        progress=lambda done, total: seen.append((done, total)),
    )
    first, second, missing = report.rows
    assert first.title_exact
    assert first.all_stats_ok
    assert not first.needs_help
    assert not second.title_exact  # "ligt"
    assert second.title_close  # but close enough for a confirmation prompt
    assert second.title_reachable
    assert second.stats_ok is not None
    assert second.stats_ok["treats"] is False
    assert second.stats_ok["victories"] is True
    assert second.needs_help
    assert missing.error == "image not found"
    assert missing.needs_help
    assert seen == [(1, 3), (2, 3), (3, 3)]
    assert len(report.readable) == 2
    assert report.rate(lambda r: r.title_exact) == 0.5
    assert report.help_rate == pytest.approx(2 / 3)


def test_evaluate_reports_an_unreadable_screenshot(tmp_path: Path) -> None:
    (tmp_path / "IMG_0001.PNG").write_text("junk", encoding="utf-8")
    truth = [TruthRow(1, "x", Activity(1, 1, 1, 1, 1))]
    report = evaluate(BadgeReader(ScriptedEngine([])), tmp_path, truth)
    assert "not a readable image" in report.rows[0].error
    assert report.readable == ()
    assert report.rate(lambda r: r.title_exact) == 0.0


def test_an_empty_report_has_zero_rates() -> None:
    report = EvalReport(())
    assert report.help_rate == 0.0
    assert report.rate(lambda r: True) == 0.0


def _report_with_problems() -> EvalReport:
    return EvalReport(
        (
            RowResult(1, "a", "a", True, True, True, {"treats": True}, True),
            RowResult(
                2,
                "portland",
                "xyz",
                False,
                False,
                False,
                {"victories": True, "treats": False},
                False,
            ),
            RowResult(3, "gone", error="image not found"),
        )
    )


def test_format_report_lists_rates_and_problems() -> None:
    text = format_report(_report_with_problems())
    assert "Screenshots checked: 3 (1 unreadable or missing)" in text
    assert "exact match" in text
    assert "would need manual input" in text
    assert "read 'xyz' expected 'portland' stats: treats" in text
    assert "3  image not found" in text.replace("    ", " ")


def test_format_report_limits_the_listed_problems() -> None:
    text = format_report(_report_with_problems(), show=1)
    assert "showing 1" in text
    assert "image not found" not in text


def test_write_problems_creates_a_csv(tmp_path: Path) -> None:
    path = tmp_path / "problems.csv"
    assert write_problems(_report_with_problems(), path) == 2
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0] == {
        "uid": "2",
        "expected_title": "portland",
        "read_title": "xyz",
        "problem": "title,treats",
    }
    assert rows[1]["problem"] == "image not found"


@pytest.mark.ocr
@pytest.mark.parametrize("jobs", [1, 3])
def test_the_reference_screenshots_score_perfectly(
    tmp_path: Path, jobs: int
) -> None:
    truth = load_truth(write_truth_csv(tmp_path / "truth.csv"))
    report = evaluate(BadgeReader(), IMAGES_DIR, truth, jobs=jobs)
    assert len(report.rows) == len(ALL)
    assert report.rate(lambda r: r.title_exact) == 1.0
    assert report.rate(lambda r: r.all_stats_ok) == 1.0
    assert report.help_rate == 0.0
