# Output Format and Failures

Return cards in this form:

```markdown
## RepoMind Code Cards

> **Search intent:** {query}
> **Matched repos:** {repo_count} | **Cards:** {card_count}

<repo-card id="{id}" repo="{owner/repo}" dimension="{dimension}"
  relevance="{score}" stars="{stars}" stale="{true_or_false}">
{card content}
</repo-card>
```

Sort by relevance descending, then stars descending. After the cards, report:

- repositories analyzed
- new cards created
- duplicates reused
- stale cards returned
- repositories that failed, with concise reasons

## Failure behavior

- Rate limited: report reset time and return local results.
- `gh` unauthenticated: ask the user to run `gh auth login`; do not claim an
  unauthenticated fallback succeeded.
- Deleted/private repository: skip and continue.
- Agent failure: retain successful cards from other repositories.
- SQLite corruption: recommend backing up the database before `reset-db`.
