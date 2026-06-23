# Joystick Gremlin — SubliminalsTV Build

My playground build of Joystick Gremlin, based on **R14.3**. This is where I test features I'm considering pushing toward the official build — if something proves itself here, it goes upstream to WhiteMagic as a proper PR. You'll know you're running it by the SubliminalsTV logo and **"Experimental Features"** badge in the top-right of the toolbar.

The trade-off's simple: you get to try new stuff early, at the cost of some stability. Want rock-solid? Run WhiteMagic's official R14.3. Want to poke at what might be coming and don't mind the occasional rough edge? This is for you.

## What's different from R14.3
- **Light / Dark / High Contrast Dark** themes — switch live, no restart
- **Minimize to system tray** — optional, off by default
- **Play Sound / Text-to-Speech** work in the packaged build
- **Offline profile CLI** (`gremlin_cli.py`) for inspecting and editing profile XML
- Runs **side-by-side** with the official build (isolated settings)

## Get it
Grab the latest from [Releases](https://github.com/SubliminalsTV/JoystickGremlin/releases), extract it, and run `joystick_gremlin_playground.exe` from the folder. If you use HidHide to hide your physical sticks, whitelist that `.exe` so they show up.

## Contributing
I'm not taking contributions here — this is just my testing bench. If you've got a feature or fix for Joystick Gremlin, take it straight to [WhiteMagic's repo](https://github.com/WhiteMagic/JoystickGremlin). That's the real project; I'm just tinkering on top of it.

Built on Joystick Gremlin by WhiteMagic. GPL-3.0-only.
