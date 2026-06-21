"""
Repo walker — recursively finds all Python source files in a directory.

Skips common non-source directories so we never ingest compiled bytecode,
virtual environments, or version control internals.
"""

from pathlib import Path

SKIP_DIRS = {
    "__pycache__",
    ".venv",
    "venv",
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    "node_modules",
    "dist",
    "build",
    ".eggs",
}


def walk_repo(repo_path: str) -> list[str]:
    """
    Recursively walk a directory and return paths of all .py files found.
    Directories in SKIP_DIRS are ignored at every level of the tree.

    input:
        repo_path: Path to the root directory to walk.
    output:
        Sorted list of .py file path strings relative to where the program runs.
    """
    root = Path(repo_path)

    if not root.exists():
        raise ValueError(f"Repo path does not exist: {repo_path}")
    if not root.is_dir():
        raise ValueError(f"Repo path is not a directory: {repo_path}")

    py_files = []
    for path in root.rglob("*.py"):
        if not any(skip in path.parts for skip in SKIP_DIRS):
            py_files.append(str(path))

    return sorted(py_files)
