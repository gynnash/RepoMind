#!/usr/bin/env python3
"""RepoMind database helper — SQLite operations for repository code cards."""

import argparse
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys


SKILL_DIR = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG_PATH = SKILL_DIR / "config" / "defaults.json"
DB_NAME = "repomind.db"
SCHEMA_VERSION = 2


def discover_project_root():
    configured = os.environ.get("REPOMIND_PROJECT_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=Path.cwd(),
            text=True,
            capture_output=True,
            check=True,
        )
        return Path(result.stdout.strip()).resolve()
    except (OSError, subprocess.CalledProcessError):
        return Path.cwd().resolve()


PROJECT_ROOT = discover_project_root()
DB_DIR = PROJECT_ROOT / ".repomind"
CONFIG_PATH = DB_DIR / "config.json"


def set_project_root(path):
    global PROJECT_ROOT, DB_DIR, CONFIG_PATH
    PROJECT_ROOT = Path(path).expanduser().resolve()
    DB_DIR = PROJECT_ROOT / ".repomind"
    CONFIG_PATH = DB_DIR / "config.json"


class CliError(Exception):
    """An expected command-line usage or input error."""


class RepoConnection(sqlite3.Connection):
    """SQLite connection that also closes when leaving a with block."""

    def __exit__(self, exc_type, exc_value, traceback):
        try:
            return super().__exit__(exc_type, exc_value, traceback)
        finally:
            self.close()


class QuietArgumentParser(argparse.ArgumentParser):
    """Argument parser that reports errors through RepoMind's JSON envelope."""

    def error(self, message):
        raise CliError(message)


def get_db_path():
    return Path(DB_DIR) / DB_NAME


def load_config():
    defaults_path = Path(DEFAULT_CONFIG_PATH)
    if not defaults_path.exists():
        raise ValueError(
            f"Bundled RepoMind config is missing: {defaults_path}"
        )
    try:
        config = json.loads(defaults_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid bundled RepoMind config: {exc}") from exc
    _validate_config(config, "bundled RepoMind config")
    path = Path(CONFIG_PATH)
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid RepoMind config: {exc}") from exc
        if not isinstance(loaded, dict):
            raise ValueError("Invalid RepoMind config: root value must be an object")
        unknown = sorted(set(loaded) - set(config))
        if unknown:
            raise ValueError(f"Unknown config key(s): {', '.join(unknown)}")
        config.update(loaded)
    _validate_config(config, "RepoMind config")
    return config


def _validate_config(config, source):
    if not isinstance(config, dict):
        raise ValueError(f"Invalid {source}: root value must be an object")

    def require_integer(name, minimum, maximum):
        value = config.get(name)
        if type(value) is not int or not minimum <= value <= maximum:
            raise ValueError(
                f"Invalid {source} field {name}: expected integer "
                f"{minimum}..{maximum}"
            )

    def require_number(name, minimum, maximum):
        value = config.get(name)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not minimum <= value <= maximum
        ):
            raise ValueError(
                f"Invalid {source} field {name}: expected number "
                f"{minimum}..{maximum}"
            )

    require_integer("max_search_repos", 1, 100)
    require_number("min_relevance_score", 0, 5)
    require_number("card_similarity_threshold", 0, 1)
    require_integer("empty_query_ttl_hours", 1, 8760)
    require_number("freshness_min_days", 0.01, 3650)
    require_number("freshness_max_days", 0.01, 3650)
    require_number("freshness_default_days", 0.01, 3650)
    require_integer("freshness_commit_sample_size", 1, 1000)
    require_number("freshness_stability_growth", 1, 10)
    require_number("freshness_change_decay", 0.01, 1)
    if not (
        config["freshness_min_days"]
        <= config["freshness_default_days"]
        <= config["freshness_max_days"]
    ):
        raise ValueError(
            f"Invalid {source}: expected freshness_min_days <= "
            "freshness_default_days <= freshness_max_days"
        )


def _create_schema(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS repos (
            id          INTEGER PRIMARY KEY,
            full_name   TEXT UNIQUE NOT NULL,
            url         TEXT NOT NULL,
            language    TEXT,
            topics      TEXT,
            stars       INTEGER,
            description TEXT,
            fetched_at  TEXT NOT NULL DEFAULT (datetime('now')),
            last_head_sha TEXT,
            default_branch TEXT,
            readme_digest TEXT,
            architecture_digest TEXT,
            structure_digest TEXT,
            last_checked_at TEXT,
            last_changed_at TEXT,
            next_check_at TEXT,
            check_interval_days REAL NOT NULL DEFAULT 7.0,
            stability_runs INTEGER NOT NULL DEFAULT 0,
            commit_intervals TEXT NOT NULL DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS cards (
            id          INTEGER PRIMARY KEY,
            repo_id     INTEGER NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
            dimension   TEXT NOT NULL,
            title       TEXT NOT NULL,
            content     TEXT NOT NULL,
            keywords    TEXT,
            embedding   BLOB,
            created_at  TEXT NOT NULL DEFAULT (datetime('now')),
            research_object TEXT,
            evidence_paths TEXT NOT NULL DEFAULT '[]',
            related_modules TEXT NOT NULL DEFAULT '[]',
            source_sha TEXT,
            freshness_status TEXT NOT NULL DEFAULT 'unknown',
            card_updated_at TEXT
        );

        CREATE TABLE IF NOT EXISTS search_history (
            query         TEXT PRIMARY KEY,
            last_empty_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        """
    )


def _add_missing_columns(conn, table, definitions):
    existing = {
        row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()
    }
    for name, definition in definitions:
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def _migrate_schema_v2(conn):
    _add_missing_columns(conn, "repos", (
        ("language", "TEXT"), ("topics", "TEXT"), ("stars", "INTEGER"),
        ("description", "TEXT"), ("fetched_at", "TEXT"),
        ("last_head_sha", "TEXT"), ("default_branch", "TEXT"),
        ("readme_digest", "TEXT"), ("architecture_digest", "TEXT"),
        ("structure_digest", "TEXT"), ("last_checked_at", "TEXT"),
        ("last_changed_at", "TEXT"), ("next_check_at", "TEXT"),
        ("check_interval_days", "REAL NOT NULL DEFAULT 7.0"),
        ("stability_runs", "INTEGER NOT NULL DEFAULT 0"),
        ("commit_intervals", "TEXT NOT NULL DEFAULT '[]'"),
    ))
    _add_missing_columns(conn, "cards", (
        ("keywords", "TEXT"), ("embedding", "BLOB"), ("created_at", "TEXT"),
        ("research_object", "TEXT"),
        ("evidence_paths", "TEXT NOT NULL DEFAULT '[]'"),
        ("related_modules", "TEXT NOT NULL DEFAULT '[]'"),
        ("source_sha", "TEXT"),
        ("freshness_status", "TEXT NOT NULL DEFAULT 'unknown'"),
        ("card_updated_at", "TEXT"),
    ))
    conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")


def _migrate_nullable_repo_id(conn):
    columns = conn.execute("PRAGMA table_info(cards)").fetchall()
    repo_id = next((column for column in columns if column[1] == "repo_id"), None)
    if repo_id is None or repo_id[3]:
        return
    orphan_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM cards c
        LEFT JOIN repos r ON r.id = c.repo_id
        WHERE c.repo_id IS NULL OR r.id IS NULL
        """
    ).fetchone()[0]
    if orphan_count:
        raise sqlite3.IntegrityError(
            f"Cannot migrate: {orphan_count} legacy cards reference missing "
            "repositories; repair or remove them before retrying"
        )
    conn.executescript(
        """
        ALTER TABLE cards RENAME TO cards_legacy;
        CREATE TABLE cards (
            id          INTEGER PRIMARY KEY,
            repo_id     INTEGER NOT NULL REFERENCES repos(id) ON DELETE CASCADE,
            dimension   TEXT NOT NULL,
            title       TEXT NOT NULL,
            content     TEXT NOT NULL,
            keywords    TEXT,
            embedding   BLOB,
            created_at  TEXT NOT NULL DEFAULT (datetime('now'))
        );
        INSERT INTO cards
            (id, repo_id, dimension, title, content, keywords, embedding, created_at)
        SELECT c.id, c.repo_id, c.dimension, c.title, c.content, c.keywords,
               c.embedding, c.created_at
        FROM cards_legacy c
        JOIN repos r ON r.id = c.repo_id;
        DROP TABLE cards_legacy;
        """
    )


def connect_db():
    """Open an initialized connection with RepoMind's safety pragmas enabled."""
    db_dir = Path(DB_DIR)
    db_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        get_db_path(), timeout=10, factory=RepoConnection
    )
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA journal_mode=WAL")
        _create_schema(conn)
        _migrate_nullable_repo_id(conn)
        _migrate_schema_v2(conn)
        conn.commit()
        return conn
    except Exception:
        conn.rollback()
        conn.close()
        raise


def init_db():
    with connect_db():
        pass


def get_card_count():
    with connect_db() as conn:
        return conn.execute("SELECT COUNT(*) FROM cards").fetchone()[0]


def insert_repo(data):
    required = ("full_name", "url")
    missing = [key for key in required if not data.get(key)]
    if missing:
        raise ValueError(f"Missing repo field(s): {', '.join(missing)}")
    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO repos
                (full_name, url, language, topics, stars, description)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(full_name) DO UPDATE SET
                url = excluded.url,
                language = excluded.language,
                topics = excluded.topics,
                stars = excluded.stars,
                description = excluded.description,
                fetched_at = datetime('now')
            """,
            (
                data["full_name"],
                data["url"],
                data.get("language"),
                json.dumps(data.get("topics", []), ensure_ascii=False),
                data.get("stars"),
                data.get("description"),
            ),
        )
        return conn.execute(
            "SELECT id FROM repos WHERE full_name = ?", (data["full_name"],)
        ).fetchone()[0]


def repo_exists(full_name):
    with connect_db() as conn:
        row = conn.execute(
            "SELECT id FROM repos WHERE full_name = ?", (full_name,)
        ).fetchone()
        return row is not None


def get_repo(full_name):
    with connect_db() as conn:
        row = conn.execute(
            "SELECT * FROM repos WHERE full_name = ?", (full_name,)
        ).fetchone()
        return dict(row) if row else None


def reset_db():
    db_path = get_db_path()
    for suffix in ("", "-wal", "-shm"):
        candidate = Path(f"{db_path}{suffix}")
        if candidate.exists():
            candidate.unlink()
    init_db()


def _validate_card(data):
    required = ("repo_id", "dimension", "title", "content")
    missing = [key for key in required if data.get(key) in (None, "")]
    if missing:
        raise ValueError(f"Missing card field(s): {', '.join(missing)}")


def _insert_card(conn, data):
    cur = conn.execute(
        """
        INSERT INTO cards (repo_id, dimension, title, content, keywords)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            data["repo_id"],
            data["dimension"],
            data["title"],
            data["content"],
            data.get("keywords"),
        ),
    )
    return cur.lastrowid


def insert_card(data):
    _validate_card(data)
    with connect_db() as conn:
        return _insert_card(conn, data)


def _tokens(value):
    return set(re.findall(r"[\w-]+", (value or "").lower()))


def _keyword_tokens(value):
    return _tokens((value or "").replace(",", " "))


def _jaccard(left, right):
    union = left | right
    return len(left & right) / len(union) if union else 0.0


def _overlap_coefficient(left, right):
    smaller = min(len(left), len(right))
    return len(left & right) / smaller if smaller else 0.0


def _find_similar_card(conn, title, keywords, threshold):
    title_tokens = _tokens(title)
    keyword_tokens = _keyword_tokens(keywords)
    rows = conn.execute("SELECT id, title, keywords FROM cards").fetchall()
    for row in rows:
        title_score = _jaccard(title_tokens, _tokens(row["title"]))
        keyword_score = _overlap_coefficient(
            keyword_tokens, _keyword_tokens(row["keywords"])
        )
        if max(title_score, keyword_score) >= threshold:
            return row["id"]
    return None


def check_similar_card(title, keywords, threshold=None):
    if threshold is None:
        threshold = float(load_config()["card_similarity_threshold"])
    with connect_db() as conn:
        return _find_similar_card(conn, title, keywords, threshold) is not None


def insert_card_if_new(data):
    _validate_card(data)
    threshold = float(load_config()["card_similarity_threshold"])
    conn = connect_db()
    try:
        conn.execute("BEGIN IMMEDIATE")
        duplicate_id = _find_similar_card(
            conn, data["title"], data.get("keywords"), threshold
        )
        if duplicate_id is not None:
            conn.commit()
            return {
                "inserted": False,
                "card_id": None,
                "duplicate_id": duplicate_id,
            }
        card_id = _insert_card(conn, data)
        conn.commit()
        return {"inserted": True, "card_id": card_id, "duplicate_id": None}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _stale_expression():
    days = float(load_config()["freshness_max_days"])
    return f"-{days:g} days"


def _serialize_rows(rows):
    results = []
    for row in rows:
        item = dict(row)
        if "is_stale" in item:
            item["is_stale"] = bool(item["is_stale"])
        results.append(item)
    return results


def search_cards_v1(keywords, limit=10):
    clean_keywords = [keyword.strip().lower() for keyword in keywords if keyword.strip()]
    if not clean_keywords:
        return []
    with connect_db() as conn:
        rows = conn.execute(
            """
            SELECT c.id, c.dimension, c.title, c.keywords, c.created_at,
                   r.full_name, r.url, r.stars, r.language,
                   r.fetched_at < datetime('now', ?) AS is_stale
            FROM cards c
            JOIN repos r ON c.repo_id = r.id
            """,
            (_stale_expression(),),
        ).fetchall()
    matches = []
    for row in _serialize_rows(rows):
        haystack = f"{row['title']} {row.get('keywords') or ''}".lower()
        matched = sum(keyword in haystack for keyword in clean_keywords)
        if not matched:
            continue
        row["relevance"] = round(5.0 * matched / len(clean_keywords), 3)
        matches.append(row)
    matches.sort(key=lambda card: (-card["relevance"], -(card["stars"] or 0)))
    return matches[:limit]


def get_all_cards_with_repo():
    with connect_db() as conn:
        rows = conn.execute(
            """
            SELECT c.id, c.dimension, c.title, c.keywords,
                   r.full_name, r.url, r.stars,
                   r.fetched_at < datetime('now', ?) AS is_stale,
                   0.0 AS relevance
            FROM cards c
            JOIN repos r ON c.repo_id = r.id
            ORDER BY r.stars DESC
            """,
            (_stale_expression(),),
        ).fetchall()
        return _serialize_rows(rows)


def get_cards_by_ids(card_ids):
    if not card_ids:
        return []
    placeholders = ",".join("?" for _ in card_ids)
    order_cases = " ".join(f"WHEN ? THEN {index}" for index, _ in enumerate(card_ids))
    with connect_db() as conn:
        rows = conn.execute(
            f"""
            SELECT c.*, r.full_name, r.url, r.stars, r.language,
                   r.fetched_at < datetime('now', ?) AS is_stale,
                   0.0 AS relevance
            FROM cards c
            JOIN repos r ON c.repo_id = r.id
            WHERE c.id IN ({placeholders})
            ORDER BY CASE c.id {order_cases} END
            """,
            [_stale_expression(), *card_ids, *card_ids],
        ).fetchall()
        return _serialize_rows(rows)


def _normalize_query(query):
    return " ".join(query.lower().split())


def record_empty_query(query):
    normalized = _normalize_query(query)
    if not normalized:
        raise ValueError("Query must not be empty")
    with connect_db() as conn:
        conn.execute(
            """
            INSERT INTO search_history (query, last_empty_at)
            VALUES (?, datetime('now'))
            ON CONFLICT(query) DO UPDATE SET last_empty_at = datetime('now')
            """,
            (normalized,),
        )


def recent_empty_query(query):
    normalized = _normalize_query(query)
    if not normalized:
        return False
    ttl = int(load_config()["empty_query_ttl_hours"])
    with connect_db() as conn:
        row = conn.execute(
            """
            SELECT last_empty_at >= datetime('now', ?) AS recent
            FROM search_history
            WHERE query = ?
            """,
            (f"-{ttl} hours", normalized),
        ).fetchone()
        return bool(row["recent"]) if row else False


def _json_argument(value):
    raw = sys.stdin.read() if value == "-" else value
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CliError(f"Invalid JSON: {exc.msg}") from exc
    if not isinstance(data, dict):
        raise CliError("JSON input must be an object")
    return data


def _parser():
    parser = QuietArgumentParser(prog="search.py", add_help=False)
    parser.add_argument("--project-root")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("init")
    subparsers.add_parser("count")
    subparsers.add_parser("config")
    search = subparsers.add_parser("search")
    search.add_argument("keywords", nargs="*")
    subparsers.add_parser("all-cards")
    for command in ("insert-repo", "insert-card", "insert-card-if-new"):
        command_parser = subparsers.add_parser(command)
        command_parser.add_argument("data")
    check_repo = subparsers.add_parser("check-repo")
    check_repo.add_argument("full_name")
    get_cards = subparsers.add_parser("get-cards")
    get_cards.add_argument("card_ids", nargs="*")
    similar = subparsers.add_parser("check-similar")
    similar.add_argument("title")
    similar.add_argument("keywords", nargs="?", default="")
    subparsers.add_parser("reset-db")
    record = subparsers.add_parser("record-empty-query")
    record.add_argument("query")
    recent = subparsers.add_parser("recent-empty-query")
    recent.add_argument("query")
    return parser


def _parse_args(argv):
    try:
        return _parser().parse_args(argv)
    except SystemExit as exc:
        raise CliError("Invalid command or arguments") from exc


def _card_ids(values):
    try:
        return [int(value) for value in values]
    except ValueError as exc:
        raise CliError("Card IDs must be integers") from exc


def run_command(args):
    command = args.command
    if command == "init":
        init_db()
        return {"status": "ok", "message": "Database initialized"}
    if command == "count":
        return {"count": get_card_count()}
    if command == "config":
        return load_config()
    if command == "search":
        return search_cards_v1(args.keywords)
    if command == "all-cards":
        return get_all_cards_with_repo()
    if command == "insert-repo":
        return {"repo_id": insert_repo(_json_argument(args.data))}
    if command == "check-repo":
        repo = get_repo(args.full_name)
        return {"exists": repo is not None, "repo": repo}
    if command == "insert-card":
        return {"card_id": insert_card(_json_argument(args.data))}
    if command == "insert-card-if-new":
        return insert_card_if_new(_json_argument(args.data))
    if command == "get-cards":
        return get_cards_by_ids(_card_ids(args.card_ids))
    if command == "check-similar":
        return {
            "similar_exists": check_similar_card(args.title, args.keywords)
        }
    if command == "reset-db":
        reset_db()
        return {"status": "ok", "message": "Database reset"}
    if command == "record-empty-query":
        record_empty_query(args.query)
        return {"recorded": True}
    if command == "recent-empty-query":
        return {"recent": recent_empty_query(args.query)}
    raise CliError(f"Unknown command: {command}")


def main(argv=None):
    try:
        args = _parse_args(sys.argv[1:] if argv is None else argv)
        if args.project_root:
            set_project_root(args.project_root)
        result = run_command(args)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (CliError, ValueError, KeyError, sqlite3.Error) as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main())
