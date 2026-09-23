"""Small, dependency-light helpers for AirTag Tracker."""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime, timedelta
from typing import Any


def sanitized_account_state(state: Mapping[str, Any]) -> dict[str, Any]:
    """Return serializable account state without the Apple password."""
    clean = deepcopy(dict(state))
    account = clean.get("account")
    if isinstance(account, dict):
        account["password"] = None
    return clean


def report_age_seconds(timestamp: datetime, now: datetime | None = None) -> int:
    """Return a non-negative age for a location report."""
    current = now or datetime.now(UTC)
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=UTC)
    return max(0, int((current - timestamp).total_seconds()))


def battery_level_from_status(status: int | None) -> str | None:
    """Decode the two battery bits reported by a Find My accessory."""
    if status is None:
        return None
    return {
        0b00: "full",
        0b01: "medium",
        0b10: "low",
        0b11: "very_low",
    }[(status >> 6) & 0b11]


def polling_interval_for_zone(
    zone_entity_id: str | None,
    inside_interval: timedelta,
    outside_interval: timedelta,
) -> tuple[timedelta, str]:
    """Select adaptive cadence and its observable mode."""
    if zone_entity_id is not None:
        return inside_interval, "inside_zone"
    return outside_interval, "outside_zones"
