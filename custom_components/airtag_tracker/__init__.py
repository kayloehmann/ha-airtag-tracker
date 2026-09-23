"""AirTag Tracker integration for Home Assistant."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from findmy import AsyncAppleAccount, FindMyAccessory
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import (
    ANISETTE_LIBS_FILENAME,
    CONF_ACCESSORY,
    CONF_ACCOUNT,
    CONF_INSIDE_POLL_INTERVAL,
    CONF_OUTSIDE_POLL_INTERVAL,
    DEFAULT_INSIDE_POLL_INTERVAL,
    DEFAULT_OUTSIDE_POLL_INTERVAL,
)
from .coordinator import AirTagUpdateCoordinator

PLATFORMS = [Platform.DEVICE_TRACKER, Platform.SENSOR]
type AirTagConfigEntry = ConfigEntry["AirTagRuntimeData"]


@dataclass(slots=True)
class AirTagRuntimeData:
    """Runtime objects owned by one config entry."""

    account: AsyncAppleAccount
    accessory: FindMyAccessory
    coordinator: AirTagUpdateCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: AirTagConfigEntry) -> bool:
    """Set up AirTag Tracker from a config entry."""
    libs_path = hass.config.path(".storage", ANISETTE_LIBS_FILENAME)
    account = AsyncAppleAccount.from_json(entry.data[CONF_ACCOUNT], anisette_libs_path=libs_path)
    accessory = FindMyAccessory.from_json(entry.data[CONF_ACCESSORY])
    inside_minutes = entry.options.get(CONF_INSIDE_POLL_INTERVAL, DEFAULT_INSIDE_POLL_INTERVAL)
    outside_minutes = entry.options.get(CONF_OUTSIDE_POLL_INTERVAL, DEFAULT_OUTSIDE_POLL_INTERVAL)
    coordinator = AirTagUpdateCoordinator(
        hass,
        entry,
        account,
        accessory,
        timedelta(minutes=inside_minutes),
        timedelta(minutes=outside_minutes),
    )
    entry.runtime_data = AirTagRuntimeData(account, accessory, coordinator)
    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await account.close()
        raise
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: AirTagConfigEntry) -> bool:
    """Unload the integration and close network resources."""
    if not await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        return False
    await entry.runtime_data.account.close()
    return True


async def _async_reload_entry(hass: HomeAssistant, entry: AirTagConfigEntry) -> None:
    """Reload after options change."""
    await hass.config_entries.async_reload(entry.entry_id)
