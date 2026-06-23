# -*- coding: utf-8; -*-

# SPDX-License-Identifier: GPL-3.0-only

from __future__ import annotations

from PySide6 import QtGui, QtWidgets

import gremlin.util
from gremlin.config import Configuration
from gremlin.ui.backend import Backend


class SystemTrayIcon:

    """System tray presence for Joystick Gremlin.

    When the minimize-to-tray option is enabled, minimizing the main window
    hides it into the tray instead of the taskbar; it can be restored by
    clicking the tray icon. The tray menu also offers quick profile activation
    and quitting, and the icon reflects whether a profile is currently active.
    """

    def __init__(
        self,
        window: QtGui.QWindow,
        app: QtWidgets.QApplication
    ) -> None:
        """Creates the tray icon and starts watching the window.

        Args:
            window: the main application window to hide and restore
            app: the running application instance (owns the tray icon)
        """
        self._window = window
        self._config = Configuration()
        self._backend = Backend()
        self._notified = False

        self._idle_icon = QtGui.QIcon(gremlin.util.resource_path("gfx/icon.ico"))
        self._active_icon = QtGui.QIcon(
            gremlin.util.resource_path("gfx/icon_active.ico")
        )

        self._tray = QtWidgets.QSystemTrayIcon(self._idle_icon, app)
        self._tray.setToolTip("Joystick Gremlin")
        self._tray.activated.connect(self._on_activated)

        menu = QtWidgets.QMenu()
        menu.addAction("Show Joystick Gremlin").triggered.connect(self.restore)
        menu.addSeparator()
        self._activation_action = menu.addAction("Activate")
        self._activation_action.triggered.connect(
            self._backend.toggleActiveState
        )
        menu.addSeparator()
        menu.addAction("Quit").triggered.connect(self._quit)
        self._menu = menu
        self._tray.setContextMenu(menu)

        self._window.visibilityChanged.connect(self._on_visibility_changed)
        self._backend.activityChanged.connect(self._refresh_activation_state)
        self._refresh_activation_state()

        self._tray.show()

    def restore(self) -> None:
        """Restores and focuses the main window."""
        self._window.showNormal()
        self._window.raise_()
        self._window.requestActivate()

    def _on_visibility_changed(
        self,
        visibility: QtGui.QWindow.Visibility
    ) -> None:
        """Hides the window to the tray when minimized, if the option is set."""
        if visibility == QtGui.QWindow.Visibility.Minimized and \
                self._config.value("global", "general", "minimize-to-tray"):
            self._window.hide()
            self._notify_once()

    def _on_activated(
        self,
        reason: QtWidgets.QSystemTrayIcon.ActivationReason
    ) -> None:
        """Restores the window on a left click or double click of the icon."""
        if reason in (
            QtWidgets.QSystemTrayIcon.ActivationReason.Trigger,
            QtWidgets.QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self.restore()

    def _refresh_activation_state(self) -> None:
        """Keeps the icon and menu label in sync with the activation state."""
        active = self._backend.gremlinActive
        self._activation_action.setText("Deactivate" if active else "Activate")
        self._tray.setIcon(self._active_icon if active else self._idle_icon)

    def _quit(self) -> None:
        """Quits via the window's close path so unsaved changes are flagged."""
        self.restore()
        self._window.close()

    def _notify_once(self) -> None:
        """Shows a one-time hint the first time the window hides to the tray."""
        if self._notified:
            return
        self._notified = True
        self._tray.showMessage(
            "Joystick Gremlin",
            "Still running in the system tray. Click the icon to restore, or "
            "right-click it to quit.",
            self._idle_icon,
        )
