# Cycle 3 — Neo4j Knowledge Graph

## Goal

Introduce a graph database (Neo4j) alongside ChromaDB. Every CodeNode becomes
a graph node. Every relationship between code entities (CALLS, IMPORTS, DEFINED_IN,
BELONGS_TO, INHERITS) becomes a graph edge. Use the graph to enrich RAG answers
and answer the question "if I change this, what breaks?"

---

## What We Actually Built

**Source code (`src/`):**

| Module | What it does |
|---|---|
| `storage/graph_store.py` | Neo4j writer and reader. `store_nodes` upserts CodeNodes as `:CodeNode` graph nodes. `store_edges` upserts edges as typed Neo4j relationships. `get_neighbors` returns all nodes connected to a given set of node_ids (any direction). `get_impact` returns all nodes that depend on a given target (incoming CALLS/IMPORTS only). |
| `parsers/ast_parser.py` (updated) | Now extracts `Edge` objects alongside `CodeNode` objects. Five edge types: `DEFINED_IN`, `BELONGS_TO`, `IMPORTS`, `INHERITS`, `CALLS`. All edges carry `team_id`. |
| `skills/ollama_client.py` (updated) | `build_prompt` now accepts an optional `neighbors` list from Neo4j alongside the ChromaDB `context_nodes`. Each section is labelled `[vector match]` or `[graph neighbor via EDGE_TYPE]`. |
| `cli.py` (updated) | `ingest` now writes to both ChromaDB and Neo4j. `query` calls `get_neighbors` after ChromaDB search and passes combined context to Ollama. New `impact` command takes `--target` and prints all dependents from graph traversal. |

**Infrastructure:**

| File | What it does |
|---|---|
| `docker-compose.yml` | Runs Neo4j Community Edition. Port 7474 = browser UI, 7687 = Bolt (Python driver). Password set via `NEO4J_AUTH` env var. Data persisted in a named Docker volume. |

**Tests (`tests/unit/`):**

| File | Tests added |
|---|---|
| `test_edge_extraction.py` | 17 tests — DEFINED_IN, BELONGS_TO, INHERITS, CALLS, no duplicates, team_id on all edges |
| `test_graph_store.py` | 20 tests — store_nodes, store_edges, get_neighbors, get_impact — all mocked, no real Neo4j |
| `test_cli.py` (updated) | store_nodes, store_edges, get_neighbors, get_impact all mocked in CLI tests |
| `test_ollama_client.py` (updated) | Header format updated to match `[vector match]` label |

Total: **153 tests, all passing.**

---

## The Two Storage Layers

Every node now lives in two places after ingestion:

```
CodeNode
    │
    ├──► ChromaDB  — stores the vector (384 numbers)
    │               used for: "find me nodes similar in meaning to this question"
    │
    └──► Neo4j     — stores the node properties + edges
                    used for: "find me nodes connected to this one by code relationships"
```

ChromaDB answers: *what is semantically similar?*
Neo4j answers: *what is structurally related?*

---

## Edge Types — What They Connect and How They Are Built

| Edge | From | To | Built from |
|---|---|---|---|
| `DEFINED_IN` | CLASS or FUNCTION | MODULE | Every class and function is defined in that file's module node |
| `BELONGS_TO` | FUNCTION (method) | CLASS | A method found inside a class body |
| `IMPORTS` | MODULE | MODULE | `from .constants import X` — resolved to the target file |
| `INHERITS` | CLASS | CLASS (parent) | `class Child(Base):` — both must exist in the same file |
| `CALLS` | FUNCTION | FUNCTION | A function call found inside a function body |

---

## How Graph-Enhanced RAG Works

Before Cycle 3, the query pipeline was:

```
Question → embed → ChromaDB top-3 → Ollama → answer
```

After Cycle 3:

```
Question → embed → ChromaDB top-3
                        │
                        ▼
               Neo4j get_neighbors(those 3 node_ids)
               returns: callers, callees, parent class, module
                        │
                        ▼
               Combined context (vector matches + graph neighbors)
                        │
                        ▼
               Ollama → richer, more grounded answer
```

The graph adds **structural context** that semantic similarity alone cannot find.
ChromaDB might return `calculate_tax`. Neo4j then reveals `process_payment` calls
it and `apply_tax` calls it — those callers become part of the LLM's context too.

---

## How Impact Analysis Works

```
CLI: impact --team team-alpha --target "PaymentProcessor.calculate_tax"
      │
      ▼
Neo4j: MATCH (caller)-[r:CALLS|IMPORTS]->(target)
       WHERE target.name = "PaymentProcessor.calculate_tax"
         AND target.team_id = "team-alpha"
      │
      ▼
Returns: every function that calls it, every module that imports it
```

Real output from our payment-service:
```
Found 3 dependent(s):
  [CALLS]  PaymentProcessor.apply_tax              — processors.py
  [CALLS]  PaymentProcessor.process_card_payment   — processors.py
  [CALLS]  PaymentProcessor.process_wallet_payment — processors.py
```

This is graph traversal — not keyword search, not semantic similarity.
The answer comes directly from the edges stored in Neo4j.

---

## Problems We Hit

### Problem 1: `raw_source` not stored in Neo4j
**What happened:** `graph_store._write_nodes` stored all properties except `raw_source`.
When `get_neighbors` returned nodes from Neo4j, they had docstrings but no code — the LLM
received thin context for graph-expanded nodes.

**Why it mattered:** Many functions have empty docstrings. Without `raw_source`, the graph
neighbor sections in the prompt were nearly empty.

**How we fixed it:** Added `raw_source` to both the Cypher `SET` clause and the Python dict
passed to Neo4j. Graph-returned nodes now carry full source code.

### Problem 2: CLI tests not mocking `store_nodes` and `store_edges`
**What happened:** `test_ingest_exits_successfully` started failing after we wired the ingest
command to Neo4j. The test didn't mock `store_nodes` or `store_edges`, so the command tried
to connect to Neo4j (not running in CI) and crashed.

**How we fixed it:** Added `patch("src.cli.store_nodes")` and `patch("src.cli.store_edges")`
to all ingest tests. Same pattern applied to `get_neighbors` and `get_impact` for query tests.

### Problem 3: `build_prompt` header format mismatch
**What happened:** We changed the section header from `--- name (TYPE) ---` to
`--- name (TYPE) [vector match] ---` to distinguish vector results from graph neighbors.
The existing test `test_build_prompt_section_header_format` checked for the old format and failed.

**How we fixed it:** Updated the assertion in the test to match the new label.

---

## Key Learnings

- **Dual storage is the core pattern.** ChromaDB and Neo4j are not alternatives — they do
  completely different things. ChromaDB stores meaning (vectors). Neo4j stores structure
  (relationships). You need both to build a real knowledge graph system.

- **`get_neighbors` vs `get_impact` solve different problems.** `get_neighbors` traverses
  in both directions and all edge types — it enriches context. `get_impact` only follows
  incoming CALLS and IMPORTS — it answers "what breaks?" These are different questions
  and different traversal strategies.

- **Edge direction matters.** `(A)-[:CALLS]->(B)` means A calls B. If you change B,
  A might break. The arrow points from the dependent to the dependency. Impact traversal
  follows arrows backwards (incoming edges to the target).

- **Neo4j does not support dynamic relationship types in a single query.** You cannot
  write `MERGE (a)-[r:$rel_type]->(b)`. We worked around this by grouping edges by
  `relation_type` and running one query per type in `_write_edges`.

- **Names are not unique identifiers.** `__init__` appears in every class. Two files can
  have a function named `validate`. `node_id` (MD5 hash) is the only globally unique
  identifier. For `get_impact` we currently search by name — acceptable for specific names
  like `PaymentProcessor.calculate_tax`, but using `node_id` would be more precise.

- **Mocking the Neo4j driver requires understanding the context manager pattern.**
  `with _driver.session() as session:` calls `_driver.session().__enter__()`. The mock
  fixture sets `driver.session.return_value.__enter__.return_value = mock_session` to
  control what the `with` block receives.

---

## Things That Surprised Us

- The live query showed ChromaDB returning `RefundProcessor.calculate_refund` as the
  most similar node to "What does calculate_tax do?" — not `PaymentProcessor.calculate_tax`
  itself. This is because `calculate_refund`'s source code mentions tax calculation,
  making it semantically close. The graph then expanded to include `process_refund` via
  CALLS — which is exactly what graph-enhanced RAG is designed to find.

- 51 edges were extracted from just 6 Python files in the payment-service. The graph is
  denser than it looks — every method generates BELONGS_TO + DEFINED_IN edges, every
  import generates an IMPORTS edge, and every internal call generates a CALLS edge.

---

## Interview Talking Points

**Q: What is a knowledge graph?**
A: A graph where nodes represent things (files, classes, functions) and edges represent
relationships between them (CALLS, IMPORTS, INHERITS). Unlike a relational database where
you join tables, a graph database lets you traverse relationships directly. In our system,
nodes are code entities and edges are extracted from the AST — import statements become
IMPORTS edges, function calls become CALLS edges.

**Q: Why use Neo4j alongside ChromaDB? Why not just one database?**
A: They solve different problems. ChromaDB stores vectors and answers "what is semantically
similar to this question?" Neo4j stores relationships and answers "what is structurally
connected to this node?" You need both for a complete picture. Semantic search finds
`calculate_tax` because it matches your question. Graph traversal then finds `process_payment`
because it calls `calculate_tax` — that relationship is invisible to semantic search.

**Q: What is graph-enhanced RAG?**
A: Standard RAG finds top-K nodes by semantic similarity and passes them to the LLM.
Graph-enhanced RAG adds a second step: after vector search, traverse the graph to find
nodes structurally connected to the results. This surfaces callers, callees, parent classes,
and related modules that semantic search would miss. The LLM gets both semantic context
and structural context in a single prompt.

**Q: How does your impact analysis work?**
A: We traverse incoming edges in Neo4j. Given a target node like `calculate_tax`, we run
a Cypher query: `MATCH (caller)-[r:CALLS|IMPORTS]->(target) WHERE target.name = $name`.
This returns every function that calls it and every module that imports it. The direction
matters — we only follow arrows that point TO the target, because those are the things
that depend on it and would break if it changed.

**Q: How does team isolation work in Neo4j?**
A: Every node and every relationship carries a `team_id` property. All Cypher queries
filter by `team_id`. The same function name in two different teams produces different
`node_id` values (MD5 includes team_id in the hash), so there is no overlap even if
two teams ingest the same codebase.

**Q: What is the Bolt protocol?**
A: Bolt is Neo4j's binary wire protocol — the language the Python driver uses to talk
to Neo4j over the network (port 7687). It is faster than HTTP because it uses a binary
format instead of JSON. The Python `neo4j` package connects via Bolt automatically when
you call `GraphDatabase.driver("bolt://localhost:7687")`.

---

## What's Next

Cycle 4 ingests Markdown and README files alongside code — so answers can combine
code structure with written documentation. The new concept: document chunking (how do
you split a large README into meaningful pieces?) and mixed modality search (one query
searches both code nodes and doc nodes and returns the most relevant mix).
