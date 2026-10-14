# JAVS – Design

## Goal

A small tray application for Linux Mint (Cinnamon, MATE, Xfce) that shows the
state of the active VPN as a short code (`OFF`, `BER`, `FRA`, `LAX`, …) and
lets the user switch between VPN connections or disconnect from a menu.

JAVS is provider-independent. It only controls connections that already exist
in NetworkManager (OpenVPN, WireGuard). Credentials are managed by
NetworkManager and never touched by JAVS.

## Non-goals

- Settings dialogs, kill switch, provider APIs, server list downloads
- Ping or latency comparison of servers
- Distribution packages (.deb, PyPI)
- Any VPN protocol implementation of its own

## Technology

- Python 3, GTK3, AyatanaAppIndicator3 (fallback: AppIndicator3), Cairo/Pango
- No runtime dependencies beyond the standard Linux Mint packages
- The badge is drawn as text on a rounded rectangle and saved as a PNG that is
  handed to the indicator

## Behaviour

### Badge

| State | Text | Colour |
|-------|------|--------|
| disconnected | `OFF` | grey |
| connecting | `…` | yellow |
| connected | code, e.g. `FRA` | green |
| `nmcli` not usable | `ERR` | red |

A failed connection attempt does not produce `ERR`; it returns to `OFF` and
shows a desktop notification.

### Code

The last segment of the connection name (split at `-`), upper case, cut to 3
characters: `surfshark-de-fra` → `FRA`. Without a hyphen the first 3 characters
are used (`mullvad` → `MUL`). Empty names yield `???`.

### Menu

- All NetworkManager connections of type `vpn` and `wireguard`, sorted
  alphabetically; the active one is marked
- "Disconnect" (enabled only while connected)
- Submenu "Poll interval" with `tight` / `medium` / `relaxed`
- "Quit"

### Switching

Choosing another server first disconnects the active connection, then connects
the new one. Otherwise NetworkManager would run several VPNs in parallel.
Choosing the already active connection does nothing. While an action is
running, the menu entries are disabled.

### Polling

| Level | Interval |
|-------|----------|
| `tight` | 2 s |
| `medium` (default) | 5 s |
| `relaxed` | 15 s |

- After each of its own actions JAVS refreshes immediately
- While a connection is being set up it polls every second
- The level only affects changes made outside JAVS
- Read-only `nmcli` queries have a short timeout (10 s) because they run on the
  GTK main thread; `connection up/down` run in a worker thread with a long one

### Error handling

- `nmcli` missing or failing: badge `ERR`, the menu shows the message, no crash
- Unexpected exceptions while refreshing end up the same way; the poll timer
  keeps running
- `up` fails: desktop notification with the message from `nmcli`, then the
  state is re-read
- Broken or missing config: defaults are used and the file is not overwritten
  until the user changes the level

## Configuration

`~/.config/javs/config.json`

```json
{
  "poll": "medium"
}
```

Valid values for `poll`: `tight`, `medium`, `relaxed`. Unknown values fall back
to `medium`.

## Structure

```
javs/
  core.py      # pure logic, no GTK: codes, sorting, badge state
  nm.py        # thin nmcli wrapper (the only place that starts processes)
  config.py    # config.json load/save, poll levels
  tray.py      # AppIndicator, badge rendering, menu, timer, notifications
tests/         # pytest, no display needed
javs.desktop   # autostart template
```

Data flow: timer or action → `nm` reads state → `core` maps it to badge text and
colour → `tray` draws the badge and rebuilds the menu when the connection list
changed.

## Locale note

`nmcli` is run with `LC_ALL=C.UTF-8`. The plain `C` locale would turn non-ASCII
characters in connection names into `?` (glib's `g_print`), and
`nmcli connection up id <name>` would then fail for those names.
