# RepoMind Usability and Generalized Research Design

## 1. Purpose

RepoMind will become a general open-source implementation research tool. It
will extract transferable evidence about architectures, feature designs,
engineering patterns, workflows, interfaces, design philosophies, and
evolution trade-offs from public repositories.

RepoMind will not handle ordinary syntax questions, single-API usage, or
routine debugging. Its boundary is whether a question benefits from comparing
public implementations and extracting reusable design or engineering evidence,
not whether the question is strictly about architecture.

The redesign must make four invocation scenarios predictable:

1. A new codebase without a query.
2. A new codebase with a query.
3. An existing codebase without a query.
4. An existing codebase with a query.

It must preserve structured local cards, search them before GitHub, validate
their freshness at an adaptive frequency, and synthesize them into a report
that directly answers the research question.

## 2. Product Model

RepoMind keeps one public entry point:

```text
/RepoMind [query]
```

Users do not select a mode. Internally, RepoMind distinguishes two states:
`direction_discovery` and `explicit_research`.

### 2.1 Direction discovery

Direction discovery applies when no query is supplied and the current context
does not already contain a sufficiently explicit research question.

RepoMind infers possible directions in this order:

1. The current task or design goal in the conversation.
2. Requirements, design documents, and plans.
3. Existing code related to the current task.
4. When no current task exists, a lightweight repository scan covering the
   README, top-level structure, dependencies, and recent changes.
5. When no useful context exists, a direct question asking what the user is
   designing or researching.

The lightweight scan stops as soon as there is enough information to propose
useful directions. RepoMind does not attempt to understand the entire codebase
before presenting candidates.

RepoMind presents one recommended direction and two or three alternatives. The
user may select one, edit one in natural language, enter a new direction, or
reject all candidates and request another set. RepoMind does not search GitHub,
initialize unnecessary research state, or generate cards until the direction
is confirmed.

### 2.2 Explicit research

Explicit research begins when the user supplies a query or confirms a proposed
direction.

The query or confirmed direction exclusively determines the research goal.
The current project supplies only constraints, technical context, and an
adaptation target. RepoMind must not broaden, narrow, or replace the research
goal based on the current repository.

### 2.3 Four-scenario behavior

| Codebase | Without query | With query |
| --- | --- | --- |
| New | Infer candidates from the conversation and design materials, then wait for confirmation. | Research the query directly; use materials only as constraints. |
| Existing | Prefer the current task; if none exists, inspect the repository lightly and propose candidates. | Research the query directly; use the repository only for adaptation analysis. |

## 3. Research Pipeline

### 3.1 Intent model

For explicit research, RepoMind derives:

- the research object;
- the concrete research question;
- relevant dimensions, such as architecture, implementation mechanism,
  workflow, interface, design rationale, trade-offs, or evolution;
- business and technical constraints;
- current-project adaptation context; and
- Chinese and English search terms and repository queries.

Dimensions are dynamic. RepoMind no longer requires every accepted repository
to produce `architecture`, `design_patterns`, and `data_flow` cards.

### 3.2 Cache-first retrieval

RepoMind retrieves local structured cards before searching GitHub. It recalls
candidates by research object, question, dimension, and keywords, then scores
semantic relevance. Relevant cards are grouped by source repository and pass
through adaptive freshness validation.

GitHub search is necessary only when validated cache evidence does not cover
the core question, does not contain sufficiently distinct approaches, lacks
independent repository evidence, or lacks source support. Card count alone is
not evidence sufficiency.

### 3.3 Public repository search

External search targets the research question, not merely repositories whose
overall architecture resembles the current project. Candidate discovery may
look for direct implementations, adjacent transferable mechanisms, design
documents, ADRs, READMEs, and evolution records.

Stars are a secondary signal. A candidate must have a direct or transferable
relationship to the question and sufficient public evidence. Archived or old
repositories are not automatically excluded: a stable or historically
important implementation may remain valuable, but its age and applicability
must be disclosed.

### 3.4 Structured cards

Cards are organized around reusable conclusions rather than fixed mandatory
dimensions. Each card contains:

- research object and dimension;
- core conclusion;
- implementation mechanism;
- documented design rationale, or an explicitly labeled inference;
- applicability and limitations;
- transferability to the current project;
- source repository, default branch, and commit SHA;
- evidence files and related modules;
- keywords and related-card references; and
- freshness and cache metadata.

One repository may produce multiple cards. When several repositories support
the same conclusion, RepoMind preserves independent evidence rather than
collapsing it into a source-free statement.

### 3.5 Default report

The user receives a synthesized research report rather than a raw card list.
The default report contains:

1. A direct answer and conclusion summary.
2. Major approaches or patterns, organized by implementation route.
3. Public-repository evidence with concrete files or documents.
4. Comparisons, trade-offs, constraints, and limitations.
5. Implications for the current project without changing the research goal.
6. Evidence freshness: newly analyzed, validated cache, or unverified cache.
7. A small number of valuable follow-up directions.

The report may reference card identifiers, but users do not need to understand
the card schema to obtain an answer.

## 4. Adaptive Cache Validation

### 4.1 Repository-level snapshots

Freshness is managed per source repository because cards from the same
repository share Git history and update frequency. Each repository snapshot
stores:

- default branch and last observed HEAD SHA;
- README and architecture-document summaries;
- top-level and important code-directory structure summaries;
- repository update and commit-frequency statistics;
- `last_checked_at`, `last_changed_at`, `check_interval_days`, and
  `next_check_at`; and
- the signals used to calculate the interval.

Cards separately store `card_updated_at`. A remote check that finds no relevant
change updates `last_checked_at`, not `card_updated_at`.

### 4.2 Adaptive detection frequency

RepoMind checks a source repository only after `next_check_at`. Relevant cards
whose repository is not due are reused without network access.

When cards are generated or refreshed, RepoMind samples a configurable number
of recent non-merge commits on the default branch and calculates the median
interval between them. Using a fixed inclusion rule makes the calculation
repeatable; the median limits distortion from bursts and long gaps.

```text
base N   = median recent commit interval
actual N = base N * stability factor
final N  = clamp(actual N, configured minimum, configured maximum)
```

The initial recommended bounds are 1 and 30 days and must be configurable. A
repository with insufficient history uses a conservative default until enough
samples exist.

The stability factor changes over time:

- a relevant change resets the factor and recalculates N from recent history;
- a HEAD change unrelated to cached evidence increases N slightly;
- repeated checks with no HEAD change increase N gradually; and
- a global refactor or major documentation rewrite temporarily decreases N.

The algorithm must be deterministic for the same stored snapshot, configuration,
and remote history. Rounding, sample size, stability multipliers, and bounds
will be specified in the implementation plan and covered by tests.

### 4.3 Two-stage change detection

When a repository is due, RepoMind first compares the remote default-branch
HEAD with the stored SHA.

- If the SHA is unchanged, cards remain valid and RepoMind updates the check
  time and next interval.
- If the SHA changed, RepoMind performs structural change detection.

Structural detection combines:

- substantive README and architecture-document changes;
- additions, removals, or moves in top-level and important modules;
- changes or deletion of files cited by cards;
- commit count between the stored and current SHAs; and
- changed-file count and change ratio in important directories.

Commit count is an auxiliary signal and cannot independently classify a major
change.

### 4.4 Targeted refresh

RepoMind maps the Git diff to card evidence paths, related modules, and research
dimensions:

- no relevant change: reuse cards and update the repository snapshot;
- localized relevant change: regenerate only affected cards; or
- global change or unreliable mapping: regenerate all cards for the repository.

Refreshes are atomic. Old cards remain available while replacements are built.
RepoMind validates the new card structure and evidence before replacing cards
and the repository snapshot in one transaction. A failed refresh preserves the
old card and marks it `refresh_failed` or `refresh_required`; it must not be
presented as freshly verified evidence.

### 4.5 Remote access failure

If remote validation fails, RepoMind retains cached data and marks it
unverified for the current run. Such cards may supplement a report with a
freshness warning, but must not silently count as verified evidence. Validation
failure alone does not trigger a full rebuild.

## 5. Plugin Collaboration Contract

RepoMind supports conditional implicit invocation and an explicit lightweight
contract for other plugins.

### 5.1 Invocation policy

The host may invoke RepoMind implicitly when a decision genuinely needs
evidence from multiple public implementations. The mere appearance of words
such as “architecture” or “design” is insufficient.

Other plugins can invoke RepoMind explicitly with a concrete research question
and relevant project constraints. Because the caller already knows the goal,
RepoMind enters explicit research directly and does not show direction
candidates unless the request is genuinely ambiguous.

### 5.2 Input contract

Natural language is the canonical portable interface. Conceptually, a caller
provides:

```yaml
research_question: "How do mature plugin systems implement lifecycle and isolation?"
project_context:
  goal: "Design a plugin mechanism for this project"
  constraints: ["Go", "single process", "fault isolation"]
focus: ["implementation mechanism", "design trade-offs"]
desired_output: "decision_support"
```

Strict YAML is not required. Callers must not access RepoMind's SQLite database
or helper script directly.

### 5.3 Result contract

RepoMind returns a report with traceable card, repository, SHA, evidence-path,
and freshness references, plus one of these stable states:

- `complete`: sufficient verified evidence covers the core question;
- `partial`: useful evidence exists but coverage or freshness is insufficient;
- `needs_clarification`: the research goal or constraints are ambiguous;
- `out_of_scope`: the request is ordinary implementation or debugging; or
- `unavailable`: RepoMind's installation or required research facilities are
  unavailable.

The caller decides how evidence affects its design and owns the final decision.
RepoMind owns cache retrieval, freshness validation, public research, card
generation, and evidence synthesis.

## 6. Failure Handling

- A sufficient validated cache can produce `complete` when GitHub is
  unavailable.
- One repository failure does not stop other analyses.
- Unverified cards are labeled and cannot masquerade as current evidence.
- A failed card refresh preserves the old record and its prior provenance.
- Direction discovery performs no external repository search.
- `needs_clarification` identifies the missing information so a user or caller
  can refine the question.
- Database migrations are transactional. Migration failure prevents new writes
  and preserves the original database.

## 7. Migration and Compatibility

Existing repositories and cards remain in place. The database gains a schema
version, repository snapshots, adaptive check fields, evidence mappings, and
card freshness status.

Legacy cards begin with unknown freshness. Their first relevant retrieval
triggers validation and metadata enrichment. If a legacy card lacks sufficient
evidence mapping and its repository changed, RepoMind refreshes all cards for
that repository.

Existing installation and invocation methods remain compatible. Existing
architecture research requests continue to work. The following materials must
be updated consistently:

- `SKILL.md` description, argument hint, scope gate, and workflow;
- Codex `openai.yaml` prompt and implicit invocation metadata;
- README and tutorial positioning, examples, and four-scenario behavior;
- fixed mandatory card dimensions;
- automatic exclusion of repositories inactive for two years;
- card-list output requirements; and
- plugin collaboration examples and result states.

## 8. Verification Strategy

Contract tests must cover all four invocation scenarios and assert both
required and prohibited behavior. In particular:

- direction candidates appear before external research when no query exists;
- users can edit, replace, or reject all candidates;
- a supplied query enters explicit research without being rewritten by the
  current repository;
- the current task precedes whole-repository analysis;
- ordinary API, syntax, and debugging requests remain out of scope;
- architecture, feature-design, engineering-pattern, and design-rationale
  research is accepted;
- validated cache evidence precedes GitHub search;
- repositories are not contacted before `next_check_at`;
- unchanged SHAs do not regenerate cards;
- localized changes regenerate only mapped cards;
- global or unmappable changes regenerate repository cards;
- adaptive intervals stay within configured bounds and respond predictably to
  stability signals;
- card update time and repository check time remain distinct;
- cross-plugin calls enter explicit research and return stable result states;
  and
- reports preserve evidence provenance and freshness.

Unit tests should cover schema migration, adaptive interval calculation,
change classification, evidence-to-card mapping, atomic refresh, and failure
rollback. Fixture-based behavioral evaluations should cover intent parsing,
cache sufficiency, report synthesis, and false implicit invocations.

## 9. Acceptance Criteria

The redesign is successful when:

- users can predict behavior in all four invocation scenarios;
- invoking RepoMind without a query does not blindly analyze the current
  repository's architecture;
- a supplied query remains the authoritative research goal;
- valid non-architecture research questions are supported;
- reports answer questions directly with traceable public evidence;
- structured cards remain cacheable, reusable, and adaptively validated;
- repository changes refresh only affected cards when safe;
- other plugins can invoke RepoMind without knowing its internals; and
- the existing architecture-research workflow remains compatible.
