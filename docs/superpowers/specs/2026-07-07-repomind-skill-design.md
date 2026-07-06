# RepoMind Skill Design

## Overview

RepoMind is a Claude Code skill that searches GitHub for open-source, popular, classic codebases similar to the user's current project, extracts architecture design and design philosophy, and summarizes them into structured "code cards" to assist code agents in architecture design.

## Trigger Mode

- **Primary**: Explicit command `/repomind <query>` — user knowingly invokes when external reference is needed
- **Secondary**: Lightweight auto-suggestion — when brainstorming/writing-plans skills enter architecture design phase, check local DB for relevant cards and suggest if available (read-only, no cost)

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Claude Code Skill                     │
│                   /repomind <query>                       │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────┐   ┌──────────┐   ┌──────────────────┐    │
│  │ 意图解析  │──▶│ 本地检索  │──▶│ 卡片组装 & 输出   │    │
│  │ (LLM)    │   │ (SQLite) │   │ (LLM)            │    │
│  └──────────┘   └────┬─────┘   └──────────────────┘    │
│                      │ 不足                              │
│                      ▼                                   │
│  ┌──────────────────────────────────────────────────┐   │
│  │            GitHub 搜索 & 分析流水线                │   │
│  │                                                   │   │
│  │  LLM生成Query → gh search → README过滤(LLM)       │   │
│  │       → Agent并行深度分析 → 生成卡片 → 写入SQLite   │   │
│  └──────────────────────────────────────────────────┘   │
│                                                          │
├─────────────────────────────────────────────────────────┤
│  持久层                                                  │
│  ┌──────────────────────┐  ┌────────────────────────┐  │
│  │  SQLite 数据库        │  │  辅助脚本               │  │
│  │  .repomind/repomind.db│  │  .repomind/search.py   │  │
│  └──────────────────────┘  └────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
```

### Components

| Component | Responsibility | Implementation |
|-----------|---------------|----------------|
| Intent Parser | Convert natural language to structured search intent (keywords, tech stack, domain, github query) | LLM call within skill |
| Local Search Engine | Manage SQLite, execute keyword/LLM-based search, return cached cards | Python script |
| GitHub Analysis Pipeline | Search repos → README filter → parallel deep analysis → structured extraction | gh CLI + Agent tool |
| Card Assembler | Reorganize matching cards into LLM-friendly context format based on user query | LLM call within skill |

## Database Schema

```sql
CREATE TABLE repos (
    id          INTEGER PRIMARY KEY,
    full_name   TEXT UNIQUE NOT NULL,
    url         TEXT NOT NULL,
    language    TEXT,
    topics      TEXT,                    -- JSON array
    stars       INTEGER,
    description TEXT,
    fetched_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE cards (
    id          INTEGER PRIMARY KEY,
    repo_id     INTEGER REFERENCES repos(id),
    dimension   TEXT NOT NULL,           -- architecture | design_patterns | data_flow
                                         -- | interface_design | tech_stack | deployment
                                         -- | evolution_history
    title       TEXT NOT NULL,
    content     TEXT NOT NULL,           -- Markdown, ends with ## 相关卡片 section for natural language references
    keywords    TEXT,                    -- Comma-separated Chinese + English keywords
    embedding   BLOB,                    -- Reserved for future semantic search
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## Card Dimensions (7 standard dimensions)

| Dimension | Description |
|-----------|-------------|
| `architecture` | Top-level architectural pattern (layered/microservices/plugin-based), module division and responsibilities |
| `design_patterns` | Key design patterns, their usage scenarios and implementation approaches |
| `data_flow` | Data flow from entry to output, state management |
| `interface_design` | API design, inter-module interfaces, external contracts |
| `tech_stack` | Technology choices and rationale |
| `deployment` | Deployment architecture, CI/CD, environment management (if available) |
| `evolution_history` | Major refactoring decisions, architectural evolution (if available) |

## Skill Workflow

```
/repomind "design an agent scheduling layer"

1. Intent Parsing (LLM)
   Input: "design an agent scheduling layer"
   Output: {keywords: [...], tech_stack: [...], domain: "...", github_query: "..."}

2. Local Retrieval
   SELECT COUNT(*) FROM cards → determine card count
   IF < 5:  keyword LIKE/INSTR matching
   IF >= 5: LLM semantic relevance scoring, take top K
   Hit → jump to step 5; Insufficient → continue

3. GitHub Search & Filter (layered strategy)
   3a. Dual-approach query generation:
       - Approach 1: LLM identifies similar repos by name/domain → gh search by repo name
       - Approach 2: LLM converts user intent to GitHub search query → gh search by code/topic
       - Both results merged and deduplicated
   3b. gh search repos --sort stars --limit 20
   3c. Fetch README per repo, LLM relevance evaluation (four-dimension scoring)
   3d. overall >= 3.5 → deep analysis; < 3.5 → skip

4. Parallel Deep Analysis (Agent tool)
   One Agent per repo, analyze designated dimensions
   Output → structured cards → write to SQLite

5. Card Assembly & Return
   Collect all matching cards
   Sort by relevance, assemble as LLM-friendly context
   Format: <repo-card title="..." dimension="..." relevance="...">content</repo-card>
```

## Relevance Evaluation (Step 3b Detail)

### Four-Dimension Scoring Model

For each candidate repo, LLM must output:

```json
{
  "repo": "owner/repo",
  "scores": {
    "domain_match":    0-5,  // Same/adjacent problem domain
    "arch_pattern":    0-5,  // Architecture pattern transferability
    "tech_overlap":    0-5,  // Tech stack overlap
    "depth_quality":   0-5   // README/docs architectural information density
  },
  "overall": weighted_average,  // domain_match 40%, others 20% each
  "evidence": ["README L45-60 describes event bus decoupling approach", ...],
  "key_insight": "One sentence: the most valuable reference point for current design",
  "verdict": "deep_analyze | skip"
}
```

### Scoring Rubric

| Dimension | 0-1 | 2-3 | 4-5 |
|-----------|-----|-----|-----|
| domain_match | Completely different domain | Adjacent domain or sub-domain overlap | Same problem domain, directly comparable |
| arch_pattern | No architectural description | Architectural concepts mentioned but not detailed | Clear architectural pattern described, directly referenceable |
| tech_overlap | Completely different tech stack | Partial overlap | Core dependencies highly consistent |
| depth_quality | Only feature descriptions | Module division described | Architecture diagrams, ADR, design docs, or detailed directory structure |

### Reliability Mechanisms

1. **Mandatory evidence citation**: Scores >= 3 must cite specific README passages as evidence
2. **User codebase context injection**: Evaluate with user's codebase info (language, framework, directory structure, core dependencies) as anchor — "can this architecture migrate to the user's project?"
3. **Two-round filtering**: Coarse filter (description + topics, no API cost) → Fine filter (README, four-dimension evaluation)
4. **Veto clauses** (auto-skip, no scoring needed):
   - README is purely non-English (Chinese/Japanese/Korean etc.) AND contains no architectural information
   - Repo is archived or not updated for > 2 years

## Deep Analysis Template (Step 4)

Each repo gets one Agent, output structure per card:

```markdown
## {repo_name} - {dimension}

### Overview
{2-3 sentence summary of core characteristics in this dimension}

### Key Design
{3-5 key points, each with specific implementation details}

### Transferable Patterns
{Which designs can be directly or slightly adapted applied to current project}

### Source References
{Specific file paths and line numbers as evidence}

### Limitations
{Applicable boundaries, known issues, unsuitable scenarios}
```

Mandatory dimensions: `architecture`, `design_patterns`, `data_flow`
Optional dimensions (based on repo content): `interface_design`, `tech_stack`, `deployment`, `evolution_history`

## Output Format

```markdown
## RepoMind Code Cards

> Search intent: design an agent scheduling layer
> Matched repos: 3 | Cards: 12

<repo-card id="1" repo="langchain/langchain" dimension="architecture" 
           relevance="0.92" stars="95000">
## Runnable Abstraction Layer Design
...
</repo-card>
```

XML-wrapped cards for easy model parsing.

## Error Handling

### GitHub API

| Scenario | Handling |
|----------|----------|
| Rate limit (429) | Report wait time to user, return partial local results |
| Unauthenticated | Prompt `gh auth login`; fall back to unauthenticated API (60 req/h) |
| Repo deleted/private | Skip, log, do not interrupt pipeline |
| No search results | Inform user, suggest query adjustment; record to avoid repeat ineffective searches |

### Deep Analysis

| Scenario | Handling |
|----------|----------|
| Repo too large, Agent token overflow | Analyze directory structure + README + top-level file headers only; card marked `depth: partial` |
| README is images/links only | Skip directly, no scoring |
| Agent timeout or error | Single repo failure does not affect overall; card marked `status: failed` with reason; return partial results |
| Multiple repos yield similar conclusions | Dedup before write: title + keyword overlap > 70% → merge rather than add new |

### Local Database

| Scenario | Handling |
|----------|----------|
| First use, no database | Auto `init`: create `.repomind/` directory and `repomind.db`, initialize schema |
| Database corruption | Detect and alert; support `repomind reset-db` to rebuild |
| Card staleness | If repo > 6 months stale AND user re-searches same domain, prompt "Some cards may be outdated, refresh?" |

### User Experience

| Scenario | Handling |
|----------|----------|
| Query too broad ("design a backend") | Do not search; ask user to focus direction first |
| Query too specific ("how to implement React useState") | Identify as implementation question, not architecture; redirect to docs |
| Long search + analysis time | Report progress step by step |

## Search Strategy

### Local Retrieval

- Card count < 5: `LIKE`/`INSTR` keyword matching on `keywords` field
- Card count >= 5: LLM semantic relevance scoring on card title + content, take top K

### GitHub Similarity Matching

Two complementary approaches:
1. LLM identifies similar repos by name/domain → search GitHub by name
2. LLM converts user intent to GitHub search query → relevance check against README

### Caching

Every search builds local structured database. Subsequent searches check local DB first; only fetch from GitHub when insufficient.

## File Structure

```
.repomind/
├── repomind.db          # SQLite database
├── search.py            # Database read/write + search helper
└── config.json          # Optional: user preferences (default sort, max repos, etc.)
```
