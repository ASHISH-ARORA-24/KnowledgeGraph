"""
Unit tests for edge extraction in src/parsers/ast_parser.py

Each test writes a small Python snippet to a tmp_path file and verifies
that parse_file produces the expected edges.
"""

import pytest
from src.parsers.ast_parser import parse_file, Edge


TEAM    = "team-alpha"
PROJECT = "payment-service"


def _edges(source: str, tmp_path) -> list[Edge]:
    f = tmp_path / "module.py"
    f.write_text(source)
    _, edges = parse_file(str(f), TEAM, PROJECT)
    return edges


def _relation_types(edges: list[Edge]) -> list[str]:
    return [e.relation_type for e in edges]


def _edge_exists(edges: list[Edge], rel_type: str, from_name_part: str = "", to_name_part: str = "") -> bool:
    for e in edges:
        if e.relation_type != rel_type:
            continue
        if from_name_part and from_name_part not in e.from_node_id + str(e):
            continue
        return True
    return False


# ---------------------------------------------------------------------------
# DEFINED_IN
# ---------------------------------------------------------------------------

def test_defined_in_edge_for_class(tmp_path):
    source = "class Foo:\n    pass\n"
    edges = _edges(source, tmp_path)
    assert any(e.relation_type == "DEFINED_IN" for e in edges)


def test_defined_in_edge_for_function(tmp_path):
    source = "def foo():\n    pass\n"
    edges = _edges(source, tmp_path)
    assert any(e.relation_type == "DEFINED_IN" for e in edges)


def test_defined_in_count_matches_non_module_nodes(tmp_path):
    source = "class Foo:\n    pass\n\ndef bar():\n    pass\n"
    f = tmp_path / "module.py"
    f.write_text(source)
    nodes, edges = parse_file(str(f), TEAM, PROJECT)
    non_module_count = sum(1 for n in nodes if n.type != "MODULE")
    defined_in_count = sum(1 for e in edges if e.relation_type == "DEFINED_IN")
    assert defined_in_count == non_module_count


def test_no_defined_in_for_module_itself(tmp_path):
    source = '"""module docstring."""\n'
    f = tmp_path / "module.py"
    f.write_text(source)
    nodes, edges = parse_file(str(f), TEAM, PROJECT)
    module_node = next(n for n in nodes if n.type == "MODULE")
    for e in edges:
        if e.relation_type == "DEFINED_IN":
            assert e.from_node_id != module_node.node_id


# ---------------------------------------------------------------------------
# BELONGS_TO
# ---------------------------------------------------------------------------

def test_belongs_to_edge_for_method(tmp_path):
    source = "class MyClass:\n    def my_method(self):\n        pass\n"
    edges = _edges(source, tmp_path)
    assert any(e.relation_type == "BELONGS_TO" for e in edges)


def test_belongs_to_count_matches_method_count(tmp_path):
    source = (
        "class MyClass:\n"
        "    def method_a(self): pass\n"
        "    def method_b(self): pass\n"
    )
    f = tmp_path / "module.py"
    f.write_text(source)
    nodes, edges = parse_file(str(f), TEAM, PROJECT)
    method_count = sum(1 for n in nodes if n.type == "FUNCTION" and n.parent_name)
    belongs_to_count = sum(1 for e in edges if e.relation_type == "BELONGS_TO")
    assert belongs_to_count == method_count


def test_no_belongs_to_for_top_level_function(tmp_path):
    source = "def standalone(): pass\n"
    edges = _edges(source, tmp_path)
    assert not any(e.relation_type == "BELONGS_TO" for e in edges)


# ---------------------------------------------------------------------------
# INHERITS
# ---------------------------------------------------------------------------

def test_inherits_edge_for_subclass(tmp_path):
    source = (
        "class Base:\n    pass\n\n"
        "class Child(Base):\n    pass\n"
    )
    edges = _edges(source, tmp_path)
    assert any(e.relation_type == "INHERITS" for e in edges)


def test_no_inherits_for_class_with_no_base(tmp_path):
    source = "class Standalone:\n    pass\n"
    edges = _edges(source, tmp_path)
    assert not any(e.relation_type == "INHERITS" for e in edges)


def test_inherits_skipped_when_base_not_in_same_file(tmp_path):
    source = "class Child(ExternalBase):\n    pass\n"
    edges = _edges(source, tmp_path)
    assert not any(e.relation_type == "INHERITS" for e in edges)


def test_multiple_inheritance_produces_multiple_edges(tmp_path):
    source = (
        "class A:\n    pass\n\n"
        "class B:\n    pass\n\n"
        "class C(A, B):\n    pass\n"
    )
    edges = _edges(source, tmp_path)
    inherits = [e for e in edges if e.relation_type == "INHERITS"]
    assert len(inherits) == 2


# ---------------------------------------------------------------------------
# CALLS
# ---------------------------------------------------------------------------

def test_calls_edge_between_two_functions(tmp_path):
    source = (
        "def helper():\n    pass\n\n"
        "def main():\n    helper()\n"
    )
    edges = _edges(source, tmp_path)
    assert any(e.relation_type == "CALLS" for e in edges)


def test_calls_edge_for_method_calling_sibling_method(tmp_path):
    source = (
        "class Calc:\n"
        "    def tax(self, x): return x * 0.18\n"
        "    def total(self, x): return x + self.tax(x)\n"
    )
    edges = _edges(source, tmp_path)
    assert any(e.relation_type == "CALLS" for e in edges)


def test_no_self_calls_edge(tmp_path):
    source = (
        "def foo():\n    foo()\n"  # recursive call
    )
    f = tmp_path / "module.py"
    f.write_text(source)
    nodes, edges = parse_file(str(f), TEAM, PROJECT)
    calls = [e for e in edges if e.relation_type == "CALLS"]
    for e in calls:
        assert e.from_node_id != e.to_node_id


# ---------------------------------------------------------------------------
# All edges carry team_id
# ---------------------------------------------------------------------------

def test_all_edges_carry_team_id(tmp_path):
    source = (
        "class Base:\n    pass\n\n"
        "class Child(Base):\n"
        "    def method(self): pass\n"
    )
    edges = _edges(source, tmp_path)
    for e in edges:
        assert e.team_id == TEAM


# ---------------------------------------------------------------------------
# No duplicate edges
# ---------------------------------------------------------------------------

def test_no_duplicate_edges(tmp_path):
    source = (
        "def helper(): pass\n\n"
        "def main():\n    helper()\n    helper()\n"
    )
    edges = _edges(source, tmp_path)
    keys = [(e.from_node_id, e.to_node_id, e.relation_type) for e in edges]
    assert len(keys) == len(set(keys))
