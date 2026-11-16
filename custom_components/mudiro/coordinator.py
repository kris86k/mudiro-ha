"""BLE connection manager and live state coordinator for Mudiro."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from bleak_retry_connector import (
    BleakClientWithServiceCache,
    establish_connection,
)
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothReachabilityIntent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    BLE_CONNECT_TIMEOUT,
    BLE_SCAN_TIMEOUT,
    DEFAULT_POLL_INTERVAL,
    DOMAIN,
    NOTIFY_CHAR_UUID,
    RECONNECT_DELAY,
    SERVICE_UUID,
    WRITE_CHAR_UUID,
)
from .protocol import (
    START_FRAME,
    STOP_FRAME,
    build_auto_start_stop,
    build_set_parameter,
    build_settings_query,
    build_status_query,
    frame_to_hex,
    parse_notification,
)

_LOGGER = logging.getLogger(__name__)


class MudiroCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Owns one persistent BLE GATT session with the Mudiro heater."""

    def __init__(
        self,
        hass: HomeAssistant,
        config_entry: ConfigEntry,
        address: str,
        poll_interval: int = DEFAULT_POLL_INTERVAL,
    ) -> None:
        self.address = address.upper()
        self.poll_interval = poll_interval
        self.client = None
        self._task: asyncio.Task[None] | None = None
        self._stop_requested = False
        self._disconnected = asyncio.Event()
        self._write_lock = asyncio.Lock()
        self._settings_5c_cache: bytes | None = None
        self._previous_status_frame: bytes | None = None

        initial_data: dict[str, Any] = {
            "connected": False,
            "settings_5c_valid": False,
            "auto_start_stop": None,
            "auto_start_stop_x14": None,
            "last_frame": None,
            "raw_5a": None,
            "raw_5c": None,
            "field_changes": None,
            "state_text": None,
            "mode_text": None,
            "error_text": None,
            "voltage": None,
            "setpoint": None,
            "auto_target_temperature": None,
            "heating_level": None,
            "stove_temperature": None,
            "room_temperature": None,
            "fuel_level": None,
            "fan_rpm": None,
            "pump_frequency": None,
            "height_npm": None,
            "frame_counter": None,
            "state_code": None,
            "error_code": None,
            "mode_code": None,
            "auto_mode": None,
            "x5": None,
            "x9": None,
            "x10": None,
            "x11": None,
            "x12": None,
            "x13": None,
            "x14": None,
            "x16": None,
            "x18": None,
            "x20": None,
        }
        super().__init__(
            hass,
            _LOGGER,
            config_entry=config_entry,
            name=DOMAIN,
            update_method=self._async_noop,
            update_interval=None,
        )
        self.async_set_updated_data(initial_data)

    async def _async_noop(self) -> dict[str, Any]:
        """Data is pushed by BLE notifications; there is no coordinator poll."""
        return self.data or {}

    @property
    def device_info(self) -> dict[str, Any]:
        """Return the Home Assistant device registry information."""
        return {
            "identifiers": {(DOMAIN, self.address)},
            "connections": {("bluetooth", self.address)},
            "name": "Mudiro",
            "manufacturer": "Mudiro",
            "model": "Ogrzewacz BLE",
        }

    async def async_start(self) -> None:
        """Start the connection/reconnection task."""
        if self._task is None:
            self._stop_requested = False
            self._task = self.hass.async_create_task(
                self._connection_loop(), name="Mudiro BLE connection"
            )

    async def async_shutdown(self) -> None:
        """Stop background tasks and release the BLE connection."""
        self._stop_requested = True
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        await self._disconnect_client()
        await super().async_shutdown()

    async def _connection_loop(self) -> None:
        """Reconnect to the heater until the integration unloads."""
        while not self._stop_requested:
            try:
                await self._connect_and_monitor()
            except asyncio.CancelledError:
                raise
            except Exception as err:  # BLE stacks can raise platform-specific exceptions
                reason = self._reachability_diagnostics()
                _LOGGER.warning(
                    "Nie udało się połączyć z Mudiro (%s). %s",
                    err,
                    reason,
                )
            finally:
                await self._disconnect_client()

            if not self._stop_requested:
                await asyncio.sleep(RECONNECT_DELAY)

    async def _get_connectable_device(self):
        """Get a BLEDevice through Home Assistant's shared Bluetooth manager."""
        device = bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if device is not None:
            return device

        # Ask AUTO-mode scanners (including ESPHome proxies) for an active
        # scan window, then ask HA again for a connectable BLEDevice.
        try:
            await bluetooth.async_process_advertisements(
                self.hass,
                lambda service_info: service_info.connectable,
                {"address": self.address, "connectable": True},
                bluetooth.BluetoothScanningMode.ACTIVE,
                BLE_SCAN_TIMEOUT,
            )
        except Exception as err:  # no adapter/scan timeout is handled below
            _LOGGER.debug("Oczekiwanie na reklamę BLE Mudiro: %s", err)

        return bluetooth.async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )

    def _reachability_diagnostics(self) -> str:
        """Return HA's human-readable reachability diagnostics when available."""
        try:
            return bluetooth.async_address_reachability_diagnostics(
                self.hass,
                self.address,
                BluetoothReachabilityIntent.CONNECTION,
            )
        except Exception:  # diagnostics must never interrupt reconnecting
            return "Sprawdź, czy HA widzi urządzenie przez Bluetooth i czy proxy ma aktywne połączenia."

    async def _connect_and_monitor(self) -> None:
        """Connect, subscribe to FFF2 and query the heater every N seconds."""
        ble_device = await self._get_connectable_device()
        if ble_device is None:
            raise RuntimeError(self._reachability_diagnostics())

        self._disconnected.clear()
        client = await establish_connection(
            BleakClientWithServiceCache,
            ble_device,
            name="Mudiro",
            disconnected_callback=self._on_ble_disconnected,
            max_attempts=4,
            use_services_cache=True,
            timeout=BLE_CONNECT_TIMEOUT,
        )
        self.client = client

        # Check that the characteristic UUIDs are available before declaring
        # the device connected. The actual write/notify is by characteristic.
        service = client.services.get_service(SERVICE_UUID)
        if service is None:
            raise RuntimeError(f"Brak usługi BLE {SERVICE_UUID}")
        if service.get_characteristic(WRITE_CHAR_UUID) is None:
            raise RuntimeError(f"Brak charakterystyki zapisu {WRITE_CHAR_UUID}")
        if service.get_characteristic(NOTIFY_CHAR_UUID) is None:
            raise RuntimeError(f"Brak charakterystyki powiadomień {NOTIFY_CHAR_UUID}")

        await client.start_notify(NOTIFY_CHAR_UUID, self._handle_notification)
        self._set_connected(True)
        _LOGGER.info("Połączono z ogrzewaczem Mudiro przez %s", ble_device.address)

        await asyncio.sleep(1)
        await self.async_request_status()

        while not self._stop_requested and client.is_connected:
            try:
                await asyncio.wait_for(
                    self._disconnected.wait(), timeout=self.poll_interval
                )
                break
            except TimeoutError:
                if client.is_connected:
                    await self.async_request_status()

        if not self._stop_requested:
            _LOGGER.warning("Połączenie BLE z Mudiro zostało przerwane")

    def _on_ble_disconnected(self, _client: Any) -> None:
        """Bleak disconnected callback; wake the monitor loop."""
        self._disconnected.set()

    def _set_connected(self, connected: bool) -> None:
        """Publish the connection state and invalidate 5C cache on disconnect."""
        data = dict(self.data or {})
        data["connected"] = connected
        if not connected:
            data["settings_5c_valid"] = False
            self._settings_5c_cache = None
        self.async_set_updated_data(data)

    async def _disconnect_client(self) -> None:
        """Stop notifications and disconnect cleanly."""
        client = self.client
        self.client = None
        self._set_connected(False)
        if client is None:
            return
        try:
            if client.is_connected:
                try:
                    await client.stop_notify(NOTIFY_CHAR_UUID)
                except Exception:
                    pass
                await client.disconnect()
        except Exception as err:
            _LOGGER.debug("Błąd podczas rozłączania Mudiro: %s", err)

    def _handle_notification(self, _sender: Any, data: bytearray) -> None:
        """Parse one notification from FFF2 and publish entity updates."""
        frame = bytes(data)
        parsed = parse_notification(frame, self._previous_status_frame)
        if parsed.get("protocol_warning"):
            _LOGGER.warning("Mudiro: %s; ramka=%s", parsed["protocol_warning"], frame_to_hex(frame))

        status_frame = parsed.pop("status_frame", None)
        settings_cache = parsed.pop("settings_5c_cache", None)
        merged = dict(self.data or {})
        merged.update(parsed)
        if status_frame is not None:
            self._previous_status_frame = status_frame
            merged["mode_code"] = status_frame[34]
        if settings_cache is not None:
            self._settings_5c_cache = settings_cache
        self.async_set_updated_data(merged)

        _LOGGER.debug("Mudiro FFF2 (%d B): %s", len(frame), frame_to_hex(frame))

    async def _write_frame(self, frame: bytes) -> None:
        """Write one protocol frame to FFF1."""
        if self.client is None or not self.client.is_connected:
            raise RuntimeError("Mudiro nie jest połączone przez BLE")
        await self.client.write_gatt_char(WRITE_CHAR_UUID, frame, response=True)
        _LOGGER.debug("Mudiro TX: %s", frame_to_hex(frame))

    async def async_request_status(self) -> None:
        """Request the 5A status frame and then the 5C settings frame."""
        if self.client is None or not self.client.is_connected:
            return
        data = self.data or {}
        mode = data.get("mode_code")
        setpoint = data.get("setpoint")
        if not isinstance(mode, int):
            mode = 1
        if not isinstance(setpoint, int):
            setpoint = 20

        async with self._write_lock:
            await self._write_frame(build_status_query(mode, setpoint))
            await asyncio.sleep(0.2)
            uptime = int(time.monotonic())
            await self._write_frame(build_settings_query(uptime))
        _LOGGER.debug("Mudiro: wysłano zapytania o status 5A i ustawienia 5C")

    async def async_set_parameter(self, mode: int, value: int) -> None:
        """Set MANUAL/AUTO mode and its value, then refresh status."""
        value = max(8, min(35, value))
        if mode not in (1, 2):
            mode = 1
        async with self._write_lock:
            await self._write_frame(build_set_parameter(mode, value))
        data = dict(self.data or {})
        data["mode_code"] = mode
        data["setpoint"] = value
        data["auto_mode"] = mode == 2
        data["settings_5c_valid"] = data.get("settings_5c_valid", False)
        self.async_set_updated_data(data)
        await asyncio.sleep(0.5)
        await self.async_request_status()

    async def async_set_auto_start_stop(self, enabled: bool) -> None:
        """Change AUTO START-STOP using the latest valid 5C settings frame."""
        if (self.data or {}).get("mode_code") != 2:
            # Match the original ESPHome behavior: log and leave the cached
            # switch state unchanged when the heater is in MANUAL mode.
            _LOGGER.warning(
                "Mudiro: AUTO START-STOP działa tylko w trybie regulacji AUTO"
            )
            return
        if not (self.data or {}).get("settings_5c_valid") or self._settings_5c_cache is None:
            await self.async_request_status()
            raise RuntimeError("Brak aktualnej ramki 5C. Odśwież status i spróbuj ponownie.")

        command = build_auto_start_stop(self._settings_5c_cache, enabled)
        async with self._write_lock:
            await self._write_frame(command)
        # The source ESPHome code updated its local settings cache immediately
        # after writing, before the heater acknowledgement arrived.
        updated_cache = bytearray(self._settings_5c_cache)
        updated_cache[14] = 0x01 if enabled else 0x00
        self._settings_5c_cache = bytes(updated_cache)
        data = dict(self.data or {})
        data["auto_start_stop"] = enabled
        data["auto_start_stop_x14"] = 1 if enabled else 0
        self.async_set_updated_data(data)
        await asyncio.sleep(0.7)
        await self.async_request_status()

    async def async_start_heater(self) -> None:
        """Send the exact start frame from the source YAML."""
        async with self._write_lock:
            await self._write_frame(START_FRAME)
        await asyncio.sleep(0.5)
        await self.async_request_status()

    async def async_stop_heater(self) -> None:
        """Send the exact stop frame from the source YAML."""
        async with self._write_lock:
            await self._write_frame(STOP_FRAME)
        await asyncio.sleep(0.5)
        await self.async_request_status()

    async def async_adjust_setpoint(self, direction: int) -> None:
        """Implement the original PLUS/MINUS behavior in MANUAL and AUTO."""
        data = self.data or {}
        mode = data.get("mode_code")
        value = data.get("setpoint")
        if mode not in (1, 2):
            mode = 1
        if not isinstance(value, int) or not 8 <= value <= 35:
            value = 20

        if mode == 1:
            # Same integer mapping as (((value - 8) + 1) / 3) + 1 in C++.
            level = (((value - 8) + 1) // 3) + 1
            level = max(1, min(10, level))
            if direction > 0 and level < 10:
                level += 1
            elif direction < 0 and level > 1:
                level -= 1
            value = 8 + ((level - 1) * 3)
        elif direction > 0:
            value = min(35, value + 1)
        else:
            value = max(8, value - 1)

        await self.async_set_parameter(mode, value)

    async def async_toggle_auto_mode(self, enabled: bool) -> None:
        """Switch between AUTO and MANUAL, retaining the YAML setpoint logic."""
        data = self.data or {}
        value = data.get("setpoint")
        if not isinstance(value, int) or not 8 <= value <= 35:
            value = 20

        if enabled:
            await self.async_set_parameter(2, value)
            return

        level = (((value - 8) + 1) // 3) + 1
        level = max(1, min(10, level))
        manual_value = 8 + ((level - 1) * 3)
        await self.async_set_parameter(1, manual_value)
