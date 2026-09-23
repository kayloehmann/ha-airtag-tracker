"""GPS device tracker for an AirTag."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_tracker.const import SourceType
from homeassistant.components.device_tracker.entity import TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AirTagConfigEntry
from .entity import AirTagEntity
from .helpers import battery_level_from_status, report_age_seconds


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirTagConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the AirTag tracker."""
    async_add_entities([AirTagTracker(entry.runtime_data.coordinator)])


class AirTagTracker(AirTagEntity, TrackerEntity):
    """Represent the latest AirTag position."""

    _attr_name = None

    @property
    def unique_id(self) -> str:
        return self._identifier

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data.report is not None

    @property
    def latitude(self) -> float | None:
        report = self.coordinator.data.report
        return report.latitude if report else None

    @property
    def longitude(self) -> float | None:
        report = self.coordinator.data.report
        return report.longitude if report else None

    @property
    def location_accuracy(self) -> float:
        report = self.coordinator.data.report
        return float(report.horizontal_accuracy) if report else 0.0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        report = self.coordinator.data.report
        if report is None:
            return {}
        return {
            "report_timestamp": report.timestamp,
            "report_age_seconds": report_age_seconds(report.timestamp),
            "last_checked": self.coordinator.data.checked_at,
            "confidence": report.confidence,
            "battery_level": battery_level_from_status(report.status),
            "zone_entity_id": self.coordinator.data.zone_entity_id,
            "polling_mode": self.coordinator.data.polling_mode,
            "next_poll_minutes": int(
                (
                    self.coordinator.update_interval or self.coordinator.inside_interval
                ).total_seconds()
                / 60
            ),
        }
