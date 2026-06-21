# Architecture

## Overview

The system is made of five layers:

```
[ Data Sources ]
      ↓
[ Crawlers & Parsers ]
      ↓
[ Enrichment Pipeline ]  (embeddings, relationship extraction)
      ↓
[ Storage Layer ]        (Graph DB + Vector DB + File Store)
      ↓
[ AI Skills Layer ]      (Claude / Ollama + RAG + Agents)
      ↑
[ User / Developer ]
```

Each layer is containerized. The full system runs locally with Docker Compose.

---

## Company vs Our Stack

| Layer | Company (GCP) | Us (Open Source) |
|---|---|---|
| Code Parsing | Custom + Tree-sitter | Python `ast` module → Tree-sitter (multi-lang later) |
| Embeddings | GCP Vertex AI Embeddings | `sentence-transformers` (local, free) |
| Graph Database | GCP Spanner Graph | Neo4j Community Edition |
| Vector Database | GCP Spanner Graph (built-in) | ChromaDB |
| File/Object Storage | GCP Cloud Storage | Local filesystem → MinIO later |
| LLM | Claude API | Ollama (local) + Claude API (skills) |
| Crawlers | Internal custom | Python (GitPython, requests, BeautifulSoup) |
| Pipeline / Orchestration | Internal | GitHub Actions + Docker Compose |
| Skills / Agents | Claude Code custom skills | Claude Code custom skills (same!) |

---

## Components

### 1. Crawlers

Responsible for pulling raw data from sources.

**Code Crawler**
- Input: local repo path or Git URL
- Uses `GitPython` to clone/pull the repo
- Walks every file in the repo
- Hands `.py` files to the Python AST Parser
- Hands other files (`.md`, `.txt`, `.json`) to the Doc Parser
- Output: raw files saved to local file store, organized by `team_id`

**Doc Crawler**
- Input: URL or file path (Confluence, Jira, Markdown, Wikipedia)
- Uses `requests` + `BeautifulSoup` for web pages
- Reads local `.md` files directly
- Output: raw text content saved to file store

### 2. Parsers

Transform raw content into structured nodes and edges.

**Python AST Parser**
- Uses Python's built-in `ast` module
- Extracts from every `.py` file:
  - Module node
  - Class nodes (name, line numbers, docstring)
  - Function/method nodes (name, parameters, return type if annotated, docstring)
  - Import statements → edges of type `IMPORTS`
  - Function calls inside functions → edges of type `CALLS`
- Output: list of CodeNode objects + list of Edge objects

**Doc Parser**
- Splits documents into chunks (paragraphs or fixed token windows)
- Creates one DocNode per chunk
- Output: list of DocNode objects

### 3. Enrichment Pipeline

Takes parsed nodes and makes them searchable.

**Embedding Generator**
- Uses `sentence-transformers` (model: `all-MiniLM-L6-v2` to start, upgradeable)
- Runs locally, no API calls needed
- For each node: concatenates `name + docstring + raw_source` → generates vector
- Stores the vector back on the node

**Relationship Enricher** (later cycles)
- Resolves import paths to actual nodes
- Links function calls to their definitions
- Creates cross-file edges

### 4. Storage Layer

**Neo4j (Graph Database)**
- Stores all CodeNodes and DocNodes as graph nodes
- Stores all Edges as graph relationships
- Every node has a `team_id` property
- All queries filter by `team_id`
- Runs as a Docker container

**ChromaDB (Vector Database)**
- Stores embeddings for fast similarity search
- Separate collection per team: `team_{team_id}_code`, `team_{team_id}_docs`
- Runs in-process (no separate container needed in early cycles)

**Local Filesystem (File Store)**
- Stores raw crawled files
- Folder structure: `data/{team_id}/repos/`, `data/{team_id}/docs/`

### 5. AI Skills Layer

**RAG Query Skill**
- User asks a question in natural language
- System embeds the question using `sentence-transformers`
- Queries ChromaDB to find top-K most relevant nodes (filtered by `team_id`)
- Optionally: expands results by traversing Neo4j graph (find related nodes)
- Passes all context to Ollama (or Claude API)
- LLM generates a grounded answer
- Returns answer to user

**Impact Analysis Skill** (later cycle)
- User says "I want to change function X"
- System finds X in the graph
- Traverses all `CALLS` and `IMPORTS` edges from X
- Returns all affected classes/functions/files

**Hotfix Agent** (later cycle)
- Full SDLC automation: understand → find impact → change code → push → PR

---

## Team Isolation Design

Every piece of data is tagged with `team_id` at ingestion time.

```
Onboarding Input:
{
  "team_id": "team-alpha",
  "name": "Alpha Team",
  "users": ["alice", "bob"],
  "repos": ["/path/to/repo1", "https://github.com/org/repo2"],
  "doc_sources": ["https://confluence.company.com/alpha", "/path/to/docs"]
}
```

**Storage isolation:**
- ChromaDB: collection named `team_alpha_code` and `team_alpha_docs`
- Neo4j: all nodes have `team_id: "team-alpha"`, all queries use `WHERE n.team_id = $team_id`
- File store: `data/team-alpha/repos/`, `data/team-alpha/docs/`

**Query isolation:**
- Before any query, the system resolves the user → team_id
- All downstream operations are scoped to that team_id
- There is no way to query across teams

---

## Infrastructure

### Local Development
- All components run via `docker-compose.yml`
- One command: `docker compose up` starts everything
- Code lives in `src/`
- Data lives in `data/` (gitignored)

### Containers
| Container | Image | Purpose |
|---|---|---|
| neo4j | `neo4j:community` | Graph database |
| ollama | `ollama/ollama` | Local LLM |
| api | custom Python | FastAPI backend (later cycles) |
| worker | custom Python | Ingestion pipeline worker |

### GitHub Actions
- Trigger: push to `main` or manual dispatch
- Steps: lint → test → build containers → (later) trigger ingestion

---

## AI Concepts This Project Covers

| Concept | Where It Appears |
|---|---|
| RAG (Retrieval Augmented Generation) | Core query skill |
| Knowledge Graphs | Neo4j, node/edge modeling |
| Embeddings & Vector Search | sentence-transformers + ChromaDB |
| LLM Integration | Ollama + Claude API |
| AI Agents | Hotfix agent, PR review agent |
| Code Intelligence | AST parsing, dependency graphs |
| Multi-agent Systems | Multiple skills chained together |
| Data Pipelines for AI | Crawl → Parse → Embed → Ingest |
| Prompt Engineering | Skill prompts, RAG context assembly |
| Tool Use / Function Calling | Agent skills calling graph/vector APIs |
