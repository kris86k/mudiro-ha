"""Button entities for Mudiro."""

from __future__ import annotations

from dataclasses import dataclass
from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.exceptions import HomeAssistantError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MudiroCoordinator


@dataclass(frozen=True, kw_only=True)
class MudiroButtonDescription(ButtonEntityDescription):
    """Button metadata plus coordinator action name."""

    action: str


BUTTONS = (
    MudiroButtonDescription(key="start", name="Mudiro WŁĄCZ", icon="mdi:power", action="start"),
    MudiroButtonDescription(key="stop", name="Mudiro WYŁĄCZ", icon="mdi:power-off", action="stop"),
    MudiroButtonDescription(key="plus", name="Mudiro PLUS", icon="mdi:plus-circle", action="plus"),
    MudiroButtonDescription(key="minus", name="Mudiro MINUS", icon="mdi:minus-circle", action="minus"),
    MudiroButtonDescription(key="refresh", name="Mudiro odśwież status", icon="mdi:refresh", action="refresh"),
)


class MudiroButton(CoordinatorEntity[MudiroCoordinator], ButtonEntity):
    """A command button for the Mudiro heater."""

    entity_description: MudiroButtonDescription
    _attr_has_entity_name = False

    def __init__(self, coordinator: MudiroCoordinator, description: MudiroButtonDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address.replace(':', '').lower()}_{description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    def available(self) -> bool:
        return super().available and bool(self.coordinator.data.get("connected"))

    async def async_press(self) -> None:
        try:
            action = self.entity_description.action
            if action == "start":
                await self.coordinator.async_start_heater()
            elif action == "stop":
                await self.coordinator.async_stop_heater()
            elif action == "plus":
                await self.coordinator.async_adjust_setpoint(1)
            elif action == "minus":
                await self.coordinator.async_adjust_setpoint(-1)
            elif action == "refresh":
                await self.coordinator.async_request_status()
        except Exception as err:
            raise HomeAssistantError(f"Polecenie Mudiro nie zostało wysłane: {err}") from err


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mudiro buttons."""
    coordinator: MudiroCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(MudiroButton(coordinator, description) for description in BUTTONS)
