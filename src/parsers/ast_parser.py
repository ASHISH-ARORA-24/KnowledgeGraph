"""
AST Parser — extracts structured CodeNodes and Edges from a Python source file.

Uses Python's built-in `ast` module. No external dependencies.
Extracts: module, classes, functions/methods, docstrings, line numbers.
Extracts: IMPORTS, CALLS, DEFINED_IN, BELONGS_TO, INHERITS relationships.
"""

import ast
import hashlib
from dataclasses import dataclass
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


@dataclass
class Edge:
    """A directed relationship between two CodeNodes."""
    from_node_id: str
    to_node_id: str
    relation_type: str  # IMPORTS | CALLS | DEFINED_IN | BELONGS_TO | INHERITS
    team_id: str


def _make_id(team_id: str, file_path: str, node_type: str, name: str) -> str:
    """Generate a stable MD5 node ID from team, file path, node type, and name."""
    key = f"{team_id}::{file_path}::{node_type}::{name}"
    return hashlib.md5(key.encode()).hexdigest()


def _get_source_segment(source_lines: list[str], start: int, end: int) -> str:
    """Extract source lines from start to end (1-indexed, both inclusive)."""
    return "".join(source_lines[start - 1 : end])


def _resolve_import_path(source_file: str, module: str, level: int) -> Optional[str]:
    """
    Resolve a relative import to an absolute file path.
    Returns None for absolute imports (stdlib / third-party) or unresolvable paths.

    input:
        source_file: Path of the file containing the import statement.
        module:      The module name from the import (e.g. "constants").
        level:       Dot level — 1 for "from .x", 2 for "from ..x", 0 for absolute.
    output:
        Resolved file path string if the file exists, otherwise None.
    """
    if level == 0:
        return None  # absolute import — stdlib or third-party, skip

    base = Path(source_file).parent
    for _ in range(level - 1):
        base = base.parent

    if module:
        parts = module.split(".")
        candidate = base.joinpath(*parts).with_suffix(".py")
        if candidate.exists():
            return str(candidate)

    return None


def _extract_call_name(call_node: ast.Call) -> Optional[str]:
    """Extract the bare function name from a Call AST node."""
    if isinstance(call_node.func, ast.Name):
        return call_node.func.id
    if isinstance(call_node.func, ast.Attribute):
        return call_node.func.attr
    return None


def _extract_edges(
    tree: ast.AST,
    source_file: str,
    team_id: str,
    nodes: list[CodeNode],
) -> list[Edge]:
    """
    Extract all edges from a parsed AST using the already-extracted nodes as a registry.
    Produces DEFINED_IN, BELONGS_TO, IMPORTS, INHERITS, and CALLS edges.
    Skips edges where the target node cannot be resolved.

    input:
        tree:        The parsed AST for the file.
        source_file: Path of the source file being parsed.
        team_id:     Team ID for isolation tagging.
        nodes:       CodeNodes already extracted from the same file.
    output:
        Deduplicated list of Edge objects found in the file.
    """
    edges: list[Edge] = []
    seen: set[tuple] = set()

    def add_edge(from_id: str, to_id: str, rel_type: str) -> None:
        key = (from_id, to_id, rel_type)
        if key not in seen:
            seen.add(key)
            edges.append(Edge(from_id, to_id, rel_type, team_id))

    # Build lookup registries
    module_node  = next((n for n in nodes if n.type == "MODULE"), None)
    class_by_name = {n.name: n for n in nodes if n.type == "CLASS"}
    func_by_name  = {n.name: n for n in nodes if n.type == "FUNCTION"}

    # Short name index: "calculate_tax" → node for "PaymentProcessor.calculate_tax"
    func_by_short: dict[str, CodeNode] = {}
    for n in nodes:
        if n.type == "FUNCTION":
            short = n.name.split(".")[-1]
            func_by_short.setdefault(short, n)

    # ------------------------------------------------------------------
    # DEFINED_IN — every class and function is defined in the module
    # ------------------------------------------------------------------
    if module_node:
        for node in nodes:
            if node.type != "MODULE":
                add_edge(node.node_id, module_node.node_id, "DEFINED_IN")

    # ------------------------------------------------------------------
    # BELONGS_TO — methods belong to their class
    # ------------------------------------------------------------------
    for node in nodes:
        if node.type == "FUNCTION" and node.parent_name:
            class_node = class_by_name.get(node.parent_name)
            if class_node:
                add_edge(node.node_id, class_node.node_id, "BELONGS_TO")

    # ------------------------------------------------------------------
    # IMPORTS — from .module import X
    # ------------------------------------------------------------------
    if module_node:
        for ast_node in ast.walk(tree):
            if isinstance(ast_node, ast.ImportFrom):
                target_file = _resolve_import_path(
                    source_file, ast_node.module or "", ast_node.level
                )
                if target_file:
                    target_id = _make_id(
                        team_id, target_file, "MODULE", Path(target_file).stem
                    )
                    add_edge(module_node.node_id, target_id, "IMPORTS")

    # ------------------------------------------------------------------
    # INHERITS — class Base(Parent)
    # ------------------------------------------------------------------
    for ast_node in ast.walk(tree):
        if isinstance(ast_node, ast.ClassDef):
            child_class = class_by_name.get(ast_node.name)
            if not child_class:
                continue
            for base in ast_node.bases:
                base_name = None
                if isinstance(base, ast.Name):
                    base_name = base.id
                elif isinstance(base, ast.Attribute):
                    base_name = base.attr
                if base_name:
                    parent_class = class_by_name.get(base_name)
                    if parent_class:
                        add_edge(child_class.node_id, parent_class.node_id, "INHERITS")

    # ------------------------------------------------------------------
    # CALLS — function calls inside function bodies
    # ------------------------------------------------------------------
    # Methods inside classes
    for ast_node in ast.walk(tree):
        if isinstance(ast_node, ast.ClassDef):
            class_name = ast_node.name
            for item in ast_node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                full_name  = f"{class_name}.{item.name}"
                caller     = func_by_name.get(full_name)
                if not caller:
                    continue
                for child in ast.walk(item):
                    if isinstance(child, ast.Call):
                        called = _extract_call_name(child)
                        if not called:
                            continue
                        target = (
                            func_by_name.get(f"{class_name}.{called}")
                            or func_by_name.get(called)
                            or func_by_short.get(called)
                        )
                        if target and target.node_id != caller.node_id:
                            add_edge(caller.node_id, target.node_id, "CALLS")

    # Top-level functions
    for ast_node in ast.walk(tree):
        if isinstance(ast_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if not any(
                isinstance(parent, ast.ClassDef)
                for parent in ast.walk(tree)
                if ast_node in ast.walk(parent) and parent is not ast_node
            ):
                caller = func_by_name.get(ast_node.name) or func_by_short.get(ast_node.name)
                if not caller:
                    continue
                for child in ast.walk(ast_node):
                    if isinstance(child, ast.Call):
                        called = _extract_call_name(child)
                        if not called:
                            continue
                        target = func_by_name.get(called) or func_by_short.get(called)
                        if target and target.node_id != caller.node_id:
                            add_edge(caller.node_id, target.node_id, "CALLS")

    return edges


def parse_file(file_path: str, team_id: str) -> tuple[list[CodeNode], list[Edge]]:
    """
    Parse a single Python file and return CodeNodes and Edges.
    One CodeNode per: module, class, top-level function, method.
    Edges capture: DEFINED_IN, BELONGS_TO, IMPORTS, INHERITS, CALLS relationships.
    """
    path = Path(file_path)
    source = path.read_text(encoding="utf-8")
    source_lines = source.splitlines(keepends=True)

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        raise ValueError(f"Cannot parse {file_path}: {e}") from e

    nodes: list[CodeNode] = []

    # Module-level node
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
        raw_source=source[:500],
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

    edges = _extract_edges(tree, file_path, team_id, nodes)
    return nodes, edges
