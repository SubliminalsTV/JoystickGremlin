# -*- coding: utf-8; -*-

# SPDX-License-Identifier: GPL-3.0-only

"""Tests for the Joystick Gremlin profile CLI.

These intentionally use only the standard library plus pytest: the CLI never
touches the Qt/QML stack, so the suite runs on a bare Python install without the
GUI dependencies (PySide6, pytest-qt) the rest of the test suite needs.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from gremlin.cli import analysis, keymap, main
from gremlin.cli.model import ProfileDocument, ProfileError

REPO_ROOT = Path(__file__).resolve().parents[2]
PROFILES = REPO_ROOT / "test" / "action_interaction" / "profiles"
REMAP_BASIC = PROFILES / "remap_basic.xml"
MODES = PROFILES / "modes.xml"
KEYBOARD = PROFILES / "map_to_keyboard.xml"
SPLIT_AXIS = PROFILES / "split_axis.xml"
# Minimal profile with a Map to vJoy button mapping (vJoy 1 button 14 on
# physical button 5); the repo fixtures only use map-to-logical-device.
VJOY_SAMPLE = Path(__file__).resolve().parent / "fixtures" / "vjoy_sample.xml"


def _write_vjoy(tmp_path: Path) -> Path:
    return _copy(VJOY_SAMPLE, tmp_path)


def _copy(src: Path, tmp_path: Path) -> Path:
    dst = tmp_path / src.name
    shutil.copy(src, dst)
    return dst


# ---------------------------------------------------------------------------
# Serialization fidelity
# ---------------------------------------------------------------------------

def test_roundtrip_is_byte_identical_modulo_newlines(tmp_path: Path) -> None:
    doc = ProfileDocument.load(REMAP_BASIC)
    out = tmp_path / "out.xml"
    doc.save(out, backup=False)
    original = REMAP_BASIC.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    written = out.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
    assert written == original


def test_writer_emits_bom_and_lf(tmp_path: Path) -> None:
    doc = ProfileDocument.load(REMAP_BASIC)
    out = tmp_path / "out.xml"
    doc.save(out, backup=False)
    raw = out.read_bytes()
    assert raw[:3] == b"\xef\xbb\xbf"  # UTF-8 BOM, as Gremlin writes
    assert b"\r\n" not in raw  # LF line endings, as Gremlin writes


def test_save_creates_backup(tmp_path: Path) -> None:
    target = _copy(REMAP_BASIC, tmp_path)
    doc = ProfileDocument.load(target)
    backup = doc.save(target)
    assert backup is not None and backup.exists()


# ---------------------------------------------------------------------------
# Model accessors
# ---------------------------------------------------------------------------

def test_load_rejects_non_profile(tmp_path: Path) -> None:
    bogus = tmp_path / "bogus.xml"
    bogus.write_text("<notaprofile/>", encoding="utf-8")
    with pytest.raises(ProfileError):
        ProfileDocument.load(bogus)


def test_modes_and_startup() -> None:
    doc = ProfileDocument.load(MODES)
    names = doc.mode_names()
    assert names == ["Default", "Parent", "Child 1", "Child Child 1",
                     "Child 2", "Independant"]
    assert doc.startup_mode() == "Default"


def test_bindings_count_and_resolution() -> None:
    doc = ProfileDocument.load(REMAP_BASIC)
    bindings = doc.bindings()
    assert len(bindings) == 4
    # The axis input resolves to a map-to-logical-device action.
    axis = next(b for b in bindings if b.input_type == "axis")
    actions = [
        info.type
        for info in doc.reachable_actions(axis.root_action_ids)
        if info.type != "root"
    ]
    assert "map-to-logical-device" in actions


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def test_validate_flags_forward_refs_and_orphans() -> None:
    findings = analysis.validate(ProfileDocument.load(REMAP_BASIC))
    messages = [f.message for f in findings]
    assert any("forward reference" in m for m in messages)
    assert any("unreachable" in m for m in messages)
    # remap_basic has issues, but no hard errors.
    assert not any(f.severity == analysis.ERROR for f in findings)


def test_validate_detects_dangling_reference(tmp_path: Path) -> None:
    target = _copy(REMAP_BASIC, tmp_path)
    text = target.read_text(encoding="utf-8-sig")
    # Repoint a real root-action reference at a non-existent action id.
    text = text.replace(
        "039ceeba-9aeb-4c0e-a794-260163903064",
        "00000000-0000-0000-0000-000000000000",
        1,
    )
    target.write_text(text, encoding="utf-8-sig")
    findings = analysis.validate(ProfileDocument.load(target))
    assert any(f.severity == analysis.ERROR for f in findings)


def test_validate_exit_code_is_one_on_error(tmp_path: Path) -> None:
    target = _copy(REMAP_BASIC, tmp_path)
    text = target.read_text(encoding="utf-8-sig").replace(
        "039ceeba-9aeb-4c0e-a794-260163903064",
        "00000000-0000-0000-0000-000000000000",
        1,
    )
    target.write_text(text, encoding="utf-8-sig")
    assert main(["validate", str(target)]) == 1


# ---------------------------------------------------------------------------
# Library graph operations
# ---------------------------------------------------------------------------

def test_orphans_identified_and_removed(tmp_path: Path) -> None:
    target = _copy(REMAP_BASIC, tmp_path)
    assert len(analysis.orphan_ids(ProfileDocument.load(target))) == 3
    assert main(["remove-orphans", str(target), "--no-backup"]) == 0
    assert analysis.orphan_ids(ProfileDocument.load(target)) == []


def test_remove_orphans_dry_run_writes_nothing(tmp_path: Path) -> None:
    target = _copy(REMAP_BASIC, tmp_path)
    before = target.read_bytes()
    assert main(["remove-orphans", str(target), "--dry-run"]) == 0
    assert target.read_bytes() == before


def test_fix_library_order_clears_forward_refs(tmp_path: Path) -> None:
    target = _copy(MODES, tmp_path)
    order, cycle = analysis.topological_order(ProfileDocument.load(target))
    assert not cycle
    assert main(["fix-library-order", str(target), "--no-backup"]) == 0
    findings = analysis.validate(ProfileDocument.load(target))
    assert not any("forward reference" in f.message for f in findings)


# ---------------------------------------------------------------------------
# Mode editing
# ---------------------------------------------------------------------------

def test_rename_mode_updates_every_reference(tmp_path: Path) -> None:
    target = _copy(MODES, tmp_path)
    doc = ProfileDocument.load(target)
    doc.set_startup_mode("Parent")  # make startup a reference too
    updated = doc.rename_mode("Parent", "MainMode")
    doc.save(target, backup=False)

    assert updated >= 1
    assert doc.startup_mode() == "MainMode"
    text = target.read_text(encoding="utf-8-sig")
    assert "MainMode" in text
    assert "Parent" not in text  # no stale capital-P reference anywhere
    # A consistent rename leaves no undeclared-mode warnings.
    findings = analysis.validate(ProfileDocument.load(target))
    assert not any("undeclared" in f.message for f in findings)


def test_set_startup_mode_rejects_unknown(tmp_path: Path) -> None:
    target = _copy(MODES, tmp_path)
    with pytest.raises(SystemExit):
        main(["set-startup-mode", str(target), "DoesNotExist"])


def test_set_startup_mode_applies(tmp_path: Path) -> None:
    target = _copy(MODES, tmp_path)
    assert main(["set-startup-mode", str(target), "Parent", "--no-backup"]) == 0
    assert ProfileDocument.load(target).startup_mode() == "Parent"


# ---------------------------------------------------------------------------
# Diff and launcher
# ---------------------------------------------------------------------------

def test_diff_reports_identical(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["diff", str(REMAP_BASIC), str(REMAP_BASIC)]) == 0
    assert "identical" in capsys.readouterr().out


def test_diff_reports_mode_changes(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = _copy(MODES, tmp_path)
    doc = ProfileDocument.load(target)
    doc.rename_mode("Independant", "Solo")
    doc.save(target, backup=False)
    assert main(["diff", str(MODES), str(target)]) == 0
    out = capsys.readouterr().out
    assert "Solo" in out and "Independant" in out


def test_info_json_payload(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["info", str(MODES), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["version"] == 14
    assert data["binding_count"] == 8
    assert data["startup_mode"] == "Default"


def test_run_dry_run_does_not_launch(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["run", str(REMAP_BASIC), "--dry-run"]) == 0
    assert "launching:" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Keyboard keys
# ---------------------------------------------------------------------------

def test_keymap_resolves_known_scan_codes() -> None:
    assert keymap.key_name(0x25, False) == "K"
    assert keymap.key_name(0x32, False) == "M"
    assert keymap.key_name(0x36, True) == "Right Shift"
    assert keymap.key_name(0x3B, False) == "F1"
    assert keymap.key_name(0xAB, False).startswith("scan:")  # unknown fallback


def test_keyboard_keys_lists_resolved_keys(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["keyboard-keys", str(KEYBOARD)]) == 0
    out = capsys.readouterr().out
    assert "K" in out
    assert "Right Shift + M" in out  # multi-input combo


def test_keyboard_keys_empty_when_none(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["keyboard-keys", str(REMAP_BASIC)]) == 0
    assert "no keyboard bindings" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# vJoy usage and retargeting
# ---------------------------------------------------------------------------

def test_vjoy_usage_reports_slots(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    target = _write_vjoy(tmp_path)
    assert main(["vjoy-usage", str(target), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data[0]["vjoy_id"] == "14"
    assert data[0]["phys_input"] == "button 5"


def test_set_vjoy_retargets_button(tmp_path: Path) -> None:
    target = _write_vjoy(tmp_path)
    rc = main([
        "set-vjoy", str(target),
        "--input-id", "5", "--from-button", "14", "--to-button", "20",
        "--no-backup",
    ])
    assert rc == 0
    doc = ProfileDocument.load(target)
    actions = doc.library_actions()
    node = actions["22222222-2222-2222-2222-222222222222"]
    assert doc.action_property(node, "vjoy-input-id") == "20"


def test_set_vjoy_errors_when_slot_not_found(tmp_path: Path) -> None:
    target = _write_vjoy(tmp_path)
    with pytest.raises(SystemExit):
        main([
            "set-vjoy", str(target),
            "--input-id", "5", "--from-button", "99", "--to-button", "20",
        ])


# ---------------------------------------------------------------------------
# Axis inversion
# ---------------------------------------------------------------------------

def _control_points(path: Path) -> list[str]:
    import re
    text = path.read_text(encoding="utf-8-sig")
    return re.findall(r"<name>point</name>\s*<value>([^<]+)</value>", text)


def test_flip_axis_inverts_control_points(tmp_path: Path) -> None:
    target = _copy(SPLIT_AXIS, tmp_path)
    before = _control_points(target)
    assert main(["flip-axis", str(target), "--input-id", "1", "--no-backup"]) == 0
    after = _control_points(target)
    # Each "x,y" should become "x,-y".
    for original, flipped in zip(before, after):
        ox, oy = original.split(",")
        fx, fy = flipped.split(",")
        assert fx == ox
        assert float(fy) == -float(oy)


def test_flip_axis_errors_without_curve(tmp_path: Path) -> None:
    target = _write_vjoy(tmp_path)  # button-only profile, no axis/curve
    with pytest.raises(SystemExit):
        main(["flip-axis", str(target), "--input-id", "5"])


# ---------------------------------------------------------------------------
# Mode deletion
# ---------------------------------------------------------------------------

def test_delete_mode_reparents_children(tmp_path: Path) -> None:
    target = _copy(MODES, tmp_path)
    assert main(["delete-mode", str(target), "Child 1", "--no-backup"]) == 0
    doc = ProfileDocument.load(target)
    names = [m.name for m in doc.modes()]
    assert "Child 1" not in names
    # 'Child Child 1' was a child of 'Child 1'; it should reparent to 'Parent'.
    child_child = next(m for m in doc.modes() if m.name == "Child Child 1")
    assert child_child.parent == "Parent"


def test_delete_mode_refuses_startup(tmp_path: Path) -> None:
    target = _copy(MODES, tmp_path)
    with pytest.raises(SystemExit):
        main(["delete-mode", str(target), "Default"])


# ---------------------------------------------------------------------------
# Action-tree inspection
# ---------------------------------------------------------------------------

TEMPO = PROFILES / "tempo.xml"
MACRO = PROFILES / "macro.xml"


def test_tree_renders_nested_structure(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["tree", str(MODES), "--input-id", "1", "--input-type", "hat",
                 "--mode", "Parent"]) == 0
    out = capsys.readouterr().out
    assert "hat-buttons" in out
    assert "[North]" in out  # generic slot labelling


def test_tempos_lists_threshold_and_branches(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["tempos", str(TEMPO)]) == 0
    out = capsys.readouterr().out
    assert "tempo, 0.2s" in out
    assert "[short-actions]" in out
    assert "[long-actions]" in out


def test_macros_lists_steps(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["macros", str(MACRO)]) == 0
    out = capsys.readouterr().out
    assert "logical" in out  # logical-device macro steps


def test_axis_config_classifies_curve(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["axis-config", str(SPLIT_AXIS)]) == 0
    out = capsys.readouterr().out
    assert "response-curve:" in out
    assert "deadzone" in out


def test_inspection_commands_handle_absence(
    capsys: pytest.CaptureFixture[str],
) -> None:
    # remap_basic has no macros / mouse / sounds / descriptions.
    for command, marker in [
        ("macros", "no macro"),
        ("mouse", "no Map to Mouse"),
        ("sounds", "no Play Sound"),
        ("descriptions", "no description"),
    ]:
        assert main([command, str(REMAP_BASIC)]) == 0
        assert marker in capsys.readouterr().out


# ---------------------------------------------------------------------------
# Action-level edits
# ---------------------------------------------------------------------------

def test_set_tempo_threshold(tmp_path: Path) -> None:
    target = _copy(TEMPO, tmp_path)
    rc = main([
        "set-tempo-threshold", str(target),
        "--input-id", "1", "--input-type", "button", "0.35", "--no-backup",
    ])
    assert rc == 0
    doc = ProfileDocument.load(target)
    thresholds = [
        doc.action_property(n, "threshold")
        for n in doc.library_actions().values()
        if n.get("type") == "tempo"
    ]
    # tempo.xml has several tempos; only the targeted input's becomes 0.35.
    assert "0.35" in thresholds


def test_set_label_rejects_overlong(tmp_path: Path) -> None:
    target = _copy(TEMPO, tmp_path)
    tempo_id = next(
        aid for aid, n in ProfileDocument.load(target).library_actions().items()
        if n.get("type") == "tempo"
    )
    with pytest.raises(SystemExit):
        main(["set-label", str(target), "--action-id", tempo_id,
              "--label", "x" * 160])


def test_set_description_creates_then_updates(tmp_path: Path) -> None:
    target = _copy(REMAP_BASIC, tmp_path)
    # Create on the axis only (input id 1 also exists as button/hat).
    rc = main(["set-description", str(target), "--input-id", "1",
               "--input-type", "axis", "First text", "--no-backup"])
    assert rc == 0
    doc = ProfileDocument.load(target)
    descs = [n for n in doc.library_actions().values()
             if n.get("type") == "description"]
    assert len(descs) == 1
    assert doc.action_property(descs[0], "description") == "First text"
    # No dangling references introduced.
    assert not any(
        f.severity == analysis.ERROR for f in analysis.validate(doc)
    )
    # Second call updates in place rather than creating a duplicate.
    main(["set-description", str(target), "--input-id", "1",
          "--input-type", "axis", "Second text", "--no-backup"])
    doc2 = ProfileDocument.load(target)
    descs2 = [n for n in doc2.library_actions().values()
              if n.get("type") == "description"]
    assert len(descs2) == 1
    assert doc2.action_property(descs2[0], "description") == "Second text"
