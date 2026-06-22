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
     (each node tagged with team_id + project_id for isolation)
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
  AST Parser (ast_parser.py)           <- Python's built-in `ast` module
  ┌──────────────────────────────────────────────────────┐
  │  Extracts nodes: MODULE, CLASS, FUNCTION             │
  │  Extracts edges: DEFINED_IN, BELONGS_TO,             │
  │                  IMPORTS, INHERITS, CALLS            │
  └──────────────────────────────────────────────────────┘
      │                          │
      │ CodeNodes                │ Edges
      ▼                          │
  CodeNode (structured data)     │     <- one object per module / class / function
  ┌──────────────────────────┐   │
  │ node_id    : MD5 hash    │   │
  │ team_id    : team-alpha  │   │
  │ project_id : payment-svc │   │
  │ type       : FUNCTION    │   │
  │ name       : calc_tax    │   │
  │ file_path  : billing.py  │   │
  │ line_start : 41          │   │
  │ line_end   : 54          │   │
  │ docstring  : "Calcs..."  │   │
  │ raw_source : "def cal..."│   │
  └──────────────────────────┘   │
      │                          │
      ▼                          ▼
  Embedder                   Neo4j (Graph Database)
  (sentence-transformers)    ┌──────────────────────────────────────────┐
  text = name+docstring+src  │  Node label: :CodeNode                   │
  vector = model.encode(text)│  Properties:                             │
      │                      │    node_id    : "a3f9..." (MD5)          │
      ▼                      │    team_id    : "team-alpha"             │
  ChromaDB (Vector DB)       │    project_id : "payment-service"        │
  collection.add(            │    type       : "FUNCTION"               │
    ids        = ["a3f9..."],│    name       : "calculate_tax"          │
    embeddings = [[...]],    │    file_path  : "processors.py"          │
    metadatas  = [{          │    docstring  : "Calculates GST tax..."  │
      team_id,               │    raw_source : "def calculate_tax(...)" │
      project_id,            │    line_start : 41                       │
      name, type,            │    line_end   : 54                       │
      file_path, docstring   └──────────────────────────────────────────┘
    }],                                       │
    documents  = ["..."]     Edges are stored as Neo4j relationships.
  )                          Each relationship has:
                               - a TYPE       (the edge label, e.g. CALLS)
                               - a direction  (from node -> to node)
                               - properties:  team_id, project_id

  DEFINED_IN : (calculate_tax)   -[:DEFINED_IN {team_id, project_id}]-> (processors)
  BELONGS_TO : (calculate_tax)   -[:BELONGS_TO {team_id, project_id}]-> (PaymentProcessor)
  IMPORTS    : (processors)      -[:IMPORTS    {team_id, project_id}]-> (constants)
  INHERITS   : (RefundProcessor) -[:INHERITS   {team_id, project_id}]-> (PaymentProcessor)
  CALLS      : (process_payment) -[:CALLS      {team_id, project_id}]-> (calculate_tax)
```

Every node lands in **both** databases:
- **ChromaDB** — stores the vector so you can find it by semantic meaning
- **Neo4j** — stores the node and all its edges so you can traverse relationships

### Query (Graph-Enhanced RAG)

```
User question: "What does the calculate_tax function do?"
      │
      ▼
  Embed question -> query vector
      │
      ▼
  ChromaDB.query(query_vector, n_results=3)
  Returns: top-3 most semantically similar CodeNodes
      │
      ▼
  Neo4j.get_neighbors(those 3 node_ids)       <- added in Cycle 3
  Returns: all nodes directly connected by edges
  e.g. "process_payment CALLS calculate_tax"
       -> process_payment is added to context
      │
      ▼
  Combined context = ChromaDB results + graph neighbors
      │
      ▼
  Build RAG prompt:
  "Answer only from the context below.
   CONTEXT: --- calculate_tax (FUNCTION) [vector match] --- Calculates GST tax...
             --- process_payment (FUNCTION) [graph neighbor via CALLS] ---
   QUESTION: What does calculate_tax do?"
      │
      ▼
  Ollama (local LLM)  ->  richer, more grounded answer
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

### Common Node Properties

Every node — regardless of type — carries these fields in both ChromaDB and Neo4j:

| Property | Description | Example |
|---|---|---|
| `node_id` | MD5 hash — globally unique identifier | `"a3f9c2..."` |
| `team_id` | Which team this node belongs to | `"team-alpha"` |
| `project_id` | Which microservice / repo this node came from | `"payment-service"` |
| `type` | Node type: MODULE, CLASS, or FUNCTION | `"FUNCTION"` |
| `name` | Name of the entity | `"PaymentProcessor.calculate_tax"` |
| `file_path` | Source file path | `"processors.py"` |
| `line_start` | Line number where entity starts | `41` |
| `line_end` | Line number where entity ends | `54` |
| `docstring` | Extracted docstring (empty string if none) | `"Calculates GST..."` |
| `raw_source` | The actual source code of the entity | `"def calculate_tax..."` |

`team_id` + `project_id` together enable two levels of isolation:
- **Team level** — a developer can only see their own team's data
- **Project level** — within a team, you can scope queries to one microservice

The `node_id` is computed as `MD5(team_id :: project_id :: file_path :: type :: name)` — so the
same function in two different projects or teams always produces a different node ID.

### Edge Types

| Edge | From | To | Built from |
|---|---|---|---|
| `DEFINED_IN` | CLASS or FUNCTION | MODULE | Every class and function is defined in the file's module |
| `BELONGS_TO` | FUNCTION (method) | CLASS | A method found inside a class body belongs to that class |
| `IMPORTS` | MODULE | MODULE | `from .constants import X` — source file imports target file |
| `INHERITS` | CLASS | CLASS (parent) | `class Child(Base):` — child inherits from parent |
| `CALLS` | FUNCTION | FUNCTION | A function call found inside a function body |

Every edge also carries `team_id` and `project_id` as properties so graph traversal
always stays within the correct team and project boundary.

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
| Graph DB | Neo4j Community | Industry standard for graph data |
| LLM | Ollama (phi, llama3, mistral) | Fully local, zero API cost |
| Repo Walker | Python `pathlib` | Recursive `.py` file discovery, skips venv/.git/pycache |
| CLI | Click | Decorator-based commands, auto help text, built-in test runner |
| Packaging | uv + pyproject.toml | Fast installs, locked transitive deps |
| Tests | pytest | Industry standard |

---

## Quick Start

**Prerequisites:** Python 3.12+, [uv](https://docs.astral.sh/uv/), [Ollama](https://ollama.com), Docker

```bash
# Clone and install
git clone <repo-url>
cd KnowledgeGraph
uv sync

# Start all services (Neo4j)
make service-start

# Pull a model into Ollama (one-time)
ollama pull phi
```

---

## Make Commands

```bash
make help                       # list all available commands
make service-start              # start all services in background
make service-start s=neo4j      # start a specific service
make service-stop               # stop all services
make service-stop s=neo4j       # stop a specific service
make service-restart            # restart all services
make service-restart s=neo4j    # restart a specific service
make service-status             # show status of all services
make clean                      # stop all services and delete all data + volumes
```

---

## CLI Commands

The CLI is built with [Click](https://click.palletsprojects.com/). Every command has a `--help` flag.

```bash
uv run python -m src.cli --help
uv run python -m src.cli ingest --help
uv run python -m src.cli query --help
```

### ingest

Three modes — single file, full project directory, or team config.

**Mode 1 — single file:**

```bash
uv run python -m src.cli ingest \
  --team team-alpha \
  --project-id payment-service \
  --file data/team-alpha/repos/payment-service/processors.py
```

**Mode 2 — full project directory:**

```bash
uv run python -m src.cli ingest \
  --team team-alpha \
  --project-id payment-service \
  --project data/team-alpha/repos/payment-service
```

Walks the directory recursively, finds every `.py` file, parses them all,
batch embeds all nodes in a single model call, and stores everything.

**Mode 3 — team config (recommended, all projects at once):**

```bash
uv run python -m src.cli ingest --config configs/team_alpha.json
```

Reads `team_id` and the `data` array from the JSON config. Each entry in `data`
is one project/microservice with its own `project_name` and `repos` list.
`project_name` becomes the `project_id` on every node from that project.

**What all modes do:**
1. Runs the AST parser — extracts MODULE, CLASS, FUNCTION nodes and all edges per file
2. Batch embeds all nodes in one `model.encode()` call
3. Stores embeddings + metadata (including `project_id`) in ChromaDB
4. Stores nodes and edges (including `project_id`) in Neo4j

**Options:**

| Flag | Requires | Description |
|---|---|---|
| `--file <path>` | `--team` | Ingest a single `.py` file |
| `--project <dir>` | `--team` | Ingest all `.py` files in a directory |
| `--project-id <id>` | `--file` or `--project` | Project / microservice name (default: `"default"`) |
| `--config <json>` | — | Read team config, ingest all projects listed |

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
2. Searches ChromaDB for the top-3 most semantically similar nodes — scoped to `team_id`
3. Calls Neo4j to find all nodes connected to those 3 (graph neighbors) — scoped to `team_id`
4. Builds a RAG prompt combining both sets — vector matches + graph neighbors
5. Sends the prompt to Ollama and prints the grounded answer

All results are automatically scoped to the team. Project-level filtering (`--project-id`)
will be added in a future cycle.

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
1. Finds the target node in Neo4j by name — scoped to `team_id`
2. Traverses all incoming `CALLS` and `IMPORTS` edges — scoped to `team_id` and `project_id`
3. Returns every function that calls it and every module that imports it

**Example output:**
```
Analysing impact of: PaymentProcessor.calculate_tax

Found 2 dependent(s):

  [CALLS]  PaymentProcessor.process_payment  (FUNCTION)  --  processors.py
  [CALLS]  PaymentProcessor.apply_tax        (FUNCTION)  --  processors.py
```

**Options:**

| Flag | Required | Description |
|---|---|---|
| `--team` | Yes | Team ID to search within |
| `--target` | Yes | Function or class name to analyse |

---

## Running Tests

```bash
# All unit tests (no services needed)
uv run pytest tests/unit/

# Integration tests (requires Neo4j running)
make service-start
uv run pytest tests/integration/

# Everything
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
│   │   └── ast_parser.py       # AST -> CodeNode + Edge extraction
│   ├── enrichment/
│   │   └── embedder.py         # CodeNode -> vector via sentence-transformers
│   ├── storage/
│   │   ├── vector_store.py     # ChromaDB store + search
│   │   └── graph_store.py      # Neo4j store_nodes + store_edges
│   ├── skills/
│   │   └── ollama_client.py    # RAG prompt builder + Ollama HTTP client
│   └── cli.py                  # Click CLI -- ingest (3 modes), query, impact
├── tests/
│   ├── conftest.py             # shared fixtures (sample_node)
│   ├── unit/                   # all mocked, fast, no services needed
│   └── integration/            # hits real Neo4j
├── configs/
│   └── team_alpha.json         # team config -- projects, repos, typed doc_sources
├── data/
│   └── team-alpha/
│       ├── repos/
│       │   ├── payment-service/    # multi-file Python project
│       │   └── order-service/      # single-file demo
│       └── docs/
│           ├── payment-service/    # local docs for payment-service
│           └── order-service/      # local docs for order-service
├── docs/
│   ├── DOMAIN.md               # data models, business rules
│   ├── ARCHITECTURE.md         # system design, component breakdown
│   ├── CYCLES.md               # all 11 cycles with done-when criteria
│   ├── PROGRESS.md             # current status and decisions log
│   └── cycles/
│       ├── cycle1.md           # journal: what we built, learnings, interview Q&A
│       ├── cycle2.md           # journal: repo walker, batch ingest, problems hit
│       └── cycle3.md           # journal: Neo4j, graph-enhanced RAG, impact analysis
├── Makefile                    # service management commands
├── docker-compose.yml          # Neo4j container
├── pyproject.toml              # dependencies + pytest config
└── uv.lock                     # full dependency lock
```

---

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

Each entry in `data` is one microservice / project. `project_name` becomes the
`project_id` on every node ingested from that project.

Supported `doc_sources` types:

| Type | Handled in | What it does |
|---|---|---|
| `local` | Cycle 4 | Reads `.md`, `.txt`, `README` files from a local folder |
| `web` | Cycle 5 | Fetches and parses a public web page |
| `confluence` | Cycle 5 | Hits Confluence REST API |
| `wikipedia` | Cycle 5 | Fetches and parses a Wikipedia article |

---

## Team and Project Isolation

Every node carries both `team_id` and `project_id`. There is no way to query across teams.
Within a team, you can filter to a specific project.

```
Node ID = MD5(team_id :: project_id :: file_path :: node_type :: name)

team-alpha / payment-service  ->  ChromaDB collection: "team-alpha"
                                  node_id: MD5(team-alpha::payment-service::...)

team-alpha / order-service    ->  ChromaDB collection: "team-alpha"
                                  node_id: MD5(team-alpha::order-service::...)

team-beta  / payment-service  ->  ChromaDB collection: "team-beta"
                                  node_id: MD5(team-beta::payment-service::...)
```

Same file name, different team or different project — completely different node IDs, zero overlap.

---

## The 11 Cycles

| Cycle | What Gets Built | New AI Concept |
|---|---|---|
| **1** done | AST parser, ChromaDB, Ollama, RAG CLI | Embeddings, Vector Search, RAG |
| **2** done | Repo walker, batch ingest, 3-mode CLI | Batch embeddings, chunking strategy |
| **3** done | Neo4j, graph nodes + edges, graph-enhanced RAG, impact query | Knowledge graphs, graph traversal |
| 4 | Markdown doc crawler, chunker, mixed search | Document chunking, mixed modality search |
| 5 | Web crawler (requests + BeautifulSoup) | Web crawling, HTML parsing |
| 6 | Multi-team registration, isolation proof | Multi-tenancy in AI systems |
| 7 | Docker, Docker Compose | Containerization |
| 8 | GitHub Actions workflow | CI/CD for AI pipelines |
| 9 | Impact analysis skill (advanced) | Directed graph analysis |
| 10 | Hotfix agent, tool use, GitHub PR | AI agents, multi-step reasoning |
| 11 | Cloud deployment (optional) | Cloud infrastructure |
