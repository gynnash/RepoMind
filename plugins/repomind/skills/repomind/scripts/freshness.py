#!/usr/bin/env python3
"""Deterministic scheduling helpers for adaptive repository freshness checks."""

from datetime import datetime
from statistics import median


SECONDS_PER_DAY = 24 * 60 * 60


def _parse_utc(timestamp):
    if isinstance(timestamp, datetime):
        return timestamp
    if timestamp.endswith("Z"):
        timestamp = f"{timestamp[:-1]}+00:00"
    return datetime.fromisoformat(timestamp)


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
    return next_check_at is None or next_check_at <= now
