"""Home Assistant integration for the Mudiro BLE heater."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_ADDRESS, CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL, DOMAIN, PLATFORMS
from .coordinator import MudiroCoordinator


def _get_poll_interval(entry: ConfigEntry) -> int:
    return int(entry.options.get(CONF_POLL_INTERVAL, entry.data.get(CONF_POLL_INTERVAL, DEFAULT_POLL_INTERVAL)))


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Mudiro from a config entry."""
    address = str(entry.data[CONF_ADDRESS]).upper()
    coordinator = MudiroCoordinator(
        hass, entry, address, _get_poll_interval(entry)
    )

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload_entry))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_start()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload platforms and stop the BLE background task."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator: MudiroCoordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.async_shutdown()
    return unload_ok


async def _async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload the integration after its options are changed."""
    await hass.config_entries.async_reload(entry.entry_id)
