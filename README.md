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

### Ingestion

```
Python file (.py)
      │
      ▼
  AST Parser (ast_parser.py)           ← Python's built-in `ast` module
  ┌──────────────────────────────────────────────────────┐
  │  Extracts nodes: MODULE, CLASS, FUNCTION             │
  │  Extracts edges: DEFINED_IN, BELONGS_TO,             │
  │                  IMPORTS, INHERITS, CALLS            │
  └──────────────────────────────────────────────────────┘
      │                          │
      │ CodeNodes                │ Edges
      ▼                          │
  CodeNode (structured data)     │     ← one object per module / class / function
  ┌─────────────────────────┐    │
  │ node_id   : MD5 hash    │    │
  │ team_id   : team-alpha  │    │
  │ type      : FUNCTION    │    │
  │ name      : calculate_tax│   │
  │ file_path : billing.py  │    │
  │ line_start: 41          │    │
  │ line_end  : 54          │    │
  │ docstring : "Calculates…"│   │
  │ raw_source: "def calc…" │    │
  └─────────────────────────┘    │
      │                          │
      ▼                          ▼
  Embedder                   Neo4j (Graph Database)
  (sentence-transformers)    ┌─────────────────────────────────────────┐
  text = name+docstring+src  │  Node label: :CodeNode                  │
  vector = model.encode(text)│  Properties:                            │
      │                      │    node_id   : "a3f9…" (MD5)           │
      ▼                      │    team_id   : "team-alpha"             │
  ChromaDB (Vector DB)       │    type      : "FUNCTION"               │
  collection.add(            │    name      : "calculate_tax"          │
    ids   = ["a3f9…"],       │    file_path : "processors.py"          │
    embeddings = [[…]],      │    docstring : "Calculates GST tax…"    │
    metadatas  = [{…}],      │    raw_source: "def calculate_tax(…)"   │
    documents  = ["…"]       │    line_start: 41                       │
  )                          │    line_end  : 54                       │
                             └─────────────────────────────────────────┘
                                              │
                             Edges are stored as Neo4j relationships.
                             Each relationship has:
                               - a TYPE  (the edge label, e.g. CALLS)
                               - a direction  (from node → to node)
                               - one property: team_id

  DEFINED_IN : (calculate_tax:CodeNode)    -[:DEFINED_IN {team_id}]-> (processors:CodeNode)
  BELONGS_TO : (calculate_tax:CodeNode)    -[:BELONGS_TO {team_id}]-> (PaymentProcessor:CodeNode)
  IMPORTS    : (processors:CodeNode)       -[:IMPORTS    {team_id}]-> (constants:CodeNode)
  INHERITS   : (RefundProcessor:CodeNode)  -[:INHERITS   {team_id}]-> (PaymentProcessor:CodeNode)
  CALLS      : (process_payment:CodeNode)  -[:CALLS      {team_id}]-> (calculate_tax:CodeNode)
```

Every node lands in **both** databases:
- **ChromaDB** — stores the vector so you can find it by semantic meaning
- **Neo4j** — stores the node and all its edges so you can traverse relationships

### Query (Graph-Enhanced RAG)

```
User question: "What does the calculate_tax function do?"
      │
      ▼
  Embed question → query vector
      │
      ▼
  ChromaDB.query(query_vector, n_results=3)
  Returns: top-3 most semantically similar CodeNodes
      │
      ▼
  Neo4j.get_neighbors(those 3 node_ids)       ← NEW in Cycle 3
  Returns: all nodes directly connected by edges
  e.g. "process_payment CALLS calculate_tax"
       → process_payment is added to context
      │
      ▼
  Combined context = ChromaDB results + graph neighbors
      │
      ▼
  Build RAG prompt:
  "Answer only from the context below.
   CONTEXT: --- calculate_tax (FUNCTION) --- Calculates GST tax…
             --- process_payment (FUNCTION) --- Calls calculate_tax…
   QUESTION: What does calculate_tax do?"
      │
      ▼
  Ollama (local LLM)  →  richer, more grounded answer
```

---

## Knowledge Graph — Nodes and Edges

Every Python file is parsed into **nodes** (things) and **edges** (relationships between things).

### Node Types

| Type | What it represents | Example |
|---|---|---|
| `MODULE` | One `.py` file as a whole | `billing.py` |
| `CLASS` | A class definition | `class PaymentProcessor` |
| `FUNCTION` | A top-level function or method | `def calculate_tax` / `PaymentProcessor.apply_tax` |

### Edge Types

| Edge | From | To | Built from |
|---|---|---|---|
| `DEFINED_IN` | CLASS or FUNCTION | MODULE | Every class and function is defined in the file's module |
| `BELONGS_TO` | FUNCTION (method) | CLASS | A method found inside a class body belongs to that class |
| `IMPORTS` | MODULE | MODULE | `from .constants import X` — source file imports target file |
| `INHERITS` | CLASS | CLASS (parent) | `class Child(Base):` — child inherits from parent |
| `CALLS` | FUNCTION | FUNCTION | A function call found inside a function body |

### Example: payment-service graph

```
processors.py (MODULE)
    │
    ├─[DEFINED_IN]── PaymentProcessor (CLASS)
    │                     │
    │                     ├─[BELONGS_TO]── PaymentProcessor.calculate_tax (FUNCTION)
    │                     │
    │                     └─[BELONGS_TO]── PaymentProcessor.process_payment (FUNCTION)
    │                                           │
    │                                           └─[CALLS]── PaymentProcessor.calculate_tax
    │
    └─[IMPORTS]──────── constants.py (MODULE)
```

This graph is what powers impact analysis: given `calculate_tax`, traverse
all incoming `CALLS` edges to find every function that depends on it.

---

## Tech Stack

| Layer | Tool | Why |
|---|---|---|
| Code parsing | Python `ast` module | Built-in, zero install, full Python AST |
| Embeddings | sentence-transformers (`all-MiniLM-L6-v2`) | Local, free, 384-dim vectors |
| Vector DB | ChromaDB | In-process, no container, SQLite-backed |
| Graph DB | Neo4j Community *(Cycle 3)* | Industry standard for graph data |
| LLM | Ollama (phi, llama3, mistral) | Fully local, zero API cost |
| Repo Walker | Python `pathlib` | Recursive `.py` file discovery, skips venv/.git/pycache |
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

# Start Neo4j (required from Cycle 3 onwards)
docker compose up -d

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

Three modes — single file, full project directory, or team config.

**Mode 1 — single file:**

```bash
uv run python -m src.cli ingest \
  --team team-alpha \
  --file data/team-alpha/repos/order-service/order_service.py
```

**Mode 2 — full project directory:**

```bash
uv run python -m src.cli ingest \
  --team team-alpha \
  --project data/team-alpha/repos/payment-service
```

Walks the directory recursively, finds every `.py` file, parses them all,
batch embeds all nodes in a single model call, and stores everything.

**Mode 3 — team config (all repos at once):**

```bash
uv run python -m src.cli ingest --config configs/team_alpha.json
```

Reads `team_id` and `repos` list from the JSON config.
Runs the project walker on each repo automatically.

**What all modes do:**
1. Runs the AST parser — extracts MODULE, CLASS, FUNCTION nodes and all edges per file
2. Batch embeds all nodes in one `model.encode()` call
3. Stores embeddings in the team's ChromaDB collection (vector search)
4. Stores nodes and edges in Neo4j (graph traversal)

**Options:**

| Flag | Requires | Description |
|---|---|---|
| `--file <path>` | `--team` | Ingest a single `.py` file |
| `--project <dir>` | `--team` | Ingest all `.py` files in a directory |
| `--config <json>` | — | Read team config, ingest all repos listed |

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
3. Calls Neo4j to find all nodes connected to those 3 (graph neighbors)
4. Builds a RAG prompt combining both sets — vector matches + graph neighbors
5. Sends the prompt to Ollama and prints the grounded answer

**Options:**

| Flag | Required | Default | Description |
|---|---|---|---|
| `--team` | Yes | — | Team ID to search within |
| `--question` | Yes | — | Natural language question |
| `--model` | No | `phi` | Ollama model to use |

---

### impact

Find everything that depends on a given function or class — pure graph traversal.

```bash
uv run python -m src.cli impact \
  --team team-alpha \
  --target "PaymentProcessor.calculate_tax"
```

**What it does:**
1. Finds the target node in Neo4j by name
2. Traverses all incoming `CALLS` and `IMPORTS` edges
3. Returns every function that calls it and every module that imports it

**Example output:**
```
Analysing impact of: PaymentProcessor.calculate_tax

Found 2 dependent(s):

  [CALLS]  PaymentProcessor.process_payment  (FUNCTION)  —  processors.py
  [CALLS]  PaymentProcessor.apply_tax        (FUNCTION)  —  processors.py
```

**Options:**

| Flag | Required | Description |
|---|---|---|
| `--team` | Yes | Team ID to search within |
| `--target` | Yes | Function or class name to analyse |

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
│   ├── crawlers/
│   │   └── repo_walker.py      # recursive .py file discovery, skips venv/.git
│   ├── parsers/
│   │   └── ast_parser.py       # AST → CodeNode + Edge extraction
│   ├── enrichment/
│   │   └── embedder.py         # CodeNode → vector via sentence-transformers
│   ├── storage/
│   │   ├── vector_store.py     # ChromaDB store + search
│   │   └── graph_store.py      # Neo4j store_nodes + store_edges (Cycle 3)
│   ├── skills/
│   │   └── ollama_client.py    # RAG prompt builder + Ollama HTTP client
│   └── cli.py                  # Click CLI — ingest (3 modes), query, impact
├── tests/
│   ├── conftest.py             # shared fixtures (sample_node)
│   ├── unit/                   # all mocked, fast
│   └── integration/            # real deps, added from Cycle 3
├── configs/
│   └── team_alpha.json         # team config — repos and doc_sources list
├── data/
│   └── team-alpha/
│       └── repos/
│           ├── payment-service/    # multi-file uv project (5 modules)
│           │   ├── constants.py
│           │   ├── exceptions.py
│           │   ├── processors.py
│           │   ├── refunds.py
│           │   └── utils.py
│           └── order-service/
│               └── order_service.py  # standalone single-file demo
├── docs/
│   ├── DOMAIN.md               # data models, business rules
│   ├── ARCHITECTURE.md         # system design, component breakdown
│   ├── CYCLES.md               # all 11 cycles with done-when criteria
│   ├── PROGRESS.md             # current status and decisions log
│   └── cycles/
│       ├── cycle1.md           # journal: what we built, learnings, interview Q&A
│       └── cycle2.md           # journal: repo walker, batch ingest, problems hit
├── docker-compose.yml          # Neo4j container (Cycle 3)
├── pyproject.toml              # dependencies + pytest config
└── uv.lock                     # full dependency lock (all 124 packages)
```

---

## The 11 Cycles

| Cycle | What Gets Built | New AI Concept |
|---|---|---|
| **1** ✅ | AST parser, ChromaDB, Ollama, RAG CLI | Embeddings, Vector Search, RAG |
| **2** ✅ | Repo walker, batch ingest, 3-mode CLI (`--file` / `--project` / `--config`) | Batch embeddings, chunking strategy |
| **3** ✅ | Neo4j, graph nodes + edges, graph-enhanced RAG, impact query | Knowledge graphs, graph traversal |
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
