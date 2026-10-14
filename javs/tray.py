#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""JAVS - Just Another VPN Switch: tray switch for NetworkManager VPNs.

Shows a short code of the active VPN connection in the tray (OFF, FRA, LAX, ...)
and lets you switch or disconnect from the menu.
"""

import math
import os
import signal
import subprocess
import sys
import threading
import traceback

import gi

gi.require_version("Gtk", "3.0")
gi.require_version("PangoCairo", "1.0")

try:
    gi.require_version("AyatanaAppIndicator3", "0.1")
    from gi.repository import AyatanaAppIndicator3 as AppIndicator
except (ValueError, ImportError):
    gi.require_version("AppIndicator3", "0.1")
    from gi.repository import AppIndicator3 as AppIndicator

import cairo
from gi.repository import GLib, Gtk, Pango, PangoCairo

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from javs import config, core, nm

APP_ID = "javs-tray"
CONFIG_FILE = config.default_config_path()
CACHE_DIR = os.path.join(GLib.get_user_cache_dir(), "javs")

ICON_HEIGHT = 22
BUSY_INTERVAL_MS = 1000


def make_icon(text, color, path, height=ICON_HEIGHT):
    """Draw `text` on a rounded badge in `color` and save it as PNG."""
    probe = cairo.ImageSurface(cairo.FORMAT_ARGB32, 4, 4)
    ctx = cairo.Context(probe)
    layout = PangoCairo.create_layout(ctx)
    layout.set_text(text, -1)
    font = Pango.FontDescription()
    font.set_family("Sans")
    font.set_weight(Pango.Weight.BOLD)
    font.set_absolute_size(height * 0.78 * Pango.SCALE)
    layout.set_font_description(font)
    text_w, text_h = layout.get_pixel_size()

    pad = max(3, height // 6)
    width = max(height, text_w + 2 * pad)
    radius = height / 3.0

    surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, width, height)
    ctx = cairo.Context(surface)

    ctx.set_source_rgba(*color, 1.0)
    ctx.new_sub_path()
    ctx.arc(width - radius, radius, radius, -math.pi / 2, 0)
    ctx.arc(width - radius, height - radius, radius, 0, math.pi / 2)
    ctx.arc(radius, height - radius, radius, math.pi / 2, math.pi)
    ctx.arc(radius, radius, radius, math.pi, 3 * math.pi / 2)
    ctx.close_path()
    ctx.fill()

    ctx.move_to((width - text_w) / 2.0, (height - text_h) / 2.0)
    ctx.set_source_rgb(1.0, 1.0, 1.0)
    PangoCairo.update_layout(ctx, layout)
    PangoCairo.show_layout(ctx, layout)

    surface.write_to_png(path)


def notify(summary, body=""):
    try:
        subprocess.Popen(
            ["notify-send", "-a", "JAVS", "-i", "network-vpn", "--", summary, body]
        )
    except OSError:
        pass


class JavsTray:
    def __init__(self):
        self.poll = config.load_poll(CONFIG_FILE)
        self.busy = False
        self.active_name = None
        self.badge = core.badge_for()
        self._timer = None
        self._menu_key = None

        self.indicator = AppIndicator.Indicator.new(
            APP_ID, "", AppIndicator.IndicatorCategory.APPLICATION_STATUS
        )
        self.indicator.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        self.indicator.set_menu(Gtk.Menu())
        self._refresh()
        self._schedule()

    # -- Read and display state ---------------------------------------------

    def _refresh(self):
        error = None
        try:
            names = core.sort_vpns(nm.list_vpns())
            active = nm.active_vpn()
        except Exception as exc:  # NmError and anything unexpected: ERR badge instead of a crash
            names, active, error = [], None, str(exc) or exc.__class__.__name__

        self.active_name = active.name if active else None
        self.badge = core.badge_for(
            self.active_name,
            activating=bool(active and active.activating),
            error=error is not None,
            busy=self.busy,
        )
        self._draw_badge()

        key = (tuple(names), self.active_name, error, self.poll, self.busy)
        if key != self._menu_key:
            self._menu_key = key
            self.indicator.set_menu(self._build_menu(names, error))

    def _draw_badge(self):
        text, state = self.badge.text, self.badge.state
        codes = "-".join(f"{ord(char):x}" for char in text)
        path = os.path.join(CACHE_DIR, f"{state}-{codes}.png")
        if not os.path.exists(path):
            os.makedirs(CACHE_DIR, exist_ok=True)
            make_icon(text, core.BADGE_COLORS[state], path)
        self.indicator.set_icon_full(path, f"JAVS: {text}")

    # -- Timer ----------------------------------------------------------------

    def _schedule(self):
        if self._timer is not None:
            GLib.source_remove(self._timer)
        if self.busy or self.badge.state == core.CONNECTING:
            delay = BUSY_INTERVAL_MS
        else:
            delay = config.POLL_INTERVALS_MS[self.poll]
        self._timer = GLib.timeout_add(delay, self._tick)

    def _tick(self):
        self._timer = None
        try:
            self._refresh()
        except Exception:
            traceback.print_exc()
        self._schedule()
        return False

    # -- Menu ---------------------------------------------------------------

    def _build_menu(self, names, error):
        menu = Gtk.Menu()

        if error:
            menu.append(self._info_item(f"NetworkManager: {error}"))
            menu.append(Gtk.SeparatorMenuItem())
        elif not names:
            menu.append(self._info_item("No VPN connections in NetworkManager"))
            menu.append(Gtk.SeparatorMenuItem())

        for name in names:
            item = Gtk.CheckMenuItem(label=name)
            item.set_draw_as_radio(True)
            item.set_active(name == self.active_name)
            item.set_sensitive(not self.busy)
            item.connect("activate", self._on_pick, name)
            menu.append(item)

        if names:
            menu.append(Gtk.SeparatorMenuItem())

        disconnect = Gtk.MenuItem(label="Disconnect")
        disconnect.set_sensitive(self.active_name is not None and not self.busy)
        disconnect.connect("activate", self._on_disconnect)
        menu.append(disconnect)

        menu.append(Gtk.SeparatorMenuItem())
        menu.append(self._build_poll_item())

        quit_item = Gtk.MenuItem(label="Quit")
        quit_item.connect("activate", lambda _item: Gtk.main_quit())
        menu.append(quit_item)

        menu.show_all()
        return menu

    @staticmethod
    def _info_item(label):
        item = Gtk.MenuItem(label=label)
        item.set_sensitive(False)
        return item

    def _build_poll_item(self):
        parent = Gtk.MenuItem(label="Poll interval")
        submenu = Gtk.Menu()
        group = None
        for level, interval_ms in config.POLL_INTERVALS_MS.items():
            label = f"{level} ({interval_ms // 1000} s)"
            radio = Gtk.RadioMenuItem.new_with_label_from_widget(group, label)
            group = group or radio
            radio.set_active(level == self.poll)
            radio.connect("toggled", self._on_poll, level)
            submenu.append(radio)
        parent.set_submenu(submenu)
        return parent

    # -- Actions ------------------------------------------------------------

    def _on_pick(self, _item, name):
        if name == self.active_name:
            self._menu_key = None  # reset the check mark
            self._refresh()
            return
        self._run_action(nm.switch, name)

    def _on_disconnect(self, _item):
        if self.active_name is not None:
            self._run_action(nm.down, self.active_name)

    def _on_poll(self, item, level):
        if not item.get_active() or level == self.poll:
            return
        self.poll = level
        try:
            config.save_poll(CONFIG_FILE, level)
        except OSError as exc:
            notify("JAVS", f"Could not save setting: {exc}")
        self._refresh()
        self._schedule()

    def _run_action(self, func, *args):
        if self.busy:
            return
        self.busy = True
        self._refresh()
        self._schedule()

        def worker():
            error = None
            try:
                func(*args)
            except Exception as exc:  # otherwise `busy` would stay set forever
                error = str(exc) or exc.__class__.__name__
            GLib.idle_add(self._action_done, error)

        threading.Thread(target=worker, daemon=True).start()

    def _action_done(self, error):
        self.busy = False
        if error:
            notify("JAVS: connection failed", error)
        try:
            self._refresh()
        except Exception:
            traceback.print_exc()
        self._schedule()
        return False

    def run(self):
        Gtk.main()


def main():
    signal.signal(signal.SIGINT, signal.SIG_DFL)
    JavsTray().run()


if __name__ == "__main__":
    main()
