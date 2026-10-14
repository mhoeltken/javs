# SPDX-License-Identifier: Apache-2.0
"""Thin wrapper around nmcli. The only place where JAVS starts processes."""

import os
import subprocess
from dataclasses import dataclass

VPN_TYPES = ("vpn", "wireguard")
# `nmcli connection up` waits up to 90 s for the connection by default.
TIMEOUT_S = 120
# Read-only queries run on the GTK main thread and must not block the UI for long.
READ_TIMEOUT_S = 10


class NmError(Exception):
    """nmcli is missing, hangs or reports an error."""


@dataclass(frozen=True)
class ActiveVpn:
    name: str
    activating: bool


def _run(args, timeout=TIMEOUT_S):
    # UTF-8 instead of "C": nmcli prints through glib, and in the C locale non-ASCII
    # characters in connection names become '?', so `connection up id <name>` finds nothing.
    env = {**os.environ, "LC_ALL": "C.UTF-8"}
    try:
        result = subprocess.run(
            ["nmcli", *args],
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            env=env,
        )
    except FileNotFoundError as exc:
        raise NmError("nmcli not found (is NetworkManager installed?)") from exc
    except OSError as exc:
        raise NmError(f"nmcli is not executable: {exc}") from exc
    except subprocess.TimeoutExpired as exc:
        raise NmError("nmcli: timed out") from exc
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip()
        raise NmError(message or f"nmcli exited with code {result.returncode}")
    return result.stdout


def split_terse(line):
    """Split a `nmcli -t` line at unescaped ':'; '\\:' and '\\\\' are unescaped."""
    fields = []
    current = []
    i = 0
    while i < len(line):
        char = line[i]
        if char == "\\" and i + 1 < len(line):
            current.append(line[i + 1])
            i += 2
            continue
        if char == ":":
            fields.append("".join(current))
            current = []
        else:
            current.append(char)
        i += 1
    fields.append("".join(current))
    return fields


def list_vpns():
    output = _run(["-t", "-f", "NAME,TYPE", "connection", "show"], timeout=READ_TIMEOUT_S)
    names = []
    for line in output.splitlines():
        fields = split_terse(line)
        if len(fields) >= 2 and fields[1] in VPN_TYPES:
            names.append(fields[0])
    return names


def active_vpn():
    output = _run(
        ["-t", "-f", "NAME,TYPE,STATE", "connection", "show", "--active"],
        timeout=READ_TIMEOUT_S,
    )
    activated = None
    activating = None
    for line in output.splitlines():
        fields = split_terse(line)
        if len(fields) < 3 or fields[1] not in VPN_TYPES:
            continue
        name, _type, state = fields[:3]
        if state == "activated" and activated is None:
            activated = ActiveVpn(name, False)
        elif state == "activating" and activating is None:
            activating = ActiveVpn(name, True)
    return activated or activating


def up(name):
    _run(["connection", "up", "id", name])


def down(name):
    _run(["connection", "down", "id", name])


def switch(name):
    """Switch to `name`: disconnect the active connection first. No-op if already active."""
    active = active_vpn()
    if active is not None and active.name == name:
        return
    if active is not None:
        down(active.name)
    up(name)
