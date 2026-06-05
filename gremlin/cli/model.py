# -*- coding: utf-8; -*-

# SPDX-License-Identifier: GPL-3.0-only

"""Lightweight, GUI-free model of a Joystick Gremlin profile document.

`ProfileDocument` wraps the profile XML as an ``ElementTree`` and exposes the
handful of structural views the CLI needs (modes, bindings, the library action
graph) plus a writer that reproduces Joystick Gremlin's own serialization
format (UTF-8 BOM, minidom pretty-print with four-space indent, LF newlines).

Nothing here imports the Qt/QML stack or the action plugins, so the model loads
instantly and never opens a window.
"""

from __future__ import annotations

import dataclasses
import shutil
import time
from pathlib import Path
from typing import Dict, List, Optional
from xml.dom import minidom
from xml.etree import ElementTree

#: Profile schema version this CLI understands (matches Profile.current_version).
SUPPORTED_VERSION = 14

#: Action types that consume the post-curve signal of an axis root. Per the R14
#: evaluation rule, a response-curve must precede these within a root's actions.
MAPPING_ACTION_TYPES = frozenset({"map-to-vjoy", "map-to-mouse"})


class ProfileError(Exception):
    """Raised when a profile cannot be parsed or fails a structural invariant."""


@dataclasses.dataclass(frozen=True)
class ModeInfo:
    """A single mode and its optional parent mode."""

    name: str
    parent: Optional[str]


@dataclasses.dataclass(frozen=True)
class ActionInfo:
    """A library action node reduced to the fields the CLI reports on."""

    action_id: str
    type: str
    label: str


@dataclasses.dataclass(frozen=True)
class Binding:
    """A physical input together with the root action(s) it triggers."""

    device_id: str
    input_type: str
    input_id: str
    mode: str
    root_action_ids: List[str]


def _local_text(node: ElementTree.Element, tag: str) -> Optional[str]:
    """Returns the text of the first direct child with the given tag."""
    child = node.find(tag)
    return child.text if child is not None else None


def _action_label(action: ElementTree.Element) -> str:
    """Extracts the ``action-label`` property value from an action node."""
    for prop in action.findall("property"):
        if _local_text(prop, "name") == "action-label":
            return _local_text(prop, "value") or ""
    return ""


def _strip_indentation(node: ElementTree.Element) -> None:
    """Removes whitespace-only text/tail so minidom can re-indent cleanly.

    Parsing an already pretty-printed file leaves indentation whitespace on
    every container element. Re-serializing without stripping it produces
    doubled blank lines. Gremlin avoids this by building the tree from scratch;
    we reproduce that clean state on a parsed tree instead.
    """
    if node.text is not None and node.text.strip() == "":
        node.text = None
    if node.tail is not None and node.tail.strip() == "":
        node.tail = None
    for child in node:
        _strip_indentation(child)


class ProfileDocument:
    """A parsed Joystick Gremlin profile with structural accessors and a writer."""

    def __init__(self, path: Path, root: ElementTree.Element) -> None:
        self.path = path
        self.root = root

    # -- loading / saving ---------------------------------------------------

    @classmethod
    def load(cls, path: Path) -> "ProfileDocument":
        """Parses the profile at ``path``.

        Raises:
            ProfileError: if the file is not well-formed or not a profile.
        """
        try:
            tree = ElementTree.parse(str(path))
        except ElementTree.ParseError as exc:
            raise ProfileError(f"{path}: not well-formed XML ({exc})") from exc
        root = tree.getroot()
        if root.tag != "profile":
            raise ProfileError(
                f"{path}: root element is <{root.tag}>, expected <profile>"
            )
        return cls(path, root)

    def serialize(self) -> str:
        """Renders the (possibly modified) tree in Gremlin's canonical format."""
        _strip_indentation(self.root)
        ugly = ElementTree.tostring(self.root, encoding="utf-8")
        dom = minidom.parseString(ugly)
        return dom.toprettyxml(indent="    ")

    def save(
        self, path: Optional[Path] = None, backup: bool = True
    ) -> Optional[Path]:
        """Writes the profile back to disk in Gremlin's canonical format.

        Args:
            path: destination; defaults to the loaded path.
            backup: when overwriting an existing file, copy it aside first.

        Returns:
            The backup path created, or ``None`` if no backup was made.
        """
        target = path or self.path
        backup_path: Optional[Path] = None
        if backup and target.exists():
            stamp = time.strftime("%Y%m%d-%H%M%S")
            backup_path = target.with_suffix(target.suffix + f".bak-{stamp}")
            shutil.copy2(target, backup_path)
        text = self.serialize()
        # utf-8-sig writes the BOM Gremlin emits; newline="" keeps the LF the
        # minidom output already uses rather than translating to CRLF.
        with open(target, "w", encoding="utf-8-sig", newline="") as handle:
            handle.write(text)
        return backup_path

    # -- top level ----------------------------------------------------------

    def version(self) -> Optional[int]:
        raw = self.root.get("version")
        return int(raw) if raw is not None and raw.isdigit() else None

    @property
    def _settings(self) -> Optional[ElementTree.Element]:
        return self.root.find("settings")

    def startup_mode(self) -> Optional[str]:
        settings = self._settings
        if settings is None:
            return None
        return _local_text(settings, "startup-mode")

    def set_startup_mode(self, mode: str) -> None:
        settings = self._settings
        if settings is None:
            settings = ElementTree.SubElement(self.root, "settings")
        node = settings.find("startup-mode")
        if node is None:
            node = ElementTree.SubElement(settings, "startup-mode")
        node.text = mode

    # -- modes --------------------------------------------------------------

    def modes(self) -> List[ModeInfo]:
        modes_node = self.root.find("modes")
        if modes_node is None:
            return []
        return [
            ModeInfo(name=node.text or "", parent=node.get("parent"))
            for node in modes_node.findall("mode")
        ]

    def mode_names(self) -> List[str]:
        return [mode.name for mode in self.modes()]

    def rename_mode(self, old: str, new: str) -> int:
        """Renames a mode everywhere it is referenced across the profile.

        Updates the mode declaration, any ``parent`` attributes pointing at it,
        every input binding's ``<mode>``, every change-mode ``<target-mode>``,
        and the startup mode. This is intentionally more thorough than
        Gremlin's own rename (which only touches the declaration and input
        bindings), so renaming can never leave a dangling change-mode target.

        Returns:
            The number of references updated (excluding the declaration).
        """
        modes_node = self.root.find("modes")
        if modes_node is None or old not in self.mode_names():
            raise ProfileError(f"mode '{old}' does not exist")
        if new in self.mode_names():
            raise ProfileError(f"mode '{new}' already exists")

        updated = 0
        for node in modes_node.findall("mode"):
            if node.text == old:
                node.text = new
            if node.get("parent") == old:
                node.set("parent", new)
                updated += 1

        inputs = self.root.find("inputs")
        if inputs is not None:
            for inp in inputs.findall("input"):
                mode_node = inp.find("mode")
                if mode_node is not None and mode_node.text == old:
                    mode_node.text = new
                    updated += 1

        # change-mode actions store the target inside <target-mode>.
        for target in self.root.iter("target-mode"):
            for prop in target.findall("property"):
                if _local_text(prop, "name") == "name":
                    value = prop.find("value")
                    if value is not None and value.text == old:
                        value.text = new
                        updated += 1

        if self.startup_mode() == old:
            self.set_startup_mode(new)
            updated += 1

        return updated

    # -- inputs / bindings --------------------------------------------------

    def bindings(self) -> List[Binding]:
        inputs = self.root.find("inputs")
        if inputs is None:
            return []
        result: List[Binding] = []
        for node in inputs.findall("input"):
            root_ids = [
                rid.text
                for cfg in node.findall("action-configuration")
                for rid in cfg.findall("root-action")
                if rid.text is not None
            ]
            result.append(
                Binding(
                    device_id=_local_text(node, "device-id") or "",
                    input_type=_local_text(node, "input-type") or "",
                    input_id=_local_text(node, "input-id") or "",
                    mode=_local_text(node, "mode") or "",
                    root_action_ids=root_ids,
                )
            )
        return result

    # -- library ------------------------------------------------------------

    @property
    def _library(self) -> Optional[ElementTree.Element]:
        return self.root.find("library")

    def library_actions(self) -> Dict[str, ElementTree.Element]:
        """Maps action id to its XML node, in document order."""
        library = self._library
        if library is None:
            return {}
        actions: Dict[str, ElementTree.Element] = {}
        for action in library.findall("action"):
            aid = action.get("id")
            if aid is not None:
                actions[aid] = action
        return actions

    def action_info(self, action: ElementTree.Element) -> ActionInfo:
        return ActionInfo(
            action_id=action.get("id") or "",
            type=action.get("type") or "",
            label=_action_label(action),
        )

    @staticmethod
    def action_references(action: ElementTree.Element) -> List[str]:
        """Returns the ids of every action referenced by this action.

        References live in ``<action-id>`` elements regardless of the container
        (``<actions>``, hat directions, tempo short/long, double-tap
        single/double, ...), so a flat descendant scan captures them all.
        """
        return [ref.text for ref in action.iter("action-id") if ref.text]

    def reachable_actions(self, start_ids: List[str]) -> List[ActionInfo]:
        """Breadth-first walk of the action graph from the given root ids.

        Returns each reachable action exactly once, in discovery order,
        including the starting ids themselves. Dangling references are skipped.
        """
        actions = self.library_actions()
        seen: List[ActionInfo] = []
        visited: set[str] = set()
        queue: List[str] = list(start_ids)
        while queue:
            aid = queue.pop(0)
            if aid in visited:
                continue
            visited.add(aid)
            node = actions.get(aid)
            if node is None:
                continue
            seen.append(self.action_info(node))
            queue.extend(self.action_references(node))
        return seen

    def reachable_action_nodes(
        self, start_ids: List[str]
    ) -> List[ElementTree.Element]:
        """Like :meth:`reachable_actions` but returns the XML nodes themselves."""
        actions = self.library_actions()
        nodes: List[ElementTree.Element] = []
        visited: set[str] = set()
        queue: List[str] = list(start_ids)
        while queue:
            aid = queue.pop(0)
            if aid in visited:
                continue
            visited.add(aid)
            node = actions.get(aid)
            if node is None:
                continue
            nodes.append(node)
            queue.extend(self.action_references(node))
        return nodes

    @staticmethod
    def action_property(action: ElementTree.Element, name: str) -> Optional[str]:
        """Returns the value of a direct ``<property>`` child by name."""
        for prop in action.findall("property"):
            if _local_text(prop, "name") == name:
                return _local_text(prop, "value")
        return None

    @staticmethod
    def set_action_property(
        action: ElementTree.Element,
        name: str,
        value: str,
        prop_type: str = "string",
    ) -> None:
        """Sets a direct ``<property>`` value, creating the property if needed."""
        for prop in action.findall("property"):
            if _local_text(prop, "name") == name:
                value_node = prop.find("value")
                if value_node is None:
                    value_node = ElementTree.SubElement(prop, "value")
                value_node.text = value
                return
        prop = ElementTree.SubElement(action, "property")
        prop.set("type", prop_type)
        name_node = ElementTree.SubElement(prop, "name")
        name_node.text = name
        value_node = ElementTree.SubElement(prop, "value")
        value_node.text = value

    def delete_mode(self, mode_name: str) -> int:
        """Removes a mode: reparents its children and drops its bindings.

        Mirrors Gremlin's own ``ModeHierarchy.delete_mode`` — children are
        re-attached to the deleted mode's parent, and every input binding in the
        mode is removed. change-mode actions that targeted the mode and the
        startup mode are left untouched here; the caller is expected to surface
        those so they can be addressed.

        Returns:
            The number of input bindings removed.
        """
        modes_node = self.root.find("modes")
        if modes_node is None:
            raise ProfileError("profile has no <modes> element")
        target = None
        for node in modes_node.findall("mode"):
            if node.text == mode_name:
                target = node
                break
        if target is None:
            raise ProfileError(f"mode '{mode_name}' does not exist")

        parent_name = target.get("parent")
        # Reparent direct children onto the deleted mode's parent.
        for node in modes_node.findall("mode"):
            if node.get("parent") == mode_name:
                if parent_name is None:
                    if "parent" in node.attrib:
                        del node.attrib["parent"]
                else:
                    node.set("parent", parent_name)
        modes_node.remove(target)

        # Drop input bindings belonging to the deleted mode.
        removed = 0
        inputs = self.root.find("inputs")
        if inputs is not None:
            for inp in list(inputs.findall("input")):
                mode_child = inp.find("mode")
                if mode_child is not None and mode_child.text == mode_name:
                    inputs.remove(inp)
                    removed += 1
        return removed

    @staticmethod
    def direct_child_ids(action: ElementTree.Element) -> List[str]:
        """Returns the ids in this action's ``<actions>`` container, in order.

        Used for the root response-curve ordering check, which is about the
        immediate child sequence of an axis root rather than the full graph.
        """
        container = action.find("actions")
        if container is None:
            return []
        return [ref.text for ref in container.findall("action-id") if ref.text]
