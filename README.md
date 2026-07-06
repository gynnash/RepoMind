# RepoMind

**Architecture research for coding agents, grounded in real open-source
implementations.**

RepoMind helps Claude Code and Codex find repositories that solve problems
similar to the system you are designing. It searches GitHub, evaluates
architectural relevance, extracts transferable design patterns, and returns
structured code cards that an agent can use during architecture work.

Instead of offering a generic list of popular projects, RepoMind asks a more
useful question:

> Which architectural decisions from existing codebases can be transferred to
> the project I am working on?

RepoMind is distributed from one source as:

- a Claude Code plugin;
- a Codex plugin; and
- a standalone Agent Skill.

## What RepoMind is for

Use RepoMind when you need evidence and precedent for decisions such as:

- choosing module boundaries and responsibilities;
- designing data flow and state management;
- building schedulers, orchestration layers, or task queues;
- comparing plugin, layered, event-driven, or service-based architectures;
- defining interfaces between major subsystems;
- understanding how mature projects evolved their architecture.

RepoMind is intentionally scoped to architecture research. It does not activate
for narrow syntax questions, framework API usage, routine debugging, or
requests such as “how do I implement `useState`?”

## Core capabilities

- **Architecture-aware search:** combines repository-name discovery with
  domain-oriented GitHub queries.
- **Evidence-based ranking:** scores domain fit, pattern relevance, technology
  overlap, and architectural depth—not popularity alone.
- **Structured code cards:** captures design decisions, transferable patterns,
  source references, and limitations.
- **Local-first caching:** reuses project-local cards, detects stale results,
  and avoids duplicate conclusions.

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

The standalone Claude Code command is:

```text
/repomind design a plugin-based event processing architecture
```

## How it works

```text
Architecture question
        |
        v
Intent and project-context analysis
        |
        v
Project-local card search ----------------------+
        | insufficient                           |
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
        +----------------> Code-card assembly <---+
```

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

## Development and validation

Run the complete test suite:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
```

Validate the Claude Code plugin and marketplace:

```bash
claude plugin validate ./plugins/repomind
claude plugin validate .
```

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
