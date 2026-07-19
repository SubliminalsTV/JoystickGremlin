// -*- coding: utf-8; -*-
// SPDX-License-Identifier: GPL-3.0-only

pragma Singleton

import QtQuick
import QtQuick.Controls.Universal

Item {
    function removeAlpha(color) {
        return Qt.rgba(color.r, color.g, color.b, 1.0)
    }

    // Picks a theme override when it is set, otherwise the Universal default.
    function _pick(override, fallback) {
        return (override !== undefined && override !== "") ? override : fallback
    }

    // The active theme record (see gremlin/ui/themes.py), applied from Main.qml.
    property var currentTheme: ({"dark": false, "accent": "", "background": "", "foreground": ""})

    property bool isDarkMode: currentTheme.dark === true

    // Color definitions.
    property var accent: _pick(currentTheme.accent, Universal.accent)
    property var theme: isDarkMode ? Universal.Dark : Universal.Light
    property var background: _pick(currentTheme.background, isDarkMode ? Universal.foreground : Universal.background)
    property var foreground: _pick(currentTheme.foreground, isDarkMode ? Universal.background : Universal.foreground)
    property var backgroundShade: isDarkMode ? Qt.tint(background, "#40ffffff") : Qt.tint(foreground, "#b0ffffff")
    property var lowColor: isDarkMode ? Qt.hsva(0.0, 0.0, 0.2, 1.0) : Qt.hsva(0.0, 0.0, 0.8, 1.0)
    property var medColor: isDarkMode ? Qt.hsva(0.0, 0.0, 0.6, 1.0) : Qt.hsva(0.0, 0.0, 0.6, 1.0)

    // Base/chrome grey ramp mirroring the Qt Universal stops, so widgets can
    // read greys from Style instead of reaching into Universal directly. Base
    // stops are the theme foreground at increasing opacity; chrome stops are
    // theme-flipped greys. A theme may override any stop via the matching field.
    property color foregroundColor: foreground
    property var baseLowColor: _pick(currentTheme.baseLowColor, Qt.rgba(foregroundColor.r, foregroundColor.g, foregroundColor.b, 0.2))
    property var baseMediumColor: _pick(currentTheme.baseMediumColor, Qt.rgba(foregroundColor.r, foregroundColor.g, foregroundColor.b, 0.4))
    property var baseMediumHighColor: _pick(currentTheme.baseMediumHighColor, Qt.rgba(foregroundColor.r, foregroundColor.g, foregroundColor.b, 0.6))
    property var baseHighColor: _pick(currentTheme.baseHighColor, Qt.rgba(foregroundColor.r, foregroundColor.g, foregroundColor.b, 0.8))
    property var chromeLowColor: _pick(currentTheme.chromeLowColor, isDarkMode ? Qt.hsva(0.0, 0.0, 0.09, 1.0) : Qt.hsva(0.0, 0.0, 0.91, 1.0))
    property var chromeMediumLowColor: _pick(currentTheme.chromeMediumLowColor, isDarkMode ? Qt.hsva(0.0, 0.0, 0.11, 1.0) : Qt.hsva(0.0, 0.0, 0.94, 1.0))
    property var chromeMediumColor: _pick(currentTheme.chromeMediumColor, isDarkMode ? Qt.hsva(0.0, 0.0, 0.13, 1.0) : Qt.hsva(0.0, 0.0, 0.87, 1.0))
    property var chromeHighColor: _pick(currentTheme.chromeHighColor, isDarkMode ? Qt.hsva(0.0, 0.0, 0.27, 1.0) : Qt.hsva(0.0, 0.0, 0.67, 1.0))
    property var chromeWhiteColor: _pick(currentTheme.chromeWhiteColor, "#ffffff")

    property var error: "#A20025"
    property var warning: "#F0A30A"

    // Spinbox presets.
    property int decimalsPrecise: 4
    property int decimalsStandard: 2

    // Various shared dimensions.
    property int tooltipMaxWidth: 500
    property int tooltipDelayMs: 500
}
