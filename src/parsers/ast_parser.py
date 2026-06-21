"""
AST Parser — extracts structured CodeNodes from a Python source file.

Uses Python's built-in `ast` module. No external dependencies.
Extracts: module, classes, functions/methods, docstrings, line numbers.
"""

import ast
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class CodeNode:
    """A single extracted unit from a Python file."""
    node_id: str
    team_id: str
    type: str          # MODULE | CLASS | FUNCTION
    name: str
    file_path: str
    line_start: int
    line_end: int
    docstring: str
    raw_source: str
    parent_name: Optional[str] = None   # class name for methods


def _make_id(team_id: str, file_path: str, node_type: str, name: str) -> str:
    """Generate a stable MD5 node ID from team, file path, node type, and name."""
    key = f"{team_id}::{file_path}::{node_type}::{name}"
    return hashlib.md5(key.encode()).hexdigest()


def _get_source_segment(source_lines: list[str], start: int, end: int) -> str:
    """Extract source lines from start to end (1-indexed, both inclusive)."""
    return "".join(source_lines[start - 1 : end])


def parse_file(file_path: str, team_id: str) -> list[CodeNode]:
    """
    Parse a single Python file and return a list of CodeNodes.
    One node per: module, class, top-level function, method.
    """
    path = Path(file_path)
    source = path.read_text(encoding="utf-8")
    source_lines = source.splitlines(keepends=True)

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        raise ValueError(f"Cannot parse {file_path}: {e}") from e

    nodes: list[CodeNode] = []

    # Module-level node — represents the whole file
    module_docstring = ast.get_docstring(tree) or ""
    module_node = CodeNode(
        node_id=_make_id(team_id, file_path, "MODULE", path.stem),
        team_id=team_id,
        type="MODULE",
        name=path.stem,
        file_path=file_path,
        line_start=1,
        line_end=len(source_lines),
        docstring=module_docstring,
        raw_source=source[:500],  # first 500 chars as summary
    )
    nodes.append(module_node)

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_docstring = ast.get_docstring(node) or ""
            end_line = max(
                getattr(child, "end_lineno", node.lineno)
                for child in ast.walk(node)
            )
            class_node = CodeNode(
                node_id=_make_id(team_id, file_path, "CLASS", node.name),
                team_id=team_id,
                type="CLASS",
                name=node.name,
                file_path=file_path,
                line_start=node.lineno,
                line_end=end_line,
                docstring=class_docstring,
                raw_source=_get_source_segment(source_lines, node.lineno, end_line),
            )
            nodes.append(class_node)

            # Methods inside this class
            for item in node.body:
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    method_docstring = ast.get_docstring(item) or ""
                    method_end = max(
                        getattr(child, "end_lineno", item.lineno)
                        for child in ast.walk(item)
                    )
                    method_node = CodeNode(
                        node_id=_make_id(
                            team_id, file_path, "FUNCTION",
                            f"{node.name}.{item.name}"
                        ),
                        team_id=team_id,
                        type="FUNCTION",
                        name=f"{node.name}.{item.name}",
                        file_path=file_path,
                        line_start=item.lineno,
                        line_end=method_end,
                        docstring=method_docstring,
                        raw_source=_get_source_segment(
                            source_lines, item.lineno, method_end
                        ),
                        parent_name=node.name,
                    )
                    nodes.append(method_node)

        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Only top-level functions (not methods — those are handled above)
            if not any(
                isinstance(parent, ast.ClassDef)
                for parent in ast.walk(tree)
                if node in ast.walk(parent) and parent is not node
            ):
                func_docstring = ast.get_docstring(node) or ""
                func_end = max(
                    getattr(child, "end_lineno", node.lineno)
                    for child in ast.walk(node)
                )
                func_node = CodeNode(
                    node_id=_make_id(team_id, file_path, "FUNCTION", node.name),
                    team_id=team_id,
                    type="FUNCTION",
                    name=node.name,
                    file_path=file_path,
                    line_start=node.lineno,
                    line_end=func_end,
                    docstring=func_docstring,
                    raw_source=_get_source_segment(
                        source_lines, node.lineno, func_end
                    ),
                )
                nodes.append(func_node)

    return nodes
