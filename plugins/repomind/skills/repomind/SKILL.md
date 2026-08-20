---
name: repomind
description: Research reusable designs from public codebases for feature design, engineering patterns, and design rationale. Requires comparative evidence; not for syntax, single-API, or routine debugging questions.
metadata:
  argument-hint: "<design question>"
---

# RepoMind

Research public implementations for `$ARGUMENTS` and synthesize reusable,
evidence-backed design guidance.

Set `SKILL_DIR=<absolute path to this skill>`: Claude Code uses
`${CLAUDE_SKILL_DIR}`; Codex uses this `SKILL.md` file source path; other hosts
use this file's directory. Then set `SEARCH_SCRIPT="$SKILL_DIR/scripts/search.py"`.
The helper discovers the project root and stores state in `.repomind/`.

## State 1: Before research confirmation

Route before any RepoMind research.

| Scenario | Action |
| --- | --- |
| Explicit query for feature design, engineering pattern, or design rationale | Treat `$ARGUMENTS` as confirmed and research directly. |
| No explicit query, but useful conversation context exists | Derive candidates from design material, task code, then lightweight repository context. Present one recommendation and 2–3 alternatives; let the user edit the candidates, provide free-form input, or request another set. Wait for confirmation. |
| A syntax question or single API question | Reject RepoMind and answer with documentation or ordinary coding help. |
| Routine debugging or narrow implementation | Reject RepoMind and use normal debugging or implementation assistance. |

Before confirmation: Do not run the RepoMind helper. Do not initialize the database
or search cards. Do not search GitHub. Do not generate cards. Permission:
bounded read-only local inspection is allowed only for relevant README sections,
task code, or lightweight repository context needed to propose questions. Do not
read RepoMind research references yet. If no credible design question exists,
ask for one rather than matching keywords.

## State 2: After research confirmation

Use the confirmed query as the authoritative research question. Treat project,
task, and conversation details as adaptation-only context: they may shape
applicability, but must not silently change the question.

## Preconditions

Run:

```bash
test -f "$SEARCH_SCRIPT"
python3 "$SEARCH_SCRIPT" init
python3 "$SEARCH_SCRIPT" config
```

If `test -f "$SEARCH_SCRIPT"` fails, STOP and report the expected path and an
incomplete plugin installation or cache. Ask the user to reinstall or refresh.
Do not continue with a best-effort RepoMind-style workflow, and do not perform GitHub research without
the helper. Use returned limits; do not hard-code them.

## Cache workflow

### 1. Parse intent

Derive bilingual design keywords, domain, relevant technologies, a repository
query, and enough structure to judge adaptation.

### 2. Search local cards

Run `count`, then `search <keywords...>` or `all-cards` as appropriate. Apply
[references/relevance-evaluation.md](references/relevance-evaluation.md).
Assess cache sufficiency by question coverage, distinct approaches,
independent repositories, evidence quality, and freshness—not card count. Keep
partial matches and mark stale evidence.

### 3. Validate repository freshness

Run `repos-for-cards <ids...>` before any GitHub search. Reuse cards whose
repository is not due without network access. For each due repository, compare
the default-branch `HEAD`; if unchanged, persist the new schedule with
`record-repo-check`. If it changed, gather structural signals and classify the
change: unrelated -> `record-repo-check`; localized -> `affected-cards`, refresh
affected cards, then `refresh-cards`; global structural change -> full refresh.

legacy cards missing source SHA, evidence paths, or related modules are
unreliable: first due changed-HEAD validation requires full refresh. Never treat
empty mapping as a localized no-op. If remote validation fails, retain cached
cards, label them unverified, and do not count them as verified evidence.

### 4. Search GitHub conditionally

Only when the cache is insufficient, check `recent-empty-query`, then search
likely repositories and the domain query with `gh`. Merge candidates, respect
configured limits, and evaluate them with
[references/relevance-evaluation.md](references/relevance-evaluation.md).
Prefer maintained evidence, but permit classic repositories when their design
remains instructive; attach an age warning instead of excluding them solely for
age. Record an empty query when applicable.

### 5. Analyze and store

Analyze only qualifying repositories, in parallel when supported, following
[references/deep-analysis.md](references/deep-analysis.md). One failure must not
stop other analyses. Insert repositories and deduplicated cards with
serializer-generated JSON.

### 6. Synthesize

Fetch complete cards with `get-cards <ids...>` and follow
[references/output-format.md](references/output-format.md). Compare approaches,
cite evidence, explain tradeoffs and adaptation, and distinguish evidence from
inference.

## Token discipline

Prefer fewer, stronger sources. Do not paste source code or long README
excerpts. Keep intermediate notes out of the final answer. In synthesis, avoid
repeating the same evidence across sections.

## Collaboration states

- `proposed`: candidate question(s) await user selection or editing.
- `confirmed`: the authoritative research question is fixed.
- `researching`: cache and, conditionally, public repositories are examined.
- `synthesized`: comparative evidence and adaptation guidance are delivered.
- `blocked`: helper failure or unavailable evidence prevents honest synthesis.

## Helper interface

The helper accepts JSON positionally or from stdin with `-`:

```bash
printf '%s' "$REPO_JSON" | python3 "$SEARCH_SCRIPT" insert-repo -
printf '%s' "$CARD_JSON" | python3 "$SEARCH_SCRIPT" insert-card-if-new -
```

Always use a JSON serializer. Relevant commands: `init`, `config`, `count`,
`search`, `all-cards`, `get-cards`, `insert-repo`, `insert-card-if-new`,
`repos-for-cards`, `record-repo-check`, `affected-cards`, `refresh-cards`,
`recent-empty-query`, and `record-empty-query`.
