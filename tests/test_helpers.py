"""Tests for dependency-light integration helpers."""

from datetime import UTC, datetime, timedelta

from custom_components.airtag_tracker.helpers import (
    battery_level_from_status,
    polling_interval_for_zone,
    report_age_seconds,
    sanitized_account_state,
)


def test_sanitized_account_state_removes_password_without_mutating_source() -> None:
    source = {"account": {"username": "parent@example.com", "password": "secret"}}

    clean = sanitized_account_state(source)

    assert clean["account"]["password"] is None
    assert source["account"]["password"] == "secret"


def test_report_age_is_non_negative() -> None:
    now = datetime(2026, 9, 23, 12, 0, tzinfo=UTC)

    assert report_age_seconds(now - timedelta(seconds=42), now) == 42
    assert report_age_seconds(now + timedelta(seconds=5), now) == 0


def test_battery_status_bits() -> None:
    assert battery_level_from_status(0b00000000) == "full"
    assert battery_level_from_status(0b01000000) == "medium"
    assert battery_level_from_status(0b10000000) == "low"
    assert battery_level_from_status(0b11000000) == "very_low"
    assert battery_level_from_status(None) is None


def test_polling_is_faster_outside_zones() -> None:
    inside = timedelta(minutes=15)
    outside = timedelta(minutes=5)

    assert polling_interval_for_zone("zone.school", inside, outside) == (
        inside,
        "inside_zone",
    )
    assert polling_interval_for_zone(None, inside, outside) == (
        outside,
        "outside_zones",
    )
