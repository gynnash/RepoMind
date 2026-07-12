---
name: repomind
description: Research reusable designs from public codebases for feature design, engineering patterns, and design rationale. Requires comparative evidence; not for syntax, single-API, or routine debugging questions.
metadata:
  argument-hint: "<design question>"
---

# RepoMind

Research public implementations relevant to `$ARGUMENTS` and turn comparative
evidence into reusable design guidance.

Use the bundled helper from this skill directory. Set
`SKILL_DIR=<absolute path to this skill>`: in Claude Code use
`${CLAUDE_SKILL_DIR}`; in Codex use the file source path shown for this
`SKILL.md`; elsewhere resolve the directory containing this file. Then set
`SEARCH_SCRIPT="$SKILL_DIR/scripts/search.py"`. It discovers the project root
and stores runtime state in that project's `.repomind/` directory.

## State 1: Before research confirmation

Route the request before beginning RepoMind research.

| Scenario | Action |
| --- | --- |
| Explicit query for feature design, engineering pattern, or design rationale | Treat `$ARGUMENTS` as confirmed and research directly. |
| No explicit query, but useful conversation context exists | Derive candidates in order from design material, task code, then lightweight repository context. Present one recommendation and 2–3 alternatives. Let the user edit the candidates, provide free-form input, or request another set. Wait for confirmation. |
| A syntax question or single API question | Reject RepoMind and answer with documentation or ordinary coding help. |
| Routine debugging or narrow implementation | Reject RepoMind and use normal debugging or implementation assistance. |

Before confirmation: Do not run the RepoMind helper. Do not initialize the database
or search cards. Do not search GitHub. Do not generate cards.
Permission: bounded read-only local inspection of candidate inputs is permitted; inspect only relevant README
sections, task code, or similarly lightweight repository context needed to propose questions.
Do not read RepoMind research references yet. If no credible design question can
be formed, ask for one rather than matching keywords.

## State 2: After research confirmation

Use the confirmed query as the authoritative research question. Treat project,
task, and conversation details only as adaptation-only context: they may shape
applicability, but must not silently change the question. Now continue through
the preconditions and cache workflow.

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

Derive bilingual design keywords, domain, relevant project technologies, a
repository query, and enough structure to judge adaptation.

### 2. Search local cards

Run `count`, then `search <keywords...>` or `all-cards` as appropriate. Apply
[references/relevance-evaluation.md](references/relevance-evaluation.md).
Assess cache sufficiency by question coverage, distinct approaches,
independent repositories, evidence quality, and freshness—not card count. Keep partial
matches and mark stale evidence.

### 3. Validate repository freshness

Run `repos-for-cards <ids...>` before any GitHub search. Reuse cards whose
repository is not due without network access. For each due repository, compare
the default-branch `HEAD`; if unchanged, persist the new schedule with
`record-repo-check`. If it changed, gather structural signals and classify the
change. Record unrelated changes with `record-repo-check`; for a localized
change run `affected-cards`, regenerate those cards, and commit them with
`refresh-cards`. A global structural change requires a full refresh.

Treat legacy cards missing source SHA, evidence paths, or related modules as an
unreliable mapping: on their first due changed-HEAD validation, `affected-cards`
signals a full refresh and the repository must be fully enriched. Never treat an
empty mapping as a localized no-op. `refresh-cards` receives the refreshed
snapshot and commit timestamps and atomically advances `next_check_at`.

If remote validation fails, retain the cached cards, label them unverified for
this run, and do not count them as verified evidence or force a rebuild.

### 4. Search GitHub conditionally

Only when the cache is insufficient, check `recent-empty-query`, then search
likely repositories and the domain query with `gh`. Merge candidates, respect
configured limits, and evaluate them with
[references/relevance-evaluation.md](references/relevance-evaluation.md).
Prefer maintained evidence, but permit classic repositories when their design
remains instructive; attach an explicit age warning instead of excluding them
solely for age. Record an empty query when applicable.

### 5. Analyze and store

Analyze qualifying repositories independently, in parallel when supported,
following [references/deep-analysis.md](references/deep-analysis.md). One
failure must not stop other analyses. Insert repositories and deduplicated cards
with serializer-generated JSON.

### 6. Synthesize

Fetch complete cards with `get-cards <ids...>` and follow
[references/output-format.md](references/output-format.md). Compare approaches,
cite evidence, explain tradeoffs and adaptation, and distinguish evidence from
inference.

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
