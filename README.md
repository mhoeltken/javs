# JAVS – Just Another VPN Switch

A tiny tray applet for Linux that shows which VPN you are connected to and lets
you switch it on, off or to another server with two clicks.

```
 OFF   no VPN         FRA   connected to Frankfurt         …   connecting
```

JAVS does not implement any VPN itself and does not care who your provider is.
It controls connections that already exist in **NetworkManager** (OpenVPN or
WireGuard), so it works with Surfshark, Mullvad, ProtonVPN, your company VPN,
and so on. NetworkManager keeps the credentials; JAVS never reads or stores
passwords.

## Features

- Badge in the system tray: `OFF`, a 3-letter server code (`FRA`, `LAX`, …),
  `…` while connecting, `ERR` if `nmcli` is not usable
- Click → list of all your VPN connections → pick one to switch, or "Disconnect"
- Switching disconnects the old VPN first, so you never end up with two at once
- Notices changes made elsewhere (`nmcli`, network applet) within a few seconds
- Desktop notification when a connection attempt fails
- No dependencies beyond what a stock Linux Mint ships

## Compatibility

Developed and tested on **Linux Mint 22 (Cinnamon)**. It uses the standard
AppIndicator tray protocol, so it should also work on MATE and Xfce; those are
untested. GNOME needs the "AppIndicator and KStatusNotifierItem Support"
extension to show tray icons at all.

## Quick start

```bash
git clone https://github.com/mhoeltken/javs.git
cd javs
python3 -m javs.tray
```

Requirements (already present on Linux Mint):

```bash
sudo apt install python3-gi gir1.2-ayatanaappindicator3-0.1 \
  python3-cairo gir1.2-pango-1.0 network-manager libnotify-bin
```

On older systems the package is called `gir1.2-appindicator3-0.1`; JAVS uses
whichever is available.

### Autostart

```bash
mkdir -p ~/.config/autostart
sed "s|@INSTALL_DIR@|$PWD|" javs.desktop > ~/.config/autostart/javs.desktop
```

## Adding VPN connections

JAVS lists every NetworkManager connection of type `vpn` or `wireguard`. If you
have an OpenVPN file from your provider:

```bash
nmcli connection import type openvpn file server.ovpn
nmcli connection modify <name> connection.id my-vpn-de-fra \
  vpn.user-name "USER" +vpn.data password-flags=0 vpn.secrets "password=PASSWORD"
```

Or import it through the network applet's GUI. Either way, name the connection
so that its **last `-`-separated part is the badge code**: `my-vpn-de-fra` →
`FRA`, `mullvad` → `MUL`.

## Configuration

`~/.config/javs/config.json` (created when you change the setting in the menu):

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

Choose it in the menu under "Poll interval". It only affects changes made
outside JAVS; after its own actions, and while a connection is coming up, JAVS
refreshes immediately or every second respectively.

## Troubleshooting

| Symptom | Likely cause |
|---------|--------------|
| No icon in the tray | AppIndicator support missing (see Compatibility); start from a terminal to see errors |
| Red `ERR` | `nmcli` not found or failing; the menu shows the message |
| Menu says "No VPN connections" | Nothing of type `vpn`/`wireguard` in NetworkManager; see "Adding VPN connections" |
| Connection fails right away | Wrong or missing credentials in the NetworkManager profile; try `nmcli connection up id <name>` to see the error |

## Development

```bash
sudo apt install python3-pytest
python3 -m pytest
```

The tests do not need a display. The code is split into `core` (pure logic),
`nm` (the only place that runs `nmcli`), `config`, and `tray` (GTK); see
[docs/DESIGN.md](docs/DESIGN.md).

Issues and pull requests are welcome.

## License

Apache-2.0, see [LICENSE](LICENSE).
