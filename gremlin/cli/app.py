# -*- coding: utf-8; -*-

# SPDX-License-Identifier: GPL-3.0-only

"""Argument parsing and command dispatch for the Joystick Gremlin CLI."""

from __future__ import annotations

import argparse
from typing import List, Optional

from gremlin.cli import commands


def _add_profile_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("profile", help="path to the profile XML file")


def _add_json_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json", action="store_true", help="emit machine-readable JSON"
    )


def _add_write_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="show what would change without writing",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="do not write a .bak-<timestamp> copy before overwriting",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gremlin-cli",
        description=(
            "Inspect and edit Joystick Gremlin profile XML files from the "
            "terminal. Operates offline on the profile on disk; it does not "
            "control a running Gremlin instance."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # -- read-only ----------------------------------------------------------
    p_info = sub.add_parser("info", help="summarize a profile")
    _add_profile_arg(p_info)
    _add_json_arg(p_info)
    p_info.set_defaults(func=commands.cmd_info)

    p_modes = sub.add_parser("modes", help="list modes and their hierarchy")
    _add_profile_arg(p_modes)
    _add_json_arg(p_modes)
    p_modes.set_defaults(func=commands.cmd_modes)

    p_bind = sub.add_parser(
        "bindings", help="list physical input -> action bindings"
    )
    _add_profile_arg(p_bind)
    p_bind.add_argument("--mode", help="only bindings in this mode")
    p_bind.add_argument(
        "--device", help="only bindings on devices matching this GUID/name"
    )
    _add_json_arg(p_bind)
    p_bind.set_defaults(func=commands.cmd_bindings)

    p_val = sub.add_parser("validate", help="run structural checks")
    _add_profile_arg(p_val)
    _add_json_arg(p_val)
    p_val.set_defaults(func=commands.cmd_validate)

    p_diff = sub.add_parser("diff", help="structurally compare two profiles")
    p_diff.add_argument("base", help="baseline profile XML")
    p_diff.add_argument("other", help="profile XML to compare against the base")
    _add_json_arg(p_diff)
    p_diff.set_defaults(func=commands.cmd_diff)

    p_keys = sub.add_parser(
        "keyboard-keys", help="list keyboard keys the profile binds"
    )
    _add_profile_arg(p_keys)
    _add_json_arg(p_keys)
    p_keys.set_defaults(func=commands.cmd_keyboard_keys)

    p_vjoy = sub.add_parser(
        "vjoy-usage", help="show which vJoy slots are used (and free)"
    )
    _add_profile_arg(p_vjoy)
    _add_json_arg(p_vjoy)
    p_vjoy.set_defaults(func=commands.cmd_vjoy_usage)

    p_tree = sub.add_parser(
        "tree", help="show an input's full action tree (all action types)"
    )
    _add_profile_arg(p_tree)
    p_tree.add_argument("--input-id", help="restrict to a physical input id")
    p_tree.add_argument("--device", help="restrict to a device (GUID/name)")
    p_tree.add_argument("--mode", help="restrict to a single mode")
    p_tree.add_argument(
        "--input-type", choices=["axis", "button", "hat"],
        help="disambiguate when an id exists for multiple input types",
    )

    p_tree.set_defaults(func=commands.cmd_tree)

    p_tempos = sub.add_parser(
        "tempos", help="list tempo (short-press vs hold) actions"
    )
    _add_profile_arg(p_tempos)
    p_tempos.set_defaults(func=commands.cmd_tempos)

    p_macros = sub.add_parser("macros", help="list macros and their steps")
    _add_profile_arg(p_macros)
    p_macros.set_defaults(func=commands.cmd_macros)

    p_mouse = sub.add_parser("mouse", help="list Map to Mouse actions")
    _add_profile_arg(p_mouse)
    _add_json_arg(p_mouse)
    p_mouse.set_defaults(func=commands.cmd_mouse)

    p_sounds = sub.add_parser(
        "sounds", help="list Play Sound / Text to Speech (flags missing files)"
    )
    _add_profile_arg(p_sounds)
    _add_json_arg(p_sounds)
    p_sounds.set_defaults(func=commands.cmd_sounds)

    p_axiscfg = sub.add_parser(
        "axis-config", help="per-axis curve / deadzone / split / merge summary"
    )
    _add_profile_arg(p_axiscfg)
    p_axiscfg.set_defaults(func=commands.cmd_axis_config)

    p_desc = sub.add_parser(
        "descriptions", help="dump the chart-bridge description text per input"
    )
    _add_profile_arg(p_desc)
    _add_json_arg(p_desc)
    p_desc.set_defaults(func=commands.cmd_descriptions)

    # -- mutating -----------------------------------------------------------
    p_startup = sub.add_parser(
        "set-startup-mode", help="pin the mode the profile starts in"
    )
    _add_profile_arg(p_startup)
    p_startup.add_argument("mode", help="mode to set as startup")
    _add_write_args(p_startup)
    p_startup.set_defaults(func=commands.cmd_set_startup_mode)

    p_rename = sub.add_parser(
        "rename-mode", help="rename a mode everywhere it is referenced"
    )
    _add_profile_arg(p_rename)
    p_rename.add_argument("old", help="existing mode name")
    p_rename.add_argument("new", help="new mode name")
    _add_write_args(p_rename)
    p_rename.set_defaults(func=commands.cmd_rename_mode)

    p_order = sub.add_parser(
        "fix-library-order",
        help="reorder <library> so definitions precede references",
    )
    _add_profile_arg(p_order)
    _add_write_args(p_order)
    p_order.set_defaults(func=commands.cmd_fix_library_order)

    p_orphan = sub.add_parser(
        "remove-orphans", help="prune library actions no input reaches"
    )
    _add_profile_arg(p_orphan)
    _add_write_args(p_orphan)
    p_orphan.set_defaults(func=commands.cmd_remove_orphans)

    p_setvjoy = sub.add_parser(
        "set-vjoy",
        help="retarget a physical button's vJoy slot (JG profile only)",
    )
    _add_profile_arg(p_setvjoy)
    p_setvjoy.add_argument(
        "--input-id", required=True, help="physical input id to retarget"
    )
    p_setvjoy.add_argument(
        "--from-button", required=True,
        help="the vJoy button id the input currently maps to",
    )
    p_setvjoy.add_argument(
        "--to-button", required=True, help="the new vJoy button id"
    )
    p_setvjoy.add_argument("--device", help="restrict to a device (GUID/name)")
    p_setvjoy.add_argument("--mode", help="restrict to a single mode")
    p_setvjoy.add_argument(
        "--input-type", choices=["axis", "button", "hat"],
        help="disambiguate when an id exists for multiple input types",
    )

    _add_write_args(p_setvjoy)
    p_setvjoy.set_defaults(func=commands.cmd_set_vjoy)

    p_flip = sub.add_parser(
        "flip-axis", help="invert an axis (mirror its response curve)"
    )
    _add_profile_arg(p_flip)
    p_flip.add_argument(
        "--input-id", required=True, help="physical axis input id to invert"
    )
    p_flip.add_argument("--device", help="restrict to a device (GUID/name)")
    p_flip.add_argument("--mode", help="restrict to a single mode")
    _add_write_args(p_flip)
    p_flip.set_defaults(func=commands.cmd_flip_axis)

    p_delmode = sub.add_parser(
        "delete-mode", help="delete a mode (reparents children, drops bindings)"
    )
    _add_profile_arg(p_delmode)
    p_delmode.add_argument("mode", help="mode to delete")
    _add_write_args(p_delmode)
    p_delmode.set_defaults(func=commands.cmd_delete_mode)

    p_setlabel = sub.add_parser(
        "set-label", help="set an action's display label by id"
    )
    _add_profile_arg(p_setlabel)
    p_setlabel.add_argument("--action-id", required=True, help="library action id")
    p_setlabel.add_argument("--label", required=True, help="new label text")
    _add_write_args(p_setlabel)
    p_setlabel.set_defaults(func=commands.cmd_set_label)

    p_settempo = sub.add_parser(
        "set-tempo-threshold", help="retune a tempo's hold timing"
    )
    _add_profile_arg(p_settempo)
    p_settempo.add_argument(
        "--input-id", required=True, help="physical input id carrying the tempo"
    )
    p_settempo.add_argument("seconds", help="new threshold in seconds")
    p_settempo.add_argument("--device", help="restrict to a device (GUID/name)")
    p_settempo.add_argument("--mode", help="restrict to a single mode")
    p_settempo.add_argument(
        "--input-type", choices=["axis", "button", "hat"],
        help="disambiguate when an id exists for multiple input types",
    )

    _add_write_args(p_settempo)
    p_settempo.set_defaults(func=commands.cmd_set_tempo_threshold)

    p_setdesc = sub.add_parser(
        "set-description",
        help="set the chart-bridge description text for an input",
    )
    _add_profile_arg(p_setdesc)
    p_setdesc.add_argument(
        "--input-id", required=True, help="physical input id to describe"
    )
    p_setdesc.add_argument("text", help="description text")
    p_setdesc.add_argument("--device", help="restrict to a device (GUID/name)")
    p_setdesc.add_argument(
        "--input-type", choices=["axis", "button", "hat"],
        help="disambiguate when an id exists for multiple input types",
    )

    p_setdesc.add_argument("--mode", help="restrict to a single mode")
    _add_write_args(p_setdesc)
    p_setdesc.set_defaults(func=commands.cmd_set_description)

    # -- launcher -----------------------------------------------------------
    p_run = sub.add_parser(
        "run", help="launch the Gremlin GUI with the given profile"
    )
    p_run.add_argument(
        "profile", nargs="?", help="profile to load on startup (optional)"
    )
    p_run.add_argument(
        "--enable", action="store_true", help="activate Gremlin on launch"
    )
    p_run.add_argument(
        "--minimized", action="store_true", help="start minimized"
    )
    p_run.add_argument(
        "--dry-run",
        action="store_true",
        help="print the launch command without starting the GUI",
    )
    p_run.set_defaults(func=commands.cmd_run)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)
