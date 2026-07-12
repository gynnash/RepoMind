# RepoMind

**Open-source implementation research for coding agents.**

RepoMind helps coding agents learn from real public implementations before
making an engineering decision. It can research implementation mechanisms,
engineering patterns, workflows, interfaces, design rationale, trade-offs,
evolution, and architecture.

It helps Claude Code and Codex answer a concrete research question with local
cached evidence and, when needed, public GitHub repositories. It evaluates
relevance, records traceable evidence as structured cards, and delivers a
synthesized research report adapted to the current project.

Instead of offering a generic list of popular projects, RepoMind asks a more
useful question:

> Which architectural decisions from existing codebases can be transferred to
> the project I am working on?

RepoMind is distributed from one source as:

- a Claude Code plugin;
- a Codex plugin; and
- a standalone Agent Skill.

For a complete end-to-end walkthrough, see the
[RepoMind Tutorial](docs/tutorial.md).

## Quick start

Install the Codex plugin:

```bash
codex plugin marketplace add gynnash/RepoMind --ref main
codex plugin add repomind@repomind
```

Start a new Codex thread after installation, then ask:

```text
Use RepoMind to find reusable architectures for a multi-agent task scheduler.
```

## What RepoMind is for

Use RepoMind when you need evidence and precedent for decisions such as:

- choosing module boundaries and responsibilities;
- designing data flow and state management;
- building schedulers, orchestration layers, or task queues;
- comparing plugin, layered, event-driven, or service-based architectures;
- defining interfaces between major subsystems;
- understanding how mature projects evolved their architecture.
- comparing concrete implementation mechanisms or engineering workflows;
- investigating why a public project chose a design and how it evolved.

## What RepoMind is not for

RepoMind is scoped to reusable engineering research, not architecture alone.
It does not activate for narrow syntax questions, single framework API usage,
routine debugging, or requests such as “how do I implement `useState`?”

## Predictable invocation

An explicit query is authoritative: RepoMind researches it directly. Project
files provide constraints and an adaptation target, but never replace or
silently rewrite the question. Without a query, RepoMind proposes one recommended
direction and 2–3 alternatives, then waits. You may edit a candidate, provide a
free-form direction, request another set, or replace all candidates before any
cache or GitHub research begins.

| Project | Query supplied | Behavior |
| --- | --- | --- |
| New | No | Infer candidates from conversation and design material; wait for confirmation. |
| New | Yes | Research the explicit query; use design material only as constraints. |
| Existing | No | Prefer the current task, then lightly inspect relevant repository context; propose candidates. |
| Existing | Yes | Research the explicit query; use the repository only for adaptation analysis. |

Examples beyond architecture:

```text
Use RepoMind to compare how mature CLI tools implement resumable downloads.
Use RepoMind to research design rationale for append-only event logs.
Use RepoMind to find engineering patterns for safe plugin upgrade workflows.
```

## Core capabilities

- **Architecture-aware search:** combines repository-name discovery with
  domain-oriented GitHub queries.
- **Evidence-based ranking:** scores domain fit, pattern relevance, technology
  overlap, and architectural depth—not popularity alone.
- **Structured code cards:** captures design decisions, transferable patterns,
  source references, and limitations.
- **Local-first caching:** reuses project-local cards, detects stale results,
  and avoids duplicate conclusions.

## Example output

A RepoMind card summarizes why a repository is relevant, what design choices it
uses, which files support the conclusion, and what should not be copied
directly.

```xml
<repo-card
  repo="example/scheduler"
  dimension="architecture"
  relevance="4.5">

### architecture

#### Overview
Uses a small control plane to persist task state and dispatch work to pluggable
executors.

#### Transferable Patterns
- Keep scheduling decisions separate from execution backends.
- Model retries as explicit task-state transitions.

#### Source References
- `internal/scheduler/state.go`
- `internal/executor/registry.go`

#### Limitations
The worker model assumes a single-region deployment and should be adapted for
distributed coordination.
</repo-card>
```

## Requirements

- Python 3.9 or newer
- [GitHub CLI](https://cli.github.com/)
- an authenticated GitHub CLI session:

  ```bash
  gh auth login
  ```

- Claude Code or Codex

RepoMind has no Python package dependencies; its helper uses only the standard
library.

## Installation

### Codex plugin

Add the repository as a Codex marketplace and install RepoMind:

```bash
codex plugin marketplace add gynnash/RepoMind --ref main
codex plugin add repomind@repomind
```

Start a new Codex thread after installation so the new plugin is loaded. You
can then explicitly ask Codex to use RepoMind or ask an architecture research
question that matches the Skill description.

Example:

```text
Use RepoMind to find reusable architectures for a multi-agent task scheduler.
```

### Claude Code plugin

Add the GitHub repository as a marketplace and install the plugin:

```bash
claude plugin marketplace add gynnash/RepoMind
claude plugin install repomind@repomind
```

Invoke the namespaced plugin skill:

```text
/repomind:repomind design an agent scheduling layer with priority queues
```

### Standalone Agent Skill

Clone the repository and copy the canonical Skill directory into either host:

```bash
git clone https://github.com/gynnash/RepoMind.git
cd RepoMind

# Claude Code
cp -R plugins/repomind/skills/repomind ~/.claude/skills/

# Codex
cp -R plugins/repomind/skills/repomind ~/.codex/skills/
```

In Claude Code, the standalone command is:

```text
/repomind design a plugin-based event processing architecture
```

In Codex, ask directly:

```text
Use RepoMind to design a plugin-based event processing architecture.
```

## How it works

```text
Confirmed research question
        |
        v
Intent and project-context analysis
        |
        v
Project-local card search and freshness check --+
        | insufficient or due                    |
        v                                        |
GitHub candidate discovery                       |
        |                                        |
        v                                        |
Metadata and README relevance filtering          |
        |                                        |
        v                                        |
Parallel repository analysis                     |
        |                                        |
        v                                        |
Deduplication and SQLite persistence              |
        |                                        |
        +------------> Synthesized report <-------+
```

Cache sufficiency depends on coverage of the question, distinct approaches,
independent repositories, evidence quality, and freshness—not card count. Each
source repository has an adaptive validation interval, configurable within the
recommended 1–30 days. A repository not due is reused without network access.
When due, an unchanged SHA preserves its cards; a localized relevant change
refreshes only mapped cards; a global or unmappable change refreshes all cards
for that repository. Replacements are atomic, so failed refreshes preserve the
older evidence and disclose its state.

The synthesized research report gives a direct answer, compares approaches,
cites repository files or documents, explains constraints and trade-offs,
adapts findings to the current project, and identifies evidence freshness. Its
stable result envelope is:

```text
complete|partial|needs_clarification|out_of_scope|unavailable
```

## Cross-plugin collaboration

RepoMind can supply evidence to another plugin without giving that plugin
direct access to its database or helper. For example, a planning plugin can ask
RepoMind to research task-queue cancellation, consume a `complete` or `partial`
report, and remain responsible for the final plan. RepoMind owns research and
provenance; the caller owns the design decision.

The implementation is organized as a single portable Skill:

```text
plugins/repomind/
├── .claude-plugin/plugin.json
├── .codex-plugin/plugin.json
└── skills/repomind/
    ├── SKILL.md
    ├── agents/openai.yaml
    ├── config/defaults.json
    ├── references/
    └── scripts/search.py
```

Claude Code and Codex consume the same `SKILL.md`, scripts, configuration, and
reference material. Platform manifests provide installation metadata without
forking the core implementation.

## Runtime data and privacy

RepoMind stores runtime data inside the project being analyzed:

```text
<project>/.repomind/repomind.db
```

The database, WAL files, and Python caches are excluded from Git by default.
Repository searches are made from the user's machine through the authenticated
`gh` CLI. RepoMind does not require a hosted RepoMind service and does not send
the local card database to the project maintainer.

To override bundled defaults, create:

```text
<project>/.repomind/config.json
```

Only include values you want to change. RepoMind validates configuration keys,
types, and ranges before using them.

## Open-source policy

RepoMind is open source under the [MIT License](LICENSE). You may use, copy,
modify, publish, and redistribute it, including in commercial projects, subject
to the license notice.

Contributions are welcome through GitHub issues and pull requests. Proposed
changes should:

- preserve the single-source Skill layout;
- remain compatible with both Claude Code and Codex;
- avoid introducing required Python dependencies where the standard library is
  sufficient; and
- include tests for behavioral or packaging changes.

RepoMind analyzes third-party repositories but does not relicense their source
code. Code cards should summarize architectural ideas and cite source paths;
users remain responsible for complying with the licenses of referenced
projects.

## Development and validation

Run the complete test suite:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

The suite includes contract tests for the Skill package and a deterministic
comparative usefulness evaluation. RepoMind-style answers must improve the
derived total score by at least 30% over a generic baseline and must not
regress on relevance or specificity. The deterministic fixture is resolved
from the repository root at `tests/fixtures/usefulness_cases.json`, so the test
works regardless of the caller's current working directory.

Validate the Claude Code plugin and marketplace:

```bash
claude plugin validate ./plugins/repomind
claude plugin validate .
```
