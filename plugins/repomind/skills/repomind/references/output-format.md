# Output Format and Failures

Return exactly one result envelope:

```markdown
<repomind-result status="complete|partial|needs_clarification|out_of_scope|unavailable">
## Research conclusion
## Approaches and trade-offs
## Public implementation evidence
## Implications for the current project
## Required code changes if adopted
## Benefits and risks for the current codebase
## Evidence freshness
## Follow-up directions
</repomind-result>
```

Use `complete` when the confirmed question is answered with sufficient public
evidence. Use `partial` when useful evidence exists but coverage is incomplete.
Use `needs_clarification` when the research object cannot be determined,
`out_of_scope` when the request is not public implementation research, and
`unavailable` when authentication, rate limits, or tooling prevent research.
Every non-success state must explain the next action.

Keep the result compact: prefer 2–4 high-signal evidence items, avoid repeated
claims across sections, and quote source only when the exact wording matters.
Use the user's language unless repository identifiers or code terms require
English.

Under **Public implementation evidence**, every evidence item includes its URL,
exact SHA, files or modules, card ID, and freshness value: `new`,
`validated_cache`, or `unverified_cache`. Do not silently upgrade unverified
cached evidence. Distinguish documented rationale from inference in the item.

Keep conclusions comparative and question-centered. Explain meaningful
approaches and trade-offs, then connect only supported implications to the
current project. In **Required code changes if adopted**, summarize the concrete
files, modules, interfaces, tests, migrations, or configuration likely to change
in the current codebase. In **Benefits and risks for the current codebase**,
separate expected gains from adoption risks, migration cost, evidence limits,
and operational trade-offs. In **Evidence freshness**, disclose cache
validation, stale or unreachable sources, and repository failures.

For rate limits, return available validated evidence and the reset time. For
missing GitHub authentication, request `gh auth login`. Skip deleted or private
repositories, retain successful evidence when one analysis fails, and recommend
a database backup before corruption recovery.
