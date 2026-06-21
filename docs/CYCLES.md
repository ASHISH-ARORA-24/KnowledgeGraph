# Development Cycles

## Rules

- Every cycle must leave the system fully working
- Each cycle adds exactly one new concept
- Never break what was built in a previous cycle
- Build raw — no LangChain, no LlamaIndex
- Team isolation (`team_id`) is present from Cycle 1 onwards

---

## Cycle 1 — The Core: One File, Ask a Question

**Goal:** Parse one Python file, embed it, store it, and ask a natural language question about it via CLI.

**What gets built:**
- Team config (JSON file with team_id, users, repo path)
- Python `ast` parser for one `.py` file — extracts modules, classes, functions, docstrings
- Embedding generator using `sentence-transformers` (`all-MiniLM-L6-v2`)
- ChromaDB vector store (runs in-process, no container needed)
- Ollama integration (local LLM, e.g. `llama3`)
- RAG query pipeline (embed question → search ChromaDB → send context to Ollama → return answer)
- CLI command: `python -m src.cli query --team <team_id> --question "..."`

**What is NOT built yet:**
- No full repo crawl (just one file)
- No Neo4j / graph
- No doc ingestion
- No web crawling

**Team isolation:**
- ChromaDB collection named `{team_id}_code`
- All nodes tagged with `team_id`
- Query always filtered by `team_id`

**Done when:**
You run `python -m src.cli query --team team-alpha --question "What does the calculate_tax function do?"` and get a grounded answer from the actual code in that file.

**AI concepts introduced:**
- Embeddings — turning text/code into vectors
- Vector search — finding similar content by meaning, not keywords
- RAG (Retrieval Augmented Generation) — grounding LLM answers in real data

---

## Cycle 2 — Full Repo Crawl

**Goal:** Scale from one file to an entire Python repository.

**What gets built:**
- Repo walker — recursively walks a directory, finds all `.py` files
- GitPython integration — clone a repo from a GitHub URL before walking
- Batch embedding — embed all files efficiently
- Updated CLI: `python -m src.cli ingest --team <team_id> --repo <path_or_url>`

**What changes from Cycle 1:**
- Ingestion now handles N files instead of 1
- Embeddings generated in batches for performance

**Done when:**
You point the system at a real GitHub repo, it clones and indexes it, and you can ask questions about any function or class across all files.

**AI concepts introduced:**
- Batch processing for embeddings
- Chunking strategy (one node per function/class vs. one node per file)

---

## Cycle 3 — Knowledge Graph (Neo4j)

**Goal:** Move from pure vector search to a graph-backed system. Store relationships between code entities and use them to enrich answers.

**What gets built:**
- Neo4j Community Edition (first Docker container)
- Graph ingestion — every CodeNode becomes a graph node, every relationship (CALLS, IMPORTS, DEFINED_IN) becomes an edge
- Graph-enhanced RAG — after vector search finds top-K nodes, traverse their edges in Neo4j to pull in related nodes as additional context
- Impact query: "What does changing function X affect?" — pure graph traversal answer

**What changes from Cycle 2:**
- Storage now has two layers: ChromaDB (find by meaning) + Neo4j (find by relationship)
- Query pipeline adds a graph expansion step after vector search

**Done when:**
You ask "if I change class Y, what else might break?" and get a list of all functions that call it and all files that import it — derived from graph traversal, not guesswork.

**AI concepts introduced:**
- Knowledge graphs — nodes and edges as a data model
- Graph traversal — walking relationships to discover connected information
- Graph-enhanced RAG — combining semantic search with structural relationships

---

## Cycle 4 — Markdown and README Docs

**Goal:** Ingest documentation files alongside code so answers can combine both.

**What gets built:**
- Doc crawler for local `.md`, `.txt`, `README` files
- Doc chunker — splits documents by heading or paragraph (not by code structure)
- DocNodes in ChromaDB and Neo4j alongside CodeNodes
- Mixed search — one query searches both code and docs, returns the most relevant mix

**Done when:**
You ask "how do I use the payment module?" and the answer combines the docstring from the code AND the explanation from the README.

**AI concepts introduced:**
- Document chunking strategies — how to split text for embedding
- Mixed modality search — searching across different types of content in one query

---

## Cycle 5 — Web Crawler

**Goal:** Ingest live web pages as documentation sources (public wikis, API docs, Wikipedia).

**What gets built:**
- Web crawler using `requests` + `BeautifulSoup`
- URL-based doc ingestion — team config can now include URLs, not just local paths
- HTML → clean text extraction
- Same DocNode pipeline as Cycle 4

**Done when:**
You add a Wikipedia URL or a public docs URL to the team config and the system indexes it automatically on onboarding.

**AI concepts introduced:**
- Web crawling — fetching and parsing live web content
- HTML cleaning — extracting meaningful text from raw HTML

---

## Cycle 6 — Multi-Team Isolation

**Goal:** Register two teams with different repos and prove that their data is completely separate.

**What gets built:**
- Team registration CLI: `python -m src.cli register --config team_config.json`
- User → team mapping (simple JSON config)
- Isolation proof: query as User A → only see Team A data; query as User B → only see Team B data

**Done when:**
Two teams are registered with different repos. A query from Team A returns zero results from Team B's codebase, and vice versa.

**AI concepts introduced:**
- Multi-tenancy in AI systems — data isolation by namespace
- This is a system design concept, not a pure AI concept — important for interviews

---

## Cycle 7 — Docker and Docker Compose

**Goal:** Containerize the entire system so it starts with one command.

**What gets built:**
- `Dockerfile` for the Python app (crawler, parser, CLI, API)
- `docker-compose.yml` with services: `neo4j`, `ollama`, `app`
- Environment variable configuration via `.env` file
- One command to start everything: `docker compose up`

**Done when:**
Fresh machine, run `docker compose up`, run the ingest command, ask a question — everything works without manual setup.

**Concepts introduced:**
- Containerization — packaging an app and its dependencies
- Docker Compose — orchestrating multiple containers locally
- Environment-based config — keeping secrets and config out of code

---

## Cycle 8 — GitHub Actions Pipeline

**Goal:** Automatically re-ingest a repo whenever code is pushed to it.

**What gets built:**
- GitHub Actions workflow (`.github/workflows/ingest.yml`)
- Triggered on push to `main`
- Pipeline steps: pull latest code → run ingest → update knowledge graph

**Done when:**
Push a code change to a repo → the knowledge graph updates automatically without any manual command.

**Concepts introduced:**
- CI/CD pipelines for AI systems
- Event-driven ingestion — keeping the knowledge graph fresh

---

## Cycle 9 — Impact Analysis Skill

**Goal:** Given a function or class, find everything in the codebase that would be affected by changing it.

**What gets built:**
- Impact analysis query: traverses all `CALLS` and `IMPORTS` edges from a given node
- Returns a ranked list: direct callers, indirect callers, files that import the module
- CLI: `python -m src.cli impact --team <team_id> --target "ClassName.method_name"`

**Done when:**
You name a function, and the system returns a complete map of every place in the codebase that depends on it — traced through the graph.

**Concepts introduced:**
- Directed graph traversal for software analysis
- This mirrors exactly what the company system does for hotfix scoping

---

## Cycle 10 — Hotfix Agent

**Goal:** Multi-step AI agent that takes a plain-English hotfix request and executes the full SDLC flow.

**What gets built:**
- Hotfix skill prompt — instructs the LLM to reason step by step
- Tool use — LLM calls: `search_code`, `get_impact`, `read_file`, `write_file`, `create_pr`
- GitHub API integration — creates a real pull request with the suggested change
- (Optional) PR review agent — second LLM call reviews the diff before merging

**Flow:**
1. User: "Fix the null check bug in the payment service"
2. Agent searches knowledge graph for relevant code
3. Agent runs impact analysis
4. Agent suggests (or makes) the code change
5. Agent creates a GitHub PR
6. PR review agent reviews and comments

**Done when:**
You describe a bug in plain English and the system creates a GitHub PR with a proposed fix.

**Concepts introduced:**
- AI agents — LLM that takes actions, not just answers
- Tool use / function calling — LLM decides which tools to call
- Multi-step reasoning — chaining actions to complete a complex task
- This is the most advanced concept in the project and directly mirrors the company system

---

## Cycle 11 — Cloud Migration (Optional)

**Goal:** Move the local system to a cloud provider.

**What changes:**
- Local filesystem → AWS S3 or GCP Cloud Storage
- Local Neo4j → Neo4j Aura free tier or self-hosted VM
- Local Ollama → keep Ollama on VM, or switch to Claude API
- Docker Compose → Kubernetes or Cloud Run (or keep Compose on a VM)

**Done when:**
The system runs on a cloud VM, accessible from anywhere, with no local dependencies.

---

## Summary Table

| Cycle | New Component | New AI Concept |
|---|---|---|
| 1 | AST parser, ChromaDB, Ollama, RAG CLI | Embeddings, Vector Search, RAG |
| 2 | Repo walker, GitPython, batch ingest | Batch embeddings, chunking |
| 3 | Neo4j, graph nodes/edges, graph traversal | Knowledge graphs, graph-enhanced RAG |
| 4 | Markdown doc crawler, chunker | Document chunking, mixed search |
| 5 | Web crawler (requests + BeautifulSoup) | Web crawling, HTML parsing |
| 6 | Multi-team registration, isolation proof | Multi-tenancy in AI systems |
| 7 | Docker, Docker Compose | Containerization |
| 8 | GitHub Actions workflow | CI/CD for AI pipelines |
| 9 | Impact analysis via graph traversal | Directed graph analysis |
| 10 | Hotfix agent, tool use, GitHub PR | AI agents, tool use, multi-step reasoning |
| 11 | Cloud deployment (optional) | Cloud infrastructure |
