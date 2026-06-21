# Domain Knowledge

## What This System Is

An AI-powered Knowledge Graph platform that ingests code repositories and documentation,
maps relationships between every piece of code and knowledge, and exposes that graph
to AI agents that can answer questions, find impacted code, and perform software
development tasks autonomously.

---

## Inspiration: The Company System

The company has a 40-person team building this at scale. Key facts about their system:

- Crawlers pull data from: Git, Jira, Confluence, Azure DevOps, Wikipedia, and more
- Source code is parsed to extract every class, function, parameter, and their relationships
- All data lands in GCP Cloud Storage buckets
- A pipeline enriches the data with embeddings and ingests it into GCP Spanner Graph
- Claude Code with custom skills acts as an AI engineer across the full SDLC
- Example use case: developer asks for a hotfix → system finds every class/function/
  microservice that needs to change → makes the changes → pushes code → creates PR →
  AI agent reviews PR → AI agent merges PR
- New teams onboard by providing repo paths and doc URLs — everything else is automatic
- Each team's data is fully isolated — Team A cannot see Team B's data

---

## What We Are Building

A simplified, open-source, solo-developer version of the same system.
Built locally, containerized with Docker, designed to be cloud-portable later.

### Goals
1. Learn AI concepts hands-on by building a real system
2. Produce a portfolio project strong enough to put on a resume
3. Understand every layer of the system (something a 40-person team cannot give you)

### Non-Goals (for now)
- Production scale
- Real multi-user auth
- Paid cloud services

---

## Roles

| Role | Description |
|---|---|
| Team Admin | Registers a team, provides repo paths and doc URLs, manages user list |
| Developer (User) | Belongs to a team, queries the knowledge graph, uses Claude skills |
| System (AI Agent) | Crawls, indexes, enriches, answers queries, performs SDLC tasks |

---

## Core Concepts

### Team
A logical unit of isolation. A team has:
- A unique `team_id`
- One or more source repositories (code)
- One or more documentation sources (URLs or file paths)
- A list of users who belong to the team

A user belongs to exactly one team. All queries are scoped to that team's data.
No data crosses team boundaries.

### Knowledge Graph
A graph structure where:
- **Nodes** represent things: files, classes, functions, parameters, documents, pages, tickets
- **Edges** represent relationships: `CALLS`, `IMPORTS`, `DEFINED_IN`, `REFERENCES`, `BELONGS_TO`

Every piece of code and every document becomes a node. Their relationships become edges.
This lets the system answer questions like:
- "Which functions call this function?"
- "Which microservices would be affected by changing this class?"
- "What documentation explains this module?"

### Embedding
A vector (list of numbers) that represents the semantic meaning of a piece of text or code.
Two pieces of text that mean similar things will have similar vectors.
Used to find relevant content when a user asks a question in natural language.

### RAG (Retrieval Augmented Generation)
The technique of:
1. Taking a user's question
2. Finding the most relevant nodes from the knowledge graph (using embeddings)
3. Passing those nodes as context to an LLM
4. The LLM generates an answer grounded in that context

This prevents hallucination — the LLM answers from real data, not from training memory.

### Skill / Agent
A Claude skill is a prompt + tool set that gives Claude a specific capability.
Example skills:
- `ask_question` — answer a question about the codebase
- `find_impact` — given a change, find all affected code
- `hotfix_agent` — end-to-end: understand the fix, change code, push, create PR

---

## Data Models

### Team
```
team_id       : string (unique, slug e.g. "team-alpha")
name          : string
users         : list of user_ids
repos         : list of repo paths or URLs
doc_sources   : list of URLs or file paths
created_at    : datetime
```

### User
```
user_id       : string
name          : string
team_id       : string (foreign key → Team)
```

### CodeNode (Graph Node)
```
node_id       : string (unique)
team_id       : string
type          : enum [FILE, CLASS, FUNCTION, PARAMETER, MODULE]
name          : string
file_path     : string
line_start    : int
line_end      : int
docstring     : string (if present)
raw_source    : string
embedding     : vector[float]
```

### DocNode (Graph Node)
```
node_id       : string (unique)
team_id       : string
type          : enum [MARKDOWN, CONFLUENCE_PAGE, JIRA_TICKET, README, WIKI]
title         : string
url           : string (source URL or file path)
content       : string
embedding     : vector[float]
```

### Edge (Graph Relationship)
```
from_node_id  : string
to_node_id    : string
relation_type : enum [CALLS, IMPORTS, DEFINED_IN, REFERENCES, BELONGS_TO, INHERITS]
team_id       : string
```

---

## Business Rules

1. **Team isolation is absolute.** Every query, every search, every graph traversal is
   filtered by `team_id`. No cross-team data access is possible.

2. **Onboarding is automatic.** Once a team provides repos and doc sources, the system
   handles crawling, parsing, embedding, and ingestion with no manual steps.

3. **The graph is the source of truth.** All answers come from the knowledge graph.
   The LLM does not answer from its own training memory — it answers from the graph.

4. **Embeddings are stored alongside graph nodes.** Every node has both its structured
   data (in the graph DB) and its vector representation (in the vector DB).

5. **Code parsing extracts structure, not just text.** A Python file is not treated as
   a blob of text — it is parsed into classes, functions, and their relationships.
