"""Mudiro BLE protocol implementation.

The offsets, frame lengths, command bytes and CRC byte order are ported from
mudiro_full_fragment.yaml supplied with the project. No undocumented 5A CRC
is added because the source YAML does not validate one.
"""

from __future__ import annotations

from typing import Any


def crc16_modbus(data: bytes | bytearray) -> int:
    """Return Modbus CRC16 (initial value 0xFFFF, polynomial 0xA001)."""
    crc = 0xFFFF
    for value in data:
        crc ^= value
        for _ in range(8):
            if crc & 0x0001:
                crc = (crc >> 1) ^ 0xA001
            else:
                crc >>= 1
    return crc & 0xFFFF


def append_crc_high_low(payload: bytes | bytearray) -> bytes:
    """Append CRC in the high-byte, low-byte order used by the YAML."""
    crc = crc16_modbus(payload)
    return bytes(payload) + bytes(((crc >> 8) & 0xFF, crc & 0xFF))


def build_status_query(mode: int, value: int) -> bytes:
    """Build the A5 query named 5A/status query in the source comments."""
    if mode not in (1, 2):
        mode = 1
    if not 8 <= value <= 35:
        value = 20
    payload = bytes((0xA5, 0x09, 0x01, 0x00, mode, value, 0x00, 0x00, 0x01))
    return append_crc_high_low(payload)


def build_settings_query(uptime_seconds: int) -> bytes:
    """Build the 5C settings query with a changing 32-bit marker."""
    marker = (0x6A6F7C19 + uptime_seconds) & 0xFFFFFFFF
    payload = bytes(
        (
            0x29,
            0x0D,
            0x5C,
            0x00,
            (marker >> 24) & 0xFF,
            (marker >> 16) & 0xFF,
            (marker >> 8) & 0xFF,
            marker & 0xFF,
            0x05,
            0xF5,
            0xE1,
            0x00,
            0x01,
        )
    )
    return append_crc_high_low(payload)


def build_set_parameter(mode: int, value: int) -> bytes:
    """Build a MANUAL/AUTO setpoint command, clamped like the ESPHome code."""
    if mode not in (1, 2):
        mode = 1
    value = max(8, min(35, value))
    payload = bytes((0xA5, 0x09, 0x01, 0x51, mode, value, 0x00, 0x00, 0x01))
    return append_crc_high_low(payload)


# These exact start/stop telegrams are copied from the supplied YAML. Their
# fixed CRC bytes have been checked against crc16_modbus().
START_FRAME = bytes((0xA5, 0x09, 0x01, 0x5A, 0x01, 0x20, 0x00, 0x00, 0x01, 0x37, 0xE6))
STOP_FRAME = bytes((0xA5, 0x09, 0x01, 0x5C, 0x01, 0x20, 0x00, 0x00, 0x01, 0x51, 0xE6))


def build_auto_start_stop(settings_frame: bytes, enabled: bool) -> bytes:
    """Build command 0x26 from a validated 5C response.

    Exactly bytes 2..16 are copied from the cached 5C response; byte 14 is
    replaced by the requested flag, matching the source YAML.
    """
    if len(settings_frame) < 17:
        raise ValueError("Brak 17 bajtów poprawnej ramki 5C")

    frame = bytearray(
        (
            0x26,
            0x12,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x00,
            0x01,
            0x00,
            0x00,
        )
    )
    for index in range(2, 17):
        frame[index] = settings_frame[index]
    frame[14] = 0x01 if enabled else 0x00

    crc = crc16_modbus(frame[:18])
    frame[18] = (crc >> 8) & 0xFF
    frame[19] = crc & 0xFF
    return bytes(frame)


def frame_to_hex(frame: bytes) -> str:
    """Format a frame as uppercase space-separated hex bytes."""
    return " ".join(f"{byte:02X}" for byte in frame)


def _signed_int8(value: int) -> int:
    return value if value < 0x80 else value - 0x100


def parse_notification(
    frame: bytes, previous_status_frame: bytes | None = None
) -> dict[str, Any]:
    """Decode one FFF2 notification into Home Assistant state values.

    `last_frame` is always returned. 5C frames are accepted only after CRC
    validation. 5A frames use the same header/length checks as the source YAML.
    """
    result: dict[str, Any] = {"last_frame": frame_to_hex(frame)}

    # 5C settings response or acknowledgement.
    if len(frame) >= 20 and frame[0] == 0x5C and frame[2] == 0x01:
        if len(frame) == 24 and frame[1] == 0x16:
            crc_length = 22
        elif len(frame) == 20 and frame[1] == 0x12:
            crc_length = 18
        else:
            return result

        computed_crc = crc16_modbus(frame[:crc_length])
        received_crc = (frame[crc_length] << 8) | frame[crc_length + 1]
        if computed_crc != received_crc:
            result["protocol_warning"] = (
                f"Niepoprawne CRC ramki 5C: obliczone={computed_crc:04X}, "
                f"odebrane={received_crc:04X}"
            )
            return result

        enabled = frame[14] == 0x01
        result.update(
            {
                "raw_5c": frame_to_hex(frame),
                "settings_5c_cache": frame[:17],
                "settings_5c_valid": True,
                "auto_start_stop": enabled,
                "auto_start_stop_x14": frame[14],
            }
        )
        return result

    # Main 5A status response. The source YAML does not validate a CRC here.
    if len(frame) != 39 or frame[0] != 0x5A or frame[1] != 0x25 or frame[2] != 0x01:
        return result

    state_code = frame[3]
    error_code = frame[4]
    voltage = frame[6] / 10.0
    rpm = (frame[7] << 8) | frame[8]
    setpoint = frame[15]
    fuel = frame[17]
    stove_temperature = frame[19]
    height_npm = frame[33]
    mode = frame[34]
    room_temperature = _signed_int8(frame[35])
    frame_counter = frame[36]

    if state_code == 0x00:
        state_text = "Wyłączona"
    elif state_code == 0x08:
        state_text = "Wygaszanie / chłodzenie"
    else:
        state_text = f"Aktywny stan 0x{state_code:02X} - do rozpoznania"

    mode_updates: dict[str, Any] = {}
    if mode == 0x01:
        mode_text = "Ręczna regulacja mocy 1–10"
        if 8 <= setpoint <= 35 and (setpoint - 8) % 3 == 0:
            mode_updates["heating_level"] = ((setpoint - 8) // 3) + 1
        else:
            mode_updates["heating_level"] = None
        mode_updates["auto_target_temperature"] = None
        mode_updates["auto_mode"] = False
    elif mode == 0x02:
        mode_text = "Automatyczna kontrola temperatury"
        mode_updates["heating_level"] = None
        mode_updates["auto_target_temperature"] = setpoint
        mode_updates["auto_mode"] = True
    else:
        # The original YAML changed only the mode text for unknown values;
        # it left the last MANUAL/AUTO-derived values untouched.
        mode_text = f"Nieznany tryb 0x{mode:02X}"
        mode_updates["auto_mode"] = None

    error_text = "Brak błędu" if error_code == 0 else f"Błąd 0x{error_code:02X}"

    result.update(
        {
            "raw_5a": frame_to_hex(frame),
            "state_code": state_code,
            "error_code": error_code,
            "voltage": voltage,
            "setpoint": setpoint,
            "stove_temperature": stove_temperature,
            "fuel_level": fuel,
            "fan_rpm": rpm,
            "x5": frame[5],
            "x9": frame[9],
            "x10": frame[10],
            "x11": frame[11],
            "pump_frequency": frame[11] / 10.0,
            "x12": frame[12],
            "x13": frame[13],
            "x14": frame[14],
            "x16": frame[16],
            "x18": frame[18],
            "x20": frame[20],
            "height_npm": height_npm,
            "frame_counter": frame_counter,
            "state_text": state_text,
            "mode_text": mode_text,
            "error_text": error_text,
        }
    )
    result.update(mode_updates)
    if -50 <= room_temperature <= 100:
        result["room_temperature"] = room_temperature

    if previous_status_frame is not None and len(previous_status_frame) == 39:
        changes: list[str] = []
        for index in range(3, 36):
            old = previous_status_frame[index]
            new = frame[index]
            if old != new:
                changes.append(f"x[{index}]:{old:02X}>{new:02X}")
        if changes:
            result["field_changes"] = " ".join(changes)

    result["status_frame"] = frame
    return result
