# -*- coding: utf-8; -*-

# SPDX-License-Identifier: GPL-3.0-only

"""Implementations of the individual CLI commands.

Each handler takes the parsed argparse namespace and returns a process exit
code. Read-only commands support ``--json``; mutating commands back up the file
before writing, support ``--dry-run``, and warn when Gremlin appears to be
running (which risks the GUI overwriting the edit on its next save).
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Dict, List, Optional
from xml.etree import ElementTree

from gremlin.cli import analysis, keymap, render
from gremlin.cli.model import Binding, ProfileDocument, ProfileError

# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _load(path_str: str) -> ProfileDocument:
    path = Path(path_str)
    if not path.is_file():
        raise SystemExit(f"error: no such file: {path}")
    try:
        return ProfileDocument.load(path)
    except ProfileError as exc:
        raise SystemExit(f"error: {exc}")


def _device_names(doc: ProfileDocument) -> Dict[str, str]:
    """Maps device GUID to its stored name, where the profile records one."""
    names: Dict[str, str] = {}
    devices = doc.root.find("devices")
    if devices is None:
        return names
    for device in devices.findall("device"):
        guid = device.find("device-id")
        name = device.find("device-name")
        if guid is not None and guid.text:
            names[guid.text] = name.text if name is not None and name.text else ""
    return names


def _device_label(guid: str, names: Dict[str, str]) -> str:
    name = names.get(guid)
    if name:
        return name
    return f"{guid[:8]}..." if len(guid) > 8 else guid


def _emit_json(payload: object) -> int:
    print(json.dumps(payload, indent=2))
    return 0


def _gremlin_running() -> Optional[bool]:
    """Best-effort check for a running Joystick Gremlin process.

    Returns True/False on platforms we can inspect, or None when unknown.
    """
    if sys.platform != "win32":
        return None
    try:
        out = subprocess.run(
            ["tasklist", "/fi", "imagename eq joystick_gremlin.exe"],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return "joystick_gremlin.exe" in out.stdout.lower()


def _warn_if_running() -> None:
    if _gremlin_running():
        print(
            "warning: Joystick Gremlin appears to be running. It may overwrite "
            "this edit when it next saves. Close it (or reload the profile "
            "without saving) for the change to stick.",
            file=sys.stderr,
        )


def _confirm_written(doc: ProfileDocument, backup: Optional[Path]) -> int:
    print(f"wrote {doc.path}")
    if backup is not None:
        print(f"backup: {backup}")
    return 0


# ---------------------------------------------------------------------------
# Read-only commands
# ---------------------------------------------------------------------------

def cmd_info(args: argparse.Namespace) -> int:
    doc = _load(args.profile)
    bindings = doc.bindings()
    actions = doc.library_actions()
    type_counts = collections.Counter(
        node.get("type") for node in actions.values()
    )
    devices = sorted({b.device_id for b in bindings if b.device_id})
    names = _device_names(doc)

    if args.json:
        return _emit_json(
            {
                "path": str(doc.path),
                "version": doc.version(),
                "startup_mode": doc.startup_mode(),
                "modes": doc.mode_names(),
                "devices": [
                    {"id": d, "name": names.get(d, "")} for d in devices
                ],
                "binding_count": len(bindings),
                "library_action_count": len(actions),
                "action_types": dict(type_counts),
            }
        )

    print(f"Profile:       {doc.path}")
    print(f"Version:       {doc.version()}")
    print(f"Startup mode:  {doc.startup_mode()}")
    print(f"Modes:         {len(doc.mode_names())} ({', '.join(doc.mode_names())})")
    print(f"Devices:       {len(devices)}")
    for guid in devices:
        print(f"               - {_device_label(guid, names)}  ({guid})")
    print(f"Bindings:      {len(bindings)}")
    print(f"Library:       {len(actions)} actions")
    for atype, count in type_counts.most_common():
        print(f"               - {atype}: {count}")
    return 0


def cmd_modes(args: argparse.Namespace) -> int:
    doc = _load(args.profile)
    modes = doc.modes()
    startup = doc.startup_mode()

    if args.json:
        return _emit_json(
            {
                "startup_mode": startup,
                "modes": [
                    {"name": m.name, "parent": m.parent} for m in modes
                ],
            }
        )

    children: Dict[Optional[str], List[str]] = collections.defaultdict(list)
    names = {m.name for m in modes}
    for mode in modes:
        parent = mode.parent if mode.parent in names else None
        children[parent].append(mode.name)

    def render(parent: Optional[str], depth: int) -> None:
        for name in children.get(parent, []):
            marker = " *" if name == startup else ""
            print(f"{'    ' * depth}{name}{marker}")
            render(name, depth + 1)

    render(None, 0)
    # Surface modes whose declared parent does not exist.
    for mode in modes:
        if mode.parent is not None and mode.parent not in names:
            print(
                f"(warning: '{mode.name}' lists missing parent '{mode.parent}')",
                file=sys.stderr,
            )
    if startup:
        print("\n* = startup mode")
    return 0


def cmd_bindings(args: argparse.Namespace) -> int:
    doc = _load(args.profile)
    names = _device_names(doc)
    rows = []
    for binding in doc.bindings():
        if args.mode and binding.mode != args.mode:
            continue
        if args.device:
            needle = args.device.lower()
            label = _device_label(binding.device_id, names).lower()
            if needle not in binding.device_id.lower() and needle not in label:
                continue
        actions = [
            f"{info.type}"
            + (f" '{info.label}'" if info.label else "")
            for info in doc.reachable_actions(binding.root_action_ids)
            if info.type != "root"
        ]
        rows.append(
            {
                "device": binding.device_id,
                "device_name": names.get(binding.device_id, ""),
                "input_type": binding.input_type,
                "input_id": binding.input_id,
                "mode": binding.mode,
                "actions": actions,
            }
        )

    if args.json:
        return _emit_json(rows)

    if not rows:
        print("(no matching bindings)")
        return 0

    rows.sort(key=lambda r: (r["device"], r["mode"], r["input_type"], r["input_id"]))
    for row in rows:
        dev = _device_label(row["device"], names)
        action_text = ", ".join(row["actions"]) if row["actions"] else "(empty)"
        print(
            f"{dev}  {row['input_type']} {row['input_id']}  "
            f"[{row['mode']}]  ->  {action_text}"
        )
    print(f"\n{len(rows)} binding(s)")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    doc = _load(args.profile)
    findings = analysis.validate(doc)

    if args.json:
        return _emit_json(
            [dataclasses.asdict(f) for f in findings]
        ) or (1 if any(f.severity == analysis.ERROR for f in findings) else 0)

    if not findings:
        print("OK: no structural issues found")
        return 0

    counts = collections.Counter(f.severity for f in findings)
    for finding in findings:
        print(f"[{finding.severity.upper()}] {finding.message}")
    summary = ", ".join(
        f"{counts[s]} {s}" for s in (analysis.ERROR, analysis.WARNING, analysis.INFO)
        if counts[s]
    )
    print(f"\n{summary}")
    return 1 if counts[analysis.ERROR] else 0


def cmd_diff(args: argparse.Namespace) -> int:
    left = _load(args.base)
    right = _load(args.other)
    result = analysis.diff_profiles(left, right)

    if args.json:
        result_json = dict(result)
        result_json["binding_diffs"] = [
            dataclasses.asdict(d) for d in result["binding_diffs"]
        ]
        return _emit_json(result_json)

    base_startup, other_startup = result["startup_mode"]
    if base_startup != other_startup:
        print(f"startup-mode: {base_startup}  ->  {other_startup}")
    for name in result["modes_added"]:
        print(f"mode added:    {name}")
    for name in result["modes_removed"]:
        print(f"mode removed:  {name}")
    for name in result["modes_reparented"]:
        print(f"mode reparented: {name}")
    lcount = result["library_count"]
    if lcount[0] != lcount[1]:
        print(f"library actions: {lcount[0]}  ->  {lcount[1]}")
    for d in result["binding_diffs"]:
        print(f"binding {d.kind}: {d.key}")
        print(f"    {d.detail}")
    total = (
        len(result["modes_added"])
        + len(result["modes_removed"])
        + len(result["modes_reparented"])
        + len(result["binding_diffs"])
    )
    if total == 0 and base_startup == other_startup and lcount[0] == lcount[1]:
        print("profiles are structurally identical")
    return 0


# ---------------------------------------------------------------------------
# Mutating commands
# ---------------------------------------------------------------------------

def cmd_set_startup_mode(args: argparse.Namespace) -> int:
    doc = _load(args.profile)
    if args.mode not in doc.mode_names():
        raise SystemExit(
            f"error: mode '{args.mode}' is not declared in this profile "
            f"(have: {', '.join(doc.mode_names())})"
        )
    if doc.startup_mode() == args.mode:
        print(f"startup-mode already '{args.mode}'; nothing to do")
        return 0
    if args.dry_run:
        print(f"would set startup-mode: {doc.startup_mode()}  ->  {args.mode}")
        return 0
    _warn_if_running()
    doc.set_startup_mode(args.mode)
    backup = doc.save(backup=not args.no_backup)
    return _confirm_written(doc, backup)


def cmd_rename_mode(args: argparse.Namespace) -> int:
    doc = _load(args.profile)
    try:
        # Validate without mutating first so --dry-run is accurate.
        if args.old not in doc.mode_names():
            raise ProfileError(f"mode '{args.old}' does not exist")
        if args.new in doc.mode_names():
            raise ProfileError(f"mode '{args.new}' already exists")
    except ProfileError as exc:
        raise SystemExit(f"error: {exc}")

    if args.dry_run:
        print(f"would rename mode '{args.old}' -> '{args.new}' "
              f"(updating bindings, change-mode targets, startup-mode)")
        return 0
    _warn_if_running()
    updated = doc.rename_mode(args.old, args.new)
    backup = doc.save(backup=not args.no_backup)
    print(f"renamed '{args.old}' -> '{args.new}' ({updated} reference(s) updated)")
    return _confirm_written(doc, backup)


def cmd_fix_library_order(args: argparse.Namespace) -> int:
    doc = _load(args.profile)
    library = doc.root.find("library")
    if library is None:
        print("no <library> element; nothing to do")
        return 0
    current = [a.get("id") for a in library.findall("action")]
    order, cycle = analysis.topological_order(doc)
    if cycle:
        print(
            "warning: dependency cycle detected; cyclic actions left in place",
            file=sys.stderr,
        )
    if current == order:
        print("library already in dependency order; nothing to do")
        return 0
    moved = sum(1 for a, b in zip(current, order) if a != b)
    if args.dry_run:
        print(f"would reorder library: {moved} action(s) move position")
        return 0
    _warn_if_running()
    nodes = {a.get("id"): a for a in library.findall("action")}
    for action in library.findall("action"):
        library.remove(action)
    for aid in order:
        library.append(nodes[aid])
    backup = doc.save(backup=not args.no_backup)
    print(f"reordered library: {moved} action(s) moved")
    return _confirm_written(doc, backup)


def cmd_remove_orphans(args: argparse.Namespace) -> int:
    doc = _load(args.profile)
    orphans = analysis.orphan_ids(doc)
    if not orphans:
        print("no orphan actions; nothing to do")
        return 0
    library = doc.root.find("library")
    nodes = {a.get("id"): a for a in library.findall("action")}

    print(f"{len(orphans)} orphan action(s):")
    for aid in orphans:
        info = doc.action_info(nodes[aid])
        label = f" '{info.label}'" if info.label else ""
        print(f"    {info.type}{label}  ({aid})")

    if args.dry_run:
        print("\n(dry run; nothing removed)")
        return 0
    _warn_if_running()
    for aid in orphans:
        library.remove(nodes[aid])
    backup = doc.save(backup=not args.no_backup)
    print(f"\nremoved {len(orphans)} orphan action(s)")
    return _confirm_written(doc, backup)


# ---------------------------------------------------------------------------
# Keyboard / vJoy inspection and editing
# ---------------------------------------------------------------------------

def _match_inputs(
    doc: ProfileDocument,
    device: Optional[str],
    input_id: Optional[str],
    mode: Optional[str],
    input_type: Optional[str] = None,
) -> List[Binding]:
    """Returns the bindings matching the given physical-input filters."""
    names = _device_names(doc)
    result: List[Binding] = []
    for binding in doc.bindings():
        if input_id is not None and binding.input_id != str(input_id):
            continue
        if mode is not None and binding.mode != mode:
            continue
        if input_type is not None and binding.input_type != input_type:
            continue
        if device is not None:
            needle = device.lower()
            label = _device_label(binding.device_id, names).lower()
            if needle not in binding.device_id.lower() and needle not in label:
                continue
        result.append(binding)
    return result


def _key_from_input_node(inp_node: object) -> str:
    """Resolves a map-to-keyboard <input> block to a display key name."""
    scan: Optional[int] = None
    is_extended = False
    for prop in inp_node.findall("property"):  # type: ignore[attr-defined]
        name = prop.find("name")
        value = prop.find("value")
        if name is None or value is None:
            continue
        if name.text == "scan-code" and value.text is not None:
            scan = int(value.text)
        elif name.text == "is-extended":
            is_extended = value.text == "True"
    return keymap.key_name(scan, is_extended) if scan is not None else "?"


def cmd_keyboard_keys(args: argparse.Namespace) -> int:
    doc = _load(args.profile)
    names = _device_names(doc)
    rows = []
    for binding in doc.bindings():
        for node in doc.reachable_action_nodes(binding.root_action_ids):
            if node.get("type") != "map-to-keyboard":
                continue
            combo = " + ".join(
                _key_from_input_node(inp) for inp in node.findall("input")
            )
            rows.append(
                {
                    "device": binding.device_id,
                    "device_name": names.get(binding.device_id, ""),
                    "input_type": binding.input_type,
                    "input_id": binding.input_id,
                    "mode": binding.mode,
                    "key": combo,
                }
            )

    if args.json:
        return _emit_json(rows)

    if not rows:
        print("(no keyboard bindings in this profile)")
        return 0

    rows.sort(key=lambda r: (r["mode"], r["device"], r["input_type"], r["input_id"]))
    for row in rows:
        dev = _device_label(row["device"], names)
        print(
            f"{dev}  {row['input_type']} {row['input_id']}  "
            f"[{row['mode']}]  ->  {row['key']}"
        )
    distinct = sorted({r["key"] for r in rows})
    print(f"\n{len(rows)} keyboard binding(s); keys used: {', '.join(distinct)}")
    return 0


def _vjoy_emissions(
    doc: ProfileDocument, binding: Binding
) -> List[tuple[str, str, str]]:
    """Returns (vjoy-device-id, vjoy-input-type, vjoy-input-id) for a binding."""
    out: List[tuple[str, str, str]] = []
    for node in doc.reachable_action_nodes(binding.root_action_ids):
        if node.get("type") != "map-to-vjoy":
            continue
        out.append(
            (
                doc.action_property(node, "vjoy-device-id") or "?",
                doc.action_property(node, "vjoy-input-type") or "?",
                doc.action_property(node, "vjoy-input-id") or "?",
            )
        )
    return out


def cmd_vjoy_usage(args: argparse.Namespace) -> int:
    doc = _load(args.profile)
    names = _device_names(doc)
    rows = []
    # used[(vjoy_device, vjoy_type)] = set of input ids
    used: Dict[tuple[str, str], set[int]] = collections.defaultdict(set)
    for binding in doc.bindings():
        for dev, vtype, vid in _vjoy_emissions(doc, binding):
            rows.append(
                {
                    "phys_device": binding.device_id,
                    "phys_input": f"{binding.input_type} {binding.input_id}",
                    "mode": binding.mode,
                    "vjoy_device": dev,
                    "vjoy_type": vtype,
                    "vjoy_id": vid,
                }
            )
            if vid.isdigit():
                used[(dev, vtype)].add(int(vid))

    if args.json:
        return _emit_json(rows)

    if not rows:
        print("(no Map to vJoy actions in this profile)")
        return 0

    print("Usage by physical input:")
    rows.sort(key=lambda r: (r["vjoy_device"], r["vjoy_type"], r["vjoy_id"]))
    for row in rows:
        dev = _device_label(row["phys_device"], names)
        print(
            f"  vJoy {row['vjoy_device']} {row['vjoy_type']} {row['vjoy_id']}"
            f"  <-  {dev} {row['phys_input']} [{row['mode']}]"
        )
    print("\nSlots in use:")
    for (vdev, vtype), ids in sorted(used.items()):
        ordered = sorted(ids)
        line = f"  vJoy {vdev} {vtype}: {', '.join(str(i) for i in ordered)}"
        if vtype == "button":
            free = next(i for i in range(1, 200) if i not in ids)
            line += f"   (lowest free button: {free})"
        print(line)
    return 0


def cmd_set_vjoy(args: argparse.Namespace) -> int:
    doc = _load(args.profile)
    candidates = _match_inputs(
        doc, args.device, args.input_id, args.mode,
        getattr(args, "input_type", None),
    )
    targets = []
    for binding in candidates:
        for node in doc.reachable_action_nodes(binding.root_action_ids):
            if node.get("type") != "map-to-vjoy":
                continue
            if doc.action_property(node, "vjoy-input-type") != "button":
                continue
            if doc.action_property(node, "vjoy-input-id") == str(args.from_button):
                targets.append((binding, node))

    if not targets:
        raise SystemExit(
            f"error: no Map to vJoy button={args.from_button} found on the "
            f"selected input(s). Run 'vjoy-usage' to see current slots."
        )

    print(f"{len(targets)} mapping(s) to retarget "
          f"vJoy button {args.from_button} -> {args.to_button}:")
    names = _device_names(doc)
    for binding, _ in targets:
        dev = _device_label(binding.device_id, names)
        print(f"    {dev} {binding.input_type} {binding.input_id} "
              f"[{binding.mode}]")

    if args.dry_run:
        print("\n(dry run; nothing changed)")
        return 0
    _warn_if_running()
    for _, node in targets:
        prop = _find_property(node, "vjoy-input-id")
        prop.find("value").text = str(args.to_button)
    backup = doc.save(backup=not args.no_backup)
    print(
        "\nNOTE: this only changes the Joystick Gremlin profile (physical "
        "button -> vJoy slot). The Star Citizen layout XML still maps vJoy "
        f"button {args.from_button} to the game action; update it separately "
        f"so the game reads vJoy button {args.to_button}."
    )
    return _confirm_written(doc, backup)


def _find_property(node: object, name: str) -> object:
    for prop in node.findall("property"):  # type: ignore[attr-defined]
        child = prop.find("name")
        if child is not None and child.text == name:
            return prop
    raise ProfileError(f"property '{name}' not found on action")


def _invert_curve(curve_node: object) -> int:
    """Mirrors a response curve on the Y axis (Gremlin's 'Invert Curve')."""
    points = curve_node.find("control-points")  # type: ignore[attr-defined]
    if points is None:
        return 0
    flipped = 0
    for prop in points.findall("property"):
        value = prop.find("value")
        if value is None or not value.text or "," not in value.text:
            continue
        x_str, y_str = value.text.split(",", 1)
        y_inverted = -float(y_str)
        if y_inverted == 0:
            y_inverted = 0.0  # avoid "-0.0"
        value.text = f"{x_str},{y_inverted!r}"
        flipped += 1
    return flipped


def cmd_flip_axis(args: argparse.Namespace) -> int:
    doc = _load(args.profile)
    candidates = _match_inputs(
        doc, args.device, args.input_id, args.mode, input_type="axis"
    )
    if not candidates:
        raise SystemExit(
            "error: no axis input matched. Check the input id and that it is "
            "an axis (see 'bindings')."
        )
    curves = []
    for binding in candidates:
        for node in doc.reachable_action_nodes(binding.root_action_ids):
            if node.get("type") == "response-curve":
                curves.append((binding, node))

    if not curves:
        raise SystemExit(
            "error: the selected axis has no response curve to invert. A flat "
            "curve must be added first (Gremlin's Invert Curve needs one)."
        )

    names = _device_names(doc)
    print(f"{len(curves)} response curve(s) to invert:")
    for binding, _ in curves:
        dev = _device_label(binding.device_id, names)
        print(f"    {dev} axis {binding.input_id} [{binding.mode}]")

    if args.dry_run:
        print("\n(dry run; nothing changed)")
        return 0
    _warn_if_running()
    for _, node in curves:
        _invert_curve(node)
    backup = doc.save(backup=not args.no_backup)
    print(f"\ninverted {len(curves)} curve(s)")
    return _confirm_written(doc, backup)


def cmd_delete_mode(args: argparse.Namespace) -> int:
    doc = _load(args.profile)
    if args.mode not in doc.mode_names():
        raise SystemExit(
            f"error: mode '{args.mode}' is not declared "
            f"(have: {', '.join(doc.mode_names())})"
        )
    if doc.startup_mode() == args.mode:
        raise SystemExit(
            f"error: '{args.mode}' is the startup mode. Set a different "
            f"startup mode first (set-startup-mode), then delete it."
        )

    # Count what will go, and any change-mode targets that will dangle.
    to_drop = sum(1 for b in doc.bindings() if b.mode == args.mode)
    dangling = 0
    for target in doc.root.iter("target-mode"):
        for prop in target.findall("property"):
            name = prop.find("name")
            value = prop.find("value")
            if name is not None and name.text == "name" and value is not None:
                if value.text == args.mode:
                    dangling += 1

    print(f"deleting mode '{args.mode}': "
          f"{to_drop} binding(s) dropped, children reparented")
    if dangling:
        print(f"warning: {dangling} change-mode action(s) target '{args.mode}' "
              f"and will dangle (validate will flag them)", file=sys.stderr)

    if args.dry_run:
        print("(dry run; nothing changed)")
        return 0
    _warn_if_running()
    removed = doc.delete_mode(args.mode)
    backup = doc.save(backup=not args.no_backup)
    print(f"deleted '{args.mode}' ({removed} binding(s) removed)")
    return _confirm_written(doc, backup)


# ---------------------------------------------------------------------------
# Action-tree inspection (works across every action type)
# ---------------------------------------------------------------------------

def _binding_header(doc: ProfileDocument, binding: Binding) -> str:
    names = _device_names(doc)
    dev = _device_label(binding.device_id, names)
    return f"{dev}  {binding.input_type} {binding.input_id}  [{binding.mode}]"


def cmd_tree(args: argparse.Namespace) -> int:
    doc = _load(args.profile)
    bindings = _match_inputs(
        doc, args.device, args.input_id, args.mode,
        getattr(args, "input_type", None),
    )
    if not bindings:
        print("(no matching inputs)")
        return 0
    for binding in bindings:
        print(_binding_header(doc, binding))
        for line in render.render_tree(doc, binding.root_action_ids, indent=1):
            print(line)
        print()
    return 0


def _reachable_of_type(
    doc: ProfileDocument, binding: Binding, action_type: str
) -> List[ElementTree.Element]:
    return [
        node
        for node in doc.reachable_action_nodes(binding.root_action_ids)
        if node.get("type") == action_type
    ]


def cmd_tempos(args: argparse.Namespace) -> int:
    doc = _load(args.profile)
    found = 0
    for binding in doc.bindings():
        for node in _reachable_of_type(doc, binding, "tempo"):
            found += 1
            threshold = doc.action_property(node, "threshold") or "?"
            print(f"{_binding_header(doc, binding)}  (tempo, {threshold}s)")
            for slot, ids in render.iter_slots(node):
                print(f"    [{slot}]")
                for line in render.render_tree(doc, ids, indent=3):
                    print(line)
            print()
    if not found:
        print("(no tempo actions)")
    return 0


def cmd_macros(args: argparse.Namespace) -> int:
    doc = _load(args.profile)
    found = 0
    for binding in doc.bindings():
        for node in _reachable_of_type(doc, binding, "macro"):
            found += 1
            label = doc.action_property(node, "action-label") or "Macro"
            print(f"{_binding_header(doc, binding)}  ({label})")
            for step in render.macro_steps(node):
                print(f"    - {step}")
            print()
    if not found:
        print("(no macro actions)")
    return 0


def cmd_mouse(args: argparse.Namespace) -> int:
    doc = _load(args.profile)
    rows = []
    for binding in doc.bindings():
        for node in _reachable_of_type(doc, binding, "map-to-mouse"):
            rows.append(
                {
                    "input": _binding_header(doc, binding),
                    "direction": doc.action_property(node, "direction") or "",
                    "mode": doc.action_property(node, "mode") or "",
                    "min_speed": doc.action_property(node, "min-speed") or "",
                    "max_speed": doc.action_property(node, "max-speed") or "",
                }
            )
    if args.json:
        return _emit_json(rows)
    if not rows:
        print("(no Map to Mouse actions)")
        return 0
    for row in rows:
        print(
            f"{row['input']}  ->  mouse {row['mode']} {row['direction']} "
            f"(speed {row['min_speed']}-{row['max_speed']})"
        )
    return 0


def cmd_sounds(args: argparse.Namespace) -> int:
    doc = _load(args.profile)
    rows = []
    for binding in doc.bindings():
        for node in _reachable_of_type(doc, binding, "play-sound"):
            filename = doc.action_property(node, "filename") or ""
            exists = bool(filename) and os.path.isfile(filename)
            rows.append(
                {
                    "input": _binding_header(doc, binding),
                    "kind": "sound",
                    "detail": filename,
                    "volume": doc.action_property(node, "volume") or "",
                    "missing": bool(filename) and not exists,
                }
            )
        for node in _reachable_of_type(doc, binding, "text-to-speech"):
            rows.append(
                {
                    "input": _binding_header(doc, binding),
                    "kind": "tts",
                    "detail": doc.action_property(node, "text") or "",
                    "volume": doc.action_property(node, "playback-volume") or "",
                    "missing": False,
                }
            )
    if args.json:
        return _emit_json(rows)
    if not rows:
        print("(no Play Sound or Text to Speech actions)")
        return 0
    missing = 0
    for row in rows:
        flag = "  [MISSING FILE]" if row["missing"] else ""
        missing += 1 if row["missing"] else 0
        print(f"{row['input']}  ->  {row['kind']}: {row['detail']}{flag}")
    if missing:
        print(f"\nwarning: {missing} sound file(s) not found on disk",
              file=sys.stderr)
    return 0


def cmd_axis_config(args: argparse.Namespace) -> int:
    doc = _load(args.profile)
    axis_types = {
        "response-curve", "axis-delta", "split-axis", "merge-axis",
        "dual-axis-deadzone",
    }
    found = 0
    for binding in doc.bindings():
        if binding.input_type != "axis":
            continue
        nodes = [
            n for n in doc.reachable_action_nodes(binding.root_action_ids)
            if n.get("type") in axis_types
        ]
        if not nodes:
            continue
        found += 1
        print(_binding_header(doc, binding))
        for node in nodes:
            atype = node.get("type")
            if atype == "response-curve":
                kind = render.classify_curve(node)
                dz = render.curve_deadzone(node)
                dz_text = ""
                if dz:
                    dz_text = (f"  deadzone "
                               f"[{dz.get('low','?')}, {dz.get('center-low','?')}, "
                               f"{dz.get('center-high','?')}, {dz.get('high','?')}]")
                print(f"    response-curve: {kind}{dz_text}")
            else:
                print(f"    {atype}")
        print()
    if not found:
        print("(no axis processing actions)")
    return 0


def cmd_descriptions(args: argparse.Namespace) -> int:
    doc = _load(args.profile)
    rows = []
    for binding in doc.bindings():
        for node in _reachable_of_type(doc, binding, "description"):
            rows.append(
                {
                    "input": _binding_header(doc, binding),
                    "device": binding.device_id,
                    "input_type": binding.input_type,
                    "input_id": binding.input_id,
                    "mode": binding.mode,
                    "text": doc.action_property(node, "description") or "",
                }
            )
    if args.json:
        return _emit_json(rows)
    if not rows:
        print("(no description actions)")
        return 0
    rows.sort(key=lambda r: (r["mode"], r["input_type"], r["input_id"]))
    for row in rows:
        print(f"{row['input']}\n    {row['text']}")
    print(f"\n{len(rows)} description(s)")
    return 0


# ---------------------------------------------------------------------------
# Action-level edits
# ---------------------------------------------------------------------------

def cmd_set_label(args: argparse.Namespace) -> int:
    doc = _load(args.profile)
    actions = doc.library_actions()
    if args.action_id not in actions:
        raise SystemExit(f"error: no library action with id {args.action_id}")
    if len(args.label) > 150:
        raise SystemExit(
            f"error: label is {len(args.label)} chars; refusing (>150 breaks "
            f"Joystick Gremlin's UI). Keep it under 100."
        )
    if len(args.label) > 100:
        print(
            f"warning: label is {len(args.label)} chars; JG truncates past ~100 "
            f"and forces horizontal scrolling.",
            file=sys.stderr,
        )
    if args.dry_run:
        print(f"would set action {args.action_id} label -> {args.label!r}")
        return 0
    _warn_if_running()
    doc.set_action_property(actions[args.action_id], "action-label", args.label)
    backup = doc.save(backup=not args.no_backup)
    print(f"set label -> {args.label!r}")
    return _confirm_written(doc, backup)


def cmd_set_tempo_threshold(args: argparse.Namespace) -> int:
    doc = _load(args.profile)
    try:
        value = float(args.seconds)
    except ValueError:
        raise SystemExit(f"error: '{args.seconds}' is not a number")
    if value <= 0:
        raise SystemExit("error: threshold must be greater than 0")

    bindings = _match_inputs(
        doc, args.device, args.input_id, args.mode,
        getattr(args, "input_type", None),
    )
    tempos = []
    for binding in bindings:
        for node in _reachable_of_type(doc, binding, "tempo"):
            tempos.append((binding, node))
    if not tempos:
        raise SystemExit("error: no tempo action found on the selected input(s)")

    for binding, _ in tempos:
        print(f"    {_binding_header(doc, binding)}")
    if args.dry_run:
        print(f"\nwould set {len(tempos)} tempo threshold(s) -> {value}s")
        return 0
    _warn_if_running()
    for _, node in tempos:
        doc.set_action_property(node, "threshold", repr(value), "float")
    backup = doc.save(backup=not args.no_backup)
    print(f"\nset {len(tempos)} tempo threshold(s) -> {value}s")
    return _confirm_written(doc, backup)


def cmd_set_description(args: argparse.Namespace) -> int:
    doc = _load(args.profile)
    bindings = _match_inputs(
        doc, args.device, args.input_id, args.mode,
        getattr(args, "input_type", None),
    )
    if not bindings:
        raise SystemExit("error: no input matched the given filters")

    library = doc.root.find("library")
    actions = doc.library_actions()
    types = {aid: node.get("type") for aid, node in actions.items()}
    updated = 0
    created = 0
    for binding in bindings:
        existing = _reachable_of_type(doc, binding, "description")
        if existing:
            doc.set_action_property(existing[0], "description", args.text)
            updated += 1
            continue
        # Create a description action and wire it into the input's root(s).
        for root_id in binding.root_action_ids:
            root_node = actions.get(root_id)
            if root_node is None:
                continue
            new_id = str(uuid.uuid4())
            desc = _make_description_action(new_id, args.text)
            # Insert before the referencing root so definitions precede uses.
            root_index = list(library).index(root_node)
            library.insert(root_index, desc)
            _wire_description_into_root(
                root_node, new_id, binding.input_type, types
            )
            created += 1

    if args.dry_run:
        print(f"would update {updated} and create {created} description(s)")
        return 0
    _warn_if_running()
    backup = doc.save(backup=not args.no_backup)
    print(f"updated {updated}, created {created} description(s)")
    return _confirm_written(doc, backup)


def _make_description_action(action_id: str, text: str) -> ElementTree.Element:
    action = ElementTree.Element("action")
    action.set("id", action_id)
    action.set("type", "description")
    doc_helper = ProfileDocument  # for set_action_property
    doc_helper.set_action_property(action, "description", text, "string")
    doc_helper.set_action_property(action, "action-label", "Description", "string")
    doc_helper.set_action_property(
        action, "activation-mode", "disallowed", "activation-mode"
    )
    return action


def _wire_description_into_root(
    root_node: ElementTree.Element,
    new_id: str,
    input_type: str,
    types: Dict[str, Optional[str]],
) -> None:
    container = root_node.find("actions")
    if container is None:
        container = ElementTree.SubElement(root_node, "actions")
    ref = ElementTree.Element("action-id")
    ref.text = new_id
    child_ids = container.findall("action-id")
    if input_type == "axis":
        # Place after the response-curve, before any mapping (R14 rule).
        after = None
        for child in child_ids:
            if types.get(child.text) == "response-curve":
                after = child
        if after is not None:
            container.insert(list(container).index(after) + 1, ref)
        else:
            container.insert(0, ref)
    elif input_type == "button":
        container.insert(0, ref)
    else:
        container.append(ref)


# ---------------------------------------------------------------------------
# Launcher
# ---------------------------------------------------------------------------

def cmd_run(args: argparse.Namespace) -> int:
    """Launches the Joystick Gremlin GUI with the existing startup flags."""
    repo_root = Path(__file__).resolve().parents[2]
    entry = repo_root / "joystick_gremlin.py"
    if not entry.is_file():
        raise SystemExit(f"error: cannot find {entry}")

    command = [sys.executable, str(entry)]
    if args.profile:
        command += ["--profile", str(Path(args.profile).resolve())]
    if args.enable:
        command.append("--enable")
    if args.minimized:
        command.append("--start-minimized")

    print("launching:", " ".join(command))
    if args.dry_run:
        return 0
    # Detach: the GUI owns its own lifetime; the CLI returns immediately.
    subprocess.Popen(command, cwd=str(repo_root))
    return 0
