# KnowledgeGraph

An AI-powered Knowledge Graph that ingests code repositories and documentation,
maps every relationship between code entities, and lets developers query it in
natural language.

Built from first principles — no LangChain, no LlamaIndex — so every layer is
understood and explainable.

Inspired by a real 40-person engineering team doing this at scale on GCP.

---

## What We Are Building

```
Developer asks:  "What does the calculate_tax function do?"
                 "If I change PaymentProcessor, what else breaks?"
                 "Fix the null check bug in the payment service."

The system:
  1. Parses every file in every repo into structured nodes
  2. Embeds each node as a vector (semantic meaning as numbers)
  3. Stores nodes in a graph DB (relationships) + vector DB (meaning)
  4. At query time: finds the most relevant nodes, passes them to an LLM
  5. LLM answers from real code — not from training memory
```

This is RAG (Retrieval Augmented Generation) over a code knowledge graph.

---

## The Full Pipeline — How a File Becomes Queryable Knowledge

```
Python file (.py)
      │
      ▼
  AST Parser                    ← Python's built-in `ast` module
  Extracts: MODULE, CLASS,
  FUNCTION nodes
      │
      ▼
  CodeNode (structured data)    ← one object per module / class / function
  ┌─────────────────────────┐
  │ node_id   : MD5 hash    │
  │ team_id   : team-alpha  │
  │ type      : FUNCTION    │
  │ name      : calculate_tax│
  │ file_path : billing.py  │
  │ line_start: 41          │
  │ line_end  : 54          │
  │ docstring : "Calculates…"│
  │ raw_source: "def calc…" │
  └─────────────────────────┘
      │
      ▼
  Embedder                      ← sentence-transformers (all-MiniLM-L6-v2)
  text = name + docstring + raw_source
  vector = model.encode(text)   ← 384 numbers representing semantic meaning
      │
      ▼
  ChromaDB (Vector Database)    ← one collection per team
  collection.add(
    ids        = ["abc123"],           ← stable MD5 node ID
    embeddings = [[0.12, -0.34, …]],  ← 384-dim vector (what gets searched)
    metadatas  = [{"team_id": "team-alpha",
                   "name":    "calculate_tax",
                   "type":    "FUNCTION",
                   "file_path":"billing.py",
                   "docstring":"Calculates tax…"}],
    documents  = ["Calculates tax…"]  ← raw text returned with results
  )
```

At query time, the question is embedded into a vector using the same model,
and ChromaDB finds the stored nodes whose vectors are closest — meaning they
are semantically similar to the question, not just keyword matches.

```
User question: "What does the calculate_tax function do?"
      │
      ▼
  Embed question → query vector
      │
      ▼
  ChromaDB.query(query_vector, n_results=3)
  Returns: top-3 most similar CodeNodes
      │
      ▼
  Build RAG prompt:
  "Answer only from the context below.
   CONTEXT: --- calculate_tax (FUNCTION) --- Calculates GST tax…
   QUESTION: What does calculate_tax do?"
      │
      ▼
  Ollama (local LLM)  →  grounded answer
```

---

## Tech Stack

| Layer | Tool | Why |
|---|---|---|
| Code parsing | Python `ast` module | Built-in, zero install, full Python AST |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`) | Local, free, 384-dim vectors |
| Vector DB | ChromaDB | In-process, no container, SQLite-backed |
| Graph DB | Neo4j Community *(Cycle 3)* | Industry standard for graph data |
| LLM | Ollama (phi, llama3, mistral) | Fully local, zero API cost |
| Crawlers | GitPython, requests, BeautifulSoup *(Cycle 2+)* | Open source, well-supported |
| CLI | Click | Decorator-based commands, auto help text, built-in test runner |
| Packaging | uv + pyproject.toml | Fast installs, locked transitive deps |
| Tests | pytest | Industry standard |

---

## Quick Start

**Prerequisites:** Python 3.12+, [uv](https://docs.astral.sh/uv/), [Ollama](https://ollama.com)

```bash
# Clone and install
git clone <repo-url>
cd KnowledgeGraph
uv sync

# Pull a model into Ollama (one-time)
ollama pull phi
```

---

## CLI Commands

The CLI is built with [Click](https://click.palletsprojects.com/). Every command has a `--help` flag.

```bash
# Show all available commands
uv run python -m src.cli --help

# Show options for a specific command
uv run python -m src.cli ingest --help
uv run python -m src.cli query --help
```

### ingest

Parse a Python file and store its nodes in ChromaDB.

```bash
uv run python -m src.cli ingest \
  --team team-alpha \
  --file data/team-alpha/repos/payment-service/payment_service.py
```

**What it does:**
1. Runs the AST parser on the file — extracts MODULE, CLASS, FUNCTION nodes
2. Embeds each node using sentence-transformers
3. Stores embeddings in the team's ChromaDB collection

**Options:**

| Flag | Required | Description |
|---|---|---|
| `--team` | Yes | Team ID — scopes data to this team |
| `--file` | Yes | Path to the `.py` file to ingest |

---

### query

Search the knowledge graph and get an AI-generated answer.

```bash
uv run python -m src.cli query \
  --team team-alpha \
  --question "What does the calculate_tax function do?"
```

With a different model:

```bash
uv run python -m src.cli query \
  --team team-alpha \
  --question "What does the calculate_tax function do?" \
  --model llama3
```

**What it does:**
1. Embeds the question into a vector
2. Searches ChromaDB for the top-3 most semantically similar nodes
3. Builds a RAG prompt with those nodes as context
4. Sends the prompt to Ollama and prints the grounded answer

**Options:**

| Flag | Required | Default | Description |
|---|---|---|---|
| `--team` | Yes | — | Team ID to search within |
| `--question` | Yes | — | Natural language question |
| `--model` | No | `phi` | Ollama model to use |

---

## Running Tests

```bash
# All unit tests
uv run pytest

# Unit tests only
uv run pytest tests/unit/

# Integration tests (Cycle 2+)
uv run pytest tests/integration/

# Verbose output
uv run pytest -v
```

---

## Project Structure

```
KnowledgeGraph/
├── src/
│   ├── parsers/
│   │   └── ast_parser.py       # AST → CodeNode extraction
│   ├── enrichment/
│   │   └── embedder.py         # CodeNode → vector via sentence-transformers
│   ├── storage/
│   │   └── vector_store.py     # ChromaDB store + search
│   ├── skills/
│   │   └── ollama_client.py    # RAG prompt builder + Ollama HTTP client
│   └── cli.py                  # Click CLI — ingest and query commands
├── tests/
│   ├── conftest.py             # shared fixtures (sample_node)
│   ├── unit/                   # 96 tests, all mocked, fast
│   └── integration/            # real deps, added from Cycle 2
├── configs/
│   └── team_alpha.json         # team registration config
├── data/
│   └── team-alpha/
│       └── repos/
│           └── payment-service/
│               └── payment_service.py   # sample file for Cycle 1
├── docs/
│   ├── DOMAIN.md               # data models, business rules
│   ├── ARCHITECTURE.md         # system design, component breakdown
│   ├── CYCLES.md               # all 11 cycles with done-when criteria
│   ├── PROGRESS.md             # current status and decisions log
│   └── cycles/
│       └── cycle1.md           # journal: what we built, learnings, interview Q&A
├── pyproject.toml              # dependencies + pytest config
└── uv.lock                     # full dependency lock (all 124 packages)
```

---

## The 11 Cycles

| Cycle | What Gets Built | New AI Concept |
|---|---|---|
| **1** ✅ | AST parser, ChromaDB, Ollama, RAG CLI | Embeddings, Vector Search, RAG |
| 2 | Repo walker, GitPython, batch ingest | Batch embeddings, chunking strategy |
| 3 | Neo4j, graph nodes + edges, graph traversal | Knowledge graphs, graph-enhanced RAG |
| 4 | Markdown doc crawler, chunker | Document chunking, mixed search |
| 5 | Web crawler (requests + BeautifulSoup) | Web crawling, HTML parsing |
| 6 | Multi-team registration, isolation proof | Multi-tenancy in AI systems |
| 7 | Docker, Docker Compose | Containerization |
| 8 | GitHub Actions workflow | CI/CD for AI pipelines |
| 9 | Impact analysis via graph traversal | Directed graph analysis |
| 10 | Hotfix agent, tool use, GitHub PR | AI agents, multi-step reasoning |
| 11 | Cloud deployment (optional) | Cloud infrastructure |

---

## Team Isolation Design

Every piece of data is tagged with `team_id` at ingestion time.
There is no way to query across teams.

```
team-alpha  →  ChromaDB collection: "team-alpha"
                Node IDs: MD5(team-alpha :: file :: type :: name)

team-beta   →  ChromaDB collection: "team-beta"
                Node IDs: MD5(team-beta :: file :: type :: name)
```

Same file, different team → completely different node IDs, completely different
collection, zero overlap.
