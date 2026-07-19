# theme-system — working notes

> Auto-generated working notes. See `theme-system.md` for the actual design.

Feature: replace Joystick Gremlin's single `dark-mode` boolean with a
data-driven UI **theme** system (a registry of named themes selectable from a
dropdown). Doc targets **upstreaming to WhiteMagic/JoystickGremlin**. Already
prototyped and working in Sub's playground build.

## Locked decisions (from the user, pre-interview)

- **Motivation:** WhiteMagic closed the old 3-mode PR (#778) citing the "0, 1, N"
  rule — don't hardcode 2-or-3 modes; make it open-ended. Theme = data, adding a
  theme = a data entry.
- **"Pure" theming:** route ALL widgets through the app's `Style` singleton so no
  widget reads Qt `Universal` colors directly → fully consistent theming. (User
  chose "pure" over the pragmatic partial approach.)
- **Built-ins only for now:** Light, Dark (#0d0d0d slate), High Contrast
  (black/white, accent = same default blue as Dark). No user-defined themes yet,
  but the Python data model must leave room for it later (the "N").
- **Migration required:** existing users have `dark-mode` set; map it to a theme.

## Grounding findings (from prototype + code exploration)

- Palette hub is `qml/Style.qml` (singleton, registered in `joystick_gremlin.py`
  via `qmlRegisterSingletonType` under module `Gremlin.Style`, ~line 524). Today
  it derives the whole palette from one `isDarkMode` bool + Qt's Universal
  Light/Dark + accent.
- `Style.qml` computes: accent, theme (Universal.Dark/Light), background,
  foreground, backgroundShade, lowColor, medColor, error, warning. The
  background/foreground use a swap trick: within Style's singleton context
  Universal.theme is the default (Light), so `background = Universal.foreground`
  synthesizes a dark surface. (Overriding background explicitly bypasses this.)
- `qml/Main.qml`: `Universal.theme: Style.theme`, `color: Style.background`;
  applies theme in `Component.onCompleted` and re-applies on `signal.onConfigChanged`
  (the live-refresh from merged PR #781). Prototype changed both to
  `Style.currentTheme = backend.currentTheme`.
- `qml/ColorInformation.qml`: exposes Universal accent/background/foreground +
  isDarkTheme to Python (`ColorInformation` in gremlin/ui/util.py); used by
  action_image_generator.py to pen action glyphs (merged PR #780).
- Config: options auto-render from their PropertyType. A `Selection` option with
  `{valid_options: [...]}` renders as a dropdown (`qml/ConfigGroup.qml:216`,
  `model: properties.valid_options`). Same pattern as `device-change-behavior`.
- Config registration in `joystick_gremlin.py::register_config_options()`.
- `backend.useDarkMode` (gremlin/ui/backend.py) previously read the `dark-mode`
  config; consumed only by Main.qml.

## Prototype as-built (playground commit ae41f6c6)

- NEW `gremlin/ui/themes.py`: `THEMES` list of records
  `{name, dark, accent, background, foreground}` ("" = use Universal default),
  `DEFAULT_THEME = "Dark"`, `theme_names()`, `theme_by_name()`.
- `backend.py`: `currentTheme` QVariantMap property (selected record);
  `useDarkMode` now derives from `currentTheme["dark"]`.
- `joystick_gremlin.py`: `dark-mode` Bool option replaced by `theme` Selection
  (valid_options = theme_names()).
- `Style.qml`: `currentTheme` property + `_pick(override, fallback)`; palette
  reads overrides, falls back to Universal defaults.
- `Main.qml`: applies `backend.currentTheme` on load + on config change.
- KNOWN GAP (the reason for "pure"): many widgets read `Universal.<color>`
  directly, so custom backgrounds aren't honored everywhere yet. Survey in
  progress to scope routing everything through Style.

## Explorer survey: Universal color usage (scopes the "pure" work)

qml/ = 78 files. Only **9 widget files read `Universal.<color>` directly**;
theme-driving (13 files) already flows through `Style.theme`. `Style.` color
reads are already widespread (~35 files) — the app is *mostly* Style-themed
already.

- 12 distinct `Universal.<color>` props read by widgets. **3 map 1:1 to existing
  Style props**: `Universal.accent/background/foreground` -> `Style.accent/background/foreground`.
- **9 have no Style equivalent** — Universal's base/chrome grey ramp:
  `baseLow/baseMedium/baseMediumHigh/baseHigh`, `chromeLow/chromeMediumLow/chromeMedium/chromeHigh/chromeWhite`.
  Existing `Style.lowColor`/`medColor` are close-in-spirit greys but only 2 stops.
- Concentrated in 3 files: `CompactSwitchIndicator.qml` (6 of 9),
  `OptionEntryCard.qml` (chromeLow/chromeMedium), `HintsTooltip.qml`
  (chromeMediumLow/chromeHigh); plus scattered `chromeMediumColor` one-liners in
  `ConfigSectionButton.qml`, `InputButton.qml`, `Main.qml:401`, `OptionEntryCard.qml`.
- `Universal.Dark/Light` enum reads outside Style only in `CompactSwitchIndicator.qml:30`
  and `ColorInformation.qml:18`.

**"Pure" mechanism (recommended):** add the ~9 base/chrome ramp slots to
`Style.qml` (defined with Universal fallbacks, exactly like `accent`/`background`/
`foreground` already are), then rewire the 9 widget files' `Universal.<color>`
reads to `Style.<color>`. Widgets stop reading Universal; Style is the single
source; a theme can override any slot. Style keeps `import ...Universal` for the
fallbacks — Universal is removed from the *widgets*, not the singleton. Effort:
small, ~9 files, 3 of them the real work.

## Search tree  (resolved / current / pending)

- RESOLVED: motivation; theme = Python data; built-ins only; migration needed;
  Selection-dropdown UI; live-apply path.
- CURRENT: the "pure" mechanism — how to make every widget follow Style
  (Universal-cascade vs replace-all-Universal-refs); what new Style color slots
  are needed. (Explorer survey running.)
- PENDING: theme record schema finalization (do we need more color slots for
  "pure"?); migration mapping (dark-mode -> theme); default theme; error/edge
  handling (unknown theme name, missing override); testing strategy; rollout.

## Open questions for the user — RESOLVED

- Migration: old `dark-mode == true` -> "Dark", `false` -> "Light". CONFIRMED.
- Upstream default theme: **Light** (matches current behavior; opt-in). CONFIRMED.
  (Playground keeps DEFAULT_THEME = "Dark".)
- Doc location: `docs/design/`. CONFIRMED.

## Synthesis — DONE

Final doc written: `docs/design/theme-system.md` (11 sections per outline).
All branches resolved. "Pure" mechanism = add ~9 base/chrome ramp slots to
Style + repoint 9 widget files (3 are the bulk). Stopped at the document per the
skill; implementation is a separate session.
