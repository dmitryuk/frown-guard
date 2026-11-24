"""
macOS menu bar (status item) integration for the Tkinter app, built on PyObjC.

Tk's Aqua event loop already drives NSApplication, so an NSStatusItem created
here receives clicks without any extra run loop. Menu actions arrive as PyObjC
callbacks *inside* Tk's event processing; calling back into tkinter from there
can corrupt _tkinter's thread state, so actions are only queued here and the
app drains them from its regular `root.after` poll.
"""
import queue
from typing import Dict, Optional, Tuple

import objc
from AppKit import (
    NSApplication,
    NSColor,
    NSImage,
    NSImageSymbolConfiguration,
    NSMenu,
    NSMenuItem,
    NSStatusBar,
    NSVariableStatusItemLength,
)
from Foundation import NSActivityUserInitiatedAllowingIdleSystemSleep, NSObject, NSProcessInfo

NSApplicationActivationPolicyRegular = 0
NSApplicationActivationPolicyAccessory = 1

# tracker_state -> (SF Symbol name, tint as NSColor selector name or None for template/monochrome)
_STATE_ICONS: Dict[str, Tuple[str, Optional[str]]] = {
    "relaxed": ("checkmark.circle.fill", "systemGreenColor"),
    "warning": ("exclamationmark.circle.fill", "systemOrangeColor"),
    "frowning": ("exclamationmark.triangle.fill", "systemRedColor"),
    "paused": ("pause.circle", None),
    "no_face": ("eye.slash", None),
    "searching": ("eye", None),
    "no_cam": ("video.slash", None),
}


class FrownGuardMenuTarget(NSObject):
    """Receives NSMenuItem actions and forwards them as strings to a Python queue."""

    def initWithQueue_(self, commands):
        self = objc.super(FrownGuardMenuTarget, self).init()
        if self is None:
            return None
        self.commands = commands
        return self

    def showSettings_(self, sender):
        self.commands.put("show")

    def toggleMonitoring_(self, sender):
        self.commands.put("toggle_monitoring")

    def toggleLogin_(self, sender):
        self.commands.put("toggle_login")

    def quitApp_(self, sender):
        self.commands.put("quit")


class MacMenuBar:
    def __init__(self, login_supported: bool) -> None:
        self.commands: "queue.Queue[str]" = queue.Queue()
        self.app = NSApplication.sharedApplication()

        # Keep timers running at full rate while no window is visible (App Nap would throttle them).
        self._activity = NSProcessInfo.processInfo().beginActivityWithOptions_reason_(
            NSActivityUserInitiatedAllowingIdleSystemSleep, "Monitoring facial expression via webcam"
        )

        self._target = FrownGuardMenuTarget.alloc().initWithQueue_(self.commands)
        self.status_item = NSStatusBar.systemStatusBar().statusItemWithLength_(NSVariableStatusItemLength)

        menu = NSMenu.alloc().init()
        menu.setAutoenablesItems_(False)

        self.status_line = self._add(menu, "", None)
        self.status_line.setEnabled_(False)
        menu.addItem_(NSMenuItem.separatorItem())
        self.show_item = self._add(menu, "", "showSettings:")
        self.pause_item = self._add(menu, "", "toggleMonitoring:")
        self.login_item: Optional[NSMenuItem] = None
        if login_supported:
            menu.addItem_(NSMenuItem.separatorItem())
            self.login_item = self._add(menu, "", "toggleLogin:")
        menu.addItem_(NSMenuItem.separatorItem())
        self.quit_item = self._add(menu, "", "quitApp:", key="q")

        self.status_item.setMenu_(menu)
        self._menu = menu
        self._icon_state: Optional[str] = None
        self.set_state("searching", "")

    def _add(self, menu: NSMenu, title: str, action: Optional[str], key: str = "") -> NSMenuItem:
        item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_(title, action, key)
        if action:
            item.setTarget_(self._target)
        menu.addItem_(item)
        return item

    def set_labels(self, show: str, quit_: str, login: str) -> None:
        self.show_item.setTitle_(show)
        self.quit_item.setTitle_(quit_)
        if self.login_item is not None:
            self.login_item.setTitle_(login)

    def set_monitoring(self, active: bool, pause_label: str, resume_label: str) -> None:
        self.pause_item.setTitle_(pause_label if active else resume_label)

    def set_login_checked(self, checked: bool) -> None:
        if self.login_item is not None:
            self.login_item.setState_(1 if checked else 0)

    def set_state(self, state: str, text: str) -> None:
        """Updates the status line text and, when the state changes, the menu bar icon."""
        self.status_line.setTitle_(text)
        if state == self._icon_state:
            return
        self._icon_state = state
        symbol, tint = _STATE_ICONS.get(state, _STATE_ICONS["searching"])
        button = self.status_item.button()
        image = NSImage.imageWithSystemSymbolName_accessibilityDescription_(symbol, "Frown Guard")
        if image is None:
            button.setImage_(None)
            button.setTitle_("FG")
            return
        if tint:
            # Bake the colour into the symbol; template images are always drawn
            # monochrome by the menu bar, so tinting them is unreliable.
            color = getattr(NSColor, tint)()
            # Palette: white glyph detail (e.g. the "!"), coloured shape behind it
            config = NSImageSymbolConfiguration.configurationWithPaletteColors_([NSColor.whiteColor(), color])
            image = image.imageWithSymbolConfiguration_(config)
            image.setTemplate_(False)
        else:
            image.setTemplate_(True)
        button.setTitle_("")
        button.setContentTintColor_(None)
        button.setImage_(image)

    def show_dock_icon(self, visible: bool) -> None:
        """Regular app (Dock icon, app menu) while the window is open; menu-bar-only otherwise."""
        if visible:
            self.app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
            if self.app.respondsToSelector_("activate"):
                self.app.activate()  # macOS 14+ cooperative activation
            else:
                self.app.activateIgnoringOtherApps_(True)
        else:
            self.app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)

    def drain(self):
        """Yields queued menu commands (call from the Tk thread)."""
        while True:
            try:
                yield self.commands.get_nowait()
            except queue.Empty:
                return


def create(login_supported: bool) -> Optional[MacMenuBar]:
    try:
        return MacMenuBar(login_supported)
    except Exception as e:
        print(f"Menu bar integration unavailable: {e}")
        return None
