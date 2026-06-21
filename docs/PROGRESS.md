# Progress

## Status: Planning Phase

No code has been written yet. The architecture and domain have been documented.

---

## Completed

- [x] Project concept defined
- [x] Architecture designed (see ARCHITECTURE.md)
- [x] Domain model documented (see DOMAIN.md)
- [x] Tech stack decided
- [x] Iterative cycles planned (8 cycles)

---

## In Progress

- [ ] Cycle 1: Foundation — One Repo, Ask Questions

---

## Pending Cycles

Full cycle details in `docs/CYCLES.md`.

| Cycle | Goal | Status |
|---|---|---|
| 1 | One file, AST parse, ChromaDB, Ollama, RAG CLI | Not started |
| 2 | Full repo crawl, GitPython, batch ingest | Not started |
| 3 | Neo4j graph, nodes + edges, graph-enhanced RAG | Not started |
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
| 2026-06-20 | No LangChain / LlamaIndex — build raw | Learning project: must understand every component. Frameworks hide the internals. Once Cycle 1 is built raw, we will know exactly what RAG, embeddings, and graph traversal do. |
