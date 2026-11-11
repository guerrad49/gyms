import os
from pathlib import Path

import pytest

from PokemonGo.discovery import discover
from PokemonGo.errors import ConfigError


def _touch(path: Path, mtime: int | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"png")
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


def test_a_folder_is_read_oldest_first_then_by_name(tmp_path: Path) -> None:
    _touch(tmp_path / "b.PNG", 100)
    _touch(tmp_path / "a.PNG", 200)
    _touch(tmp_path / "c.PNG", 100)
    names = [p.name for p in discover([tmp_path], tmp_path)]
    assert names == ["b.PNG", "c.PNG", "a.PNG"]


def test_png_is_matched_ignoring_case(tmp_path: Path) -> None:
    for name in ("a.PNG", "b.png", "c.Png"):
        _touch(tmp_path / name)
    assert len(discover([tmp_path], tmp_path)) == 3


def test_other_files_and_resource_forks_are_ignored(tmp_path: Path) -> None:
    _touch(tmp_path / "real.PNG")
    _touch(tmp_path / "photo.jpg")
    _touch(tmp_path / "notes.txt")
    _touch(tmp_path / "._real.PNG")  # macOS resource fork
    (tmp_path / "folder.PNG").mkdir()  # a folder that looks like a file
    assert [p.name for p in discover([tmp_path], tmp_path)] == ["real.PNG"]


def test_subfolders_are_only_searched_on_request(tmp_path: Path) -> None:
    _touch(tmp_path / "top.PNG", 100)
    _touch(tmp_path / "sub" / "deep.PNG", 200)
    assert [p.name for p in discover([tmp_path], tmp_path)] == ["top.PNG"]
    deep = discover([tmp_path], tmp_path, recursive=True)
    assert [p.name for p in deep] == ["top.PNG", "deep.PNG"]


def test_explicit_files_keep_the_order_given(tmp_path: Path) -> None:
    b = _touch(tmp_path / "b.PNG", 100)
    a = _touch(tmp_path / "a.PNG", 200)
    assert discover([a, b], tmp_path) == [a, b]
    assert discover([b, a], tmp_path) == [b, a]


def test_files_and_folders_can_be_mixed(tmp_path: Path) -> None:
    folder = tmp_path / "folder"
    inside = _touch(folder / "in.PNG", 100)
    alone = _touch(tmp_path / "alone.PNG")
    assert discover([alone, folder], tmp_path) == [alone, inside]


def test_the_same_file_is_never_returned_twice(tmp_path: Path) -> None:
    shot = _touch(tmp_path / "shot.PNG")
    assert discover([shot, shot, tmp_path], tmp_path) == [shot]


def test_one_file_under_two_names_counts_once(tmp_path: Path) -> None:
    """On macOS IMG.png and IMG.PNG are one file; a hard link is the same."""
    first = _touch(tmp_path / "IMG_1.PNG")
    link = tmp_path / "also.png"
    os.link(first, link)
    assert len(discover([first, link], tmp_path)) == 1
    assert len(discover([tmp_path], tmp_path)) == 1


def test_the_default_folder_is_used_when_no_path_is_given(
    tmp_path: Path,
) -> None:
    shot = _touch(tmp_path / "x.PNG")
    assert discover([], tmp_path) == [shot]


def test_an_empty_folder_gives_an_empty_list(tmp_path: Path) -> None:
    assert discover([tmp_path], tmp_path) == []


def test_a_missing_path_is_an_error_before_anything_else(
    tmp_path: Path,
) -> None:
    good = _touch(tmp_path / "good.PNG")
    with pytest.raises(ConfigError, match="path not found"):
        discover([good, tmp_path / "nope.PNG"], tmp_path)


def test_a_named_file_must_be_a_png(tmp_path: Path) -> None:
    photo = _touch(tmp_path / "photo.jpg")
    with pytest.raises(ConfigError, match="only PNG screenshots"):
        discover([photo], tmp_path)


def test_a_home_folder_shortcut_is_expanded(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    shot = _touch(tmp_path / "Downloads" / "x.PNG")
    assert discover([Path("~/Downloads")], tmp_path) == [shot]
