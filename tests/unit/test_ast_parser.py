"""
Unit tests for src/parsers/ast_parser.py

parse_file tests use tmp_path — a built-in pytest fixture that creates a
temporary directory per test. This avoids touching real project files.
"""

import pytest
from src.parsers.ast_parser import _make_id, _get_source_segment, parse_file


# ---------------------------------------------------------------------------
# _make_id
# ---------------------------------------------------------------------------

def test_make_id_returns_string():
    result = _make_id("team-alpha", "src/app.py", "FUNCTION", "foo")
    assert isinstance(result, str)


def test_make_id_returns_32_char_hex():
    result = _make_id("team-alpha", "src/app.py", "FUNCTION", "foo")
    assert len(result) == 32
    assert all(c in "0123456789abcdef" for c in result)


def test_make_id_is_deterministic():
    a = _make_id("team-alpha", "src/app.py", "FUNCTION", "foo")
    b = _make_id("team-alpha", "src/app.py", "FUNCTION", "foo")
    assert a == b


@pytest.mark.parametrize("kwargs", [
    dict(team_id="team-beta",  file_path="src/app.py",   node_type="FUNCTION", name="foo"),
    dict(team_id="team-alpha", file_path="src/other.py", node_type="FUNCTION", name="foo"),
    dict(team_id="team-alpha", file_path="src/app.py",   node_type="CLASS",    name="foo"),
    dict(team_id="team-alpha", file_path="src/app.py",   node_type="FUNCTION", name="bar"),
])
def test_make_id_differs_when_any_input_changes(kwargs):
    baseline = _make_id("team-alpha", "src/app.py", "FUNCTION", "foo")
    assert _make_id(**kwargs) != baseline


# ---------------------------------------------------------------------------
# _get_source_segment
# ---------------------------------------------------------------------------

LINES = ["line1\n", "line2\n", "line3\n", "line4\n", "line5\n"]


@pytest.mark.parametrize("start, end, expected", [
    (1, 1, "line1\n"),
    (2, 2, "line2\n"),
    (1, 3, "line1\nline2\nline3\n"),
    (3, 5, "line3\nline4\nline5\n"),
    (2, 4, "line2\nline3\nline4\n"),
])
def test_get_source_segment(start, end, expected):
    assert _get_source_segment(LINES, start, end) == expected


# ---------------------------------------------------------------------------
# parse_file — MODULE node
# ---------------------------------------------------------------------------

def test_parse_file_returns_list(tmp_path):
    f = tmp_path / "empty.py"
    f.write_text("")
    nodes, _ = parse_file(str(f), "team-alpha")
    assert isinstance(nodes, list)


def test_parse_file_always_returns_module_node(tmp_path):
    f = tmp_path / "mod.py"
    f.write_text("")
    nodes, _ = parse_file(str(f), "team-alpha")
    assert len([n for n in nodes if n.type == "MODULE"]) == 1


def test_parse_file_module_node_team_id(tmp_path):
    f = tmp_path / "mod.py"
    f.write_text("")
    nodes, _ = parse_file(str(f), "team-alpha")
    module = next(n for n in nodes if n.type == "MODULE")
    assert module.team_id == "team-alpha"


def test_parse_file_module_node_name_is_file_stem(tmp_path):
    f = tmp_path / "billing.py"
    f.write_text("")
    nodes, _ = parse_file(str(f), "team-alpha")
    module = next(n for n in nodes if n.type == "MODULE")
    assert module.name == "billing"


def test_parse_file_module_node_line_start_is_one(tmp_path):
    f = tmp_path / "mod.py"
    f.write_text("x = 1\n")
    nodes, _ = parse_file(str(f), "team-alpha")
    module = next(n for n in nodes if n.type == "MODULE")
    assert module.line_start == 1


def test_parse_file_module_docstring_is_extracted(tmp_path):
    f = tmp_path / "mod.py"
    f.write_text('"""This is the module docstring."""\n')
    nodes, _ = parse_file(str(f), "team-alpha")
    module = next(n for n in nodes if n.type == "MODULE")
    assert module.docstring == "This is the module docstring."


def test_parse_file_module_docstring_is_empty_string_when_absent(tmp_path):
    f = tmp_path / "mod.py"
    f.write_text("x = 1\n")
    nodes, _ = parse_file(str(f), "team-alpha")
    module = next(n for n in nodes if n.type == "MODULE")
    assert module.docstring == ""


# ---------------------------------------------------------------------------
# parse_file — CLASS nodes
# ---------------------------------------------------------------------------

CLASS_SOURCE = '''\
class PaymentProcessor:
    """Handles payment processing."""

    def process(self, amount):
        """Process a payment."""
        return amount
'''


def test_parse_file_extracts_one_class_node(tmp_path):
    f = tmp_path / "payments.py"
    f.write_text(CLASS_SOURCE)
    nodes, _ = parse_file(str(f), "team-alpha")
    assert len([n for n in nodes if n.type == "CLASS"]) == 1


def test_parse_file_class_node_name(tmp_path):
    f = tmp_path / "payments.py"
    f.write_text(CLASS_SOURCE)
    nodes, _ = parse_file(str(f), "team-alpha")
    class_node = next(n for n in nodes if n.type == "CLASS")
    assert class_node.name == "PaymentProcessor"


def test_parse_file_class_node_docstring(tmp_path):
    f = tmp_path / "payments.py"
    f.write_text(CLASS_SOURCE)
    nodes, _ = parse_file(str(f), "team-alpha")
    class_node = next(n for n in nodes if n.type == "CLASS")
    assert class_node.docstring == "Handles payment processing."


def test_parse_file_class_node_team_id(tmp_path):
    f = tmp_path / "payments.py"
    f.write_text(CLASS_SOURCE)
    nodes, _ = parse_file(str(f), "team-alpha")
    class_node = next(n for n in nodes if n.type == "CLASS")
    assert class_node.team_id == "team-alpha"


# ---------------------------------------------------------------------------
# parse_file — FUNCTION nodes (top-level)
# ---------------------------------------------------------------------------

FUNC_SOURCE = '''\
def calculate_tax(amount):
    """Calculates tax for a given amount."""
    return amount * 0.18
'''


def test_parse_file_extracts_top_level_function(tmp_path):
    f = tmp_path / "tax.py"
    f.write_text(FUNC_SOURCE)
    nodes, _ = parse_file(str(f), "team-alpha")
    func_nodes = [n for n in nodes if n.type == "FUNCTION"]
    assert len(func_nodes) == 1
    assert func_nodes[0].name == "calculate_tax"


def test_parse_file_function_docstring(tmp_path):
    f = tmp_path / "tax.py"
    f.write_text(FUNC_SOURCE)
    nodes, _ = parse_file(str(f), "team-alpha")
    func = next(n for n in nodes if n.type == "FUNCTION")
    assert func.docstring == "Calculates tax for a given amount."


def test_parse_file_function_team_id(tmp_path):
    f = tmp_path / "tax.py"
    f.write_text(FUNC_SOURCE)
    nodes, _ = parse_file(str(f), "team-alpha")
    func = next(n for n in nodes if n.type == "FUNCTION")
    assert func.team_id == "team-alpha"


# ---------------------------------------------------------------------------
# parse_file — FUNCTION nodes (methods inside a class)
# ---------------------------------------------------------------------------

def test_parse_file_method_has_parent_name(tmp_path):
    f = tmp_path / "payments.py"
    f.write_text(CLASS_SOURCE)
    nodes, _ = parse_file(str(f), "team-alpha")
    method = next(n for n in nodes if n.type == "FUNCTION")
    assert method.parent_name == "PaymentProcessor"


def test_parse_file_method_name_is_class_dot_method(tmp_path):
    f = tmp_path / "payments.py"
    f.write_text(CLASS_SOURCE)
    nodes, _ = parse_file(str(f), "team-alpha")
    method = next(n for n in nodes if n.type == "FUNCTION")
    assert method.name == "PaymentProcessor.process"


def test_parse_file_method_docstring(tmp_path):
    f = tmp_path / "payments.py"
    f.write_text(CLASS_SOURCE)
    nodes, _ = parse_file(str(f), "team-alpha")
    method = next(n for n in nodes if n.type == "FUNCTION")
    assert method.docstring == "Process a payment."


# ---------------------------------------------------------------------------
# parse_file — team isolation
# ---------------------------------------------------------------------------

def test_parse_file_all_nodes_carry_team_id(tmp_path):
    f = tmp_path / "payments.py"
    f.write_text(CLASS_SOURCE)
    nodes, _ = parse_file(str(f), "team-alpha")
    for node in nodes:
        assert node.team_id == "team-alpha"


def test_parse_file_different_teams_produce_different_node_ids(tmp_path):
    f = tmp_path / "tax.py"
    f.write_text(FUNC_SOURCE)
    alpha_nodes, _ = parse_file(str(f), "team-alpha")
    alpha_ids = {n.node_id for n in alpha_nodes}
    beta_nodes, _  = parse_file(str(f), "team-beta")
    beta_ids  = {n.node_id for n in beta_nodes}
    assert alpha_ids.isdisjoint(beta_ids)


def test_parse_file_node_ids_are_stable_across_runs(tmp_path):
    f = tmp_path / "tax.py"
    f.write_text(FUNC_SOURCE)
    first_nodes, _  = parse_file(str(f), "team-alpha")
    first  = [n.node_id for n in first_nodes]
    second_nodes, _ = parse_file(str(f), "team-alpha")
    second = [n.node_id for n in second_nodes]
    assert first == second


# ---------------------------------------------------------------------------
# parse_file — error handling
# ---------------------------------------------------------------------------

def test_parse_file_raises_value_error_on_syntax_error(tmp_path):
    f = tmp_path / "broken.py"
    f.write_text("def foo(:\n    pass\n")
    with pytest.raises(ValueError, match="Cannot parse"):
        parse_file(str(f), "team-alpha")
