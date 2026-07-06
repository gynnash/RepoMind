# Deep Repository Analysis

Run one isolated analysis per accepted repository, in parallel when supported.

## Evidence collection

1. Fetch the top-level listing with `gh api repos/{owner}/{repo}/contents/`.
2. Inspect `ADR/`, `docs/architecture/`, `ARCHITECTURE.md`, and
   `CONTRIBUTING.md`.
3. Read architecture documents and the first 50 lines of key module files.
4. For more than 100 top-level files, limit work to the README, directory
   structure, and ten source headers; mark every card `depth: partial`.

## Cards

Always create:

- `architecture`
- `design_patterns`
- `data_flow`

Create `interface_design`, `tech_stack`, `deployment`, or
`evolution_history` only with repository evidence.

Each card must contain:

```markdown
### {dimension}

#### Overview
Two or three evidence-based sentences.

#### Key Design
- Three to five implementation details with modules or files.

#### Transferable Patterns
How the design applies to the user's request.

#### Source References
Repository paths and line numbers where available.

#### Limitations
Boundaries and unsuitable scenarios.
```

## Persistence

Upsert repository metadata through `insert-repo`, capture `repo_id`, then pass
each serialized card to `insert-card-if-new`. This command performs atomic
similarity checking; never run a separate check-then-insert sequence.

Return created IDs, reused `duplicate_id` values, and failures. Assign the
repository's fine-filter `overall` score to all cards from that repository.
