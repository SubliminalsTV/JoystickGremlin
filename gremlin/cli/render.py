# -*- coding: utf-8; -*-

# SPDX-License-Identifier: GPL-3.0-only

"""Formatting helpers for the inspection commands.

The tree walker is deliberately generic: any element that contains
``<action-id>`` children is treated as a "slot" and rendered with its tag as the
label. That means tempo (short/long), double-tap (single/double), chain
(chain-N), condition (true/false), hat-buttons (North/East/...), split-axis and
dual-axis-deadzone all render correctly without special-casing — and any future
container action does too. Action types with no dedicated view still show their
type and label, so nothing is silently dropped.
"""

from __future__ import annotations

from typing import Dict, List, Tuple
from xml.etree import ElementTree

from gremlin.cli import keymap
from gremlin.cli.model import ProfileDocument

# Labels that carry no information and only add noise to a tree.
_NOISE_LABELS = frozenset({"Root", ""})


def _props(node: ElementTree.Element) -> Dict[str, str]:
    """Collects a node's direct ``<property>`` children as a name->value dict."""
    result: Dict[str, str] = {}
    for prop in node.findall("property"):
        name = prop.find("name")
        value = prop.find("value")
        if name is not None and name.text is not None:
            result[name.text] = value.text if value is not None else ""
    return result


def iter_slots(action: ElementTree.Element) -> List[Tuple[str, List[str]]]:
    """Returns (slot-tag, [child action ids]) for every child holding action-ids."""
    slots: List[Tuple[str, List[str]]] = []
    for child in action:
        ids = [ref.text for ref in child.findall("action-id") if ref.text]
        if ids:
            slots.append((child.tag, ids))
    return slots


def render_tree(
    doc: ProfileDocument,
    root_ids: List[str],
    indent: int = 0,
    visited: frozenset[str] = frozenset(),
) -> List[str]:
    """Renders an indented action tree starting from the given action ids."""
    actions = doc.library_actions()
    lines: List[str] = []
    pad = "  " * indent
    for rid in root_ids:
        if rid in visited:
            lines.append(f"{pad}{rid} (already shown)")
            continue
        node = actions.get(rid)
        if node is None:
            lines.append(f"{pad}<missing action {rid}>")
            continue
        info = doc.action_info(node)
        suffix = f"  - {info.label}" if info.label not in _NOISE_LABELS else ""
        extra = _inline_detail(doc, node)
        lines.append(f"{pad}{info.type}{extra}{suffix}")
        for slot, child_ids in iter_slots(node):
            lines.append(f"{pad}  [{slot}]")
            lines.extend(
                render_tree(doc, child_ids, indent + 2, visited | {rid})
            )
    return lines


def _inline_detail(doc: ProfileDocument, node: ElementTree.Element) -> str:
    """A short, type-specific parenthetical for the tree (vJoy slot, key, ...)."""
    atype = node.get("type")
    p = _props(node)
    if atype == "map-to-vjoy":
        return f" (vJoy {p.get('vjoy-device-id','?')} " \
               f"{p.get('vjoy-input-type','?')} {p.get('vjoy-input-id','?')})"
    if atype == "map-to-keyboard":
        keys = " + ".join(keyboard_keys(node))
        return f" ({keys})" if keys else ""
    if atype == "change-mode":
        return f" ({p.get('change-type','?')})"
    if atype == "tempo":
        return f" (threshold {p.get('threshold','?')}s)"
    if atype == "description":
        text = p.get("description", "")
        return f' ("{text[:40]}")' if text else ""
    return ""


def keyboard_keys(node: ElementTree.Element) -> List[str]:
    """Resolves a map-to-keyboard node's <input> blocks to key names."""
    names: List[str] = []
    for inp in node.findall("input"):
        scan = None
        extended = False
        for prop in inp.findall("property"):
            name = prop.find("name")
            value = prop.find("value")
            if name is None or value is None:
                continue
            if name.text == "scan-code" and value.text is not None:
                scan = int(value.text)
            elif name.text == "is-extended":
                extended = value.text == "True"
        if scan is not None:
            names.append(keymap.key_name(scan, extended))
    return names


def macro_steps(node: ElementTree.Element) -> List[str]:
    """Renders a macro's <macro-action> steps as readable strings."""
    steps: List[str] = []
    for step in node.findall("macro-action"):
        stype = step.get("type", "?")
        p = _props(step)
        if stype == "key":
            scan = p.get("scan-code")
            extended = p.get("is-extended") == "True"
            key = keymap.key_name(int(scan), extended) if scan else "?"
            press = p.get("is-pressed")
            verb = "press" if press == "True" else "release" if press == "False" \
                else "tap"
            steps.append(f"key {verb} {key}")
        elif stype == "pause":
            steps.append(f"pause {p.get('duration', p.get('value', '?'))}s")
        elif stype == "vjoy":
            steps.append(
                f"vjoy {p.get('vjoy-input-type','?')} "
                f"{p.get('vjoy-input-id','?')} = {p.get('value','?')}"
            )
        elif stype == "logical-device":
            steps.append(
                f"logical {p.get('input-type','?')} "
                f"{p.get('input-id','?')} = {p.get('value','?')}"
            )
        elif stype in ("mouse-button", "mouse-motion"):
            detail = ", ".join(f"{k}={v}" for k, v in p.items())
            steps.append(f"{stype} {detail}")
        else:
            detail = ", ".join(f"{k}={v}" for k, v in p.items())
            steps.append(f"{stype} {detail}".rstrip())
    return steps


def classify_curve(node: ElementTree.Element) -> str:
    """Labels a response-curve as identity, inverted, or custom."""
    points = node.find("control-points")
    if points is None:
        return "unknown"
    pairs: List[Tuple[float, float]] = []
    for prop in points.findall("property"):
        value = prop.find("value")
        if value is None or not value.text or "," not in value.text:
            continue
        x_str, y_str = value.text.split(",", 1)
        try:
            pairs.append((float(x_str), float(y_str)))
        except ValueError:
            return "custom"
    if not pairs:
        return "unknown"
    if all(abs(y - x) < 1e-6 for x, y in pairs):
        return "identity"
    if all(abs(y + x) < 1e-6 for x, y in pairs):
        return "inverted"
    return "custom"


def curve_deadzone(node: ElementTree.Element) -> Dict[str, str]:
    """Extracts the deadzone block of a response curve, if present."""
    dz = node.find("deadzone")
    if dz is None:
        return {}
    return _props(dz)
