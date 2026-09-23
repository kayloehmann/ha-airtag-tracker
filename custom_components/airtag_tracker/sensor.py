"""Diagnostic and automation sensors for an AirTag."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfLength, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import AirTagConfigEntry
from .entity import AirTagEntity
from .helpers import battery_level_from_status, report_age_seconds


@dataclass(frozen=True, kw_only=True)
class AirTagSensorDescription(SensorEntityDescription):
    """Describe an AirTag sensor."""

    value_fn: Callable[[Any], Any]


SENSORS = (
    AirTagSensorDescription(
        key="last_seen",
        translation_key="last_seen",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda report: report.timestamp,
    ),
    AirTagSensorDescription(
        key="report_age",
        translation_key="report_age",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.SECONDS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda report: report_age_seconds(report.timestamp),
    ),
    AirTagSensorDescription(
        key="accuracy",
        translation_key="accuracy",
        device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.METERS,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda report: report.horizontal_accuracy,
    ),
    AirTagSensorDescription(
        key="battery_level",
        translation_key="battery_level",
        device_class=SensorDeviceClass.ENUM,
        options=["full", "medium", "low", "very_low"],
        value_fn=lambda report: battery_level_from_status(report.status),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AirTagConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up AirTag sensors."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities(AirTagSensor(coordinator, description) for description in SENSORS)


class AirTagSensor(AirTagEntity, SensorEntity):
    """Expose one value from the latest AirTag report."""

    entity_description: AirTagSensorDescription

    def __init__(self, coordinator, description: AirTagSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{self._identifier}_{description.key}"

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data.report is not None

    @property
    def native_value(self) -> Any:
        report = self.coordinator.data.report
        return self.entity_description.value_fn(report) if report else None
