"""Switch entities for Mudiro."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MudiroCoordinator


class MudiroAutoModeSwitch(CoordinatorEntity[MudiroCoordinator], SwitchEntity):
    """Select manual or automatic temperature control."""

    _attr_name = "Mudiro tryb AUTO"
    _attr_has_entity_name = False
    _attr_icon = "mdi:thermostat-auto"

    def __init__(self, coordinator: MudiroCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address.replace(':', '').lower()}_auto_mode"
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.get("auto_mode") is True

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.data.get("connected", False) and self.coordinator.data.get("auto_mode") is not None

    async def async_turn_on(self, **kwargs) -> None:
        try:
            await self.coordinator.async_toggle_auto_mode(True)
        except Exception as err:
            raise HomeAssistantError(f"Nie udało się włączyć trybu AUTO Mudiro: {err}") from err

    async def async_turn_off(self, **kwargs) -> None:
        try:
            await self.coordinator.async_toggle_auto_mode(False)
        except Exception as err:
            raise HomeAssistantError(f"Nie udało się wyłączyć trybu AUTO Mudiro: {err}") from err


class MudiroAutoStartStopSwitch(CoordinatorEntity[MudiroCoordinator], SwitchEntity):
    """Enable/disable AUTO START-STOP using the latest 5C payload."""

    _attr_name = "Mudiro AUTO START-STOP"
    _attr_has_entity_name = False
    _attr_icon = "mdi:engine-outline"

    def __init__(self, coordinator: MudiroCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address.replace(':', '').lower()}_auto_start_stop"
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool:
        return self.coordinator.data.get("auto_start_stop") is True

    @property
    def available(self) -> bool:
        data = self.coordinator.data
        return super().available and bool(data.get("connected")) and bool(data.get("settings_5c_valid"))

    async def async_turn_on(self, **kwargs) -> None:
        try:
            await self.coordinator.async_set_auto_start_stop(True)
        except Exception as err:
            raise HomeAssistantError(f"Nie udało się włączyć AUTO START-STOP: {err}") from err

    async def async_turn_off(self, **kwargs) -> None:
        try:
            await self.coordinator.async_set_auto_start_stop(False)
        except Exception as err:
            raise HomeAssistantError(f"Nie udało się wyłączyć AUTO START-STOP: {err}") from err


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mudiro switches."""
    coordinator: MudiroCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [MudiroAutoModeSwitch(coordinator), MudiroAutoStartStopSwitch(coordinator)]
    )
