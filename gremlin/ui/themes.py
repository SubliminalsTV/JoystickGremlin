# -*- coding: utf-8; -*-

# SPDX-License-Identifier: GPL-3.0-only

"""Definitions of the available UI colour themes.

A theme is pure data: a display name, the Universal base it builds on (light or
dark), and optional accent / background / foreground overrides. An empty string
override means "use the Universal style's default value". Adding a theme is a
matter of appending an entry to ``THEMES`` -- no code paths need to change,
which keeps the set open-ended rather than a hard-coded handful of modes.
"""

from __future__ import annotations

THEMES: list[dict[str, object]] = [
    {
        "name": "Light",
        "dark": False,
        "accent": "",
        "background": "",
        "foreground": "",
    },
    {
        "name": "Dark",
        "dark": True,
        "accent": "",
        "background": "#0d0d0d",
        "foreground": "",
    },
    {
        "name": "High Contrast",
        "dark": True,
        "accent": "",
        "background": "#000000",
        "foreground": "#ffffff",
    },
]

DEFAULT_THEME = "Dark"


def theme_names() -> list[str]:
    """Returns the theme names in registry order."""
    return [str(theme["name"]) for theme in THEMES]


def theme_by_name(name: str) -> dict[str, object]:
    """Returns the theme with the given name, or the first theme as a fallback.

    Args:
        name: name of the theme to look up

    Returns:
        The matching theme record, or the first registered theme if no match.
    """
    for theme in THEMES:
        if theme["name"] == name:
            return theme
    return THEMES[0]
