"""Sensor entities for Mudiro."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorEntityDescription, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory, PERCENTAGE, UnitOfElectricPotential, UnitOfTemperature
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import MudiroCoordinator


@dataclass(frozen=True, kw_only=True)
class MudiroSensorDescription(SensorEntityDescription):
    """Add the key used in the coordinator data."""

    data_key: str


SENSORS: tuple[MudiroSensorDescription, ...] = (
    MudiroSensorDescription(key="voltage", data_key="voltage", name="Mudiro napięcie", native_unit_of_measurement=UnitOfElectricPotential.VOLT, device_class=SensorDeviceClass.VOLTAGE, state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=1, icon="mdi:car-battery"),
    MudiroSensorDescription(key="setpoint", data_key="setpoint", name="Mudiro wartość nastawy x15", suggested_display_precision=0, icon="mdi:tune-variant"),
    MudiroSensorDescription(key="auto_target_temperature", data_key="auto_target_temperature", name="Mudiro temperatura zadana AUTO", native_unit_of_measurement=UnitOfTemperature.CELSIUS, device_class=SensorDeviceClass.TEMPERATURE, suggested_display_precision=0),
    MudiroSensorDescription(key="heating_level", data_key="heating_level", name="Mudiro poziom grzania", suggested_display_precision=0, icon="mdi:fire"),
    MudiroSensorDescription(key="stove_temperature", data_key="stove_temperature", name="Mudiro temperatura pieca", native_unit_of_measurement=UnitOfTemperature.CELSIUS, device_class=SensorDeviceClass.TEMPERATURE, state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=0),
    MudiroSensorDescription(key="room_temperature", data_key="room_temperature", name="Mudiro temperatura pomieszczenia", native_unit_of_measurement=UnitOfTemperature.CELSIUS, device_class=SensorDeviceClass.TEMPERATURE, state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=0),
    MudiroSensorDescription(key="fuel_level", data_key="fuel_level", name="Mudiro poziom paliwa", native_unit_of_measurement=PERCENTAGE, suggested_display_precision=0, icon="mdi:fuel"),
    MudiroSensorDescription(key="fan_rpm", data_key="fan_rpm", name="Mudiro obroty wentylatora", native_unit_of_measurement="rpm", state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=0, icon="mdi:fan"),
    MudiroSensorDescription(key="auto_start_stop_x14", data_key="auto_start_stop_x14", name="Mudiro AUTO START-STOP x14", suggested_display_precision=0, entity_category=EntityCategory.DIAGNOSTIC),
    MudiroSensorDescription(key="x11", data_key="x11", name="Mudiro pole x11 TEST", suggested_display_precision=0, entity_category=EntityCategory.DIAGNOSTIC),
    MudiroSensorDescription(key="pump_frequency", data_key="pump_frequency", name="Mudiro pompka x11 TEST", native_unit_of_measurement="Hz", suggested_display_precision=1, entity_category=EntityCategory.DIAGNOSTIC),
    MudiroSensorDescription(key="x5", data_key="x5", name="Mudiro pole x5 TEST", suggested_display_precision=0, entity_category=EntityCategory.DIAGNOSTIC),
    MudiroSensorDescription(key="x9", data_key="x9", name="Mudiro pole x9 TEST", suggested_display_precision=0, entity_category=EntityCategory.DIAGNOSTIC),
    MudiroSensorDescription(key="x10", data_key="x10", name="Mudiro pole x10 TEST", suggested_display_precision=0, entity_category=EntityCategory.DIAGNOSTIC),
    MudiroSensorDescription(key="x12", data_key="x12", name="Mudiro pole x12 TEST", suggested_display_precision=0, entity_category=EntityCategory.DIAGNOSTIC),
    MudiroSensorDescription(key="x13", data_key="x13", name="Mudiro pole x13 TEST", suggested_display_precision=0, entity_category=EntityCategory.DIAGNOSTIC),
    MudiroSensorDescription(key="x14", data_key="x14", name="Mudiro pole x14 TEST", suggested_display_precision=0, entity_category=EntityCategory.DIAGNOSTIC),
    MudiroSensorDescription(key="x16", data_key="x16", name="Mudiro pole x16 TEST", suggested_display_precision=0, entity_category=EntityCategory.DIAGNOSTIC),
    MudiroSensorDescription(key="x18", data_key="x18", name="Mudiro pole x18 TEST", suggested_display_precision=0, entity_category=EntityCategory.DIAGNOSTIC),
    MudiroSensorDescription(key="x20", data_key="x20", name="Mudiro pole x20 TEST", suggested_display_precision=0, entity_category=EntityCategory.DIAGNOSTIC),
    MudiroSensorDescription(key="height_npm", data_key="height_npm", name="Mudiro wysokość NPM TEST", native_unit_of_measurement="m", suggested_display_precision=0, icon="mdi:image-filter-hdr"),
    MudiroSensorDescription(key="frame_counter", data_key="frame_counter", name="Mudiro licznik ramki x36 TEST", suggested_display_precision=0, entity_category=EntityCategory.DIAGNOSTIC),
    MudiroSensorDescription(key="state_code", data_key="state_code", name="Mudiro kod stanu x3", suggested_display_precision=0, entity_category=EntityCategory.DIAGNOSTIC),
    MudiroSensorDescription(key="error_code", data_key="error_code", name="Mudiro kod błędu x4", suggested_display_precision=0, entity_category=EntityCategory.DIAGNOSTIC),
    MudiroSensorDescription(key="mode_code", data_key="mode_code", name="Mudiro kod trybu x34", suggested_display_precision=0, entity_category=EntityCategory.DIAGNOSTIC),
    MudiroSensorDescription(key="state_text", data_key="state_text", name="Mudiro stan", icon="mdi:radiator"),
    MudiroSensorDescription(key="mode_text", data_key="mode_text", name="Mudiro tryb regulacji", icon="mdi:tune"),
    MudiroSensorDescription(key="error_text", data_key="error_text", name="Mudiro błąd", icon="mdi:alert-circle-outline"),
    MudiroSensorDescription(key="last_frame", data_key="last_frame", name="Mudiro ostatnia ramka BLE", entity_category=EntityCategory.DIAGNOSTIC),
    MudiroSensorDescription(key="raw_5a", data_key="raw_5a", name="Mudiro surowa ramka 5A", entity_category=EntityCategory.DIAGNOSTIC),
    MudiroSensorDescription(key="raw_5c", data_key="raw_5c", name="Mudiro surowa ramka 5C", entity_category=EntityCategory.DIAGNOSTIC),
    MudiroSensorDescription(key="field_changes", data_key="field_changes", name="Mudiro zmiany pól TEST", entity_category=EntityCategory.DIAGNOSTIC),
)


class MudiroSensor(CoordinatorEntity[MudiroCoordinator], SensorEntity):
    """Represent one value decoded from the heater's notifications."""

    entity_description: MudiroSensorDescription
    _attr_has_entity_name = False

    def __init__(self, coordinator: MudiroCoordinator, description: MudiroSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.address.replace(':', '').lower()}_{description.key}"
        self._attr_device_info = coordinator.device_info

    @property
    def native_value(self) -> Any:
        return self.coordinator.data.get(self.entity_description.data_key)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Mudiro sensors."""
    coordinator: MudiroCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(MudiroSensor(coordinator, description) for description in SENSORS)
