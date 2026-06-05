# -*- coding: utf-8; -*-

# SPDX-License-Identifier: GPL-3.0-only

"""Command line entry point for Joystick Gremlin profile tooling.

Run ``py gremlin_cli.py --help`` for the available commands. This is an
offline tool: it reads and edits profile XML files on disk and can launch the
GUI, but it never controls a running Gremlin instance.
"""

from __future__ import annotations

import os
import sys

# Run independent of the current working directory, mirroring joystick_gremlin.py.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gremlin.cli import main

if __name__ == "__main__":
    raise SystemExit(main())
