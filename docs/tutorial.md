# RepoMind Tutorial

This tutorial walks through a complete RepoMind workflow in both Claude Code
and Codex. You will install the plugin, run an architecture search, interpret
the resulting code cards, reuse the local cache, and customize the search
policy.

The example task is:

> Design a scheduling layer for a multi-agent system with priorities, retries,
> and multiple execution backends.

## 1. Understand the goal

RepoMind is an architecture research Skill. It is useful when you want to learn
from real repositories before committing to module boundaries, data flow,
interfaces, or system-level design patterns.

It is not a general GitHub search assistant. A good RepoMind request names an
architectural concern:

```text
Find reusable architectures for a multi-agent task scheduler with priorities,
retries, persistent state, and pluggable execution backends.
```

A request such as the following is too broad:

```text
Design my backend.
```

A request such as this is too narrow:

```text
How do I write a Python priority queue?
```

RepoMind should ask you to narrow the first request and redirect the second to
ordinary coding assistance.

## 2. Prepare your environment

RepoMind requires Python 3.9 or newer and the GitHub CLI.

Check Python:

```bash
python3 --version
```

Install the GitHub CLI using the instructions for your operating system at
[cli.github.com](https://cli.github.com/), then authenticate:

```bash
gh auth login
gh auth status
```

Run RepoMind from the root of the project you are designing. The helper locates
the current Git repository and keeps its cache there.

For a scratch tutorial project:

```bash
mkdir scheduler-design
cd scheduler-design
git init
```

## 3. Install RepoMind

Choose the host you use. Both installations load the same Skill, scripts, and
reference material.

### Option A: Claude Code

Add the RepoMind GitHub marketplace:

```bash
claude plugin marketplace add gynnash/RepoMind
```

Install the plugin:

```bash
claude plugin install repomind@repomind
```

Start Claude Code:

```bash
claude
```

The plugin command is namespaced:

```text
/repomind:repomind <architecture question>
```

If the command does not appear immediately, restart Claude Code or run
`/reload-plugins`.

### Option B: Codex

Add the RepoMind Git marketplace:

```bash
codex plugin marketplace add gynnash/RepoMind --ref main
```

Install the plugin:

```bash
codex plugin add repomind@repomind
```

Start a new Codex thread after installation. In Codex, invoke RepoMind by name:

```text
Use RepoMind to research an architecture for a multi-agent task scheduler with
priorities, retries, persistent state, and pluggable execution backends.
```

RepoMind can also activate automatically when a request clearly asks for
architecture research.

## 4. Run the first architecture search

### Claude Code request

```text
/repomind:repomind design a multi-agent task scheduler with priorities,
retries, persistent state, and pluggable execution backends
```

### Codex request

```text
Use RepoMind to design a multi-agent task scheduler with priorities, retries,
persistent state, and pluggable execution backends.
```

On a new project, the local card database is empty. RepoMind should report its
progress through these stages:

1. Parse the architecture intent and inspect the current project.
2. Check the local code-card cache.
3. Search GitHub for candidate repositories.
4. Reject archived, stale, or weakly documented candidates.
5. Score the remaining repositories for architectural relevance.
6. Analyze accepted repositories.
7. Save new cards and assemble the response.

GitHub commands remain subject to your normal Claude Code or Codex permission
settings. Review the proposed commands before approving them.

## 5. Read a code card

RepoMind returns XML-wrapped Markdown so another coding agent can reliably
identify each card:

```xml
<repo-card
  id="12"
  repo="example/project"
  dimension="architecture"
  relevance="4.4"
  stars="12000"
  stale="false">

### architecture

#### Overview
...

#### Key Design
...

#### Transferable Patterns
...

#### Source References
...

#### Limitations
...
</repo-card>
```

Pay attention to five fields:

- **Dimension** tells you whether the card covers architecture, data flow,
  interfaces, deployment, or another design concern.
- **Relevance** reflects architectural fit with your request.
- **Key Design** describes concrete implementation choices.
- **Source References** identifies the files or documentation supporting the
  conclusion.
- **Limitations** explains where the pattern may not transfer safely.

Treat cards as researched design input, not as instructions to copy an entire
architecture. Compare the repository's scale, language, deployment model, and
operational constraints with your own project.

## 6. Turn research into a design decision

After reviewing the cards, ask the host agent to synthesize them for your
project:

```text
Using the RepoMind cards, propose a scheduler architecture for this project.
Separate the control plane from execution, define the task state machine, and
explain which patterns should not be copied.
```

Useful follow-up questions include:

```text
Compare the executor abstractions found in these cards.
```

```text
Which persistence model best supports retries and crash recovery?
```

```text
Create a decision table covering scalability, complexity, and operational
cost.
```

```text
Draft module boundaries and interfaces, citing the relevant RepoMind cards.
```

The strongest workflow is research first, synthesis second, implementation
planning third.

## 7. Reuse the local cache

RepoMind stores generated cards at:

```text
<project>/.repomind/repomind.db
```

Run a related request from the same project:

```text
Use RepoMind to compare persistent task-state models for the scheduler.
```

RepoMind checks local cards before calling GitHub. With a small cache it uses
keyword matching; with a larger cache it asks the model to score card
relevance. If enough cards match, it can answer without another repository
search.

Cards older than the configured freshness period are marked stale. RepoMind
should ask whether you want to refresh them rather than silently replacing
them.

## 8. Customize RepoMind

Bundled defaults work for most projects. To override them, create:

```text
<project>/.repomind/config.json
```

For example:

```json
{
  "max_search_repos": 12,
  "min_relevance_score": 4.0,
  "card_staleness_months": 3
}
```

Project configuration is merged over the bundled defaults. Unknown keys,
incorrect types, and out-of-range values are rejected with a structured error.

Available settings:

| Setting | Purpose | Default |
|---|---|---:|
| `max_search_repos` | Maximum GitHub candidates | `20` |
| `min_relevance_score` | Fine-filter acceptance score | `3.5` |
| `card_similarity_threshold` | Duplicate-card threshold | `0.7` |
| `card_staleness_months` | Card freshness period | `6` |
| `empty_query_ttl_hours` | Empty-search suppression period | `24` |
| `mandatory_dimensions` | Cards generated for every accepted repo | architecture, design patterns, data flow |
| `optional_dimensions` | Cards generated only when evidence exists | interfaces, stack, deployment, evolution |

Use a higher relevance threshold for focused research. Reduce
`max_search_repos` when you want a faster, narrower search.

## 9. Troubleshooting

### GitHub authentication fails

Run:

```bash
gh auth status
gh auth login
```

RepoMind cannot perform its GitHub pipeline until `gh` can access the API.

### The Skill is not visible in Claude Code

Check that the plugin is installed:

```bash
claude plugin list
```

Then restart Claude Code or run `/reload-plugins`.

### The plugin is not visible in Codex

Check configured marketplaces and plugins:

```bash
codex plugin marketplace list
codex plugin list
```

After installing or updating a plugin, open a new thread.

### RepoMind refuses the request

Rewrite the request around a system-level decision. Include the domain,
architectural concern, important constraints, and relevant project context.

### GitHub rate limits interrupt the search

RepoMind should return any local or partial results it already has. Wait until
the GitHub rate limit resets, then retry.

### The local database is corrupted

Back up this directory before rebuilding:

```text
<project>/.repomind/
```

The database contains locally generated research cards. Removing it discards
the cache but does not change your project source code.

## 10. Next steps

Try RepoMind on a real architecture decision from your project:

```text
Use RepoMind to find proven plugin architectures for an event-processing
system that needs isolated extensions, versioned contracts, and failure
containment.
```

Then ask your coding agent to produce an architecture decision record based on
the returned evidence, including rejected alternatives and migration risks.

For a shorter overview, installation reference, and project architecture, see
the main [README](../README.md).
