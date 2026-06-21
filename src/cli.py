"""
CLI entry point — provides `ingest` and `query` commands for the KnowledgeGraph system.

Usage:
    python -m src.cli ingest --team <team_id> --file <path>
    python -m src.cli query  --team <team_id> --question "<question>" [--model <model>]
"""

import click
from src.parsers.ast_parser import parse_file
from src.storage.vector_store import store, search
from src.skills.ollama_client import build_prompt, ask_ollama


@click.group()
def cli():
    """KnowledgeGraph CLI — ingest code and ask questions about it."""


@cli.command()
@click.option("--team", required=True, help="Team ID")
@click.option("--file", "file_path", required=True, help="Path to a Python file to ingest")
def ingest(team, file_path):
    """Parse a Python file and store its CodeNodes in the team's ChromaDB collection."""
    click.echo(f"Parsing {file_path}...")
    nodes = parse_file(file_path, team)
    click.echo(f"Found {len(nodes)} nodes")

    click.echo("Storing in ChromaDB...")
    store(nodes, team)


@cli.command()
@click.option("--team", required=True, help="Team ID")
@click.option("--question", required=True, help="Natural language question about the codebase")
@click.option("--model", default="phi", show_default=True, help="Ollama model to use")
def query(team, question, model):
    """Search ChromaDB for relevant nodes and ask Ollama to answer the question."""
    click.echo(f"Searching for: {question}")
    results = search(question, team)

    click.echo(f"Found {len(results)} relevant nodes")
    for r in results:
        click.echo(f"  - {r['metadata']['name']} (score: {r['score']:.4f})")

    click.echo("\nAsking Ollama...")
    prompt = build_prompt(question, results)
    answer = ask_ollama(prompt, model=model)

    click.echo("\n=== ANSWER ===")
    click.echo(answer)


if __name__ == "__main__":
    cli()
