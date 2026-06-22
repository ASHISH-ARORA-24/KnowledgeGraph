"""
Unit tests for src/storage/graph_store.py

The Neo4j driver (_driver) is patched — no real database connection is made.
All tests verify that the correct session methods are called with the right arguments.
"""

import pytest
from unittest.mock import MagicMock, patch
from src.storage.graph_store import store_nodes, store_edges, get_neighbors, get_impact
from src.parsers.ast_parser import CodeNode, Edge


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_node(name="calculate_tax", node_type="FUNCTION"):
    return CodeNode(
        node_id="abc123",
        team_id="team-alpha",
        project_id="payment-service",
        type=node_type,
        name=name,
        file_path="processors.py",
        line_start=1,
        line_end=10,
        docstring="Calculates tax.",
        raw_source="def calculate_tax(): pass",
    )


def _sample_edge():
    return Edge(
        from_node_id="abc123",
        to_node_id="def456",
        relation_type="CALLS",
        team_id="team-alpha",
        project_id="payment-service",
    )


@pytest.fixture
def mock_driver():
    """Patch the module-level _driver with a MagicMock."""
    with patch("src.storage.graph_store._driver") as driver:
        session = MagicMock()
        driver.session.return_value.__enter__.return_value = session
        driver.session.return_value.__exit__.return_value = False
        yield driver, session


# ---------------------------------------------------------------------------
# store_nodes
# ---------------------------------------------------------------------------

def test_store_nodes_opens_a_session(mock_driver):
    driver, _ = mock_driver
    store_nodes([_sample_node()])
    driver.session.assert_called_once()


def test_store_nodes_calls_execute_write(mock_driver):
    _, session = mock_driver
    store_nodes([_sample_node()])
    session.execute_write.assert_called_once()


def test_store_nodes_works_with_empty_list(mock_driver):
    _, session = mock_driver
    store_nodes([])
    session.execute_write.assert_called_once()


def test_store_nodes_works_with_multiple_nodes(mock_driver):
    _, session = mock_driver
    store_nodes([_sample_node("func_a"), _sample_node("func_b")])
    session.execute_write.assert_called_once()


# ---------------------------------------------------------------------------
# store_edges
# ---------------------------------------------------------------------------

def test_store_edges_opens_a_session(mock_driver):
    driver, _ = mock_driver
    store_edges([_sample_edge()])
    driver.session.assert_called_once()


def test_store_edges_calls_execute_write(mock_driver):
    _, session = mock_driver
    store_edges([_sample_edge()])
    session.execute_write.assert_called_once()


def test_store_edges_works_with_empty_list(mock_driver):
    _, session = mock_driver
    store_edges([])
    session.execute_write.assert_called_once()


# ---------------------------------------------------------------------------
# get_neighbors
# ---------------------------------------------------------------------------

def test_get_neighbors_opens_a_session(mock_driver):
    driver, session = mock_driver
    session.execute_read.return_value = []
    get_neighbors(["abc123"], "team-alpha")
    driver.session.assert_called_once()


def test_get_neighbors_calls_execute_read(mock_driver):
    _, session = mock_driver
    session.execute_read.return_value = []
    get_neighbors(["abc123"], "team-alpha")
    session.execute_read.assert_called_once()


def test_get_neighbors_returns_list(mock_driver):
    _, session = mock_driver
    session.execute_read.return_value = [
        {
            "node_id": "xyz", "name": "process_payment", "type": "FUNCTION",
            "file_path": "processors.py", "docstring": "", "raw_source": "",
            "relation_type": "CALLS",
        }
    ]
    result = get_neighbors(["abc123"], "team-alpha")
    assert isinstance(result, list)
    assert len(result) == 1


def test_get_neighbors_returns_empty_when_no_connections(mock_driver):
    _, session = mock_driver
    session.execute_read.return_value = []
    result = get_neighbors(["abc123"], "team-alpha")
    assert result == []


def test_get_neighbors_passes_node_ids_and_team(mock_driver):
    _, session = mock_driver
    session.execute_read.return_value = []
    get_neighbors(["id1", "id2"], "team-beta")
    call_args = session.execute_read.call_args
    assert call_args.args[1] == ["id1", "id2"]
    assert call_args.args[2] == "team-beta"


# ---------------------------------------------------------------------------
# get_impact
# ---------------------------------------------------------------------------

def test_get_impact_opens_a_session(mock_driver):
    driver, session = mock_driver
    session.execute_read.return_value = []
    get_impact("calculate_tax", "team-alpha")
    driver.session.assert_called_once()


def test_get_impact_calls_execute_read(mock_driver):
    _, session = mock_driver
    session.execute_read.return_value = []
    get_impact("calculate_tax", "team-alpha")
    session.execute_read.assert_called_once()


def test_get_impact_returns_list(mock_driver):
    _, session = mock_driver
    session.execute_read.return_value = [
        {
            "name": "process_payment", "type": "FUNCTION",
            "file_path": "processors.py", "relation_type": "CALLS",
        }
    ]
    result = get_impact("calculate_tax", "team-alpha")
    assert isinstance(result, list)
    assert len(result) == 1


def test_get_impact_returns_empty_when_no_dependents(mock_driver):
    _, session = mock_driver
    session.execute_read.return_value = []
    result = get_impact("orphan_func", "team-alpha")
    assert result == []


def test_get_impact_passes_target_name_and_team(mock_driver):
    _, session = mock_driver
    session.execute_read.return_value = []
    get_impact("calculate_tax", "team-beta")
    call_args = session.execute_read.call_args
    assert call_args.args[1] == "calculate_tax"
    assert call_args.args[2] == "team-beta"
