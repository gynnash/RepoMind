#!/usr/bin/env python3
"""Deterministic scheduling helpers for adaptive repository freshness checks."""

from datetime import datetime, timezone
from statistics import median


SECONDS_PER_DAY = 24 * 60 * 60


def _normalize_path(path):
    value = str(path).replace("\\", "/").strip()
    parts = []
    for part in value.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if parts:
                parts.pop()
            continue
        parts.append(part)
    return "/".join(parts)


def _paths_overlap(left, right):
    left, right = _normalize_path(left), _normalize_path(right)
    return bool(left and right) and (
        left == right or left.startswith(right + "/") or right.startswith(left + "/")
    )


def classify_repository_change(observation):
    """Classify a repository observation without using commit volume as a signal."""
    previous = observation.get("previous_head_sha")
    current = observation.get("head_sha")
    if previous is not None and current == previous:
        return {"kind": "unchanged", "affected_paths": [],
                "reasons": ["head_unchanged"]}

    paths = sorted({_normalize_path(path)
                    for path in observation.get("changed_paths", []) if _normalize_path(path)})
    deleted = sorted({_normalize_path(path)
                      for path in observation.get("deleted_paths", []) if _normalize_path(path)})
    architecture = bool(observation.get("architecture_changed"))
    structure = bool(observation.get("structure_changed"))
    key_dirs = [_normalize_path(path) for path in observation.get("key_directories", [])]
    key_count = sum(any(_paths_overlap(path, directory) for directory in key_dirs)
                    for path in paths)
    ratio = key_count / len(paths) if paths else 0.0
    if architecture and structure:
        return {"kind": "global", "affected_paths": paths,
                "reasons": ["architecture_and_structure_changed"]}
    if ratio >= 0.5 and paths:
        return {"kind": "global", "affected_paths": paths,
                "reasons": ["key_directory_ratio_gte_0.5"]}

    relevant = list(observation.get("evidence_paths", [])) + list(
        observation.get("module_paths", observation.get("related_modules", [])))
    affected = sorted(path for path in set(paths + deleted)
                      if any(_paths_overlap(path, target) for target in relevant))
    if affected:
        reasons = ["relevant_path_changed"]
        if any(any(_paths_overlap(path, target) for target in relevant)
               for path in deleted):
            reasons.insert(0, "evidence_deleted")
        return {"kind": "localized", "affected_paths": affected, "reasons": reasons}
    return {"kind": "unrelated", "affected_paths": [],
            "reasons": ["no_relevant_paths_changed"]}


def _parse_utc(timestamp):
    if isinstance(timestamp, datetime):
        parsed = timestamp
    else:
        if timestamp.endswith("Z"):
            timestamp = f"{timestamp[:-1]}+00:00"
        parsed = datetime.fromisoformat(timestamp)
    # Database timestamps without an explicit offset are stored as UTC.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def median_commit_interval_days(timestamps):
    """Return the median gap in days between chronologically sorted commits."""
    if len(timestamps) < 2:
        return None
    ordered = sorted(_parse_utc(timestamp) for timestamp in timestamps)
    intervals = [
        (later - earlier).total_seconds() / SECONDS_PER_DAY
        for earlier, later in zip(ordered, ordered[1:])
    ]
    return median(intervals)


def calculate_check_interval(
    commit_interval_days,
    stability_runs,
    global_change_detected,
    relevant_change_detected,
    minimum_days,
    maximum_days,
    stability_growth,
    change_decay,
):
    """Calculate a bounded check interval from cadence and observed changes."""
    interval = commit_interval_days
    if global_change_detected and relevant_change_detected:
        interval *= change_decay
    elif not global_change_detected:
        interval *= stability_growth ** stability_runs
    return round(min(max(interval, minimum_days), maximum_days), 3)


def is_check_due(next_check_at, now):
    """Return whether a repository's scheduled check time has arrived."""
    return next_check_at is None or _parse_utc(next_check_at) <= _parse_utc(now)
