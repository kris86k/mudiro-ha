"""Binary sensors for Mudiro."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MudiroCoordinator


class MudiroConnectionSensor(CoordinatorEntity[MudiroCoordinator], BinarySensorEntity):
    """BLE connection state."""

    _attr_name = "Mudiro połączenie BLE"
    _attr_has_entity_name = False
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_icon = "mdi:bluetooth-connect"

    def __init__(self, coordinator: MudiroCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.address.replace(':', '').lower()}_ble_connection"
        self._attr_device_info = coordinator.device_info

    @property
    def is_on(self) -> bool:
        return bool(self.coordinator.data.get("connected"))


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mudiro binary sensors."""
    coordinator: MudiroCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([MudiroConnectionSensor(coordinator)])
