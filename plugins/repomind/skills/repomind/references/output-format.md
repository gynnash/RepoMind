# Output Format and Failures

Return exactly one result envelope:

```markdown
<repomind-result status="complete|partial|needs_clarification|out_of_scope|unavailable">
## Research conclusion
## Approaches and trade-offs
## Public implementation evidence
## Implications for the current project
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

Under **Public implementation evidence**, every evidence item includes its URL,
exact SHA, files or modules, card ID, and freshness value: `new`,
`validated_cache`, or `unverified_cache`. Do not silently upgrade unverified
cached evidence. Distinguish documented rationale from inference in the item.

Keep conclusions comparative and question-centered. Explain meaningful
approaches and trade-offs, then connect only supported implications to the
current project. In **Evidence freshness**, disclose cache validation, stale or
unreachable sources, and repository failures.

For rate limits, return available validated evidence and the reset time. For
missing GitHub authentication, request `gh auth login`. Skip deleted or private
repositories, retain successful evidence when one analysis fails, and recommend
a database backup before corruption recovery.
