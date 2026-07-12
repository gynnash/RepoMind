# RepoMind Tutorial

This tutorial walks through RepoMind's generalized research workflow in both
Claude Code and Codex: direction discovery, explicit questions, synthesized
reports, adaptive cache validation, and collaboration with another plugin.

The example task is:

> Design a scheduling layer for a multi-agent system with priorities, retries,
> and multiple execution backends.

## 1. Understand the goal

RepoMind is an open-source implementation research Skill. Use it to investigate
implementation mechanisms, workflows, interfaces, rationale, trade-offs,
evolution, architecture, and other reusable engineering patterns.

It is not a general GitHub search assistant. A good RepoMind request names a
reusable implementation mechanism, engineering or design pattern, workflow,
interface, or design rationale:

```text
Find reusable architectures for a multi-agent task scheduler with priorities,
retries, persistent state, and pluggable execution backends.
```

A request such as the following is too broad:

```text
Design my backend.
```

A request such as this is too narrow because it asks for syntax-level
implementation rather than comparative research:

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

The plugin command is namespaced and accepts a research question:

```text
/repomind:repomind <research question>
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
reusable implementation or engineering-design research.

## 4. Try the invocation scenarios

### No-query discovery

Invoke RepoMind without a question while discussing a new design. It derives
one recommended direction and 2–3 alternatives from the conversation and
design materials. In an existing project it prefers the current task, then may
inspect only relevant README, plan, manifest, or code context. Research has not
started yet: edit a candidate, enter a free-form direction, ask for another
set, or replace all candidates. RepoMind waits for confirmation before reading
the cache or contacting GitHub.

### New project with an explicit query

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

The query is authoritative. Project material may constrain the answer but does
not broaden, narrow, or replace the research goal. On a new project, the local
card database is empty. RepoMind should report its
progress through these stages:

1. Parse the research intent and inspect the current project.
2. Check the local code-card cache.
3. Search GitHub for candidate repositories.
4. Reject archived, stale, or weakly documented candidates.
5. Score the remaining repositories for relevance to the research question.
6. Analyze accepted repositories.
7. Save new cards and assemble the response.

GitHub commands remain subject to your normal Claude Code or Codex permission
settings. Review the proposed commands before approving them.

### Existing project with a non-architecture query

RepoMind also handles reusable engineering questions such as:

```text
Use RepoMind to compare how established Python CLIs implement resumable,
idempotent downloads and explain the trade-offs for this project.
```

It researches that mechanism directly and uses the existing repository only
to adapt findings. Narrow syntax questions, single-framework API usage, and
routine debugging remain out of scope.

## 5. Read the synthesized report

RepoMind returns a synthesized answer, not merely raw cards. It summarizes the
conclusion, compares implementation routes, cites public files or documents,
explains trade-offs and limitations, adapts findings without changing the
question, and labels evidence freshness. Cards remain traceable evidence:

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
- **Relevance** reflects fit with your research question.
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

## 7. Reuse and refresh the local cache

RepoMind stores generated cards at:

```text
<project>/.repomind/repomind.db
```

Run a related request from the same project:

```text
Use RepoMind to compare persistent task-state models for the scheduler.
```

RepoMind checks local cards before GitHub and judges sufficiency by question
coverage, distinct approaches, independent repositories, evidence quality, and
freshness. Card count alone is insufficient.

Freshness is tracked per source repository on an adaptive schedule, normally
bounded to 1–30 days. If a matching repository is not due, its cards are reused
without network access. When it is due:

- an unchanged SHA updates only the check schedule and reuses every card;
- a localized change regenerates only cards mapped to affected evidence;
- a global or unmappable change regenerates all cards for that repository;
- an unrelated change updates the snapshot without rewriting cards.

Replacement is atomic. If validation or generation fails, old evidence remains
available but is marked unverified, `refresh_failed`, or `refresh_required`
rather than presented as freshly checked.

## 8. Collaborate with another plugin

A planning or brainstorming plugin can call RepoMind with a structured research
request and consume its report. It should handle all five states:

```xml
<repomind-result status="complete|partial|needs_clarification|out_of_scope|unavailable">
```

In particular, `status="partial"` means useful evidence exists but coverage or
freshness is insufficient. The caller may use it with that limitation, ask a
follow-up question, or continue its own work; it must not present partial
evidence as complete. The caller owns the final decision, while RepoMind owns
research, cache validation, and provenance.

## 9. Customize RepoMind

Bundled defaults work for most projects. To override them, create:

```text
<project>/.repomind/config.json
```

For example:

```json
{
  "max_search_repos": 12,
  "min_relevance_score": 4.0,
  "freshness_min_days": 2,
  "freshness_max_days": 21
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
| `empty_query_ttl_hours` | Empty-search suppression period | `24` |
| `freshness_min_days` | Minimum adaptive check interval | `1` |
| `freshness_max_days` | Maximum adaptive check interval | `30` |
| `freshness_default_days` | Interval used with insufficient history | `7` |
| `freshness_commit_sample_size` | Recent commits sampled for cadence | `20` |
| `freshness_stability_growth` | Multiplier after stable checks | `1.5` |
| `freshness_change_decay` | Multiplier after a global relevant change | `0.5` |

Use a higher relevance threshold for focused research. Reduce
`max_search_repos` when you want a faster, narrower search.

## 10. Troubleshooting

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

### RepoMind says the helper script is missing

RepoMind must use its bundled helper at:

```text
<plugin>/skills/repomind/scripts/search.py
```

If Codex reports that only `SKILL.md` is available, the plugin cache or thread
state is stale. Check that the installed plugin package contains
`scripts/search.py`, then reinstall or refresh the plugin and open a new Codex
thread. Treat any answer produced without the helper as a degraded fallback,
not a complete RepoMind run.

### RepoMind refuses the request

Rewrite the request around a reusable implementation mechanism, engineering or
design pattern, workflow, interface, or design rationale. Include the domain,
important constraints, and relevant project context. Narrow syntax questions,
single-framework API usage, and routine debugging remain out of scope.

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

## 11. Next steps

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
