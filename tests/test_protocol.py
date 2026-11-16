"""Offline tests for the Mudiro protocol port."""

import importlib.util
from pathlib import Path

_PROTOCOL_PATH = Path(__file__).parents[1] / "custom_components" / "mudiro" / "protocol.py"
_SPEC = importlib.util.spec_from_file_location("mudiro_protocol", _PROTOCOL_PATH)
_protocol = importlib.util.module_from_spec(_SPEC)
assert _SPEC and _SPEC.loader
_SPEC.loader.exec_module(_protocol)

START_FRAME = _protocol.START_FRAME
STOP_FRAME = _protocol.STOP_FRAME
append_crc_high_low = _protocol.append_crc_high_low
build_auto_start_stop = _protocol.build_auto_start_stop
build_set_parameter = _protocol.build_set_parameter
build_settings_query = _protocol.build_settings_query
build_status_query = _protocol.build_status_query
crc16_modbus = _protocol.crc16_modbus
parse_notification = _protocol.parse_notification


def test_known_start_stop_crc_bytes() -> None:
    assert START_FRAME[9:] == bytes((0x37, 0xE6))
    assert STOP_FRAME[9:] == bytes((0x51, 0xE6))
    assert crc16_modbus(START_FRAME[:9]) == 0x37E6
    assert crc16_modbus(STOP_FRAME[:9]) == 0x51E6


def test_status_and_parameter_frames_are_11_bytes() -> None:
    assert len(build_status_query(2, 22)) == 11
    assert build_status_query(99, 1)[4:6] == bytes((1, 20))
    assert len(build_set_parameter(2, 99)) == 11
    assert build_set_parameter(2, 99)[4:6] == bytes((2, 35))


def test_settings_query_frame_is_15_bytes() -> None:
    frame = build_settings_query(10)
    assert len(frame) == 15
    assert frame[:4] == bytes((0x29, 0x0D, 0x5C, 0x00))
    assert int.from_bytes(frame[-2:], "big") == crc16_modbus(frame[:-2])


def test_auto_start_stop_preserves_settings_except_x14() -> None:
    settings = bytes(range(17))
    frame = build_auto_start_stop(settings, True)
    assert len(frame) == 20
    assert frame[0:2] == bytes((0x26, 0x12))
    for index in range(2, 17):
        assert frame[index] == (1 if index == 14 else settings[index])
    assert frame[14] == 1
    assert frame[17] == 1
    assert int.from_bytes(frame[-2:], "big") == crc16_modbus(frame[:18])


def test_5a_decoder_preserves_original_offsets() -> None:
    frame = bytearray(39)
    frame[0:3] = bytes((0x5A, 0x25, 0x01))
    frame[3] = 0x08
    frame[4] = 0x02
    frame[6] = 124
    frame[7:9] = bytes((0x01, 0xF4))
    frame[15] = 20
    frame[17] = 75
    frame[19] = 180
    frame[33] = 42
    frame[34] = 0x02
    frame[35] = 22
    frame[36] = 9
    decoded = parse_notification(bytes(frame))
    assert decoded["voltage"] == 12.4
    assert decoded["fan_rpm"] == 500
    assert decoded["setpoint"] == 20
    assert decoded["fuel_level"] == 75
    assert decoded["stove_temperature"] == 180
    assert decoded["room_temperature"] == 22
    assert decoded["auto_target_temperature"] == 20
    assert decoded["state_text"] == "Wygaszanie / chłodzenie"
    assert decoded["error_text"] == "Błąd 0x02"


def test_5c_crc_is_required() -> None:
    body = bytes((0x5C, 0x16, 0x01, 0x00) + tuple(range(4, 22)))
    frame = append_crc_high_low(body)
    assert len(frame) == 24
    decoded = parse_notification(frame)
    assert decoded["settings_5c_valid"] is True
    assert decoded["auto_start_stop_x14"] == frame[14]

    damaged = bytearray(frame)
    damaged[10] ^= 1
    bad_decoded = parse_notification(bytes(damaged))
    assert "settings_5c_valid" not in bad_decoded
    assert "protocol_warning" in bad_decoded


def test_5c_twelve_byte_ack_uses_20_byte_frame_and_crc() -> None:
    body = bytes((0x5C, 0x12, 0x01, 0x00) + tuple(range(4, 18)))
    frame = append_crc_high_low(body)
    assert len(frame) == 20
    decoded = parse_notification(frame)
    assert decoded["settings_5c_valid"] is True
    assert decoded["raw_5c"] == " ".join(f"{b:02X}" for b in frame)


def test_manual_mode_maps_power_step_and_signed_temperature() -> None:
    frame = bytearray(39)
    frame[0:3] = bytes((0x5A, 0x25, 0x01))
    frame[15] = 17
    frame[34] = 0x01
    frame[35] = 0xF6
    decoded = parse_notification(bytes(frame))
    assert decoded["heating_level"] == 4
    assert decoded["auto_target_temperature"] is None
    assert decoded["auto_mode"] is False
    assert decoded["room_temperature"] == -10


def test_invalid_room_temperature_does_not_overwrite_existing_value() -> None:
    frame = bytearray(39)
    frame[0:3] = bytes((0x5A, 0x25, 0x01))
    frame[34] = 0x02
    frame[35] = 0x9C
    decoded = parse_notification(bytes(frame))
    assert "room_temperature" not in decoded
