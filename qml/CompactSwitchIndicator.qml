// -*- coding: utf-8; -*-
// SPDX-License-Identifier: GPL-3.0-only

import QtQuick
import QtQuick.Templates as T
import QtQuick.Controls.Universal
import Gremlin.Style

Item {
    id: indicator

    implicitWidth: control.contentItem.font.pixelSize * 2.2
    implicitHeight: control.contentItem.font.pixelSize

    property T.AbstractButton control


    Rectangle {
        id: slot

        width: parent.width
        height: parent.height

        radius: height / 2 //10
        color: !indicator.control.enabled ? "transparent" :
                indicator.control.pressed ? Style.baseMediumColor :
                indicator.control.checked ? Style.accent : "transparent"
        border.color: !indicator.control.enabled ? Style.baseLowColor :
                       indicator.control.checked && !indicator.control.pressed ? Style.accent :
                       indicator.control.hovered && !indicator.control.checked && !indicator.control.pressed ? Style.baseHighColor : Style.baseMediumColor
        opacity: enabled && indicator.control.hovered && indicator.control.checked && !indicator.control.pressed ? (indicator.control.Universal.theme === Universal.Light ? 0.7 : 0.9) : 1.0
        border.width: height < 20 ? 1 : 2
    }

    Rectangle {
        id: circle

        width: 0.6 * slot.height //10
        height: 0.6 * slot.height //10
        radius: height / 2 //5

        color: !indicator.control.enabled ? Style.baseLowColor :
                indicator.control.pressed || indicator.control.checked ? Style.chromeWhiteColor :
                indicator.control.hovered && !indicator.control.checked ? Style.baseHighColor : Style.baseMediumHighColor

        x: indicator.control.visualPosition < 0.5 ? width / 2 : parent.width - 1.5 * width
        y: (parent.height - height) / 2

        Behavior on x {
            enabled: !indicator.control.pressed
            SmoothedAnimation { velocity: 200 }
        }
    }
}
