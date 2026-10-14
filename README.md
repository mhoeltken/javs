# JAVS – Just Another VPN Switch

A small tray applet for Linux Mint (Cinnamon, MATE, Xfce). It shows a short
code for the active VPN connection in the system tray (`OFF`, `FRA`, `LAX`, …)
and lets you switch between VPNs or disconnect with a click.

JAVS is provider-independent: it controls connections that already exist in
NetworkManager (OpenVPN, WireGuard). NetworkManager manages the credentials;
JAVS never reads or stores passwords.

## Badge

| Badge | Meaning |
|-------|---------|
| `OFF` (grey) | no VPN active |
| `…` (yellow) | connection is being set up or switched |
| `FRA` (green) | connected; the code is the last segment of the connection name |
| `ERR` (red) | `nmcli` is not usable |

`surfshark-de-fra` becomes `FRA`, `mullvad` becomes `MUL`.

## Requirements

On Linux Mint everything is normally present already:

```bash
sudo apt install python3-gi gir1.2-ayatanaappindicator3-0.1 \
  python3-cairo gir1.2-pango-1.0 network-manager libnotify-bin
```

On older systems the package is called `gir1.2-appindicator3-0.1`; JAVS uses
whichever is available.

## Creating VPN connections

JAVS lists every NetworkManager connection of type `vpn` or `wireguard`.
Example for an OpenVPN file:

```bash
nmcli connection import type openvpn file server.ovpn
nmcli connection modify <name> connection.id my-vpn-de-fra \
  vpn.user-name "USER" +vpn.data password-flags=0 vpn.secrets "password=PASSWORD"
```

The last part of the name (`fra`) becomes the badge code.

## Run

```bash
python3 -m javs.tray
```

## Autostart

```bash
mkdir -p ~/.config/autostart
sed "s|@INSTALL_DIR@|$PWD|" javs.desktop > ~/.config/autostart/javs.desktop
```

## Configuration

`~/.config/javs/config.json`:

```json
{
  "poll": "medium"
}
```

| Level | Interval |
|-------|----------|
| `tight` | 2 s |
| `medium` (default) | 5 s |
| `relaxed` | 15 s |

Switchable in the menu under "Poll interval". The level only affects changes
made outside JAVS; after its own actions and while a connection is being set
up, JAVS refreshes immediately or every second respectively.

## Tests

```bash
sudo apt install python3-pytest
python3 -m pytest
```

The tests do not need a display.

## Design

See [docs/DESIGN.md](docs/DESIGN.md).

## License

Apache-2.0, see [LICENSE](LICENSE).
