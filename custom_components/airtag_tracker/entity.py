"""Base entity for AirTag Tracker."""

from __future__ import annotations

from functools import cached_property

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import AirTagUpdateCoordinator


class AirTagEntity(CoordinatorEntity[AirTagUpdateCoordinator]):
    """Base class shared by all AirTag entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: AirTagUpdateCoordinator) -> None:
        super().__init__(coordinator)
        identifier = coordinator.accessory.identifier
        if not identifier:
            raise ValueError("AirTag accessory has no stable identifier")
        self._identifier = identifier

    @cached_property
    def device_info(self) -> DeviceInfo:
        """Group all entities below one Home Assistant device."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._identifier)},
            manufacturer="Apple",
            model="AirTag / Find My accessory",
            name=self.coordinator.accessory.name or "AirTag",
        )
