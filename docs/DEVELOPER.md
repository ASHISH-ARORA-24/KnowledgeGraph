# Developer Guide

## Prerequisites

- Python 3.11+
- Docker + Docker Compose
- Git
- Ollama (install from https://ollama.com)

## Quick Start

```bash
# 1. Start Neo4j (required from Cycle 3 onwards)
docker compose up -d

# 2. Install Python dependencies
uv sync

# 3. Ingest a team's repos
uv run python -m src.cli ingest --config configs/team_alpha.json

# 4. Ask a question
uv run python -m src.cli query --team team-alpha --question "What does calculate_tax do?"
```

## Repository Structure

```
KnowledgeGraph/
├── docs/
│   ├── DOMAIN.md          # Domain model, business rules, data models
│   ├── ARCHITECTURE.md    # System design, tech stack, component breakdown
│   ├── PROGRESS.md        # Cycle status, decisions log
│   └── DEVELOPER.md       # This file — how to run and develop
├── src/
│   ├── crawlers/          # Code and doc crawlers
│   ├── parsers/           # AST parser, doc chunker
│   ├── enrichment/        # Embedding generation, relationship resolution
│   ├── storage/           # Neo4j client, ChromaDB client, file store
│   ├── skills/            # Claude/Ollama skill implementations
│   └── api/               # FastAPI backend (later cycles)
├── data/                  # Gitignored — crawled data lives here
│   └── {team_id}/
│       ├── repos/
│       └── docs/
├── tests/
├── docker-compose.yml
├── .github/
│   └── workflows/
└── README.md
```

## Running Locally

```bash
# Start Neo4j
docker compose up -d

# Install Python dependencies
uv sync

# Ingest a single file
uv run python -m src.cli ingest --team team-alpha --project-id payment-service --file path/to/file.py

# Ingest a full directory
uv run python -m src.cli ingest --team team-alpha --project-id payment-service --project path/to/repo/

# Ingest all repos for a team from config (recommended)
uv run python -m src.cli ingest --config configs/team_alpha.json

# Ask a question
uv run python -m src.cli query --team team-alpha --question "What does function X do?"
```

## Team Config Format

```json
{
  "team_id": "team-alpha",
  "name": "Alpha Team",
  "users": ["alice", "bob"],
  "data": [
    {
      "project_name": "payment-service",
      "repos": ["data/team-alpha/repos/payment-service"],
      "doc_sources": [
        { "type": "local",      "path": "data/team-alpha/docs/payment-service" },
        { "type": "confluence", "url": "https://confluence.company.com/space/PAYMENT" }
      ]
    },
    {
      "project_name": "order-service",
      "repos": ["data/team-alpha/repos/order-service"],
      "doc_sources": [
        { "type": "local",     "path": "data/team-alpha/docs/order-service" },
        { "type": "wikipedia", "url": "https://en.wikipedia.org/wiki/Order_management_system" }
      ]
    }
  ]
}
```

Each entry in `data` is one microservice / project. `project_name` becomes the `project_id`
on every node ingested from that project — enabling filtering by project in addition to team.

Supported `doc_sources` types:
| Type | What it does |
|---|---|
| `local` | Reads `.md`, `.txt`, `README` files from a local folder (Cycle 4) |
| `web` | Fetches and parses a public web page (Cycle 5) |
| `confluence` | Hits Confluence REST API (Cycle 5) |
| `wikipedia` | Fetches and parses a Wikipedia article (Cycle 5) |

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `NEO4J_URI` | Neo4j connection URI | `bolt://localhost:7687` |
| `NEO4J_USER` | Neo4j username | `neo4j` |
| `NEO4J_PASSWORD` | Neo4j password | `password` |
| `OLLAMA_HOST` | Ollama API host | `http://localhost:11434` |
| `OLLAMA_MODEL` | Model to use | `llama3` |
| `EMBEDDING_MODEL` | sentence-transformers model | `all-MiniLM-L6-v2` |
| `DATA_DIR` | Where crawled data is stored | `./data` |

## Adding a New Skill

> Details will be added in Cycle 7.

## Running Tests

```bash
pytest tests/
```
