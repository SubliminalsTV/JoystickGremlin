# Joystick Gremlin — SubliminalsTV Build

My playground build of Joystick Gremlin. This one tracks WhiteMagic's **in-progress `kobold-style` branch** — the ground-up replacement for Gremlin's old Qt Universal look — so it's a preview of where the official UI is heading, not a copy of any release. You'll know you're running it by the SubliminalsTV logo and **"Experimental"** badge in the top-right of the toolbar.

The trade-off's simple, and it's steeper than usual this time: you're running an unreleased UI rewrite that WhiteMagic is still actively changing. Want rock-solid? Run the official **R15**. Want an early look at the new interface and don't mind rough edges? This is for you.

## What's different
- **The new Kobold UI** — a custom Qt Quick style replacing Universal. Much denser and less space-hungry, with themes (Light, Dark, Zenburn) and 100/150/200% UI scaling in Settings.
- **Minimize to system tray** — optional, off by default. Also an optional "close hides to tray".
- **Offline profile CLI** (`gremlin_cli.py`) for inspecting and editing profile XML without launching the app.
- Keeps its **own settings directory**, so it never stomps on the official build's config or profiles.

> Don't run this and the official build at the same time — they both grab the vJoy devices. Pick one, close it, then start the other.

## Known rough edges
- The title bar still reports **R14.3**. The Kobold branch was cut just before the R15 version bump; it's cosmetic.
- Drag & drop of actions is a prototype on WhiteMagic's side and only partly works.

## Get it
Grab the latest from [Releases](https://github.com/SubliminalsTV/JoystickGremlin/releases), extract it, and run `joystick_gremlin_playground.exe` from the folder. If you use HidHide to hide your physical sticks, whitelist that `.exe` so they show up.

## Contributing
I'm not taking contributions here — this is just my testing bench. If you've got a feature or fix for Joystick Gremlin, take it straight to [WhiteMagic's repo](https://github.com/WhiteMagic/JoystickGremlin). That's the real project; I'm just tinkering on top of it.

Built on Joystick Gremlin by WhiteMagic. GPL-3.0-only.
