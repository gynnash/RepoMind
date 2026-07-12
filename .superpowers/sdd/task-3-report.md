# Task 3 report

## RED

Command:

`python3 -m unittest tests.test_search.SearchTests.test_repositories_for_cards_groups_ids_and_reports_due_without_network tests.test_search.SearchTests.test_unchanged_check_advances_schedule_without_updating_cards -v`

Result: 2 errors. Both tests failed with the expected `AttributeError` because
`get_repositories_for_cards` and `record_repository_check` did not exist.

## GREEN

Command:

`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_search -v`

Result: 26 tests passed. This includes local repository grouping, deterministic
unchanged-check scheduling, preservation of `card_updated_at`, and both new CLI
commands with stdin JSON.

Full-suite command: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`

Result: 50 passed, 1 unrelated pre-existing release-contract failure. The
README does not mention `tests/fixtures/usefulness_cases.json`; Task 3 does not
modify the README or release contract.

## Implementation notes

- Repository grouping reads SQLite only and performs no network calls.
- Check outcomes are restricted to `unchanged`, `unrelated`, `localized`, and
  `global`.
- Median commit cadence falls back to the configured default; the existing pure
  freshness helper applies stability, decay, bounds, and rounding.
- `last_changed_at` changes only for localized/global outcomes.
- `get-cards` now returns card provenance plus repository freshness fields.

## Reviewer follow-up: timestamp offsets

The due check now parses ISO 8601 timestamps and compares normalized UTC
instants instead of comparing their string representations. Naive timestamps
are interpreted as UTC, matching the database's stored timestamp convention;
`None` remains due and equal instants remain due.

Regression coverage includes `2026-07-12T09:00:00+08:00` being due at
`2026-07-12T08:00:00Z`, plus explicit naive-as-UTC behavior.

Verification commands:

- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_freshness -v`
  — 8 tests passed.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest tests.test_search -v`
  — 26 tests passed.
