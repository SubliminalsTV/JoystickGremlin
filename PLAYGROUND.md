# Joystick Gremlin — SubliminalsTV Playground Build

An experimental build of [Joystick Gremlin](https://github.com/WhiteMagic/JoystickGremlin)
(by WhiteMagic) maintained by **SubliminalsTV**, based on the **R14.3** release.

You can tell you're running this build by the **SubliminalsTV logo + bold
"Experimental Features" badge** in the top-right of the main toolbar. (If you're
helping someone in Discord and you see that badge, they're on this build — not
the official one.)

> ⚠️ **Experimental / unofficial.** This is a personal playground for trying ideas
> ahead of (and on top of) the official app. For the stable, supported version use
> WhiteMagic's official **R14.3**. Several of the features below are being
> contributed back upstream — see [Upstreaming](#upstreaming).

## What this build adds over R14.3

### Light / Dark / High Contrast Dark themes — switch live
A `Color mode` option (Settings) with three palettes — **Light**, **Dark** (soft
charcoal), and **High Contrast Dark** (the original pure black/white). Switching
applies **immediately**, no restart, and the action-icon glyphs recolour to stay
legible in every theme.

### Minimize to system tray
A `Minimize to tray` option (off by default). When enabled, minimizing the window
hides it to a tray icon instead of leaving it on the taskbar; click the icon to
restore. The tray menu offers profile activate/deactivate and quit, and the icon
reflects whether a profile is currently active.

### Offline profile CLI (`gremlin_cli.py`)
A Qt-free command-line tool for inspecting and editing profile XML without launching
the GUI — info, modes, bindings, validate, diff, tree, and targeted edits (rename
mode, set vJoy, flip axis, set labels/descriptions, and more). It reproduces JG's
exact file serialization, so edited profiles stay byte-compatible. Handy for
maintaining the Curated Bindings profiles in bulk.

### Audio / Text-to-Speech works in the compiled build
The frozen build keeps `Qt6Multimedia`, which the stock packaging strips — so
the **Play Sound** and **Text-to-Speech** actions work in this distributable build
rather than only when run from source.

### Isolated data directory (coexists with other builds)
Honors a `JG_DATA_DIR` environment variable for its config/profiles, so this build
runs side-by-side with the official R14.3 without the two overwriting each other's
settings. (The included launcher points it at its own folder automatically.)

## Upstreaming

These features are being submitted to WhiteMagic's repo as small, focused PRs:

- **Action glyphs follow the theme + live recolour** — [#780](https://github.com/WhiteMagic/JoystickGremlin/pull/780) (merged)
- **Legible inactive tab labels in dark mode** — [#783](https://github.com/WhiteMagic/JoystickGremlin/pull/783) (merged)
- **Apply UI config changes live (no restart)** — [#781](https://github.com/WhiteMagic/JoystickGremlin/pull/781) (open)
- **Minimize to system tray** — [#789](https://github.com/WhiteMagic/JoystickGremlin/pull/789) (open)

The three-mode `Color mode` picker and the profile CLI are fork extensions on top of
that work.

## Credits & license

Built on **[Joystick Gremlin](https://github.com/WhiteMagic/JoystickGremlin)** by
WhiteMagic and licensed **GPL-3.0-only**, the same as upstream. The full
corresponding source for this build is this branch — please support the upstream
project.
