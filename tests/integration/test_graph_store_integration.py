"""
Integration tests for src/storage/graph_store.py

These tests hit a REAL Neo4j instance.
If Neo4j is not running they fail immediately with a clear message — not a cryptic
connection error buried in the output.

Run with Neo4j up:
    docker compose up -d
    uv run pytest tests/integration/ -v
"""

import pytest
from neo4j import GraphDatabase
from src.storage.graph_store import store_nodes, store_edges, get_neighbors, get_impact
from src.parsers.ast_parser import CodeNode, Edge


NEO4J_URI      = "bolt://localhost:7687"
NEO4J_USER     = "neo4j"
NEO4J_PASSWORD = "password123"
TEST_TEAM      = "integration-test-team"


# ---------------------------------------------------------------------------
# Session-level connectivity check — fails immediately if Neo4j is not up
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def require_neo4j():
    """Fail the entire integration test session if Neo4j is not reachable."""
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        driver.close()
    except Exception:
        pytest.fail(
            "\n\nNeo4j is not running.\n"
            "Start it with:  docker compose up -d\n"
            "Then re-run:    uv run pytest tests/integration/ -v\n"
        )


# ---------------------------------------------------------------------------
# Per-test cleanup — wipe all test team data before and after each test
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def clean_test_data():
    """Delete all nodes for TEST_TEAM before and after every test."""
    _wipe()
    yield
    _wipe()


def _wipe():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:
        session.run(
            "MATCH (n:CodeNode {team_id: $team_id}) DETACH DELETE n",
            team_id=TEST_TEAM,
        )
    driver.close()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _node(name: str, node_type: str = "FUNCTION", node_id: str = None) -> CodeNode:
    return CodeNode(
        node_id=node_id or f"test-id-{name}",
        team_id=TEST_TEAM,
        project_id="test-project",
        type=node_type,
        name=name,
        file_path="test_module.py",
        line_start=1,
        line_end=10,
        docstring=f"Docstring for {name}.",
        raw_source=f"def {name}(): pass",
    )


def _edge(from_id: str, to_id: str, rel_type: str) -> Edge:
    return Edge(from_node_id=from_id, to_node_id=to_id,
                relation_type=rel_type, team_id=TEST_TEAM, project_id="test-project")


def _node_count() -> int:
    """Return number of CodeNodes stored for TEST_TEAM in Neo4j."""
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:
        result = session.run(
            "MATCH (n:CodeNode {team_id: $team_id}) RETURN count(n) AS c",
            team_id=TEST_TEAM,
        )
        count = result.single()["c"]
    driver.close()
    return count


# ---------------------------------------------------------------------------
# store_nodes
# ---------------------------------------------------------------------------

def test_store_nodes_writes_to_neo4j():
    store_nodes([_node("func_a")])
    assert _node_count() == 1


def test_store_nodes_writes_multiple_nodes():
    store_nodes([_node("func_a"), _node("func_b"), _node("func_c")])
    assert _node_count() == 3


def test_store_nodes_is_idempotent():
    """Re-ingesting the same node must not create a duplicate."""
    node = _node("func_a")
    store_nodes([node])
    store_nodes([node])
    assert _node_count() == 1


def test_store_nodes_persists_raw_source():
    store_nodes([_node("func_a")])
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:
        result = session.run(
            "MATCH (n:CodeNode {team_id: $team_id, name: 'func_a'}) RETURN n.raw_source AS src",
            team_id=TEST_TEAM,
        )
        src = result.single()["src"]
    driver.close()
    assert "func_a" in src


# ---------------------------------------------------------------------------
# store_edges
# ---------------------------------------------------------------------------

def test_store_edges_writes_relationship():
    a = _node("caller", node_id="id-caller")
    b = _node("callee", node_id="id-callee")
    store_nodes([a, b])
    store_edges([_edge("id-caller", "id-callee", "CALLS")])

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:
        result = session.run(
            "MATCH ()-[r:CALLS {team_id: $team_id}]->() RETURN count(r) AS c",
            team_id=TEST_TEAM,
        )
        count = result.single()["c"]
    driver.close()
    assert count == 1


def test_store_edges_is_idempotent():
    """Re-ingesting the same edge must not create a duplicate."""
    a = _node("caller", node_id="id-caller")
    b = _node("callee", node_id="id-callee")
    store_nodes([a, b])
    edge = _edge("id-caller", "id-callee", "CALLS")
    store_edges([edge])
    store_edges([edge])

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:
        result = session.run(
            "MATCH ()-[r:CALLS {team_id: $team_id}]->() RETURN count(r) AS c",
            team_id=TEST_TEAM,
        )
        count = result.single()["c"]
    driver.close()
    assert count == 1


# ---------------------------------------------------------------------------
# get_neighbors
# ---------------------------------------------------------------------------

def test_get_neighbors_returns_connected_node():
    a = _node("func_a", node_id="id-a")
    b = _node("func_b", node_id="id-b")
    store_nodes([a, b])
    store_edges([_edge("id-a", "id-b", "CALLS")])

    neighbors = get_neighbors(["id-a"], TEST_TEAM)
    names = [n["name"] for n in neighbors]
    assert "func_b" in names


def test_get_neighbors_traverses_both_directions():
    """get_neighbors should find nodes on both ends of an edge."""
    a = _node("func_a", node_id="id-a")
    b = _node("func_b", node_id="id-b")
    store_nodes([a, b])
    store_edges([_edge("id-a", "id-b", "CALLS")])

    # from b's perspective — func_a is on the other side
    neighbors = get_neighbors(["id-b"], TEST_TEAM)
    names = [n["name"] for n in neighbors]
    assert "func_a" in names


def test_get_neighbors_excludes_seed_nodes():
    """Nodes already in the input list must not appear in results."""
    a = _node("func_a", node_id="id-a")
    b = _node("func_b", node_id="id-b")
    store_nodes([a, b])
    store_edges([_edge("id-a", "id-b", "CALLS")])

    neighbors = get_neighbors(["id-a"], TEST_TEAM)
    returned_ids = [n["node_id"] for n in neighbors]
    assert "id-a" not in returned_ids


def test_get_neighbors_returns_empty_for_isolated_node():
    store_nodes([_node("isolated", node_id="id-iso")])
    neighbors = get_neighbors(["id-iso"], TEST_TEAM)
    assert neighbors == []


# ---------------------------------------------------------------------------
# get_impact
# ---------------------------------------------------------------------------

def test_get_impact_returns_direct_caller():
    caller = _node("process_payment", node_id="id-caller")
    target = _node("calculate_tax",   node_id="id-target")
    store_nodes([caller, target])
    store_edges([_edge("id-caller", "id-target", "CALLS")])

    results = get_impact("calculate_tax", TEST_TEAM)
    names = [r["name"] for r in results]
    assert "process_payment" in names


def test_get_impact_does_not_return_callees():
    """get_impact must NOT return nodes that the target calls — only its callers."""
    target  = _node("calculate_tax", node_id="id-target")
    callee  = _node("helper",        node_id="id-callee")
    store_nodes([target, callee])
    store_edges([_edge("id-target", "id-callee", "CALLS")])

    results = get_impact("calculate_tax", TEST_TEAM)
    names = [r["name"] for r in results]
    assert "helper" not in names


def test_get_impact_returns_empty_when_no_dependents():
    store_nodes([_node("orphan", node_id="id-orphan")])
    results = get_impact("orphan", TEST_TEAM)
    assert results == []


def test_get_impact_includes_relation_type():
    caller = _node("process_payment", node_id="id-caller")
    target = _node("calculate_tax",   node_id="id-target")
    store_nodes([caller, target])
    store_edges([_edge("id-caller", "id-target", "CALLS")])

    results = get_impact("calculate_tax", TEST_TEAM)
    assert results[0]["relation_type"] == "CALLS"


# ---------------------------------------------------------------------------
# Team isolation
# ---------------------------------------------------------------------------

def test_get_neighbors_does_not_cross_team_boundary():
    """A node from another team must never appear in neighbors."""
    other_team_node = CodeNode(
        node_id="id-other", team_id="other-team", project_id="test-project", type="FUNCTION",
        name="other_func", file_path="other.py",
        line_start=1, line_end=5,
        docstring="", raw_source="def other_func(): pass",
    )
    my_node = _node("my_func", node_id="id-mine")

    store_nodes([other_team_node, my_node])

    # Even if we try to create a cross-team edge, the Cypher MATCH filters by team_id
    # so the other team node won't appear in results for TEST_TEAM
    neighbors = get_neighbors(["id-mine"], TEST_TEAM)
    names = [n["name"] for n in neighbors]
    assert "other_func" not in names


def test_get_impact_does_not_cross_team_boundary():
    other_caller = CodeNode(
        node_id="id-other-caller", team_id="other-team", project_id="test-project", type="FUNCTION",
        name="other_caller", file_path="other.py",
        line_start=1, line_end=5,
        docstring="", raw_source="def other_caller(): pass",
    )
    target = _node("calculate_tax", node_id="id-target")

    store_nodes([other_caller, target])

    results = get_impact("calculate_tax", TEST_TEAM)
    names = [r["name"] for r in results]
    assert "other_caller" not in names
