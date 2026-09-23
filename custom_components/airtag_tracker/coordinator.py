"""Apple Find My update coordinator."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from findmy import (
    AsyncAppleAccount,
    FindMyAccessory,
    InvalidStateError,
    LocationReport,
    UnauthorizedError,
)
from findmy.errors import EmptyResponseError
from homeassistant.components.zone import async_active_zone
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import CONF_ACCESSORY, CONF_ACCOUNT, DOMAIN
from .helpers import polling_interval_for_zone, sanitized_account_state

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class AirTagData:
    """Latest known data for an AirTag."""

    report: LocationReport | None
    checked_at: datetime
    zone_entity_id: str | None
    polling_mode: str


class AirTagUpdateCoordinator(DataUpdateCoordinator[AirTagData]):
    """Fetch and retain the latest AirTag report."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        account: AsyncAppleAccount,
        accessory: FindMyAccessory,
        inside_interval: timedelta,
        outside_interval: timedelta,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=inside_interval,
            always_update=False,
        )
        self.account = account
        self.accessory = accessory
        self.inside_interval = inside_interval
        self.outside_interval = outside_interval

    async def _async_update_data(self) -> AirTagData:
        """Fetch a report, preserving the last location if Apple has no new one."""
        try:
            report = await self.account.fetch_location(self.accessory)
        except (UnauthorizedError, InvalidStateError) as err:
            raise ConfigEntryAuthFailed("Apple session is no longer valid") from err
        except EmptyResponseError as err:
            raise UpdateFailed("Apple returned an empty location response") from err
        except Exception as err:
            raise UpdateFailed(f"Unable to fetch AirTag location: {type(err).__name__}") from err

        previous = self.data.report if self.data is not None else None
        latest = report or previous
        zone_entity_id: str | None = None
        polling_mode = "unknown"
        if latest is not None:
            zone = async_active_zone(
                self.hass,
                latest.latitude,
                latest.longitude,
                latest.horizontal_accuracy,
            )
            zone_entity_id = zone.entity_id if zone else None
            self.update_interval, polling_mode = polling_interval_for_zone(
                zone_entity_id,
                self.inside_interval,
                self.outside_interval,
            )
        self._persist_runtime_state()
        return AirTagData(
            report=latest,
            checked_at=datetime.now(UTC),
            zone_entity_id=zone_entity_id,
            polling_mode=polling_mode,
        )

    def _persist_runtime_state(self) -> None:
        """Persist alignment/session changes without ever persisting the password."""
        data: dict[str, Any] = dict(self.config_entry.data)
        data[CONF_ACCOUNT] = sanitized_account_state(self.account.to_json())
        data[CONF_ACCESSORY] = self.accessory.to_json()
        self.hass.config_entries.async_update_entry(self.config_entry, data=data)
