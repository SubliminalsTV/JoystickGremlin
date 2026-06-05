# -*- coding: utf-8; -*-

# SPDX-License-Identifier: GPL-3.0-only

"""Scan-code -> human key-name resolution for keyboard bindings.

Joystick Gremlin stores keyboard bindings as a (scan-code, is-extended) pair
and resolves the display name at runtime via the Windows keyboard layout API
(see ``gremlin/keyboard.py``, which calls into ``user32``). That is Windows-only
and not appropriate for an offline, cross-platform CLI, so we embed a static
table instead.

The special keys (function keys, navigation block, numpad, modifiers) are copied
verbatim from Gremlin's own ``g_name_to_key`` table so the names match exactly.
The alphanumeric and punctuation rows use the standard US scan-code set 1
mapping that Gremlin would otherwise resolve dynamically; on a non-US layout
those names may differ, which is noted where the resolver is used.
"""

from __future__ import annotations

from typing import Dict, Tuple

# Standard US scan-code set 1 alphanumerics and punctuation (all non-extended).
_ALPHANUMERIC: Dict[Tuple[int, bool], str] = {
    (0x02, False): "1", (0x03, False): "2", (0x04, False): "3",
    (0x05, False): "4", (0x06, False): "5", (0x07, False): "6",
    (0x08, False): "7", (0x09, False): "8", (0x0A, False): "9",
    (0x0B, False): "0", (0x0C, False): "-", (0x0D, False): "=",
    (0x10, False): "Q", (0x11, False): "W", (0x12, False): "E",
    (0x13, False): "R", (0x14, False): "T", (0x15, False): "Y",
    (0x16, False): "U", (0x17, False): "I", (0x18, False): "O",
    (0x19, False): "P", (0x1A, False): "[", (0x1B, False): "]",
    (0x1E, False): "A", (0x1F, False): "S", (0x20, False): "D",
    (0x21, False): "F", (0x22, False): "G", (0x23, False): "H",
    (0x24, False): "J", (0x25, False): "K", (0x26, False): "L",
    (0x27, False): ";", (0x28, False): "'", (0x29, False): "`",
    (0x2B, False): "\\", (0x2C, False): "Z", (0x2D, False): "X",
    (0x2E, False): "C", (0x2F, False): "V", (0x30, False): "B",
    (0x31, False): "N", (0x32, False): "M", (0x33, False): ",",
    (0x34, False): ".", (0x35, False): "/",
}

# Special keys, names copied from gremlin.keyboard.g_name_to_key.
_SPECIAL: Dict[Tuple[int, bool], str] = {
    (0x3B, False): "F1", (0x3C, False): "F2", (0x3D, False): "F3",
    (0x3E, False): "F4", (0x3F, False): "F5", (0x40, False): "F6",
    (0x41, False): "F7", (0x42, False): "F8", (0x43, False): "F9",
    (0x44, False): "F10", (0x57, False): "F11", (0x58, False): "F12",
    (0x37, True): "Print Screen", (0x46, False): "Scroll Lock",
    (0x45, False): "Pause",
    (0x52, True): "Insert", (0x47, True): "Home", (0x49, True): "PageUp",
    (0x53, True): "Delete", (0x4F, True): "End", (0x51, True): "PageDown",
    (0x48, True): "Up", (0x4B, True): "Left", (0x50, True): "Down",
    (0x4D, True): "Right",
    (0x45, True): "NumLock", (0x35, True): "Numpad /",
    (0x37, False): "Numpad *", (0x4A, False): "Numpad -",
    (0x4E, False): "Numpad +", (0x1C, True): "Numpad Enter",
    (0x53, False): "Numpad Delete",
    (0x52, False): "Numpad 0", (0x4F, False): "Numpad 1",
    (0x50, False): "Numpad 2", (0x51, False): "Numpad 3",
    (0x4B, False): "Numpad 4", (0x4C, False): "Numpad 5",
    (0x4D, False): "Numpad 6", (0x47, False): "Numpad 7",
    (0x48, False): "Numpad 8", (0x49, False): "Numpad 9",
    (0x0E, False): "Backspace", (0x39, False): "Space",
    (0x0F, False): "Tab", (0x3A, False): "CapsLock",
    (0x2A, False): "Left Shift", (0x1D, False): "Left Control",
    (0x5B, True): "Left Win", (0x38, False): "Left Alt",
    (0x36, False): "Right Shift", (0x36, True): "Right Shift",
    (0x1D, True): "Right Control", (0x5C, True): "Right Win",
    (0x38, True): "Right Alt", (0x5D, True): "Apps",
    (0x1C, False): "Enter", (0x01, False): "Esc",
    (0xFC, False): "Noname", (0xF9, False): "EraseEof", (0xFB, False): "Zoom",
    (0x7C, False): "F13", (0x7D, False): "F14", (0x7E, False): "F15",
    (0x7F, False): "F16", (0x80, False): "F17", (0x81, False): "F18",
    (0x82, False): "F19", (0x83, False): "F20", (0x84, False): "F21",
    (0x85, False): "F22", (0x86, False): "F23", (0x87, False): "F24",
}

# Special entries win on any overlap (none expected, given the extended flag).
SCAN_CODE_TO_NAME: Dict[Tuple[int, bool], str] = {**_ALPHANUMERIC, **_SPECIAL}


def key_name(scan_code: int, is_extended: bool) -> str:
    """Returns the display name for a scan code, or a raw fallback if unknown."""
    name = SCAN_CODE_TO_NAME.get((scan_code, is_extended))
    if name is not None:
        return name
    suffix = " (ext)" if is_extended else ""
    return f"scan:{scan_code}{suffix}"
