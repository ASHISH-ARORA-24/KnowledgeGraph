"""
CLI entry point — provides `ingest` and `query` commands for the KnowledgeGraph system.

Usage:
    python -m src.cli ingest --team <team_id> --file <path>
    python -m src.cli query  --team <team_id> --question "<question>" [--model <model>]
"""

import argparse
from src.parsers.ast_parser import parse_file
from src.storage.vector_store import store, search
from src.skills.ollama_client import build_prompt, ask_ollama


def ingest(args):
    """Parse a Python file and store its CodeNodes in the team's ChromaDB collection."""
    print(f"Parsing {args.file}...")
    nodes = parse_file(args.file, args.team)
    print(f"Found {len(nodes)} nodes")

    print("Storing in ChromaDB...")
    store(nodes, args.team)


def query(args):
    """Search ChromaDB for relevant nodes and ask Ollama to answer the question."""
    print(f"Searching for: {args.question}")
    results = search(args.question, args.team)

    print(f"Found {len(results)} relevant nodes")
    for r in results:
        print(f"  - {r['metadata']['name']} (score: {r['score']:.4f})")

    print("\nAsking Ollama...")
    prompt = build_prompt(args.question, results)
    answer = ask_ollama(prompt, model=args.model)

    print("\n=== ANSWER ===")
    print(answer)


def main():
    """Parse CLI arguments and dispatch to the ingest or query handler."""
    parser = argparse.ArgumentParser(description="KnowledgeGraph CLI")
    subparsers = parser.add_subparsers(dest="command")

    ingest_parser = subparsers.add_parser("ingest")
    ingest_parser.add_argument("--team", required=True)
    ingest_parser.add_argument("--file", required=True)

    query_parser = subparsers.add_parser("query")
    query_parser.add_argument("--team", required=True)
    query_parser.add_argument("--question", required=True)
    query_parser.add_argument("--model", default="phi")

    args = parser.parse_args()

    if args.command == "ingest":
        ingest(args)
    elif args.command == "query":
        query(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
