# Joystick Gremlin CLI

A command-line tool for **inspecting and editing Joystick Gremlin profile XML
files** from the terminal — without opening the graphical app.

It is an *offline* tool: it reads and edits the profile files on disk and can
launch the GUI, but it does **not** reach into an already-running Gremlin
process. (Gremlin has no way to be commanded from outside while it runs.)

## Why it exists / how it works

The normal Joystick Gremlin program is a full Windows GUI app. This CLI lets you
do common profile chores — check what's in a profile, list its modes and
bindings, sanity-check its structure, fix a few common problems — quickly from a
terminal or a script.

It works directly on the profile's raw XML, and deliberately avoids loading
Gremlin's full in-memory model (which would drag in the entire Qt/QML interface
layer). The upshot:

- **No window ever opens.** It runs instantly and headlessly.
- **It only needs plain Python** — no PySide6/Qt install required.
- It is safe to run while the GUI is open (see the warning below).

## Running it

From the repository root:

```
py gremlin_cli.py <command> [options]
py gremlin_cli.py --help
py gremlin_cli.py <command> --help
```

## Commands

### Read-only (never change your file)

| Command | What it does |
|---|---|
| `info <profile>` | One-screen summary: version, modes, devices, binding count, and a breakdown of the library actions by type. |
| `modes <profile>` | The mode list drawn as a parent/child tree, with the startup mode flagged `*`. |
| `bindings <profile>` | Every physical input and the action(s) it triggers. Filter with `--mode <name>` and/or `--device <guid-or-name>`. |
| `validate <profile>` | Structural health check (see below). Exits non-zero if it finds errors — handy in scripts. |
| `diff <base> <other>` | Structural comparison of two profiles: which modes, bindings, and startup mode differ. |
| `keyboard-keys <profile>` | Every keyboard key the profile binds (via Map to Keyboard actions), with the physical input and mode that triggers it. |
| `vjoy-usage <profile>` | Which vJoy device/slot each input drives, plus the slots in use and the lowest free button — handy before picking a slot for a new bind. |
| `tree <profile>` | The **full action tree** for an input — tempo (short/hold), double-tap, chain, condition, hat directions, macros, all of it, indented. Filter with `--input-id`, `--input-type`, `--device`, `--mode`. Names every action type it meets, even ones with no dedicated view. |
| `tempos <profile>` | Every tempo action: the input, its hold threshold, and the short-press vs hold branches. |
| `macros <profile>` | Every macro and its steps (key presses, pauses, vJoy taps, mouse, logical-device). |
| `mouse <profile>` | Map to Mouse bindings (direction, mode, speed). |
| `sounds <profile>` | Play Sound and Text to Speech actions — **flags Play Sound files missing on disk** (the stale-wav-path distribution gotcha). |
| `axis-config <profile>` | Per axis: response curve (identity / inverted / custom) + deadzone, plus split / merge / delta / dual-deadzone processing. |
| `descriptions <profile>` | Dumps the chart-bridge `description` text per input (the backbone of the three-way audit). |

All accept `--json` for machine-readable output (where output is tabular).

> **Disambiguating an input:** an input id like `1` can exist as an axis *and* a
> button *and* a hat at once. Commands that target one input (`tree`,
> `set-description`, `set-tempo-threshold`, `set-vjoy`) take `--input-type
> axis|button|hat` to pin it down.

> `keyboard-keys` resolves scan codes using the standard US layout for letters,
> digits, and punctuation; special keys (F-keys, numpad, modifiers, nav block)
> use Gremlin's own names. It reads Map to Keyboard actions, not keys pressed
> from inside macros.

### Editing (change the file — always backs up first)

| Command | What it does |
|---|---|
| `set-startup-mode <profile> <mode>` | Pins which mode the profile starts in. Refuses a mode that isn't declared. |
| `rename-mode <profile> <old> <new>` | Renames a mode **everywhere** it's referenced — the declaration, parent links, every binding, every change-mode target, and the startup mode. |
| `fix-library-order <profile>` | Reorders the `<library>` so every action is defined before anything that references it (clears "forward reference" warnings). |
| `remove-orphans <profile>` | Deletes library actions that no input can reach (dead weight left behind by earlier edits). |
| `flip-axis <profile> --input-id N` | Inverts an axis by mirroring its response curve (same as Gremlin's **Invert Curve** button). Needs the axis to already have a response curve. `--device` / `--mode` narrow the target. |
| `set-vjoy <profile> --input-id N --from-button J --to-button K` | Retargets which vJoy button a physical input drives. **Joystick Gremlin side only** — see the warning below. |
| `delete-mode <profile> <mode>` | Removes a mode: its children reparent to its parent, and its bindings are dropped. Refuses to delete the startup mode. |
| `set-description <profile> --input-id N "text"` | Sets the chart-bridge description for an input. Updates an existing one, or creates one placed correctly (after the response-curve on axes, first on buttons) and wired into the library. |
| `set-label <profile> --action-id ID --label "text"` | Sets any action's display label. Warns past ~100 chars, refuses past 150 (JG's UI truncates). |
| `set-tempo-threshold <profile> --input-id N <seconds>` | Retunes a tempo's hold timing on the targeted input. |

> **`set-vjoy` only changes the Gremlin profile** (physical button → vJoy slot).
> The Star Citizen layout XML still maps the *old* vJoy slot to the game action,
> so after a `set-vjoy` you must update the layout XML separately or the in-game
> bind moves to the wrong button. The command prints this reminder when it runs.

> **`delete-mode`** leaves any change-mode action that targeted the deleted mode
> pointing at nothing; it warns you, and `validate` will list them so you can fix
> or remove them.

Editing commands share two safety options:

- `--dry-run` — show exactly what *would* change, write nothing.
- `--no-backup` — skip the automatic `*.bak-<timestamp>` copy (on by default).

### Launching the GUI

| Command | What it does |
|---|---|
| `run [profile]` | Starts the normal Joystick Gremlin GUI. Optional flags: `--enable` (activate on launch), `--minimized`, `--dry-run` (print the launch command only). |

## What `validate` checks

- Profile version is the expected one (14).
- No duplicate library action IDs.
- No references to actions that don't exist (dangling links).
- No "forward references" (an action used before it's defined) — *warning*,
  fixable with `fix-library-order`.
- On axis inputs, the response-curve comes **before** the output mapping
  (otherwise the curve silently does nothing).
- The startup mode and every binding's mode are actually declared.
- change-mode actions don't target a deleted mode.
- Flags library actions nothing reaches — *info*, cleanable with
  `remove-orphans`.

## Important: editing while the GUI is open

Joystick Gremlin loads a profile into memory and only writes it back to disk when
**you press Save in the GUI**. So if you edit a file with this CLI while Gremlin
is open:

1. Gremlin won't see your change until you reload the profile, **and**
2. if you then press Save in the GUI, it will **overwrite** your CLI edit.

The safe pattern is to edit with Gremlin closed (or reload-after-edit and don't
Save in the GUI). The editing commands print a warning if they detect Gremlin
running.

## File format

Editing commands rewrite the file in Gremlin's own canonical format (UTF-8 with
a BOM, four-space indentation, LF line endings) — byte-for-byte the same as what
the GUI produces when it saves. A profile saved by this CLI and one saved by the
GUI are interchangeable.

## Running the tests

The CLI has its own test suite at `test/cli/test_cli.py`. Because the CLI never
loads the Qt/QML interface, these tests need **only Python and pytest** — not
the heavier GUI dependencies (PySide6) the rest of the project's tests require.

In the normal Poetry dev environment (where everything is installed), the whole
suite runs the usual way:

```
py -m pytest test/cli/
```

On a bare Python install without the GUI dependencies, skip the project's
Qt-loading shared test setup with `--noconftest`:

```
py -m pytest --noconftest test/cli/test_cli.py
```

## Examples

```
# Look before you touch
py gremlin_cli.py info  "Profiles/My Stick [R14].xml"
py gremlin_cli.py modes "Profiles/My Stick [R14].xml"

# Sanity-check before shipping a profile
py gremlin_cli.py validate "Profiles/My Stick [R14].xml"

# Preview an edit, then apply it
py gremlin_cli.py rename-mode "Profiles/My Stick [R14].xml" "Aux Mode" "Auxiliary" --dry-run
py gremlin_cli.py rename-mode "Profiles/My Stick [R14].xml" "Aux Mode" "Auxiliary"

# See what changed between two versions of a profile
py gremlin_cli.py diff "old.xml" "new.xml"

# Launch the GUI with this profile, already activated
py gremlin_cli.py run "Profiles/My Stick [R14].xml" --enable
```
