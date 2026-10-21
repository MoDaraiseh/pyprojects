import os

import pytest

import organize


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_recursive_sort_never_overwrites_same_named_files(tmp_path):
    _write(tmp_path / "trip1" / "IMG_0001.jpg", "trip 1")
    _write(tmp_path / "trip2" / "IMG_0001.jpg", "trip 2")
    organize.sort_folder(tmp_path, by_date=False, dry_run=False, recursive=True)
    images = sorted(p.read_text(encoding="utf-8") for p in (tmp_path / "Images").iterdir())
    assert images == ["trip 1", "trip 2"]
    assert (tmp_path / "Images" / "IMG_0001 (1).jpg").exists()


def test_dry_run_moves_nothing_and_plans_distinct_names(tmp_path, capsys):
    _write(tmp_path / "a" / "x.pdf", "1")
    _write(tmp_path / "b" / "x.pdf", "2")
    organize.sort_folder(tmp_path, by_date=False, dry_run=True, recursive=True)
    out = capsys.readouterr().out
    assert "x (1).pdf" in out and "Would move 2 file(s)" in out
    assert not (tmp_path / "Documents").exists()


def test_sort_skips_files_already_in_category_folders(tmp_path, capsys):
    _write(tmp_path / "Images" / "done.jpg", "x")
    _write(tmp_path / "new.jpg", "y")
    organize.sort_folder(tmp_path, by_date=False, dry_run=False, recursive=True)
    assert sorted(p.name for p in (tmp_path / "Images").iterdir()) == ["done.jpg", "new.jpg"]
    organize.sort_folder(tmp_path, by_date=False, dry_run=False, recursive=True)
    assert "already tidy" in capsys.readouterr().out


def test_unique_destination_respects_claimed(tmp_path):
    dest = tmp_path / "Images" / "a.jpg"
    claimed = {organize._key(dest)}
    assert organize.unique_destination(dest, claimed).name == "a (1).jpg"


def test_dupes_delete_keeps_first_copy(tmp_path):
    _write(tmp_path / "a.txt", "same")
    _write(tmp_path / "b.txt", "same")
    _write(tmp_path / "c.txt", "different")
    organize.find_duplicates(tmp_path, delete=True, dry_run=False)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["a.txt", "c.txt"]


def test_dupes_ignores_symlinks_so_real_file_survives(tmp_path):
    real = tmp_path / "z_real.jpg"
    _write(real, "only copy")
    link = tmp_path / "a_link.jpg"  # sorts first: would have been "kept"
    try:
        os.symlink(real, link)
    except (OSError, NotImplementedError):
        pytest.skip("symlinks not permitted here")
    organize.find_duplicates(tmp_path, delete=True, dry_run=False)
    assert real.read_text(encoding="utf-8") == "only copy"
