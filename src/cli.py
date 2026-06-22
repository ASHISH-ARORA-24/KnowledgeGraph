"""
CLI entry point — provides `ingest` and `query` commands for the KnowledgeGraph system.

Usage:
    python -m src.cli ingest --team <team_id> --file <path>
    python -m src.cli ingest --team <team_id> --project <dir>
    python -m src.cli ingest --config <team_config.json>
    python -m src.cli query  --team <team_id> --question "<question>" [--model <model>]
"""

import json
import click
from src.parsers.ast_parser import parse_file
from src.crawlers.repo_walker import walk_repo
from src.storage.vector_store import store, search
from src.storage.graph_store import store_nodes, store_edges, get_neighbors, get_impact
from src.skills.ollama_client import build_prompt, ask_ollama


@click.group()
def cli():
    """KnowledgeGraph CLI — ingest code and ask questions about it."""


@cli.command()
@click.option("--team",       help="Team ID (required for --file and --project)")
@click.option("--project-id", "project_id", default="default", help="Project / microservice name")
@click.option("--file",       "file_path",    help="Ingest a single Python file")
@click.option("--project",    "project_path", help="Ingest all .py files in a directory")
@click.option("--config",     "config_path",  type=click.Path(exists=True), help="Team config JSON")
def ingest(team, project_id, file_path, project_path, config_path):
    """Ingest Python source code into the team's ChromaDB collection.

    \b
    Three modes:
      --file     ingest a single .py file
      --project  ingest all .py files in a directory
      --config   ingest all repos defined in a team config JSON
    """
    if file_path:
        _ingest_file(file_path, _require_team(team, "--file"), project_id)

    elif project_path:
        _ingest_project(project_path, _require_team(team, "--project"), project_id)

    elif config_path:
        _ingest_config(config_path)

    else:
        raise click.UsageError("Provide one of: --file, --project, or --config")


@cli.command()
@click.option("--team",     required=True, help="Team ID")
@click.option("--question", required=True, help="Natural language question about the codebase")
@click.option("--model",    default="phi", show_default=True, help="Ollama model to use")
def query(team, question, model):
    """Search ChromaDB for relevant nodes and ask Ollama to answer the question."""
    click.echo(f"Searching for: {question}")
    results = search(question, team)

    click.echo(f"Found {len(results)} relevant nodes")
    for r in results:
        click.echo(f"  - {r['metadata']['name']} (score: {r['score']:.4f})")

    node_ids = [r["node_id"] for r in results]
    neighbors = get_neighbors(node_ids, team)
    if neighbors:
        click.echo(f"Graph expansion: +{len(neighbors)} connected nodes from Neo4j")
        for n in neighbors:
            click.echo(f"  - {n['name']} (via {n['relation_type']})")

    click.echo("\nAsking Ollama...")
    prompt = build_prompt(question, results, neighbors)
    answer = ask_ollama(prompt, model=model)

    click.echo("\n=== ANSWER ===")
    click.echo(answer)


@cli.command()
@click.option("--team",   required=True, help="Team ID")
@click.option("--target", required=True, help="Function or class name to analyse (e.g. 'PaymentProcessor.calculate_tax')")
def impact(team, target):
    """Show every function and module that depends on the given target (graph traversal)."""
    click.echo(f"Analysing impact of: {target}")
    results = get_impact(target, team)

    if not results:
        click.echo("No dependents found — nothing calls or imports this node.")
        return

    click.echo(f"\nFound {len(results)} dependent(s):\n")
    for r in results:
        click.echo(f"  [{r['relation_type']}]  {r['name']}  ({r['type']})  —  {r['file_path']}")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _require_team(team: str, flag: str) -> str:
    """Raise UsageError if --team was not provided alongside the given flag."""
    if not team:
        raise click.UsageError(f"--team is required when using {flag}")
    return team


def _ingest_file(file_path: str, team_id: str, project_id: str) -> None:
    """Parse a single file and store its nodes and edges."""
    click.echo(f"Parsing {file_path}...")
    nodes, edges = parse_file(file_path, team_id, project_id)
    click.echo(f"  Found {len(nodes)} nodes, {len(edges)} edges")

    click.echo("  Storing in ChromaDB...")
    store(nodes, team_id)

    click.echo("  Storing in Neo4j...")
    store_nodes(nodes)
    store_edges(edges)


def _ingest_project(project_path: str, team_id: str, project_id: str) -> None:
    """Walk a directory, parse every .py file, batch embed and store all nodes and edges."""
    click.echo(f"Walking {project_path}...")
    py_files = walk_repo(project_path)
    click.echo(f"  Found {len(py_files)} Python files")

    all_nodes = []
    all_edges = []
    for file_path in py_files:
        click.echo(f"  Parsing {file_path}...")
        nodes, edges = parse_file(file_path, team_id, project_id)
        click.echo(f"    {len(nodes)} nodes, {len(edges)} edges")
        all_nodes.extend(nodes)
        all_edges.extend(edges)

    click.echo(f"Storing {len(all_nodes)} nodes in ChromaDB...")
    store(all_nodes, team_id)

    click.echo(f"Storing {len(all_nodes)} nodes and {len(all_edges)} edges in Neo4j...")
    store_nodes(all_nodes)
    store_edges(all_edges)


def _ingest_config(config_path: str) -> None:
    """Read a team config JSON and ingest every project listed in it."""
    with open(config_path) as f:
        config = json.load(f)

    team_id  = config["team_id"]
    projects = config.get("data", [])

    click.echo(f"Team     : {team_id}")
    click.echo(f"Projects : {len(projects)}")

    for project in projects:
        project_id = project["project_name"]
        repos      = project.get("repos", [])
        click.echo(f"\nProject  : {project_id} ({len(repos)} repo(s))")
        for repo_path in repos:
            click.echo(f"  Ingesting repo: {repo_path}")
            _ingest_project(repo_path, team_id, project_id)


if __name__ == "__main__":
    cli()
