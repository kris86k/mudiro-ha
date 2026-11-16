"""Constants for the Mudiro integration."""

from __future__ import annotations

DOMAIN = "mudiro"
DEFAULT_NAME = "Mudiro"
DEFAULT_ADDRESS = ""  # Enter the heater address in the Home Assistant setup form.
DEFAULT_POLL_INTERVAL = 3
MIN_POLL_INTERVAL = 3
MAX_POLL_INTERVAL = 60
RECONNECT_DELAY = 5
BLE_SCAN_TIMEOUT = 10
BLE_CONNECT_TIMEOUT = 20

SERVICE_UUID = "0000FFF0-0000-1000-8000-00805F9B34FB"
WRITE_CHAR_UUID = "0000FFF1-0000-1000-8000-00805F9B34FB"
NOTIFY_CHAR_UUID = "0000FFF2-0000-1000-8000-00805F9B34FB"

CONF_ADDRESS = "address"
CONF_POLL_INTERVAL = "poll_interval"

PLATFORMS = ["binary_sensor", "sensor", "switch", "button"]
