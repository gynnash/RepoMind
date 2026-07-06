# RepoMind Skill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Claude Code skill (`/repomind`) that searches GitHub for similar open-source repos, extracts architecture design patterns, and returns structured code cards for architecture design assistance.

**Architecture:** A Claude Code skill file orchestrates the workflow via LLM + tools (gh CLI, Agent, Bash). A Python helper script (`search.py`) manages a local SQLite database for caching structured code cards. The workflow parses user intent, checks local cache first (V1 keyword when <5 cards, V2 LLM semantic when >=5), falls back to GitHub search with layered relevance filtering, then runs parallel deep analysis via Agent subagents.

**Tech Stack:** Python 3.9+ (stdlib only: sqlite3, json, argparse), gh CLI (GitHub search), Claude Code Agent tool (parallel deep analysis)

## Global Constraints

- Python 3.9+, stdlib only (no pip installs)
- SQLite WAL mode for concurrent reads
- All file paths relative to project root
- Skill file lives in `.claude/skills/repomind.md`
- Data lives in `.repomind/repomind.db`
- Max 20 repos per GitHub search
- Relevance threshold: 3.5 (weighted four-dimension score)
- Card dedup threshold: 70% title+keyword overlap
- Card staleness: 6 months

---

### Task 1: Create search.py — database init, schema, and repo CRUD

**Files:**
- Create: `.repomind/search.py`

**Interfaces:**
- Produces: `init_db()`, `get_card_count()`, `insert_repo(data: dict) -> int`, `repo_exists(full_name: str) -> bool`, `get_repo(full_name: str) -> dict | None`

- [ ] **Step 1: Create `.repomind/` directory and `search.py` skeleton**

```bash
mkdir -p .repomind
```

Write `.repomind/search.py`:

```python
#!/usr/bin/env python3
"""RepoMind database helper — SQLite operations for repo cards."""

import sqlite3
import json
import sys
import os


DB_DIR = ".repomind"
DB_NAME = "repomind.db"


def get_db_path():
    return os.path.join(DB_DIR, DB_NAME)


def init_db():
    """Initialize database and create tables if they don't exist."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(get_db_path())
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS repos (
            id          INTEGER PRIMARY KEY,
            full_name   TEXT UNIQUE NOT NULL,
            url         TEXT NOT NULL,
            language    TEXT,
            topics      TEXT,
            stars       INTEGER,
            description TEXT,
            fetched_at  TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS cards (
            id          INTEGER PRIMARY KEY,
            repo_id     INTEGER REFERENCES repos(id),
            dimension   TEXT NOT NULL,
            title       TEXT NOT NULL,
            content     TEXT NOT NULL,
            keywords    TEXT,
            embedding   BLOB,
            created_at  TEXT DEFAULT (datetime('now'))
        );
    """)
    conn.commit()
    conn.close()


def get_card_count():
    conn = sqlite3.connect(get_db_path())
    count = conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]
    conn.close()
    return count


def insert_repo(data):
    conn = sqlite3.connect(get_db_path())
    cur = conn.execute(
        """INSERT OR IGNORE INTO repos (full_name, url, language, topics, stars, description)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (data["full_name"], data["url"], data.get("language"),
         json.dumps(data.get("topics", [])), data.get("stars"),
         data.get("description"))
    )
    conn.commit()
    repo_id = cur.lastrowid
    if repo_id == 0:
        repo_id = conn.execute(
            "SELECT id FROM repos WHERE full_name = ?", (data["full_name"],)
        ).fetchone()[0]
    conn.close()
    return repo_id


def repo_exists(full_name):
    conn = sqlite3.connect(get_db_path())
    row = conn.execute(
        "SELECT id FROM repos WHERE full_name = ?", (full_name,)
    ).fetchone()
    conn.close()
    return row is not None


def get_repo(full_name):
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM repos WHERE full_name = ?", (full_name,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def reset_db():
    db_path = get_db_path()
    if os.path.exists(db_path):
        os.remove(db_path)
    init_db()
```

- [ ] **Step 2: Verify init_db works**

```bash
python3 .repomind/search.py -c "
import sys; sys.path.insert(0, '.repomind')
from search import init_db, get_card_count
init_db()
print('DB initialized, card count:', get_card_count())
"
```

Expected output: `DB initialized, card count: 0`

- [ ] **Step 3: Verify insert_repo and repo_exists**

```bash
python3 .repomind/search.py -c "
import sys; sys.path.insert(0, '.repomind')
from search import init_db, insert_repo, repo_exists, get_repo
init_db()
rid = insert_repo({
    'full_name': 'test-org/test-repo',
    'url': 'https://github.com/test-org/test-repo',
    'language': 'Python',
    'topics': ['agent', 'scheduling'],
    'stars': 5000,
    'description': 'A test repo for agent scheduling'
})
print(f'Inserted repo id: {rid}')
print(f'Repo exists: {repo_exists(\"test-org/test-repo\")}')
print(f'Repo not exists: {repo_exists(\"nonexistent/repo\")}')
repo = get_repo('test-org/test-repo')
print(f'Got repo: {repo[\"full_name\"]} stars={repo[\"stars\"]}')
"
```

Expected: repo insert returns id, exists=True/False correct, get_repo returns correct data

- [ ] **Step 4: Clean up test data and commit**

```bash
rm -f .repomind/repomind.db
git add .repomind/search.py
git commit -m "feat: add search.py with DB init, schema, and repo CRUD"
```

---

### Task 2: Add card CRUD, V1 search, and similarity check to search.py

**Files:**
- Modify: `.repomind/search.py`

**Interfaces:**
- Consumes: `init_db()`, `insert_repo()` from Task 1
- Produces: `insert_card(data: dict) -> int`, `search_cards_v1(keywords: list[str], limit: int) -> list[dict]`, `get_all_cards_with_repo() -> list[dict]`, `get_cards_by_ids(card_ids: list[int]) -> list[dict]`, `check_similar_card(title: str, keywords: str, threshold: float) -> bool`

- [ ] **Step 1: Add card CRUD and search functions**

Append to `.repomind/search.py` (after `reset_db`):

```python
def insert_card(data):
    conn = sqlite3.connect(get_db_path())
    cur = conn.execute(
        """INSERT INTO cards (repo_id, dimension, title, content, keywords)
           VALUES (?, ?, ?, ?, ?)""",
        (data["repo_id"], data["dimension"], data["title"],
         data["content"], data.get("keywords"))
    )
    conn.commit()
    card_id = cur.lastrowid
    conn.close()
    return card_id


def search_cards_v1(keywords, limit=10):
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row

    clauses = []
    params = []
    for kw in keywords:
        clauses.append("(keywords LIKE ? OR title LIKE ?)")
        like_kw = f"%{kw}%"
        params.extend([like_kw, like_kw])

    if not clauses:
        conn.close()
        return []

    query = f"""SELECT c.id, c.dimension, c.title, c.keywords, c.created_at,
                       r.full_name, r.url, r.stars, r.language
                FROM cards c
                JOIN repos r ON c.repo_id = r.id
                WHERE {' OR '.join(clauses)}
                ORDER BY r.stars DESC
                LIMIT ?"""
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_all_cards_with_repo():
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT c.id, c.dimension, c.title, c.keywords,
                   r.full_name, r.url, r.stars
            FROM cards c
            JOIN repos r ON c.repo_id = r.id
            ORDER BY r.stars DESC"""
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_cards_by_ids(card_ids):
    if not card_ids:
        return []
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    placeholders = ",".join("?" * len(card_ids))
    rows = conn.execute(
        f"""SELECT c.*, r.full_name, r.url, r.stars, r.language
            FROM cards c
            JOIN repos r ON c.repo_id = r.id
            WHERE c.id IN ({placeholders})""",
        card_ids
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def check_similar_card(title, keywords, threshold=0.7):
    conn = sqlite3.connect(get_db_path())
    existing = conn.execute("SELECT title, keywords FROM cards").fetchall()
    conn.close()

    title_words = set(title.lower().split())
    kw_words = set((keywords or "").lower().replace(",", " ").split())
    combined = title_words | kw_words

    if not combined:
        return False

    for ex_title, ex_keywords in existing:
        ex_title_words = set(ex_title.lower().split())
        ex_kw_words = set((ex_keywords or "").lower().replace(",", " ").split())
        ex_combined = ex_title_words | ex_kw_words

        if not ex_combined:
            continue
        overlap = len(combined & ex_combined) / len(combined | ex_combined)
        if overlap > threshold:
            return True
    return False
```

- [ ] **Step 2: Add CLI entry point**

Append to `.repomind/search.py`:

```python
def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: python search.py <command> [args]"}))
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "init":
        init_db()
        print(json.dumps({"status": "ok", "message": "Database initialized"}))

    elif cmd == "count":
        count = get_card_count()
        print(json.dumps({"count": count}))

    elif cmd == "search":
        keywords = sys.argv[2:]
        results = search_cards_v1(keywords)
        print(json.dumps(results, indent=2, ensure_ascii=False))

    elif cmd == "all-cards":
        results = get_all_cards_with_repo()
        print(json.dumps(results, indent=2, ensure_ascii=False))

    elif cmd == "insert-repo":
        data = json.loads(sys.argv[2])
        repo_id = insert_repo(data)
        print(json.dumps({"repo_id": repo_id}))

    elif cmd == "check-repo":
        full_name = sys.argv[2]
        exists = repo_exists(full_name)
        repo = get_repo(full_name) if exists else None
        print(json.dumps({"exists": exists, "repo": repo}, ensure_ascii=False))

    elif cmd == "insert-card":
        data = json.loads(sys.argv[2])
        card_id = insert_card(data)
        print(json.dumps({"card_id": card_id}))

    elif cmd == "get-cards":
        card_ids = [int(x) for x in sys.argv[2:]]
        cards = get_cards_by_ids(card_ids)
        print(json.dumps(cards, indent=2, ensure_ascii=False))

    elif cmd == "check-similar":
        title = sys.argv[2]
        keywords = sys.argv[3] if len(sys.argv) > 3 else ""
        similar = check_similar_card(title, keywords)
        print(json.dumps({"similar_exists": similar}))

    elif cmd == "reset-db":
        reset_db()
        print(json.dumps({"status": "ok", "message": "Database reset"}))

    else:
        print(json.dumps({"error": f"Unknown command: {cmd}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Test CLI — init, insert, search**

```bash
python3 .repomind/search.py init &&

python3 .repomind/search.py insert-repo '{"full_name":"langchain-ai/langchain","url":"https://github.com/langchain-ai/langchain","language":"Python","topics":["llm","agent","orchestration"],"stars":95000,"description":"Building applications with LLMs through composability"}' &&

python3 .repomind/search.py insert-card '{"repo_id":1,"dimension":"architecture","title":"LangChain Runnable Abstraction","content":"## Overview\nLangChain uses a composable Runnable interface...\n\n## Key Design\n1. All components implement the Runnable protocol\n2. LCEL for declarative composition\n3. Streaming support built into the core abstraction\n\n## Transferable Patterns\n- Interface-based design with single protocol\n- Declarative composition over imperative wiring\n\n## Limitations\n- Runnable interface is Python-specific","keywords":"agent,orchestration,runnable,composition,abstraction"}' &&

python3 .repomind/search.py count &&

python3 .repomind/search.py search agent orchestration
```

Expected: count=1, search returns card with langchain info

- [ ] **Step 4: Test similarity check**

```bash
python3 .repomind/search.py check-similar "LangChain Runnable Abstraction" "agent,orchestration,runnable"
# expected: similar_exists: false (first card)

python3 .repomind/search.py insert-card '{"repo_id":1,"dimension":"design_patterns","title":"LangChain Chain Composition Pattern","content":"## Overview\nChain composition using the pipe operator...","keywords":"agent,orchestration,composition,chain"}' &&

python3 .repomind/search.py check-similar "LangChain Chain Composition Pattern" "agent,orchestration,composition,chain"
# expected: similar_exists: true (similar to existing)
```

- [ ] **Step 5: Commit**

```bash
rm -f .repomind/repomind.db
git add .repomind/search.py
git commit -m "feat: add card CRUD, V1 search, similarity check to search.py"
```

---

### Task 3: Create config.json and skill file skeleton

**Files:**
- Create: `.repomind/config.json`
- Create: `.claude/skills/repomind.md`

**Interfaces:**
- Consumes: `search.py` CLI from Tasks 1-2
- Produces: config.json schema, repomind.md skill skeleton with intent parsing (Step 1 of workflow)

- [ ] **Step 1: Create config.json**

Write `.repomind/config.json`:

```json
{
  "max_search_repos": 20,
  "min_relevance_score": 3.5,
  "card_similarity_threshold": 0.7,
  "card_staleness_months": 6,
  "mandatory_dimensions": ["architecture", "design_patterns", "data_flow"],
  "optional_dimensions": ["interface_design", "tech_stack", "deployment", "evolution_history"]
}
```

- [ ] **Step 2: Create skill file with intent parsing workflow**

Create `.claude/skills/` directory and write `.claude/skills/repomind.md`:

```markdown
---
name: repomind
description: Search GitHub for similar open-source repos, extract architecture design patterns, and summarize into code cards for architecture design assistance.
---

# RepoMind

Search GitHub for open-source repos architecturally similar to the current codebase, extract design patterns and architecture decisions, and return structured code cards to assist code agents in architecture design.

## Trigger

- **Primary:** User invokes `/repomind <query>`
- **Secondary:** When other architecture-phase skills detect a design task, suggest checking local RepoMind cards

## Workflow

### Step 1: Intent Parsing

When the user invokes `/repomind <query>`, first parse their intent into a structured form.

Extract from the query:
- `keywords`: 3-5 Chinese + English keywords capturing the core architectural concern
- `tech_stack`: Programming language, framework, key dependencies inferred from the current project
- `domain`: The problem domain (e.g., "ai-agent-framework", "distributed-systems", "real-time-collaboration")
- `github_query`: A GitHub search query string optimized for finding repos with architectural documentation

Also gather current codebase context to inject into later relevance evaluation:
- Project language(s) from file extensions
- Key frameworks/dependencies from package files (package.json, requirements.txt, go.mod, Cargo.toml, etc.)
- Top-level directory structure

Example:
```
Query: "design an agent scheduling layer with priority queues"
→ keywords: ["agent", "scheduling", "task-queue", "priority", "orchestration"]
→ tech_stack: ["python", "asyncio"]
→ domain: "ai-agent-framework"
→ github_query: "agent task scheduler OR agent orchestration framework architecture"
```

### Step 2: Local Retrieval

Run `python3 .repomind/search.py count` to get the current card count.
Run `python3 .repomind/search.py all-cards` to get all card summaries.

**If card count < 5 (V1):**
Run `python3 .repomind/search.py search <keyword1> <keyword2> ...` with the parsed keywords.
Collect matching cards. If >= 3 cards found with good relevance, skip to Step 5.

**If card count >= 5 (V2):**
Pass all card titles + keywords to LLM for semantic relevance scoring against the user's query.
Score each card 0-5. Take cards with score >= 3, up to 10.
If >= 3 relevant cards found, skip to Step 5.

**If insufficient local results:** Continue to Step 3.

### Step 3: GitHub Search & Relevance Filtering

> Remaining steps defined in subsequent tasks. For now, if reached, tell the user: "No matching local cards found. GitHub search pipeline is not yet implemented."
```

- [ ] **Step 3: Verify skill loads**

```bash
ls -la .claude/skills/repomind.md
cat .repomind/config.json
```

- [ ] **Step 4: Commit**

```bash
git add .repomind/config.json .claude/skills/repomind.md
git commit -m "feat: add config.json and repomind skill skeleton with intent parsing"
```

---

### Task 4: Implement local retrieval flow in skill (Step 2)

**Files:**
- Modify: `.claude/skills/repomind.md`

**Interfaces:**
- Consumes: `search.py` CLI (count, search, all-cards, get-cards)
- Produces: Complete Step 2 of the skill workflow (local retrieval with V1/V2 switching)

- [ ] **Step 1: Replace Step 2 placeholder with full local retrieval logic**

In `.claude/skills/repomind.md`, replace the Step 2 section (from `### Step 2: Local Retrieval` through the end) with:

```markdown
### Step 2: Local Retrieval

Run `python3 .repomind/search.py count` to get the current card count.

**If card count == 0:**
No local database exists or it's empty. Skip directly to Step 3 (GitHub search).

**If card count < 5 (V1 — keyword matching):**
Run `python3 .repomind/search.py search <keyword1> <keyword2> ...` with the parsed keywords from Step 1.
This returns cards whose `keywords` or `title` fields contain any of the search keywords, sorted by repo stars DESC.
- If >= 3 cards returned: present a brief summary (repo name, dimension, title) to the user, then skip to Step 5 (assemble and return these cards).
- If < 3 cards: note the count and continue to Step 3.

**If card count >= 5 (V2 — LLM semantic scoring):**
Run `python3 .repomind/search.py all-cards` to get all card summaries (id, dimension, title, keywords, repo name, stars).
Pass the user's original query + all card summaries to LLM with this prompt:

```
Score each of the following code cards for relevance to the query: "{user_query}"

Scoring criteria:
- 5: Directly addresses the same architectural concern
- 4: Highly relevant, same problem domain and pattern
- 3: Moderately relevant, adjacent domain with transferable patterns
- 2: Loosely related, may have tangential insights
- 1-0: Not relevant

Cards:
{json_array_of_cards_with_id_title_keywords}

Return ONLY a JSON array of {{"id": <card_id>, "relevance": <score>}} for cards scoring >= 3, sorted by score descending, max 10.
```

If >= 3 cards score >= 3: note them, then skip to Step 5.
If < 3 relevant cards: continue to Step 3 (GitHub search).

### Step 3: GitHub Search & Relevance Filtering

> Remaining steps defined in subsequent tasks. For now, if reached, tell the user: "No matching local cards found. GitHub search pipeline is not yet implemented. Local results: {summary of any local hits found}"
```

- [ ] **Step 2: Verify V1 search works end-to-end**

```bash
# Re-init and insert a test card
python3 .repomind/search.py init &&
python3 .repomind/search.py insert-repo '{"full_name":"prefecthq/prefect","url":"https://github.com/prefecthq/prefect","language":"Python","topics":["workflow","orchestration","scheduling"],"stars":18000,"description":"Prefect is a workflow orchestration framework for building data pipelines"}' &&
python3 .repomind/search.py insert-card '{"repo_id":1,"dimension":"architecture","title":"Prefect Task Scheduling Architecture","content":"## Overview\nPrefect uses a hybrid execution model with a server-side scheduler and client-side execution...\n\n## Key Design\n1. Separation of scheduling from execution\n2. Late binding of task parameters\n3. State-based execution model with retry policies\n\n## Transferable Patterns\n- Decouple scheduler from executor\n- State machine for task lifecycle\n\n## Limitations\n- Requires persistent server connection","keywords":"scheduling,workflow,orchestration,task,execution,state-machine"}' &&

# Test V1 search with relevant keywords
python3 .repomind/search.py search scheduling task orchestration
```

Expected: Returns the Prefect card with dimension=architecture

- [ ] **Step 3: Commit**

```bash
git add .claude/skills/repomind.md
git commit -m "feat: implement local retrieval with V1/V2 switching in repomind skill"
```

---

### Task 5: Implement GitHub search and relevance evaluation (Step 3)

**Files:**
- Modify: `.claude/skills/repomind.md`

**Interfaces:**
- Consumes: Intent parsing output from Step 1, local retrieval results from Step 2
- Produces: List of repos that passed relevance filter, ready for deep analysis

- [ ] **Step 1: Replace Step 3 placeholder with full GitHub search logic**

In `.claude/skills/repomind.md`, replace the Step 3 section with:

```markdown
### Step 3: GitHub Search & Relevance Filtering

Report progress: "Searching GitHub for similar repositories..."

**3a. Dual-approach query generation:**

Approach 1 — LLM identifies similar repos by name:
Based on the user's query and domain, generate 3-5 well-known open-source repo names in that space. Then search for each:
```bash
gh search repos "<repo_name>" --sort stars --limit 5 --json fullName,url,language,topics,stargazersCount,description
```

Approach 2 — LLM generates a topic/code search query:
Use the `github_query` from Step 1:
```bash
gh search repos "<github_query> architecture" --sort stars --limit 20 --json fullName,url,language,topics,stargazersCount,description
```

Merge both result sets, deduplicate by `fullName`. If the result set is > 20 repos, keep the top 20 by stars.

**3b. Coarse filter (no API cost):**

For each candidate repo, apply veto clauses immediately:
- README is purely non-English (Chinese/Japanese/Korean etc.) AND contains no architectural information → skip
- Repo is archived or last pushed > 2 years ago → skip

Check archived/last-pushed via:
```bash
gh repo view <owner/repo> --json isArchived,pushedAt
```

For remaining repos, do a quick LLM evaluation based on description + topics only (no README fetch yet). Score 0-5 for domain relevance. Keep repos scoring >= 3.

**3c. Fine filter (READ fetch):**

For each repo that passed coarse filter, fetch the README:
```bash
gh api repos/<owner/repo>/readme --jq '.content' | base64 -d 2>/dev/null || gh api repos/<owner/repo>/readme -q '.content' | base64 -d
```

Truncate README to first 8000 characters to manage token usage.

For each README, run the four-dimension relevance evaluation:

```
You are evaluating a GitHub repository for its relevance as an architectural reference for the user's design task.

**User's task:** {user_query}
**User's codebase context:** language={language}, frameworks={frameworks}, directory structure={top_level_dirs}

**Candidate repo:** {repo_name} ({stars} stars)
**Description:** {description}
**README (truncated):**
{readme_content}

Evaluate on four dimensions (0-5 each):

| Dimension | 0-1 | 2-3 | 4-5 |
|-----------|-----|-----|-----|
| domain_match | Completely different domain | Adjacent domain or sub-domain overlap | Same problem domain, directly comparable |
| arch_pattern | No architectural description | Architectural concepts mentioned but not detailed | Clear architectural pattern described, directly referenceable |
| tech_overlap | Completely different tech stack | Partial overlap | Core dependencies highly consistent |
| depth_quality | Only feature descriptions | Module division described | Architecture diagrams, ADR, design docs, or detailed directory structure |

**Rules:**
- Scores >= 3 MUST cite specific README passages as evidence.
- The anchor question: can the architectural patterns in this repo be migrated to the user's project?
- Apply veto: if README is non-English with no architectural info → skip. If archived or > 2 years stale → skip.

Calculate overall = domain_match * 0.4 + arch_pattern * 0.2 + tech_overlap * 0.2 + depth_quality * 0.2

Return ONLY valid JSON:
{
  "repo": "owner/repo",
  "scores": {
    "domain_match": <0-5>,
    "arch_pattern": <0-5>,
    "tech_overlap": <0-5>,
    "depth_quality": <0-5>
  },
  "overall": <weighted_score>,
  "evidence": ["<citation>", ...],
  "key_insight": "<one sentence: most valuable reference point>",
  "verdict": "deep_analyze | skip"
}
```

Repos with overall >= 3.5 proceed to Step 4 (deep analysis).
Repos scoring < 3.5 are recorded (skip) and not analyzed further.

Report progress: "Found {total} candidates → {passed} passed relevance filter → proceeding to deep analysis"

If no repos passed: inform user and suggest broadening the search query. Return any local results found in Step 2.

### Step 4: Parallel Deep Analysis

> Defined in next task.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/repomind.md
git commit -m "feat: implement GitHub search and four-dimension relevance evaluation"
```

---

### Task 6: Implement parallel deep analysis and card generation (Step 4)

**Files:**
- Modify: `.claude/skills/repomind.md`

**Interfaces:**
- Consumes: Filtered repo list from Step 3
- Produces: Structured cards written to SQLite via `search.py insert-card`

- [ ] **Step 1: Replace Step 4 placeholder with deep analysis logic**

In `.claude/skills/repomind.md`, replace the Step 4 section with:

```markdown
### Step 4: Parallel Deep Analysis

For each repo that passed the relevance filter, dispatch one Agent (Claude Code Agent tool) to perform deep architectural analysis.

**Agent dispatch (one per repo, all in parallel):**

For each repo, launch an Agent with this prompt:

```
You are analyzing the architecture of the GitHub repository {repo_full_name} ({repo_url}).

**User's design task:** {user_query}
**Relevance scores:** {scores_json}
**Key insight from evaluation:** {key_insight}

## Analysis Instructions

First, explore the repo structure:
1. Fetch the top-level directory listing via: gh api repos/{owner}/{repo}/contents/ --jq '.[].name'
2. Check for architecture docs: look for ADR/, docs/architecture/, ARCHITECTURE.md, CONTRIBUTING.md
3. If docs exist, read them. Also read key source file headers (just the first 50 lines of main module files).

Then, produce structured code cards for each applicable dimension.

**Mandatory dimensions (always produce):**
- architecture
- design_patterns
- data_flow

**Optional dimensions (produce only if evidence exists in the repo):**
- interface_design
- tech_stack
- deployment
- evolution_history

## Card Content Template

For each dimension, output a card with this exact structure:

### {dimension}

#### Overview
{2-3 sentences summarizing the core characteristics of this dimension in the repo}

#### Key Design
{3-5 bullet points, each with specific implementation details. Reference specific files/modules.}

#### Transferable Patterns
{Which designs can be directly or with adaptation applied to the user's project: "{user_query}"}

#### Source References
{Specific file paths (and line numbers where possible) that evidence this analysis}

#### Limitations
{Applicable boundaries, known issues, scenarios where this design would NOT apply}

IMPORTANT: After generating all cards, write each one to the local database using these commands:

For each card:
1. First check if a similar card already exists:
```bash
python3 .repomind/search.py check-similar "<card_title>" "<card_keywords>"
```
2. If similar_exists is false, insert:
```bash
python3 .repomind/search.py insert-repo '{"full_name":"{repo_full_name}","url":"{repo_url}","language":"{language}","topics":[...],"stars":{stars},"description":"{description}"}'
```
(The insert-repo command is idempotent — it uses INSERT OR IGNORE)
```bash
python3 .repomind/search.py insert-card '{"repo_id":<repo_id>,"dimension":"{dimension}","title":"{title}","content":"{full_markdown_content}","keywords":"{comma_separated_keywords}"}'
```
3. Return a JSON summary of all cards created:
```json
[{"card_id": 1, "dimension": "architecture", "title": "..."}, ...]
```

Important: Ensure all card content is escaped properly for JSON (use jq or proper escaping). If a card is similar to an existing one (similar_exists: true), skip it and note it in the summary.
```

**After all Agents complete:**

Collect all card summaries. For each new card created, record its ID.
Report to user: "Deep analysis complete: {N} repos analyzed, {M} new cards created, {K} duplicates skipped."

### Step 5: Card Assembly & Return

> Defined in next task.
```

- [ ] **Step 2: Commit**

```bash
git add .claude/skills/repomind.md
git commit -m "feat: implement parallel deep analysis with Agent dispatch"
```

---

### Task 7: Implement card assembly, secondary mode, and error handling

**Files:**
- Modify: `.claude/skills/repomind.md`

**Interfaces:**
- Consumes: Card IDs from Step 2 (local) or Step 4 (newly created)
- Produces: Full workflow (Step 5), secondary mode instructions, error handling matrix

- [ ] **Step 1: Add Step 5 (Card Assembly & Return)**

In `.claude/skills/repomind.md`, replace the Step 5 placeholder with:

```markdown
### Step 5: Card Assembly & Return

Collect all matching cards (from local retrieval in Step 2 or newly created in Step 4).

Retrieve full card contents:
```bash
python3 .repomind/search.py get-cards <id1> <id2> ...
```

Assemble output in this format:

```markdown
## RepoMind Code Cards

> **Search intent:** {user_query}
> **Matched repos:** {N} | **Cards:** {M}

<repo-card id="{card_id}" repo="{owner/repo}" dimension="{dimension}" relevance="{score}" stars="{stars}">
{full card content}
</repo-card>

<repo-card id="{card_id}" repo="{owner/repo}" dimension="{dimension}" relevance="{score}" stars="{stars}">
{full card content}
</repo-card>
...
```

Sort cards: by relevance score descending, then by stars descending.

Present the assembled cards to the user. The XML `<repo-card>` wrapper enables easy parsing by downstream code agents.
```

- [ ] **Step 2: Add secondary mode instructions**

Append after Step 5 in `.claude/skills/repomind.md`:

```markdown
## Secondary Mode: Passive Suggestion

When other skills (brainstorming, writing-plans) enter an architecture design phase, they MAY check RepoMind for existing relevant cards.

To check for relevant cards without triggering a full GitHub search:
```bash
python3 .repomind/search.py count
```
If count > 0:
```bash
python3 .repomind/search.py search <keywords_from_current_discussion>
```

If matching cards exist, present a lightweight suggestion:
> "Repomind has {N} existing code card(s) that may be relevant to this design task. Use `/repomind {topic}` to retrieve them."

Do NOT proceed to GitHub search or deep analysis in secondary mode. This is read-only and zero-cost.
```

- [ ] **Step 3: Add error handling reference table**

Append after secondary mode in `.claude/skills/repomind.md`:

```markdown
## Error Handling

### GitHub API errors
- **Rate limit (429):** Parse the `X-RateLimit-Reset` header or error message. Tell user: "GitHub API rate limit reached. Resets at {time}. Returning {N} local results only." Return partial results from Step 2.
- **Unauthenticated:** If `gh auth status` fails, prompt: "Run `gh auth login` for higher rate limits. Proceeding with unauthenticated access (60 req/hour)."
- **Repo deleted/private:** Silently skip. Log to stderr. Continue with remaining repos.
- **No search results:** Tell user: "No matching repos found for '{query}'. Try broader terms." Record the query + empty result timestamp to avoid repeated ineffective searches.

### Deep Analysis errors
- **Repo too large:** Agent instruction includes: "If the repo has > 100 top-level files, analyze only directory structure + README + top 10 source file headers. Mark cards with `depth: partial`."
- **README is images/links only:** Skip during coarse filter. If discovered during fine filter, skip.
- **Agent timeout/error:** Single repo failure does not halt the pipeline. Mark in summary: `{repo}: failed — {reason}`. Return successful cards.
- **Duplicate conclusions:** Before insert, `check-similar` with threshold 0.7. If similar exists, merge (skip insert, note in summary).

### Local Database errors
- **First use (no DB):** `search.py init` auto-creates `.repomind/` and `repomind.db`. No user action needed.
- **DB corruption:** If `search.py` commands return SQLite errors, tell user: "Database may be corrupted. Run `python3 .repomind/search.py reset-db` to rebuild (existing cards will be lost)."

### User Experience
- **Query too broad** (e.g., "design a backend"): Do not search. Ask: "What specific aspect of backend design are you focusing on? (e.g., API design, data processing, system architecture, authentication)"
- **Query too specific** (e.g., "how to implement React useState"): Respond: "This appears to be an implementation question rather than an architecture design question. RepoMind is designed for architectural reference. Consider consulting the framework documentation directly."
- **Long search time:** Report progress at each stage: "Searching GitHub..." → "Found 12 candidates" → "Evaluating relevance..." → "5/12 passed" → "Deep analyzing [repo1, repo2]..." → "3 new cards created"
```

- [ ] **Step 4: Final review of complete skill file**

Read the full skill file to verify all sections are consistent and complete:

```bash
wc -l .claude/skills/repomind.md && cat .claude/skills/repomind.md
```

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/repomind.md
git commit -m "feat: add card assembly, secondary mode, and error handling to repomind skill"
```

---

### Task 8: End-to-end integration test

**Files:**
- No new files — verification only

This task verifies that all components work together correctly.

- [ ] **Step 1: Fresh database init**

```bash
rm -f .repomind/repomind.db
python3 .repomind/search.py init
python3 .repomind/search.py count
```

Expected: `{"count": 0}`

- [ ] **Step 2: Insert a known repo and card manually to simulate cached data**

```bash
python3 .repomind/search.py insert-repo '{"full_name":"apache/airflow","url":"https://github.com/apache/airflow","language":"Python","topics":["workflow","scheduler","orchestration","pipeline"],"stars":38000,"description":"Apache Airflow - A platform to programmatically author, schedule, and monitor workflows"}'

python3 .repomind/search.py insert-card '{"repo_id":1,"dimension":"architecture","title":"Airflow DAG Scheduling Architecture","content":"## Overview\nAirflow uses a DAG-based scheduling model where tasks are defined as directed acyclic graphs. The scheduler parses DAG files, determines task dependencies, and triggers execution when upstream tasks complete and scheduling conditions are met.\n\n## Key Design\n1. DAG parser reads Python files to extract task definitions and dependencies\n2. Scheduler continuously evaluates DAG state and queues ready tasks\n3. Executors abstract task execution (LocalExecutor, CeleryExecutor, KubernetesExecutor)\n4. Metadata database stores all DAG run state and task instances\n5. Heartbeat-based health monitoring for task liveness\n\n## Transferable Patterns\n- Declarative DAG definition for workflow specification\n- Executor abstraction enables scaling from single-machine to distributed\n- Metadata-driven state management with database persistence\n\n## Source References\n- airflow/models/dag.py: DAG model definition\n- airflow/scheduler.py: Core scheduler loop\n- airflow/executors/: Executor abstraction implementations\n\n## Limitations\n- DAG parsing overhead for large numbers of DAGs\n- No built-in streaming support\n- Scheduler is a single point of contention at scale","keywords":"scheduling,DAG,workflow,airflow,executor,orchestration"}'
```

- [ ] **Step 3: Verify V1 search returns expected card**

```bash
python3 .repomind/search.py search scheduling orchestration workflow
```

Expected: Returns 1 card with title "Airflow DAG Scheduling Architecture"

- [ ] **Step 4: Verify get-cards returns full content**

```bash
python3 .repomind/search.py get-cards 1
```

Expected: Full card content with all fields

- [ ] **Step 5: Verify check-similar detects near-duplicate**

```bash
python3 .repomind/search.py check-similar "Airflow Task Scheduling Design" "scheduling,DAG,airflow,workflow,executor"
```

Expected: `{"similar_exists": true}`

- [ ] **Step 6: Verify search.py CLI handles error cases**

```bash
python3 .repomind/search.py check-repo "nonexistent/repo"
# Expected: {"exists": false, "repo": null}

python3 .repomind/search.py search
# Expected: [] (empty keywords = no results, no crash)

python3 .repomind/search.py unknown-command
# Expected: error message
```

- [ ] **Step 7: Verify skill file is syntactically valid**

```bash
# Check skill frontmatter is valid YAML
head -10 .claude/skills/repomind.md
```

Expected: valid `---` delimited frontmatter with `name` and `description` fields

- [ ] **Step 8: Cleanup test data**

```bash
rm -f .repomind/repomind.db
```

- [ ] **Step 9: Verify tracked files and add .gitignore**

```bash
git status
```

Verify no `.db` files are staged. Add a `.gitignore` to exclude the database:

```bash
echo ".repomind/repomind.db" >> .gitignore
git add .gitignore docs/superpowers/
git status
```
