# Deep Repository Analysis

Run one isolated analysis per accepted repository, in parallel when supported.

## Token budget (hard limit)

**Total output per repository: 1,200 words maximum across all cards.** This is
a hard limit. If you exceed it, truncate the least-important card rather than
expanding the total.

Per card:

- 3 mandatory cards × ~300 words = 900 words
- Up to 2 optional cards × ~150 words = 300 words
- Total: ~1,200 words

Each card section is capped:

| Section | Limit |
|---------|-------|
| Overview | 2 sentences, 80 words max |
| Key Design | 3 bullet points, 120 words max |
| Transferable Patterns | 2 bullet points, 80 words max |
| Source References | 1-3 paths, no commentary |
| Limitations | 1 sentence, 40 words max |

Every word over budget is a word the user pays for twice (output tokens cost
5× input tokens). Be concise.

## Evidence collection

1. Fetch the top-level listing: `gh api repos/{owner}/{repo}/contents/`.
2. Read the README (first 200 lines only).
3. Read **one** architecture document if present (`ARCHITECTURE.md`,
   `docs/architecture/`, or `ADR/`).
4. For repos over 100 top-level files: README + directory listing only. Mark
   every card `depth: partial` and note it in Limitations.
5. Do not read source files unless the architecture document references them
   and they are essential to a Key Design bullet.

## Cards

Always create `architecture`, `design_patterns`, and `data_flow`.

Create `interface_design`, `tech_stack`, `deployment`, or `evolution_history`
only when the repository has direct evidence. Skip the card entirely rather
than padding it.

Format:

```markdown
### {dimension}

#### Overview
Two sentences. State the pattern, name the mechanism. No preamble.

#### Key Design
- Point one with file or module reference.
- Point two with file or module reference.
- Point three with file or module reference.

#### Transferable Patterns
- One transferable idea. Why it applies.
- One transferable idea. Why it applies.

#### Source References
- `path/to/file.py:120-145` — one-line description
- `path/to/module/` — one-line description

#### Limitations
One sentence: what this pattern does NOT cover or when it breaks.
```

Do not add commentary, introductions, code blocks, or summaries. Each card is
a reference entry, not an essay.

## Persistence

Upsert repository metadata through `insert-repo`, capture `repo_id`, then pass
each serialized card to `insert-card-if-new`. This command performs atomic
similarity checking; never run a separate check-then-insert sequence.

Use `--max-snippet-lines 0` or equivalent to avoid embedding full file
contents in your requests.

Return created IDs, reused `duplicate_id` values, and failures. Assign the
repository's fine-filter `overall` score to all cards from that repository.
