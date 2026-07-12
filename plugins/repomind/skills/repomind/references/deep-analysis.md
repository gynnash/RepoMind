# Deep Repository Analysis

Analyze each accepted repository at a pinned commit SHA. Read only the files
needed to answer the confirmed research object, prioritizing implementation,
tests, architecture records, and documentation that explain the mechanism.

## Dynamic cards

Generate only question-relevant dimensions. Names may describe a protocol,
scheduling strategy, state model, boundary, failure policy, or another concept
supported by the repository. Do not require architecture, design-pattern, or
data-flow cards. Skip a dimension when direct evidence is insufficient.

Keep all cards for a repository within 1,200 words. Each serialized card must
carry:

```yaml
dimension: question-relevant name
research_object: the confirmed question this card addresses
mechanism: how the implementation works
limitations: boundaries, costs, or missing evidence
transferability: what can be reused and under which constraints
sha: exact analyzed commit
evidence_paths: [path/to/file-or-module]
keywords: [retrieval, terms]
```

Tie mechanism claims to paths or modules. Label repository-stated intent as
`documented rationale`; label analyst-derived explanations as `inference` and
state the supporting evidence. Never present inference as author intent.

## Persistence

Upsert repository metadata, then use `insert-card-if-new` atomically for every
card. Preserve created IDs, reused duplicate IDs, failures, SHA, and evidence
paths. Do not embed full source files in requests.
