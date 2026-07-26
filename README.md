# UsbPCMonitor 3.5" (1a86:5722) on Linux

Your AliExpress USB-C display is a **"smart screen"**, not a true extended monitor.
It has no DisplayLink/HDMI hardware — the OS can never see it as a screen in display
settings. Instead, software pushes rendered images to it over USB using a
reverse-engineered protocol. That is what the bundled
[turing-smart-screen-python](https://github.com/mathoudebine/turing-smart-screen-python)
project does (your device is its "revision A" / UsbPCMonitor variant — auto-detected
by USB ID `1a86:5722`).

## Setup (one time)

```bash
./setup.sh
```

This creates a venv, installs dependencies, and installs the udev rule
(`99-usbmonitor.rules`) so you don't need root to talk to the display.
Unplug/replug the display afterwards.

## Run

```bash
cd turing-smart-screen-python
./venv/bin/python configure.py   # optional GUI: pick theme, brightness, sensors
./venv/bin/python main.py        # start the system monitor
```

The default config (`config.yaml`) is already correct for your device:
`REVISION: A`, `COM_PORT: AUTO`, theme `3.5inchTheme2` (320x480).
Included extra themes: BigClock, Landscape6Grid, LandscapeEarth, LandscapeMagicBlue.
More themes: https://github.com/mathoudebine/turing-smart-screen-python/tree/main/res/themes
(this is a sparse checkout — fetch more with `git sparse-checkout add "res/themes/<Name>"`).

## Auto-start on plug-in (optional)

```bash
./install-autostart.sh
```

The udev rule starts a single `smartscreen.service` when the display is plugged
in (`BindsTo` stops it on unplug). The service runs `/usr/local/bin/smartscreen-launch`,
which `switch-panel.sh` rewrites to point at the chosen panel — so switching never
touches systemd dependencies. (The launcher lives outside $HOME because SELinux
blocks systemd from exec'ing files in home directories.)
Status: `systemctl status smartscreen` · Logs: `journalctl -u smartscreen -f`

## Display custom content from your own code

```python
# see turing-smart-screen-python/simple-program.py for a full example
from library.lcd.lcd_comm_rev_a import LcdCommRevA, Orientation
lcd = LcdCommRevA(com_port="AUTO", display_width=320, display_height=480)
lcd.Reset(); lcd.InitializeComm(); lcd.SetBrightness(25)
lcd.SetOrientation(Orientation.LANDSCAPE)
lcd.DisplayBitmap("path/to/image.png")
```

## Proxmox panel

`proxmox-panel/` shows your PVE node on the screen: CPU/RAM/uptime, VM & LXC
statuses, storage bars, live network throughput.

1. Create an API token in the PVE UI: Datacenter → Permissions → API Tokens
   (untick "Privilege Separation", or grant the token the PVEAuditor role on `/`).
2. Copy the example config and fill in your values:
   `cp proxmox-panel/config.yaml.example proxmox-panel/config.yaml`
   (host, node name, token). The real `config.yaml` is gitignored so your
   token never gets committed.
3. Test without the display: `proxmox-panel/run-proxmox.sh --once` writes
   `test-frame.png` using live data — check it looks right.
4. Run on the display: `proxmox-panel/run-proxmox.sh`

To choose what appears automatically on plug-in:

```bash
./switch-panel.sh proxmox   # or: ./switch-panel.sh stats
```

## Troubleshooting

- Device should appear as a serial port (`/dev/ttyACM0` or `/dev/ttyUSB0`) — check with
  `ls /dev/ttyACM* /dev/ttyUSB*` after plugging in.
- Permission denied without the udev rule? Add yourself to the serial group:
  `sudo usermod -aG dialout $USER` (Debian/Ubuntu) or `uucp` (Arch), then re-login.
- Project troubleshooting wiki:
  https://github.com/mathoudebine/turing-smart-screen-python/wiki/Troubleshooting

## Credits & License

This repo bundles a vendored copy of
[**turing-smart-screen-python**](https://github.com/mathoudebine/turing-smart-screen-python)
by [@mathoudebine](https://github.com/mathoudebine) and contributors — the
reverse-engineered driver that pushes images to the display. That project is
licensed under the **GNU GPL v3.0**; its full license text is kept intact at
[`turing-smart-screen-python/LICENSE`](turing-smart-screen-python/LICENSE).
All credit for the display protocol and driver goes to that project.

The original code in this repo (`proxmox-panel/`, the setup/service scripts,
and the udev integration) is my own work. Because it is distributed together
with the GPLv3-licensed driver, treat the combined work as **GPLv3**.
