import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SKILL_PATH = ROOT / "plugins" / "repomind" / "skills" / "repomind"
SEARCH_PATH = SKILL_PATH / "scripts" / "search.py"
FRESHNESS_PATH = SKILL_PATH / "scripts" / "freshness.py"
DEFAULT_CONFIG_PATH = SKILL_PATH / "config" / "defaults.json"


def load_search():
    spec = importlib.util.spec_from_file_location("repomind_search", SEARCH_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SearchTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.home = Path(self.temp_dir.name) / ".repomind"
        self.home.mkdir()
        self.config_path = self.home / "config.json"
        self.config_path.write_text(
            "{}",
            encoding="utf-8",
        )
        self.search = load_search()
        self.search.DB_DIR = self.home
        self.search.CONFIG_PATH = self.config_path
        self.search.DEFAULT_CONFIG_PATH = DEFAULT_CONFIG_PATH

    def tearDown(self):
        self.temp_dir.cleanup()

    def repo_data(self, stars=38000):
        return {
            "full_name": "apache/airflow",
            "url": "https://github.com/apache/airflow",
            "language": "Python",
            "topics": ["workflow", "scheduler"],
            "stars": stars,
            "description": "Airflow",
        }

    def card_data(self, repo_id=1):
        return {
            "repo_id": repo_id,
            "dimension": "architecture",
            "title": "Airflow DAG Scheduling Architecture",
            "content": "full content",
            "keywords": "scheduling,DAG,workflow,airflow,executor,orchestration",
        }

    def test_public_reads_auto_initialize_database(self):
        self.assertEqual(self.search.get_card_count(), 0)
        self.assertEqual(self.search.search_cards_v1(["scheduler"]), [])
        self.assertEqual(self.search.get_all_cards_with_repo(), [])

    def test_adaptive_freshness_defaults(self):
        config = self.search.load_config()
        self.assertEqual(config["freshness_min_days"], 1)
        self.assertEqual(config["freshness_max_days"], 30)
        self.assertEqual(config["freshness_default_days"], 7)
        self.assertEqual(config["freshness_commit_sample_size"], 20)
        self.assertEqual(config["freshness_stability_growth"], 1.5)
        self.assertEqual(config["freshness_change_decay"], 0.5)
        self.assertNotIn("card_staleness_months", config)
        self.assertNotIn("mandatory_dimensions", config)

    def test_freshness_bounds_are_validated(self):
        self.config_path.write_text(
            json.dumps({"freshness_default_days": 31}), encoding="utf-8"
        )
        with self.assertRaisesRegex(ValueError, "freshness_min_days <="):
            self.search.load_config()

    def test_schema_v2_adds_snapshot_and_evidence_fields(self):
        repo_id = self.search.insert_repo(self.repo_data())
        card_id = self.search.insert_card(self.card_data(repo_id))
        with self.search.connect_db() as conn:
            self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 2)
            repo = dict(
                conn.execute("SELECT * FROM repos WHERE id=?", (repo_id,)).fetchone()
            )
            card = dict(
                conn.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone()
            )
        self.assertIsNone(repo["last_head_sha"])
        self.assertEqual(repo["check_interval_days"], 7.0)
        self.assertEqual(card["freshness_status"], "unknown")
        self.assertEqual(card["evidence_paths"], "[]")

    def test_schema_v2_migration_preserves_legacy_data(self):
        database = self.home / "repomind.db"
        conn = sqlite3.connect(database)
        conn.executescript(
            """
            CREATE TABLE repos (
                id INTEGER PRIMARY KEY,
                full_name TEXT UNIQUE NOT NULL,
                url TEXT NOT NULL,
                language TEXT,
                topics TEXT,
                stars INTEGER,
                description TEXT,
                fetched_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            CREATE TABLE cards (
                id INTEGER PRIMARY KEY,
                repo_id INTEGER NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
                dimension TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                keywords TEXT,
                embedding BLOB,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
            INSERT INTO repos (id, full_name, url) VALUES (4, 'legacy/repo', 'url');
            INSERT INTO cards (id, repo_id, dimension, title, content)
            VALUES (8, 4, 'architecture', 'legacy card', 'preserve me');
            PRAGMA user_version = 1;
            """
        )
        conn.commit()
        conn.close()

        with self.search.connect_db() as migrated:
            self.assertEqual(migrated.execute("PRAGMA user_version").fetchone()[0], 2)
            repo = dict(migrated.execute("SELECT * FROM repos WHERE id=4").fetchone())
            card = dict(migrated.execute("SELECT * FROM cards WHERE id=8").fetchone())
        self.assertEqual(repo["full_name"], "legacy/repo")
        self.assertEqual(card["content"], "preserve me")
        self.assertEqual(repo["check_interval_days"], 7.0)
        self.assertEqual(card["evidence_paths"], "[]")

    def test_existing_repo_is_refreshed(self):
        repo_id = self.search.insert_repo(self.repo_data(stars=1))
        self.search.insert_repo(self.repo_data(stars=2))
        repo = self.search.get_repo("apache/airflow")
        self.assertEqual(repo_id, repo["id"])
        self.assertEqual(repo["stars"], 2)

    def test_foreign_key_rejects_orphan_card(self):
        with self.assertRaises(sqlite3.IntegrityError):
            self.search.insert_card(self.card_data(repo_id=999))

    def test_airflow_near_duplicate_is_detected(self):
        repo_id = self.search.insert_repo(self.repo_data())
        self.search.insert_card(self.card_data(repo_id))
        self.assertTrue(
            self.search.check_similar_card(
                "Airflow Task Scheduling Design",
                "scheduling,DAG,airflow,workflow,executor",
            )
        )
        self.assertFalse(
            self.search.check_similar_card(
                "React Component Rendering",
                "react,frontend,component,state",
            )
        )

    def test_similarity_threshold_comes_from_config(self):
        repo_id = self.search.insert_repo(self.repo_data())
        self.search.insert_card(self.card_data(repo_id))
        config = json.loads(self.config_path.read_text(encoding="utf-8"))
        config["card_similarity_threshold"] = 0.9
        self.config_path.write_text(json.dumps(config), encoding="utf-8")
        self.assertFalse(
            self.search.check_similar_card(
                "Unrelated title",
                "scheduling,DAG,airflow,workflow,unmatched",
            )
        )

    def test_atomic_insert_creates_only_one_duplicate(self):
        repo_id = self.search.insert_repo(self.repo_data())
        card = self.card_data(repo_id)
        barrier = threading.Barrier(4)
        results = []

        def insert():
            barrier.wait()
            results.append(self.search.insert_card_if_new(card))

        threads = [threading.Thread(target=insert) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        self.assertEqual(sum(result["inserted"] for result in results), 1)
        self.assertEqual(self.search.get_card_count(), 1)

    def test_search_has_relevance_and_staleness(self):
        repo_id = self.search.insert_repo(self.repo_data())
        self.search.insert_card(self.card_data(repo_id))
        fresh = self.search.search_cards_v1(["scheduling", "missing"])[0]
        self.assertEqual(fresh["relevance"], 2.5)
        self.assertFalse(fresh["is_stale"])

        with self.search.connect_db() as conn:
            conn.execute(
                "UPDATE repos SET fetched_at = datetime('now', '-31 days') WHERE id = ?",
                (repo_id,),
            )
        stale = self.search.get_cards_by_ids([1])[0]
        self.assertTrue(stale["is_stale"])
        self.search.insert_repo(self.repo_data())
        refreshed = self.search.get_cards_by_ids([1])[0]
        self.assertFalse(refreshed["is_stale"])

    def test_get_cards_preserves_requested_order(self):
        repo_id = self.search.insert_repo(self.repo_data())
        first = self.search.insert_card(self.card_data(repo_id))
        second_data = self.card_data(repo_id)
        second_data["title"] = "Second card"
        second = self.search.insert_card(second_data)
        cards = self.search.get_cards_by_ids([second, first])
        self.assertEqual([card["id"] for card in cards], [second, first])

    def test_repositories_for_cards_groups_ids_and_reports_due_without_network(self):
        repo_id = self.search.insert_repo(self.repo_data())
        card_id = self.search.insert_card(self.card_data(repo_id))

        repositories = self.search.get_repositories_for_cards(
            [card_id], now="2026-07-12T08:00:00Z"
        )

        self.assertEqual(len(repositories), 1)
        self.assertEqual(repositories[0]["id"], repo_id)
        self.assertEqual(repositories[0]["card_ids"], [card_id])
        self.assertTrue(repositories[0]["check_due"])

    def test_unchanged_check_advances_schedule_without_updating_cards(self):
        repo_id = self.search.insert_repo(self.repo_data())
        card_id = self.search.insert_card(self.card_data(repo_id))
        with self.search.connect_db() as conn:
            conn.execute(
                "UPDATE cards SET card_updated_at=? WHERE id=?",
                ("2026-07-01T00:00:00Z", card_id),
            )

        result = self.search.record_repository_check({
            "repo_id": repo_id,
            "outcome": "unchanged",
            "head_sha": "abc123",
            "checked_at": "2026-07-12T08:00:00Z",
            "commit_timestamps": [
                "2026-07-08T08:00:00Z",
                "2026-07-10T08:00:00Z",
                "2026-07-12T08:00:00Z",
            ],
        })

        repo = self.search.get_repo("apache/airflow")
        card = self.search.get_cards_by_ids([card_id])[0]
        self.assertEqual(repo["last_checked_at"], "2026-07-12T08:00:00Z")
        self.assertEqual(repo["last_head_sha"], "abc123")
        self.assertEqual(repo["check_interval_days"], 3.0)
        self.assertEqual(repo["next_check_at"], "2026-07-15T08:00:00Z")
        self.assertEqual(card["card_updated_at"], "2026-07-01T00:00:00Z")
        self.assertEqual(result["outcome"], "unchanged")

    def test_affected_cards_match_exact_ancestor_and_descendant_paths(self):
        repo_id = self.search.insert_repo(self.repo_data())
        first = self.card_data(repo_id)
        first.update({"evidence_paths": ["src/core/engine.py"],
                      "related_modules": ["src/api"]})
        first_id = self.search.insert_card(first)
        second = self.card_data(repo_id)
        second.update({"title": "Docs", "evidence_paths": ["docs/guide.md"]})
        second_id = self.search.insert_card(second)
        self.assertEqual(
            self.search.affected_card_ids(repo_id, ["src/core", "src/api/v1.py"]),
            [first_id],
        )
        self.assertNotIn(second_id, self.search.affected_card_ids(repo_id, ["src/core"]))

    def test_refresh_replaces_only_requested_card_and_preserves_identity(self):
        repo_id = self.search.insert_repo(self.repo_data())
        first_id = self.search.insert_card(self.card_data(repo_id))
        other = self.card_data(repo_id)
        other["title"] = "Preserved"
        other_id = self.search.insert_card(other)
        with self.search.connect_db() as conn:
            conn.execute("UPDATE cards SET card_updated_at=? WHERE id=?",
                         ("2026-07-01T00:00:00Z", other_id))
        result = self.search.refresh_cards_atomically({
            "repo_id": repo_id, "head_sha": "newsha",
            "status": "fresh", "updated_at": "2026-07-12T08:00:00Z",
            "replacements": [{**self.card_data(repo_id), "id": first_id,
                              "title": "Refreshed"}],
        })
        cards = self.search.get_cards_by_ids([first_id, other_id])
        self.assertEqual(result["card_ids"], [first_id])
        self.assertEqual(cards[0]["title"], "Refreshed")
        self.assertEqual(cards[1]["title"], "Preserved")
        self.assertEqual(cards[1]["card_updated_at"], "2026-07-01T00:00:00Z")
        self.assertEqual(cards[0]["last_head_sha"], "newsha")

    def test_invalid_refresh_rolls_back_cards_and_snapshot(self):
        repo_id = self.search.insert_repo(self.repo_data())
        card_id = self.search.insert_card(self.card_data(repo_id))
        with self.assertRaisesRegex(ValueError, "Missing card field"):
            self.search.refresh_cards_atomically({
                "repo_id": repo_id, "head_sha": "must-not-stick",
                "status": "fresh", "updated_at": "2026-07-12T08:00:00Z",
                "replacements": [{"id": card_id, "repo_id": repo_id,
                                  "dimension": "architecture", "title": "bad"}],
            })
        card = self.search.get_cards_by_ids([card_id])[0]
        self.assertEqual(card["title"], "Airflow DAG Scheduling Architecture")
        self.assertIsNone(card["last_head_sha"])

    def test_empty_query_history_expires(self):
        self.search.record_empty_query("agent scheduler")
        self.assertTrue(self.search.recent_empty_query(" agent   scheduler "))
        with self.search.connect_db() as conn:
            conn.execute(
                "UPDATE search_history SET last_empty_at = datetime('now', '-25 hours')"
            )
        self.assertFalse(self.search.recent_empty_query("agent scheduler"))

    def test_legacy_migration_rejects_orphans_without_data_loss(self):
        database = self.home / "repomind.db"
        conn = sqlite3.connect(database)
        conn.executescript(
            """
            CREATE TABLE repos (
                id INTEGER PRIMARY KEY,
                full_name TEXT UNIQUE NOT NULL,
                url TEXT NOT NULL
            );
            CREATE TABLE cards (
                id INTEGER PRIMARY KEY,
                repo_id INTEGER REFERENCES repos(id),
                dimension TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                keywords TEXT,
                embedding BLOB,
                created_at TEXT DEFAULT (datetime('now'))
            );
            INSERT INTO cards
                (repo_id, dimension, title, content)
            VALUES (999, 'architecture', 'orphan', 'must survive');
            """
        )
        conn.commit()
        conn.close()

        with self.assertRaisesRegex(
            sqlite3.IntegrityError, "legacy cards reference missing repositories"
        ):
            self.search.connect_db()

        conn = sqlite3.connect(database)
        self.assertEqual(conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0], 1)
        self.assertEqual(
            conn.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE name = 'cards_legacy'"
            ).fetchone()[0],
            0,
        )
        conn.close()

    def test_migration_failure_rolls_back_all_schema_and_data_changes(self):
        database = self.home / "repomind.db"
        conn = sqlite3.connect(database)
        conn.executescript(
            """
            CREATE TABLE repos (
                id INTEGER PRIMARY KEY,
                full_name TEXT UNIQUE NOT NULL,
                url TEXT NOT NULL
            );
            CREATE TABLE cards (
                id INTEGER PRIMARY KEY,
                repo_id INTEGER REFERENCES repos(id),
                dimension TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                keywords TEXT,
                embedding BLOB,
                created_at TEXT DEFAULT (datetime('now'))
            );
            INSERT INTO repos (id, full_name, url)
            VALUES (4, 'legacy/repo', 'url');
            INSERT INTO cards (id, repo_id, dimension, title, content)
            VALUES (8, 4, 'architecture', 'legacy card', 'preserve me');
            PRAGMA user_version = 1;
            """
        )
        conn.close()

        with mock.patch.object(
            self.search, "_migrate_schema_v2", side_effect=RuntimeError("later failure")
        ):
            with self.assertRaisesRegex(RuntimeError, "later failure"):
                self.search.connect_db()

        conn = sqlite3.connect(database)
        self.assertEqual(conn.execute("PRAGMA user_version").fetchone()[0], 1)
        repo_id_column = next(
            row for row in conn.execute("PRAGMA table_info(cards)") if row[1] == "repo_id"
        )
        self.assertEqual(
            repo_id_column[3],
            0,
        )
        self.assertEqual(
            conn.execute("SELECT content FROM cards WHERE id = 8").fetchone()[0],
            "preserve me",
        )
        self.assertEqual(
            conn.execute(
                "SELECT COUNT(*) FROM sqlite_master "
                "WHERE type = 'table' AND name = 'search_history'"
            ).fetchone()[0],
            0,
        )
        conn.close()


class CliTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.skill_dir = self.root / "skill"
        self.tool_dir = self.skill_dir / "scripts"
        self.tool_dir.mkdir(parents=True)
        self.script = self.tool_dir / "search.py"
        self.script.write_bytes(SEARCH_PATH.read_bytes())
        (self.tool_dir / "freshness.py").write_bytes(FRESHNESS_PATH.read_bytes())
        config_dir = self.skill_dir / "config"
        config_dir.mkdir()
        self.config = {
            "max_search_repos": 20,
            "min_relevance_score": 3.5,
            "card_similarity_threshold": 0.7,
            "empty_query_ttl_hours": 24,
            "freshness_min_days": 1,
            "freshness_max_days": 30,
            "freshness_default_days": 7,
            "freshness_commit_sample_size": 20,
            "freshness_stability_growth": 1.5,
            "freshness_change_decay": 0.5,
        }
        (config_dir / "defaults.json").write_text(
            json.dumps(self.config), encoding="utf-8"
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def run_cli(self, *args, stdin=None):
        return subprocess.run(
            [sys.executable, str(self.script), *args],
            cwd=self.root,
            input=stdin,
            text=True,
            capture_output=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )

    def test_first_use_count_and_config(self):
        count = self.run_cli("count")
        self.assertEqual(count.returncode, 0)
        self.assertEqual(json.loads(count.stdout), {"count": 0})
        config = self.run_cli("config")
        self.assertEqual(json.loads(config.stdout)["max_search_repos"], 20)

    def test_cli_accepts_json_from_stdin(self):
        repo = self.run_cli(
            "insert-repo",
            "-",
            stdin=json.dumps(
                {
                    "full_name": "a/b",
                    "url": "https://github.com/a/b",
                    "stars": 1,
                }
            ),
        )
        self.assertEqual(repo.returncode, 0)
        self.assertEqual(json.loads(repo.stdout)["repo_id"], 1)

    def test_snapshot_commands_accept_card_ids_and_json_stdin(self):
        repo = self.run_cli(
            "insert-repo", "-",
            stdin=json.dumps({"full_name": "a/b", "url": "https://github.com/a/b"}),
        )
        repo_id = json.loads(repo.stdout)["repo_id"]
        card = self.run_cli(
            "insert-card", "-",
            stdin=json.dumps({
                "repo_id": repo_id, "dimension": "architecture",
                "title": "A card", "content": "Evidence",
            }),
        )
        card_id = json.loads(card.stdout)["card_id"]

        grouped = self.run_cli("repos-for-cards", str(card_id))
        self.assertEqual(json.loads(grouped.stdout)[0]["card_ids"], [card_id])
        recorded = self.run_cli(
            "record-repo-check", "-",
            stdin=json.dumps({
                "repo_id": repo_id, "outcome": "unchanged", "head_sha": "abc",
                "checked_at": "2026-07-12T08:00:00Z", "commit_timestamps": [],
            }),
        )
        self.assertEqual(recorded.returncode, 0, recorded.stdout)
        self.assertEqual(json.loads(recorded.stdout)["outcome"], "unchanged")

    def test_targeted_refresh_commands_are_exposed(self):
        repo = self.run_cli(
            "insert-repo", "-",
            stdin=json.dumps({"full_name": "a/b", "url": "https://github.com/a/b"}),
        )
        repo_id = json.loads(repo.stdout)["repo_id"]
        card = self.run_cli(
            "insert-card", "-",
            stdin=json.dumps({
                "repo_id": repo_id, "dimension": "architecture", "title": "Old",
                "content": "Evidence", "evidence_paths": ["src/core.py"],
            }),
        )
        card_id = json.loads(card.stdout)["card_id"]
        affected = self.run_cli("affected-cards", str(repo_id), "src")
        self.assertEqual(json.loads(affected.stdout), {"card_ids": [card_id]})
        refreshed = self.run_cli(
            "refresh-cards", "-",
            stdin=json.dumps({
                "repo_id": repo_id, "head_sha": "new", "status": "fresh",
                "updated_at": "2026-07-12T08:00:00Z",
                "replacements": [{
                    "id": card_id, "repo_id": repo_id, "dimension": "architecture",
                    "title": "New", "content": "New evidence",
                }],
            }),
        )
        self.assertEqual(refreshed.returncode, 0, refreshed.stdout)
        self.assertEqual(json.loads(refreshed.stdout)["card_ids"], [card_id])

    def test_cli_validation_errors_are_json(self):
        cases = [
            ("check-repo",),
            ("insert-repo", "{bad json"),
            ("get-cards", "not-an-id"),
            ("unknown-command",),
        ]
        for args in cases:
            with self.subTest(args=args):
                result = self.run_cli(*args)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("error", json.loads(result.stdout))
                self.assertEqual(result.stderr, "")

    def test_project_root_env_controls_database_location(self):
        project = self.root / "target-project"
        nested = project / "src" / "nested"
        nested.mkdir(parents=True)
        result = subprocess.run(
            [sys.executable, str(self.script), "count"],
            cwd=nested,
            text=True,
            capture_output=True,
            env={
                **os.environ,
                "PYTHONDONTWRITEBYTECODE": "1",
                "REPOMIND_PROJECT_ROOT": str(project),
            },
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((project / ".repomind" / "repomind.db").is_file())

    def test_git_root_is_discovered_from_nested_directory(self):
        project = self.root / "git-project"
        nested = project / "src" / "nested"
        nested.mkdir(parents=True)
        subprocess.run(
            ["git", "init", "-q"],
            cwd=project,
            check=True,
            capture_output=True,
            text=True,
        )
        result = subprocess.run(
            [sys.executable, str(self.script), "count"],
            cwd=nested,
            text=True,
            capture_output=True,
            env={
                **os.environ,
                "PYTHONDONTWRITEBYTECODE": "1",
                "REPOMIND_PROJECT_ROOT": "",
            },
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertTrue((project / ".repomind" / "repomind.db").is_file())

    def test_project_config_overrides_bundled_defaults(self):
        project = self.root / "configured-project"
        state = project / ".repomind"
        state.mkdir(parents=True)
        (state / "config.json").write_text(
            json.dumps({"max_search_repos": 7}), encoding="utf-8"
        )
        env_project = self.root / "environment-project"
        env_project.mkdir()
        result = subprocess.run(
            [
                sys.executable,
                str(self.script),
                "--project-root",
                str(project),
                "config",
            ],
            text=True,
            capture_output=True,
            env={
                **os.environ,
                "PYTHONDONTWRITEBYTECODE": "1",
                "REPOMIND_PROJECT_ROOT": str(env_project),
            },
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["max_search_repos"], 7)
        self.assertEqual(
            json.loads(result.stdout)["card_similarity_threshold"], 0.7
        )

    def test_invalid_project_config_is_a_structured_cli_error(self):
        project = self.root / "invalid-project"
        state = project / ".repomind"
        state.mkdir(parents=True)
        (state / "config.json").write_text(
            json.dumps({"freshness_min_days": 31}), encoding="utf-8"
        )
        result = subprocess.run(
            [
                sys.executable,
                str(self.script),
                "--project-root",
                str(project),
                "config",
            ],
            text=True,
            capture_output=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("freshness_min_days", json.loads(result.stdout)["error"])
        self.assertEqual(result.stderr, "")

    def test_unknown_project_config_key_is_rejected(self):
        project = self.root / "unknown-config-project"
        state = project / ".repomind"
        state.mkdir(parents=True)
        (state / "config.json").write_text(
            json.dumps({"surprise": True}), encoding="utf-8"
        )
        result = subprocess.run(
            [
                sys.executable,
                str(self.script),
                "--project-root",
                str(project),
                "config",
            ],
            text=True,
            capture_output=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        self.assertEqual(result.returncode, 1)
        self.assertIn("Unknown config key", json.loads(result.stdout)["error"])
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
