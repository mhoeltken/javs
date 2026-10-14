# SPDX-License-Identifier: Apache-2.0
"""Robustness tests for the tray logic without a display (GTK widgets are replaced)."""

from types import SimpleNamespace

import pytest

try:
    from javs import tray
except (ImportError, ValueError) as exc:  # GTK/AppIndicator not installed
    pytest.skip(f"GTK not available: {exc}", allow_module_level=True)

from javs import core


def bare_tray():
    """JavsTray without __init__ (no indicator, no display needed)."""
    t = object.__new__(tray.JavsTray)
    t.busy = False
    t.poll = "medium"
    t.active_name = None
    t._timer = None
    t._menu_key = None
    t.badge = core.badge_for()
    return t


def test_tick_reschedules_even_when_refresh_raises():
    t = bare_tray()
    scheduled = []

    def broken_refresh():
        raise OSError("cache not writable")

    t._refresh = broken_refresh
    t._schedule = lambda: scheduled.append(True)

    assert t._tick() is False
    assert scheduled == [True]


def test_refresh_turns_unexpected_errors_into_err_badge():
    t = bare_tray()
    shown = []
    t.indicator = SimpleNamespace(set_menu=shown.append)
    t._draw_badge = lambda: None
    t._build_menu = lambda names, error: ("menu", error)

    def boom():
        raise RuntimeError("boom")

    # nm is replaced via attributes so that no real nmcli runs
    original = (tray.nm.list_vpns, tray.nm.active_vpn)
    tray.nm.list_vpns = boom
    tray.nm.active_vpn = lambda: None
    try:
        t._refresh()
    finally:
        tray.nm.list_vpns, tray.nm.active_vpn = original

    assert t.badge == core.Badge("ERR", core.ERROR)
    assert shown == [("menu", "boom")]


def test_action_done_resets_busy_and_reschedules_even_if_refresh_raises():
    t = bare_tray()
    t.busy = True
    scheduled = []

    def broken_refresh():
        raise OSError("broken")

    t._refresh = broken_refresh
    t._schedule = lambda: scheduled.append(True)

    assert t._action_done(None) is False
    assert t.busy is False
    assert scheduled == [True]


def test_worker_failure_does_not_leave_tray_busy(monkeypatch):
    t = bare_tray()
    t._refresh = lambda: None
    t._schedule = lambda: None
    notified = []
    monkeypatch.setattr(tray, "notify", lambda summary, body="": notified.append((summary, body)))
    monkeypatch.setattr(tray, "GLib", SimpleNamespace(idle_add=lambda func, *args: func(*args)))

    class InlineThread:
        def __init__(self, target, daemon=None):
            self._target = target

        def start(self):
            self._target()

    monkeypatch.setattr(tray, "threading", SimpleNamespace(Thread=InlineThread))

    def boom():
        raise RuntimeError("unexpected")

    t._run_action(boom)

    assert t.busy is False
    assert len(notified) == 1
    assert "unexpected" in notified[0][1]
