# Relevance Evaluation

Evaluate each repository or cached card against the confirmed research object,
not a fixed architecture taxonomy. Score every dimension from 0–5:

| Dimension | Weight | Meaning |
|---|---:|---|
| `question_match` | 0.30 | Directly answers the research question |
| `transferability` | 0.25 | Mechanism can be adapted to the current project |
| `constraint_fit` | 0.20 | Fits stated technical and operational constraints |
| `evidence_depth` | 0.15 | Claims trace to implementation or documentation |
| `independence` | 0.10 | Adds evidence distinct from already selected sources |

`overall = question_match*.30 + transferability*.25 + constraint_fit*.20 + evidence_depth*.15 + independence*.10`

Keep candidates scoring at least the configured threshold. A high score must
name the evidence supporting it. Stars break ties only; popularity never
overrides question fit or evidence quality. Prefer a smaller set of independent
implementations over several forks or near-duplicates.

Return the repository, research object, per-dimension scores, overall score,
evidence paths or README sections, transferable insight, and `deep_analyze` or
`skip` verdict.
