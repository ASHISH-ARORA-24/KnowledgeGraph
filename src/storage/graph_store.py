"""
Graph store — persists CodeNodes and Edges into Neo4j.

Each CodeNode becomes a graph node with label :CodeNode.
Each Edge becomes a Neo4j relationship with its relation_type as the label.
All nodes and relationships carry team_id for isolation.
"""

from neo4j import GraphDatabase
from src.parsers.ast_parser import CodeNode, Edge

NEO4J_URI      = "bolt://localhost:7687"
NEO4J_USER     = "neo4j"
NEO4J_PASSWORD = "password123"

_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def store_nodes(nodes: list[CodeNode]) -> None:
    """
    Upsert a list of CodeNodes into Neo4j as :CodeNode graph nodes.
    Uses MERGE on node_id so re-ingesting the same file is safe.

    input:
        nodes: CodeNodes to persist, all tagged with the same team_id.
    """
    with _driver.session() as session:
        session.execute_write(_write_nodes, nodes)


def store_edges(edges: list[Edge]) -> None:
    """
    Upsert a list of Edges into Neo4j as typed relationships.
    The relation_type becomes the Neo4j relationship label (e.g. CALLS, IMPORTS).
    Uses MERGE so re-ingesting the same file does not create duplicate edges.

    input:
        edges: Edges to persist, all tagged with the same team_id.
    """
    with _driver.session() as session:
        session.execute_write(_write_edges, edges)


def close() -> None:
    """Close the Neo4j driver connection."""
    _driver.close()


# ---------------------------------------------------------------------------
# Internal write functions — run inside transactions
# ---------------------------------------------------------------------------

def _write_nodes(tx, nodes: list[CodeNode]) -> None:
    query = """
    UNWIND $nodes AS n
    MERGE (node:CodeNode {node_id: n.node_id})
    SET node.team_id   = n.team_id,
        node.type      = n.type,
        node.name      = n.name,
        node.file_path = n.file_path,
        node.docstring = n.docstring,
        node.line_start = n.line_start,
        node.line_end   = n.line_end
    """
    tx.run(query, nodes=[{
        "node_id":    n.node_id,
        "team_id":    n.team_id,
        "type":       n.type,
        "name":       n.name,
        "file_path":  n.file_path,
        "docstring":  n.docstring,
        "line_start": n.line_start,
        "line_end":   n.line_end,
    } for n in nodes])


def _write_edges(tx, edges: list[Edge]) -> None:
    # Neo4j does not support dynamic relationship types in a single query.
    # We group edges by relation_type and run one query per type.
    from collections import defaultdict
    by_type: dict[str, list[Edge]] = defaultdict(list)
    for e in edges:
        by_type[e.relation_type].append(e)

    for rel_type, group in by_type.items():
        query = f"""
        UNWIND $edges AS e
        MATCH (a:CodeNode {{node_id: e.from_node_id}})
        MATCH (b:CodeNode {{node_id: e.to_node_id}})
        MERGE (a)-[r:{rel_type} {{team_id: e.team_id}}]->(b)
        """
        tx.run(query, edges=[{
            "from_node_id": e.from_node_id,
            "to_node_id":   e.to_node_id,
            "team_id":      e.team_id,
        } for e in group])
