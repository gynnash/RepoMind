# Relevance Evaluation

Use this rubric for semantic local-card selection and GitHub fine filtering.

## Local cards

Score each card from 0–5 against the original request:

- 5: directly addresses the same architectural concern
- 4: same domain and highly transferable pattern
- 3: adjacent domain with a useful transferable pattern
- 2: tangential insight
- 0–1: not relevant

Return at most ten cards scoring 3+, ordered by score.

## Repository fine filter

Evaluate the README and project context on four 0–5 dimensions:

| Dimension | Weight | Meaning |
|---|---:|---|
| `domain_match` | 0.4 | Same or adjacent problem domain |
| `arch_pattern` | 0.2 | Architectural pattern clarity and transferability |
| `tech_overlap` | 0.2 | Language, framework, and dependency overlap |
| `depth_quality` | 0.2 | Architecture docs, ADRs, diagrams, or module detail |

Scores of 3+ must cite a specific README passage. Calculate:

`overall = domain_match*0.4 + arch_pattern*0.2 + tech_overlap*0.2 + depth_quality*0.2`

Return valid JSON:

```json
{
  "repo": "owner/repo",
  "scores": {
    "domain_match": 0,
    "arch_pattern": 0,
    "tech_overlap": 0,
    "depth_quality": 0
  },
  "overall": 0,
  "evidence": ["README passage or section"],
  "key_insight": "Most transferable architectural idea",
  "verdict": "deep_analyze"
}
```

Use `skip` when overall is below configured `min_relevance_score`.
