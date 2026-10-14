# SPDX-License-Identifier: Apache-2.0
import subprocess
from types import SimpleNamespace

import pytest

from javs import nm

LIST_OUTPUT = """\
surfshark-de-fra:vpn
Auto AirAlsie Guest:802-11-wireless
br-c1c4d2b88cfa:bridge
lo:loopback
tun0:tun
home-wg:wireguard
Wired connection 1:802-3-ethernet
"""

ACTIVE_OUTPUT = """\
surfshark-de-fra:vpn:activated
Auto AirAlsie Guest:802-11-wireless:activated
tun0:tun:activated
"""


def stub_run(monkeypatch, output):
    calls = []

    def fake(args, timeout=None):
        calls.append(args)
        return output

    monkeypatch.setattr(nm, "_run", fake)
    return calls


# -- split_terse --------------------------------------------------------------

@pytest.mark.parametrize(
    "line, expected",
    [
        ("a:b", ["a", "b"]),
        ("a:b:c", ["a", "b", "c"]),
        (r"Auto\: x:vpn", ["Auto: x", "vpn"]),
        (r"a\\b:c", ["a\\b", "c"]),
        ("", [""]),
        ("a:", ["a", ""]),
        ("trailing\\", ["trailing\\"]),
    ],
)
def test_split_terse(line, expected):
    assert nm.split_terse(line) == expected


# -- list_vpns ----------------------------------------------------------------

def test_list_vpns_filters_by_type(monkeypatch):
    calls = stub_run(monkeypatch, LIST_OUTPUT)
    assert nm.list_vpns() == ["surfshark-de-fra", "home-wg"]
    assert calls == [["-t", "-f", "NAME,TYPE", "connection", "show"]]


def test_list_vpns_empty_output(monkeypatch):
    stub_run(monkeypatch, "")
    assert nm.list_vpns() == []


def test_list_vpns_unescapes_colons(monkeypatch):
    stub_run(monkeypatch, "my\\:vpn:vpn\nplain:vpn\n")
    assert nm.list_vpns() == ["my:vpn", "plain"]


def test_list_vpns_ignores_malformed_lines(monkeypatch):
    stub_run(monkeypatch, "no-colon-here\n\nok:vpn\n")
    assert nm.list_vpns() == ["ok"]


# -- active_vpn ---------------------------------------------------------------

def test_active_vpn_none_when_only_other_types(monkeypatch):
    stub_run(monkeypatch, "Auto x:802-11-wireless:activated\ntun0:tun:activated\n")
    assert nm.active_vpn() is None


def test_active_vpn_none_on_empty_output(monkeypatch):
    stub_run(monkeypatch, "")
    assert nm.active_vpn() is None


def test_active_vpn_activated(monkeypatch):
    calls = stub_run(monkeypatch, ACTIVE_OUTPUT)
    assert nm.active_vpn() == nm.ActiveVpn("surfshark-de-fra", False)
    assert calls == [["-t", "-f", "NAME,TYPE,STATE", "connection", "show", "--active"]]


def test_active_vpn_activating(monkeypatch):
    stub_run(monkeypatch, "surfshark-de-fra:vpn:activating\n")
    assert nm.active_vpn() == nm.ActiveVpn("surfshark-de-fra", True)


def test_active_vpn_prefers_activated(monkeypatch):
    stub_run(monkeypatch, "new-vpn:vpn:activating\nold-vpn:vpn:activated\n")
    assert nm.active_vpn() == nm.ActiveVpn("old-vpn", False)


def test_active_vpn_ignores_deactivating(monkeypatch):
    stub_run(monkeypatch, "old-vpn:vpn:deactivating\n")
    assert nm.active_vpn() is None


# -- up / down / switch -------------------------------------------------------

def test_up_and_down_use_id_keyword(monkeypatch):
    calls = stub_run(monkeypatch, "")
    nm.up("-weird name")
    nm.down("surfshark-de-fra")
    assert calls == [
        ["connection", "up", "id", "-weird name"],
        ["connection", "down", "id", "surfshark-de-fra"],
    ]


def record_switch_calls(monkeypatch, active):
    calls = []
    monkeypatch.setattr(nm, "active_vpn", lambda: active)
    monkeypatch.setattr(nm, "up", lambda name: calls.append(("up", name)))
    monkeypatch.setattr(nm, "down", lambda name: calls.append(("down", name)))
    return calls


def test_switch_from_nothing_only_connects(monkeypatch):
    calls = record_switch_calls(monkeypatch, None)
    nm.switch("b")
    assert calls == [("up", "b")]


def test_switch_disconnects_old_before_connecting_new(monkeypatch):
    calls = record_switch_calls(monkeypatch, nm.ActiveVpn("a", False))
    nm.switch("b")
    assert calls == [("down", "a"), ("up", "b")]


def test_switch_to_already_active_is_noop(monkeypatch):
    calls = record_switch_calls(monkeypatch, nm.ActiveVpn("a", False))
    nm.switch("a")
    assert calls == []


# -- _run ---------------------------------------------------------------------

def patch_subprocess(monkeypatch, result=None, raises=None):
    seen = {}

    def fake(cmd, **kwargs):
        seen["cmd"] = cmd
        seen["kwargs"] = kwargs
        if raises:
            raise raises
        return result

    monkeypatch.setattr(nm.subprocess, "run", fake)
    return seen


def test_run_returns_stdout_and_forces_utf8_locale(monkeypatch):
    seen = patch_subprocess(
        monkeypatch, SimpleNamespace(returncode=0, stdout="out\n", stderr="")
    )
    assert nm._run(["-t", "connection", "show"]) == "out\n"
    assert seen["cmd"] == ["nmcli", "-t", "connection", "show"]
    # "C" would turn non-ASCII characters in connection names into '?' (glib g_print).
    assert seen["kwargs"]["env"]["LC_ALL"] == "C.UTF-8"
    assert seen["kwargs"]["timeout"] == nm.TIMEOUT_S


def test_run_replaces_undecodable_bytes_instead_of_raising(monkeypatch):
    seen = patch_subprocess(
        monkeypatch, SimpleNamespace(returncode=0, stdout="", stderr="")
    )
    nm._run(["x"])
    assert seen["kwargs"]["errors"] == "replace"


def test_run_accepts_custom_timeout(monkeypatch):
    seen = patch_subprocess(
        monkeypatch, SimpleNamespace(returncode=0, stdout="", stderr="")
    )
    nm._run(["x"], timeout=3)
    assert seen["kwargs"]["timeout"] == 3


def test_reads_use_short_timeout_and_actions_use_default(monkeypatch):
    seen = []

    def fake(args, timeout=nm.TIMEOUT_S):
        seen.append((args[0], timeout))
        return ""

    monkeypatch.setattr(nm, "_run", fake)
    nm.list_vpns()
    nm.active_vpn()
    nm.up("x")
    assert seen == [
        ("-t", nm.READ_TIMEOUT_S),
        ("-t", nm.READ_TIMEOUT_S),
        ("connection", nm.TIMEOUT_S),
    ]
    assert nm.READ_TIMEOUT_S < nm.TIMEOUT_S


def test_run_nmcli_missing(monkeypatch):
    patch_subprocess(monkeypatch, raises=FileNotFoundError())
    with pytest.raises(nm.NmError, match="nmcli not found"):
        nm._run(["x"])


def test_run_nmcli_not_executable(monkeypatch):
    patch_subprocess(monkeypatch, raises=PermissionError("denied"))
    with pytest.raises(nm.NmError, match="not executable"):
        nm._run(["x"])


def test_run_timeout(monkeypatch):
    patch_subprocess(monkeypatch, raises=subprocess.TimeoutExpired("nmcli", 1))
    with pytest.raises(nm.NmError, match="timed out"):
        nm._run(["x"])


def test_run_error_uses_stderr(monkeypatch):
    patch_subprocess(
        monkeypatch, SimpleNamespace(returncode=10, stdout="", stderr="Error: no such connection\n")
    )
    with pytest.raises(nm.NmError, match="no such connection"):
        nm._run(["x"])


def test_run_error_without_message_mentions_exit_code(monkeypatch):
    patch_subprocess(monkeypatch, SimpleNamespace(returncode=3, stdout="", stderr=""))
    with pytest.raises(nm.NmError, match="code 3"):
        nm._run(["x"])
