---
name: repomind
description: Find architecturally similar open-source repositories and extract reusable architecture, module-boundary, data-flow, scheduling, and design-pattern code cards. Use for architecture research and design decisions; do not use for narrow implementation or API-usage questions.
metadata:
  argument-hint: "<architecture question>"
---

# RepoMind

Research open-source implementations relevant to this architecture request:

`$ARGUMENTS`

Use the bundled helper from this skill directory. Set
`SKILL_DIR=<absolute path to this skill>`: in Claude Code use
`${CLAUDE_SKILL_DIR}`; in Codex use the file source path shown for this
`SKILL.md`; in other hosts resolve the directory containing this file. Then set
`SEARCH_SCRIPT="$SKILL_DIR/scripts/search.py"`. The helper discovers the
current project root automatically and stores runtime state in that project's
`.repomind/` directory.

## Mandatory scope gate

Classify `$ARGUMENTS` before reading references or running any command.

- Proceed only when the request asks for architecture, module boundaries,
  system data flow, orchestration, scheduling architecture, or transferable
  design patterns.
- For a narrow implementation, syntax, framework API, debugging, or
  how-to-code question, STOP. Do not run any tool, initialize the database,
  read references, or search GitHub. Explain that RepoMind is for architecture
  research and direct the user to framework documentation or ordinary coding
  assistance.
- For an overly broad architecture request, STOP and ask for the architectural
  concern to research.

## Preconditions

After the scope gate passes, run:

```bash
test -f "$SEARCH_SCRIPT"
python3 "$SEARCH_SCRIPT" init
python3 "$SEARCH_SCRIPT" config
```

If `test -f "$SEARCH_SCRIPT"` fails, STOP and report that the RepoMind plugin
installation or cache is incomplete. Include the expected `SEARCH_SCRIPT` path
and ask the user to reinstall or refresh the plugin. Do not continue with a
best-effort RepoMind-style workflow, and do not perform GitHub research without
the helper.

Use the returned limits and thresholds. Do not hard-code replacements.

## 1. Parse intent

Derive:

- 3–5 Chinese and English architectural keywords
- languages, frameworks, and dependencies from the current project
- the problem domain
- a GitHub repository search query
- the project's top-level structure

## 2. Search local cards

Run `count`.

- For fewer than five cards, run `search <keywords...>`. Preserve every result
  and its helper-provided relevance.
- For five or more cards, run `all-cards`, then follow
  [references/relevance-evaluation.md](references/relevance-evaluation.md) to
  select up to ten cards scoring at least 3.
- If at least three relevant cards exist, continue to assembly.
- Keep partial local matches when continuing to GitHub.
- If a card is stale, ask whether to refresh it. If declined, return it with a
  stale marker.

## 3. Search and filter GitHub

Before network access, run:

```bash
python3 "$SEARCH_SCRIPT" recent-empty-query "$ARGUMENTS"
```

If the response is recent, return local matches and recommend broader terms.
Otherwise report that GitHub search is starting.

Generate two candidate sets:

1. Search 3–5 likely repository names with `gh search repos`.
2. Search the generated domain query with `gh search repos`.

Request `fullName,url,language,topics,stargazersCount,description`, merge by
`fullName`, sort by stars, and cap at configured `max_search_repos`.

For each candidate:

1. Use `gh repo view` to skip archived repositories or repositories not pushed
   in two years.
2. Score description and topics for domain relevance; retain scores of 3+.
3. Fetch and decode the README. Skip image/link-only READMEs and non-English
   READMEs without architectural information.
4. Apply the fine evaluation in
   [references/relevance-evaluation.md](references/relevance-evaluation.md).

If GitHub returned no candidates, run:

```bash
python3 "$SEARCH_SCRIPT" record-empty-query "$ARGUMENTS"
```

Then return partial local results.

## 4. Analyze repositories

Analyze every repository meeting configured `min_relevance_score` in parallel
when the host supports parallel agents. Follow
[references/deep-analysis.md](references/deep-analysis.md) exactly.

One repository failure must not stop other analyses. Collect new card IDs,
duplicate IDs, repository relevance, and failures.

## 5. Assemble results

Merge local IDs, new IDs, and duplicate IDs by card ID. Retrieve complete cards
with `get-cards <ids...>`, then follow
[references/output-format.md](references/output-format.md).

Sort by relevance descending and stars descending. Use local keyword relevance
for V1 cards, semantic scores for V2 cards, and repository overall relevance
for newly analyzed or duplicate cards.

## Helper interface

The helper accepts JSON as a positional value or from stdin with `-`:

```bash
printf '%s' "$REPO_JSON" | python3 "$SEARCH_SCRIPT" insert-repo -
printf '%s' "$CARD_JSON" | python3 "$SEARCH_SCRIPT" insert-card-if-new -
```

Always generate payloads with a JSON serializer. Never interpolate unescaped
Markdown into shell-quoted JSON.

Relevant commands are `init`, `config`, `count`, `search`, `all-cards`,
`get-cards`, `insert-repo`, `insert-card-if-new`, `recent-empty-query`, and
`record-empty-query`.
