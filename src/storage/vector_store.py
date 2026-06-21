"""
Vector store layer — wraps ChromaDB for persisting and searching embedded CodeNodes.

Each team gets its own ChromaDB collection named after the team_id,
which enforces data isolation at the storage level.
"""

import logging
import chromadb
from src.enrichment.embedder import embed_nodes, model
from src.parsers.ast_parser import CodeNode

client = chromadb.PersistentClient(path="data/chromadb")


def store(nodes: list[CodeNode], team_id: str) -> None:
    """Embed and persist a list of CodeNodes into the team's ChromaDB collection."""
    collection = client.get_or_create_collection(name=team_id)
    embedded = embed_nodes(nodes)

    collection.add(
        ids=[e["node_id"] for e in embedded],
        embeddings=[e["vector"].tolist() for e in embedded],
        metadatas=[
            {
                "team_id":   e["team_id"],
                "name":      e["name"],
                "type":      e["type"],
                "file_path": e["file_path"],
                "docstring": e["docstring"],
            }
            for e in embedded
        ],
        documents=[e["docstring"] for e in embedded],
    )
    print(f"Stored {len(embedded)} nodes into collection '{team_id}'")


def search(query: str, team_id: str, top_k: int = 3) -> list[dict]:
    """Embed the query and return the top-K most semantically similar nodes for this team."""
    _log = logging.getLogger("chromadb")
    _prev_level = _log.level
    _log.setLevel(logging.ERROR)

    try:
        collection = client.get_or_create_collection(name=team_id)
        query_vector = model.encode([query])[0].tolist()

        results = collection.query(
            query_embeddings=[query_vector],
            n_results=top_k,
        )

        matches = []
        for i in range(len(results["ids"][0])):
            matches.append({
                "node_id":   results["ids"][0][i],
                "score":     results["distances"][0][i],
                "metadata":  results["metadatas"][0][i],
                "document":  results["documents"][0][i],
            })
        return matches
    finally:
        _log.setLevel(_prev_level)
