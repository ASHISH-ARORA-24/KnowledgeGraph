# Cycle 1 — Foundation: One File, Ask a Question

## Goal

Parse one Python file, embed it, store it in ChromaDB, and answer a natural language
question about it via CLI — the smallest possible end-to-end RAG pipeline.

---

## What We Actually Built

**Source code (`src/`):**

| Module | What it does |
|---|---|
| `parsers/ast_parser.py` | Parses a `.py` file using Python's built-in `ast` module. Extracts MODULE, CLASS, and FUNCTION nodes with docstrings, line numbers, and raw source. Each node gets a stable MD5 ID scoped to `team_id`. |
| `enrichment/embedder.py` | Loads `all-MiniLM-L6-v2` from sentence-transformers. Concatenates `name + docstring + raw_source` for each node and runs `model.encode()` to produce a 384-dimensional vector. |
| `storage/vector_store.py` | Wraps ChromaDB. `store()` persists nodes into a per-team collection. `search()` embeds a query and returns the top-K most semantically similar nodes. |
| `skills/ollama_client.py` | Builds a RAG prompt by injecting retrieved node context. Calls the local Ollama HTTP API and returns the generated answer. |
| `cli.py` | Two commands: `ingest` (parse + embed + store) and `query` (search + prompt + answer). |

**Tests (`tests/unit/`):**

97 unit tests across 5 files. Every external dependency (ChromaDB, sentence-transformers
model, requests/Ollama, filesystem) is mocked. Tests run in under 20 seconds.

**Tooling:**
- Migrated from `pip + requirements.txt` to `uv` with `pyproject.toml` and `uv.lock`
- `pytest` config lives inside `pyproject.toml` — no separate `pytest.ini`
- Dev dependencies (pytest) separated from production dependencies

---

## Problems We Hit

### Problem 1: ChromaDB "existing embedding ID" warnings on re-ingest
**What happened:** Running `ingest` twice on the same file printed dozens of
`Add of existing embedding ID: ...` warnings.

**Why it happened:** ChromaDB's `collection.add()` does not upsert by default —
it warns when you try to add an ID that already exists.

**How we fixed it:** Did not fix it in Cycle 1. The data is correct and the warnings
are non-fatal. In a later cycle, we will switch to `collection.upsert()` to silently
overwrite existing nodes on re-ingest.

### Problem 2: Small LLM answer quality
**What happened:** The `phi` model (1.3B parameters) gave a rambling, off-topic answer
despite receiving the correct context.

**Why it happened:** Small local models struggle with structured reasoning. The RAG
retrieval worked correctly — the right nodes were returned. The failure was the model's
inability to stay on task.

**How we fixed it:** Not a code problem. Larger models (`llama3`, `mistral`) give
much better answers. The `--model` CLI flag lets you switch models per query.

---

## Key Learnings

- **Embeddings are not magic.** They are just vectors — lists of ~384 numbers.
  Two pieces of text that mean similar things produce similar vectors.
  ChromaDB finds the closest vectors using distance functions (L2 or cosine).

- **RAG grounds the LLM.** Without RAG, the LLM answers from its training memory
  and may hallucinate. With RAG, we force it to answer from real code — even if the
  model is small, the context is accurate.

- **ChromaDB stores four things per node:** `id`, `embedding`, `metadata`, `document`.
  The embedding is what gets searched. The metadata and document are what gets returned
  to the caller. They are stored separately and served together.

- **Mocking is the foundation of fast unit tests.** The sentence-transformers model
  is 80MB and takes seconds to encode. By mocking `model.encode()`, our 97 tests run
  in under 20 seconds. Unit tests test YOUR logic, not the library.

- **uv lock file vs requirements.txt.** `requirements.txt` only pins direct
  dependencies. `uv.lock` pins all 124 packages — including every transitive
  dependency. This is the difference between "probably reproducible" and
  "guaranteed reproducible".

---

## Things That Surprised Us

- The AST parser needs special handling to avoid double-counting methods: methods
  inside a class are collected directly from `node.body` — if you also let `ast.walk()`
  pick them up as top-level functions, each method appears twice.

- ChromaDB distances are not intuitive. Lower distance = more similar.
  When we queried "What does calculate_tax do?", `apply_tax` came back as MORE
  similar than `calculate_tax` itself — because `apply_tax`'s docstring says
  "Internally calls calculate_tax", making its embedding semantically close to
  the query string.

- `pyproject.toml` replaced three files: `requirements.txt`, a separate dev
  requirements file, and `pytest.ini`. One file for everything is the modern Python
  standard.

---

## Interview Talking Points

**Q: What is RAG?**
A: Retrieval Augmented Generation. Instead of asking an LLM to answer from its
training memory, you first retrieve the most relevant content from your own data,
inject it into the prompt as context, and then ask the LLM to answer only from
that context. This prevents hallucination and keeps answers grounded in real data.

**Q: How do embeddings work in your system?**
A: We use `sentence-transformers` with the `all-MiniLM-L6-v2` model. For each code
node we extract — module, class, function — we concatenate its name, docstring, and
raw source into a single string and run it through the model. The model outputs a
384-dimensional vector. Similar code produces similar vectors. ChromaDB stores those
vectors and uses them to find the closest match to a query vector at search time.

**Q: What is ChromaDB and why did you choose it?**
A: ChromaDB is an open-source vector database. It stores embeddings alongside metadata
and supports similarity search out of the box. We chose it for Cycle 1 because it runs
in-process — no Docker container, no server, no setup. It persists to a local SQLite
file. Each team gets its own named collection, which enforces data isolation.

**Q: How does your team isolation work?**
A: Every CodeNode carries a `team_id`. The MD5 node ID is derived from the team_id
plus the file path and node name — so the same function in two different teams produces
two completely different IDs. In ChromaDB, each team has its own named collection. A
query for `team-alpha` only ever touches the `team-alpha` collection. There is no
shared state between teams.

**Q: What did you mock in your unit tests and why?**
A: We mocked three things: the sentence-transformers model (`model.encode`), the
ChromaDB client, and the Ollama HTTP call (`requests.post`). We mocked them because
unit tests should test your own logic in isolation. Loading an 80MB model, connecting
to a database, or making an HTTP call would make tests slow, fragile, and dependent
on external state. Mocking replaces those with predictable fakes.

---

## What's Next

Cycle 2 adds full repository crawling. Instead of pointing the system at one file,
we will give it a repo path (or a GitHub URL), walk every `.py` file recursively,
and batch-ingest them all. The new concept: batch embeddings and the chunking decision
(one node per function vs. one node per file).
