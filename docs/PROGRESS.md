# Progress

## Status: Cycle 3 Complete

---

## Completed

- [x] Project concept defined
- [x] Architecture designed (see ARCHITECTURE.md)
- [x] Domain model documented (see DOMAIN.md)
- [x] Tech stack decided
- [x] Iterative cycles planned (11 cycles)
- [x] Cycle 1 — Foundation: One File, Ask a Question
- [x] Cycle 2 — Full Repo Crawl
- [x] Cycle 3 — Neo4j Knowledge Graph

---

## In Progress

- [ ] Cycle 4 — Markdown and README Doc Ingestion

---

## Cycle Status

| Cycle | Goal | Status |
|---|---|---|
| 1 | One file, AST parse, ChromaDB, Ollama, RAG CLI | **Complete** |
| 2 | Repo walker, batch ingest, 3-mode CLI | **Complete** |
| 3 | Neo4j graph, nodes + edges, graph-enhanced RAG | **Complete** |
| 4 | Markdown / README doc ingestion | Not started |
| 5 | Web URL crawler (requests + BeautifulSoup) | Not started |
| 6 | Multi-team registration + isolation proof | Not started |
| 7 | Docker + Docker Compose | Not started |
| 8 | GitHub Actions pipeline (auto re-ingest on push) | Not started |
| 9 | Impact analysis skill (graph traversal) | Not started |
| 10 | Hotfix agent — full SDLC automation | Not started |
| 11 | Cloud migration (optional) | Not started |

---

## Decisions Log

| Date | Decision | Reason |
|---|---|---|
| 2026-06-20 | Use Python `ast` module for code parsing | Built-in, no install, sufficient for Python repos |
| 2026-06-20 | Use Tree-sitter in later cycles | Multi-language support when needed |
| 2026-06-20 | Use Ollama for LLM | Zero API cost during development |
| 2026-06-20 | Use sentence-transformers for embeddings | Local, free, no API needed |
| 2026-06-20 | Use ChromaDB for vector storage | Simple, runs in-process, no container needed early |
| 2026-06-20 | Use Neo4j Community for graph | Most popular open-source graph DB, good tooling |
| 2026-06-20 | Build team isolation from Cycle 1 | Retrofitting isolation later would require restructuring everything |
| 2026-06-20 | Local-first, Docker-first | Zero cost, portable to any cloud later |
| 2026-06-20 | No LangChain / LlamaIndex — build raw | Learning project: must understand every component |
| 2026-06-21 | Use uv instead of pip + requirements.txt | Lock file pins all 124 transitive deps; reproducible installs across machines |
| 2026-06-21 | pytest config merged into pyproject.toml | One less config file; pyproject.toml is the modern Python standard |
| 2026-06-21 | Unit tests added for all Cycle 1 modules | 97 tests covering ast_parser, embedder, vector_store, ollama_client, cli |
| 2026-06-21 | Neo4j driver wired into ingest pipeline | Both ChromaDB and Neo4j are written on every ingest; docker-compose.yml provides the container |
| 2026-06-21 | Integration tests added for graph_store | 16 tests hit real Neo4j; fail immediately with clear message if Neo4j is not running |
| 2026-06-22 | Add `project_id` to all nodes and edges | Teams can have multiple microservices; project_id enables filtering within a team |
| 2026-06-22 | Team config restructured — `data` array replaces flat `repos` list | Each project now has its own `project_name`, `repos`, and typed `doc_sources` |
| 2026-06-22 | `doc_sources` use typed entries (`type`, `path`/`url`) | Different source types (local, web, confluence, wikipedia) need different crawlers |
| 2026-06-22 | Add Makefile with service management commands | Single place for all dev ops commands — start, stop, restart, status, clean |
