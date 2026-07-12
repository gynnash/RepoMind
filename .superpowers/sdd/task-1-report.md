# Task 1 Report: Adaptive configuration and schema v2

## Scope

Implemented adaptive freshness configuration and SQLite schema v2 in the three
Task 1 files. Existing repository and card rows are retained during migration,
and the orphan-card migration guard remains active. The implementation uses only
the Python standard library.

## RED evidence

Command:

```text
python3 -m unittest tests.test_search -v
```

Initial result: 22 tests run, 6 failures and 2 errors. The intended new tests
failed because the bundled defaults lacked `freshness_min_days`, project config
rejected `freshness_default_days`, `PRAGMA user_version` remained 0/1, and the
new repository/card columns were absent.

## GREEN evidence

Focused command:

```text
python3 -m unittest tests.test_search -v
```

Result: 22 tests run, all passed.

Full command:

```text
python3 -m unittest discover -s tests -v
```

Result: 41 tests run; 40 passed and one unrelated pre-existing release contract
test failed. `test_readme_documents_usefulness_evaluation` expects README.md to
contain `tests/fixtures/usefulness_cases.json`. README.md is outside Task 1 and
was not modified.

Additional verification:

```text
git diff --check
```

Result: passed with no whitespace errors.

## Implementation

- Replaced fixed card staleness and dimension-list settings with validated
  adaptive freshness bounds, commit sample size, stability growth, and change
  decay.
- Added `SCHEMA_VERSION = 2` and persisted it through `PRAGMA user_version`.
- Added repository HEAD/default-branch, content digest, check scheduling,
  stability, and commit-interval columns.
- Added card research-object, evidence-path, related-module, source-SHA,
  freshness-status, and update-time columns.
- Added additive schema migration that preserves legacy rows and defaults new
  fields (`check_interval_days=7.0`, `evidence_paths='[]'`, and
  `freshness_status='unknown'`).
- Retained nullable-`repo_id` migration orphan protection.
- Updated legacy staleness compatibility reads to use the configured maximum
  freshness interval.

## Self-review

- Confirmed only the three requested Task 1 source/test files are staged for the
  commit.
- Confirmed untracked `docs/articles/` and the implementation plan are untouched.
- No third-party dependency was introduced.
- Concern: the repository-wide suite remains red solely because of the unrelated
  README release-contract expectation described above.

## Important-review fix: atomic migration

RED command:

```text
python3 -m unittest tests.test_search.SearchTests.test_migration_failure_rolls_back_all_schema_and_data_changes -v
```

Result before the fix: 1 test run, 1 failure. After an injected later v2
migration failure, `cards.repo_id` remained `NOT NULL` (`1 != 0`), proving that
the earlier `executescript()` migration had committed partial schema/data work.

GREEN command:

```text
python3 -m unittest tests.test_search -v
```

Result after the fix: 23 tests run, all passed. Schema creation and the nullable
`repo_id` rebuild now use individual statements inside one explicit transaction;
no migration path uses transaction-boundary-changing `executescript()`.
