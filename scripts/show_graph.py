"""
Quick inspection script — shows all nodes and edges extracted from a repo.
Usage: uv run python scripts/show_graph.py <repo_path> [team_id]
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.parsers.ast_parser import parse_file
from src.crawlers.repo_walker import walk_repo

repo_path = sys.argv[1] if len(sys.argv) > 1 else "data/team-alpha/repos/payment-service"
team_id   = sys.argv[2] if len(sys.argv) > 2 else "team-alpha"

all_nodes = {}
all_edges = []

for f in walk_repo(repo_path):
    nodes, edges = parse_file(f, team_id)
    for n in nodes:
        all_nodes[n.node_id] = n
    all_edges.extend(edges)

def name(node_id):
    n = all_nodes.get(node_id)
    return n.name if n else node_id[:10] + "..."

print("=" * 60)
print("NODES")
print("=" * 60)
for n in all_nodes.values():
    print(f"  [{n.type:<8}]  {n.name}  ({n.file_path.split('/')[-1]})")

print()
print("=" * 60)
print("EDGES")
print("=" * 60)

for rel in ["DEFINED_IN", "BELONGS_TO", "IMPORTS", "INHERITS", "CALLS"]:
    group = [e for e in all_edges if e.relation_type == rel]
    if not group:
        continue
    print(f"\n  -- {rel} ({len(group)}) --")
    for e in group:
        print(f"    {name(e.from_node_id):<45} ->  {name(e.to_node_id)}")

print()
print(f"Total nodes : {len(all_nodes)}")
print(f"Total edges : {len(all_edges)}")
