# -*- coding: utf-8; -*-

# SPDX-License-Identifier: GPL-3.0-only

"""Command line interface for inspecting and editing Joystick Gremlin profiles.

This package provides an offline, GUI-free CLI that operates directly on the
profile XML tree. It deliberately avoids loading Joystick Gremlin's full
in-memory model, because doing so pulls in the QML/Qt UI layer (action plugins
register QML types on import). Working on the raw ElementTree keeps the tool
fast, dependency-light, and safe to run alongside a running Gremlin instance.
"""

from __future__ import annotations

from gremlin.cli.app import main

__all__ = ["main"]
