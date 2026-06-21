# Cycle 2 — Full Repo Crawl

## Goal

Scale from ingesting one file at a time to ingesting an entire Python project
in a single command. Introduce batch embedding and a config-driven ingest pipeline.

---

## What We Actually Built

**Source code (`src/`):**

| Module | What it does |
|---|---|
| `crawlers/repo_walker.py` | Recursively walks a directory using `pathlib.rglob`. Returns all `.py` file paths sorted. Skips `__pycache__`, `.venv`, `.git`, `dist`, `build`, and other non-source directories. |
| `cli.py` (updated) | `ingest` command now supports three modes: `--file` (single file, Cycle 1 behaviour), `--project` (full directory), `--config` (team JSON with multiple repos). |

**Sample data (`data/`):**

| Repo | Type | Files |
|---|---|---|
| `payment-service` | Multi-file uv project | `constants.py`, `exceptions.py`, `processors.py`, `refunds.py`, `utils.py` |
| `order-service` | Single-file demo | `order_service.py` |

**Team config (`configs/team_alpha.json`):**

Both repos are listed under `repos`. Running `ingest --config` processes them
all in one shot — no manual file-by-file commands.

**Tests (`tests/unit/`):**

19 new unit tests for `repo_walker`. Covers happy path (finding files,
subdirectories, sorted output), skip directories (parametrized across all
entries in `SKIP_DIRS`), and error handling (non-existent path, file instead
of directory). Total: 115 tests.

---

## How the Three Ingest Modes Work

```
--file path/to/file.py
    └── parse_file()  →  embed_nodes()  →  store()

--project path/to/dir/
    └── walk_repo()
        ├── file1.py → parse_file() ─┐
        ├── file2.py → parse_file() ─┤→ all nodes → embed_nodes() → store()
        └── file3.py → parse_file() ─┘
            (one batch call, not N separate calls)

--config team_config.json
    └── reads team_id + repos list
        ├── repo1/ → same as --project ──┐
        └── repo2/ → same as --project ──┘→ stored in team collection
```

The key difference from Cycle 1: all nodes from all files are collected first,
then passed to `embed_nodes()` in a single call. One `model.encode()` for the
whole project, not one per file.

---

## Problems We Hit

### Problem 1: uv treated payment-service as a workspace member
**What happened:** Running `uv init` inside `data/team-alpha/repos/payment-service`
automatically added it as a member of the KnowledgeGraph uv workspace, breaking
`uv run pytest`.

**Why it happened:** uv detects parent `pyproject.toml` files and links projects
into a workspace automatically when `uv init` is run in a subdirectory.

**How we fixed it:** Removed the `[tool.uv.workspace]` section that uv had
auto-added to the root `pyproject.toml`. The payment-service is sample data,
not a workspace member.

### Problem 2: ChromaDB HNSW reload noise during query
**What happened:** Running `ingest` showed "Add of existing embedding ID" warnings —
expected and fine. But `query` also showed the same warnings even though query
never calls `collection.add()`.

**Why it happened:** ChromaDB's HNSW index is loaded from SQLite into memory on
every fresh process. During that reload, it logs "Add of existing embedding ID"
for every item it rebuilds in the in-memory index.

**How we fixed it:** Used a `try/finally` block inside `search()` to temporarily
raise the chromadb logger level to ERROR, then restore it. Ingest still shows
its own warnings. Query output is clean.

---

## Key Learnings

- **Batch embedding is faster than N individual calls.** `model.encode()` is
  optimized to process many texts at once using matrix operations on the GPU/CPU.
  Passing 50 texts in one call is significantly faster than 50 calls of 1 text each.

- **`pathlib.rglob("*.py")` does all the recursion for you.** No manual directory
  traversal needed. The only work is filtering out directories you don't want.

- **Skipping the right directories matters.** Without filtering, the repo walker
  would ingest `.venv` (thousands of library files), `__pycache__` (compiled
  bytecode), and `.git` (binary objects). The `SKIP_DIRS` set is the guard.

- **Config-driven ingestion is the right architecture.** Passing `--team` and
  `--file` manually doesn't scale. Reading from a JSON config means the system
  knows everything about a team — repos, doc sources, team ID — from one file.
  This is how the real 40-person system works.

- **Relative imports (`from .constants import ...`) are the correct Python
  package style.** They work regardless of where the package is installed.
  Bare imports (`from constants import ...`) only work when you run from
  exactly the right directory.

---

## Things That Surprised Us

- `uv init` in a subdirectory automatically modifies the parent `pyproject.toml`
  to add a workspace entry. This is uv's workspace feature — powerful for
  monorepos, but not what we wanted here.

- The payment-service split from one file into 5 files actually produced fewer
  nodes than the original (23 vs 15 from the original single file). The original
  had more functions concentrated in one place; splitting added more module-level
  nodes but each module is smaller.

---

## Interview Talking Points

**Q: What is batch embedding and why does it matter?**
A: Instead of calling `model.encode()` once per document, you pass all documents
in a single call. The model processes them in parallel using vectorized operations.
For a repo with 50 functions, batch encoding can be 10-20x faster than 50
individual calls. In production systems at scale, this is the difference between
minutes and hours.

**Q: How does your repo walker know what to skip?**
A: We maintain a `SKIP_DIRS` set containing directory names like `__pycache__`,
`.venv`, `.git`, `dist`, `build`. When `pathlib.rglob` finds a `.py` file, we
check if any of those names appear in the file's path parts. If they do, we skip
it. This prevents ingesting compiled bytecode, library dependencies, or git
internals.

**Q: Why use a JSON config file instead of CLI flags?**
A: A real knowledge graph system handles multiple teams, each with multiple repos
and doc sources. Passing all of that as CLI flags would be unmanageable. The config
file is the team's onboarding record — it captures everything the system needs to
know about a team in one place. Adding a new repo to the team is one JSON edit,
not a new command.

**Q: How does the three-mode CLI design work?**
A: The `ingest` command accepts `--file`, `--project`, or `--config`. All three
converge on the same underlying functions — `walk_repo()` and `parse_file()`.
`--file` skips the walker entirely. `--project` runs the walker on one directory.
`--config` reads the JSON, then runs the walker on each repo in the list. The
storage and embedding logic is identical across all three modes.

---

## What's Next

Cycle 3 introduces Neo4j as a graph database alongside ChromaDB. Every CodeNode
becomes a graph node. Every `import` statement and function call becomes a graph
edge (`IMPORTS`, `CALLS`). This enables a new type of query: not just "what is
most similar to my question?" but "what does changing this function affect?" —
answered by traversing the graph.
