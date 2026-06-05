# -*- coding: utf-8; -*-

# SPDX-License-Identifier: GPL-3.0-only

"""Structural analyses over a `ProfileDocument`.

These functions are pure: they read the document and return findings or derived
orderings without mutating anything (mutation is the caller's job, e.g. the
``fix-library-order`` and ``remove-orphans`` commands).
"""

from __future__ import annotations

import dataclasses
from typing import Dict, List, Set, Tuple

from gremlin.cli.model import MAPPING_ACTION_TYPES, ProfileDocument

ERROR = "error"
WARNING = "warning"
INFO = "info"


@dataclasses.dataclass(frozen=True)
class Finding:
    """A single validation result."""

    severity: str
    message: str


def _input_root_ids(doc: ProfileDocument) -> List[str]:
    """All root-action ids referenced by physical inputs."""
    ids: List[str] = []
    for binding in doc.bindings():
        ids.extend(binding.root_action_ids)
    return ids


def reachable_ids(doc: ProfileDocument) -> Set[str]:
    """Set of library action ids reachable from any physical input."""
    return {info.action_id for info in doc.reachable_actions(_input_root_ids(doc))}


def orphan_ids(doc: ProfileDocument) -> List[str]:
    """Library action ids not reachable from any physical input, in doc order."""
    reachable = reachable_ids(doc)
    return [aid for aid in doc.library_actions() if aid not in reachable]


def topological_order(doc: ProfileDocument) -> Tuple[List[str], bool]:
    """Orders library ids so every action precedes those that reference it.

    Returns the ordered id list and a flag that is ``True`` when a dependency
    cycle was detected (in which case the offending ids are appended in their
    original document order rather than dropped).
    """
    actions = doc.library_actions()
    order = list(actions.keys())
    index = {aid: i for i, aid in enumerate(order)}

    # prerequisites[a] = ids a references that must come first.
    prerequisites: Dict[str, Set[str]] = {}
    enables: Dict[str, List[str]] = {aid: [] for aid in order}
    for aid, node in actions.items():
        refs = {r for r in doc.action_references(node) if r in actions}
        prerequisites[aid] = set(refs)
        for ref in refs:
            enables[ref].append(aid)

    remaining = {aid: len(prereqs) for aid, prereqs in prerequisites.items()}
    ready = sorted((aid for aid, n in remaining.items() if n == 0), key=index.get)
    result: List[str] = []
    while ready:
        aid = ready.pop(0)
        result.append(aid)
        newly_ready: List[str] = []
        for dependent in enables[aid]:
            remaining[dependent] -= 1
            if remaining[dependent] == 0:
                newly_ready.append(dependent)
        # Keep the original document order as a stable tie-break.
        ready.extend(newly_ready)
        ready.sort(key=index.get)

    has_cycle = len(result) != len(order)
    if has_cycle:
        leftover = [aid for aid in order if aid not in set(result)]
        result.extend(leftover)
    return result, has_cycle


def validate(doc: ProfileDocument) -> List[Finding]:
    """Runs the full set of structural checks and returns ordered findings."""
    findings: List[Finding] = []
    actions = doc.library_actions()
    types = {aid: node.get("type") for aid, node in actions.items()}

    # Schema version.
    version = doc.version()
    if version is None:
        findings.append(Finding(ERROR, "profile has no version attribute"))
    elif version != 14:
        findings.append(
            Finding(WARNING, f"profile version is {version}, expected 14")
        )

    # Duplicate library ids. (library_actions() collapses dupes, so re-scan.)
    library = doc.root.find("library")
    if library is not None:
        seen: Set[str] = set()
        for action in library.findall("action"):
            aid = action.get("id")
            if aid is None:
                findings.append(Finding(ERROR, "library action without an id"))
            elif aid in seen:
                findings.append(
                    Finding(ERROR, f"duplicate library action id: {aid}")
                )
            else:
                seen.add(aid)

    # Dangling references from inputs.
    for binding in doc.bindings():
        for rid in binding.root_action_ids:
            if rid not in actions:
                findings.append(
                    Finding(
                        ERROR,
                        f"input {binding.input_type} {binding.input_id} "
                        f"[{binding.mode}] references missing root action {rid}",
                    )
                )

    # Dangling references within the library.
    for aid, node in actions.items():
        for ref in doc.action_references(node):
            if ref not in actions:
                findings.append(
                    Finding(ERROR, f"action {aid} references missing action {ref}")
                )

    # Forward references (defined later than the action that references them).
    order_index = {aid: i for i, aid in enumerate(actions)}
    for aid, node in actions.items():
        for ref in doc.action_references(node):
            if ref in order_index and order_index[ref] > order_index[aid]:
                findings.append(
                    Finding(
                        WARNING,
                        f"forward reference: {aid} references {ref} which is "
                        f"defined later (run fix-library-order)",
                    )
                )

    # Response-curve must precede axis mappings within a root.
    for aid, node in actions.items():
        if types.get(aid) != "root":
            continue
        child_types = [types.get(cid) for cid in doc.direct_child_ids(node)]
        if "response-curve" not in child_types:
            continue
        curve_pos = child_types.index("response-curve")
        mapping_positions = [
            i for i, t in enumerate(child_types) if t in MAPPING_ACTION_TYPES
        ]
        if mapping_positions and min(mapping_positions) < curve_pos:
            findings.append(
                Finding(
                    ERROR,
                    f"root {aid}: response-curve appears after an axis mapping; "
                    f"the curve becomes a silent no-op",
                )
            )

    # Startup mode must exist.
    mode_names = set(doc.mode_names())
    startup = doc.startup_mode()
    if startup is not None and startup not in mode_names:
        findings.append(
            Finding(ERROR, f"startup-mode '{startup}' is not a declared mode")
        )

    # Input bindings referencing undeclared modes.
    for binding in doc.bindings():
        if binding.mode and binding.mode not in mode_names:
            findings.append(
                Finding(
                    WARNING,
                    f"input {binding.input_type} {binding.input_id} uses "
                    f"undeclared mode '{binding.mode}'",
                )
            )

    # change-mode targets referencing undeclared modes.
    for target in doc.root.iter("target-mode"):
        for prop in target.findall("property"):
            name = prop.find("name")
            value = prop.find("value")
            if name is not None and name.text == "name" and value is not None:
                if value.text and value.text not in mode_names:
                    findings.append(
                        Finding(
                            WARNING,
                            f"change-mode targets undeclared mode "
                            f"'{value.text}'",
                        )
                    )

    # Orphans (informational; remove-orphans can clean them up).
    orphans = orphan_ids(doc)
    if orphans:
        findings.append(
            Finding(
                INFO,
                f"{len(orphans)} library action(s) unreachable from any input "
                f"(run remove-orphans to prune)",
            )
        )

    return findings


@dataclasses.dataclass(frozen=True)
class BindingDiff:
    """A single binding-level difference between two profiles."""

    kind: str  # "added" | "removed" | "changed"
    key: str
    detail: str


def _binding_signature(doc: ProfileDocument) -> Dict[str, str]:
    """Maps each physical input to a stable description of what it triggers."""
    signatures: Dict[str, str] = {}
    for binding in doc.bindings():
        key = (
            f"{binding.device_id} {binding.input_type} "
            f"{binding.input_id} [{binding.mode}]"
        )
        actions = [
            f"{info.type}:{info.label}"
            for info in doc.reachable_actions(binding.root_action_ids)
            if info.type != "root"
        ]
        signatures[key] = ", ".join(actions) if actions else "(empty)"
    return signatures


def diff_profiles(
    left: ProfileDocument, right: ProfileDocument
) -> Dict[str, object]:
    """Computes a structural diff of two profiles (left = base, right = other)."""
    left_modes = {m.name: m.parent for m in left.modes()}
    right_modes = {m.name: m.parent for m in right.modes()}
    modes_added = sorted(set(right_modes) - set(left_modes))
    modes_removed = sorted(set(left_modes) - set(right_modes))
    modes_reparented = [
        name
        for name in set(left_modes) & set(right_modes)
        if left_modes[name] != right_modes[name]
    ]

    left_sig = _binding_signature(left)
    right_sig = _binding_signature(right)
    binding_diffs: List[BindingDiff] = []
    for key in sorted(set(right_sig) - set(left_sig)):
        binding_diffs.append(BindingDiff("added", key, right_sig[key]))
    for key in sorted(set(left_sig) - set(right_sig)):
        binding_diffs.append(BindingDiff("removed", key, left_sig[key]))
    for key in sorted(set(left_sig) & set(right_sig)):
        if left_sig[key] != right_sig[key]:
            binding_diffs.append(
                BindingDiff(
                    "changed", key, f"{left_sig[key]}  ->  {right_sig[key]}"
                )
            )

    return {
        "startup_mode": (left.startup_mode(), right.startup_mode()),
        "modes_added": modes_added,
        "modes_removed": modes_removed,
        "modes_reparented": modes_reparented,
        "library_count": (
            len(left.library_actions()),
            len(right.library_actions()),
        ),
        "binding_diffs": binding_diffs,
    }
