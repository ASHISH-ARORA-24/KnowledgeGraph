"""
Unit tests for src/crawlers/repo_walker.py

Uses tmp_path to create controlled temporary directory trees so tests
never depend on the real project files.
"""

import pytest
from src.crawlers.repo_walker import walk_repo, SKIP_DIRS


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_walk_repo_finds_py_files(tmp_path):
    (tmp_path / "module.py").write_text("x = 1")
    result = walk_repo(str(tmp_path))
    assert str(tmp_path / "module.py") in result


def test_walk_repo_finds_multiple_py_files(tmp_path):
    for name in ["a.py", "b.py", "c.py"]:
        (tmp_path / name).write_text("")
    result = walk_repo(str(tmp_path))
    assert len(result) == 3


def test_walk_repo_finds_files_in_subdirectories(tmp_path):
    sub = tmp_path / "subpackage"
    sub.mkdir()
    (sub / "module.py").write_text("")
    result = walk_repo(str(tmp_path))
    assert str(sub / "module.py") in result


def test_walk_repo_returns_sorted_paths(tmp_path):
    for name in ["c.py", "a.py", "b.py"]:
        (tmp_path / name).write_text("")
    result = walk_repo(str(tmp_path))
    assert result == sorted(result)


def test_walk_repo_ignores_non_py_files(tmp_path):
    (tmp_path / "module.py").write_text("")
    (tmp_path / "readme.md").write_text("")
    (tmp_path / "data.json").write_text("")
    result = walk_repo(str(tmp_path))
    assert len(result) == 1
    assert result[0].endswith(".py")


def test_walk_repo_returns_empty_list_for_empty_directory(tmp_path):
    assert walk_repo(str(tmp_path)) == []


# ---------------------------------------------------------------------------
# Skip directories
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("skip_dir", list(SKIP_DIRS))
def test_walk_repo_skips_known_directories(tmp_path, skip_dir):
    skipped = tmp_path / skip_dir
    skipped.mkdir()
    (skipped / "hidden.py").write_text("")
    result = walk_repo(str(tmp_path))
    assert result == []


def test_walk_repo_skips_pycache_but_finds_sibling_py(tmp_path):
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "compiled.py").write_text("")
    (tmp_path / "real.py").write_text("")
    result = walk_repo(str(tmp_path))
    assert len(result) == 1
    assert result[0].endswith("real.py")


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------

def test_walk_repo_raises_for_nonexistent_path():
    with pytest.raises(ValueError, match="does not exist"):
        walk_repo("/nonexistent/path/to/repo")


def test_walk_repo_raises_when_path_is_a_file(tmp_path):
    f = tmp_path / "file.py"
    f.write_text("")
    with pytest.raises(ValueError, match="not a directory"):
        walk_repo(str(f))
