#!/usr/bin/env python3
"""Proxmox dashboard for UsbPCMonitor 3.5" smart screen (1a86:5722).

Polls the Proxmox VE API and renders node CPU/RAM/uptime, VM & LXC statuses,
storage usage and network throughput to a 480x320 landscape frame.

Usage:
    panel.py            run against the real display
    panel.py --test     render one frame with fake data to test-frame.png
    panel.py --once     fetch real data, render one frame to test-frame.png
"""
import sys
import time
import signal
from pathlib import Path

import yaml
import requests
import urllib3
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
REPO = HERE.parent / "turing-smart-screen-python"
sys.path.insert(0, str(REPO))

W, H = 480, 320
FONT_DIR = REPO / "res" / "fonts" / "roboto"

# Colors
BG = (12, 14, 22)
PANEL = (24, 28, 40)
FG = (230, 233, 240)
DIM = (130, 138, 155)
ACCENT = (90, 170, 255)
GREEN = (80, 200, 120)
RED = (235, 90, 90)
YELLOW = (240, 190, 70)


def font(size, bold=False):
    name = "Roboto-Bold.ttf" if bold else "Roboto-Regular.ttf"
    return ImageFont.truetype(str(FONT_DIR / name), size)


F_TITLE = font(20, bold=True)
F_BIG = font(17, bold=True)
F_MED = font(14)
F_SMALL = font(12)
F_TINY = font(11)


def load_config():
    with open(HERE / "config.yaml") as f:
        return yaml.safe_load(f)


class Proxmox:
    def __init__(self, cfg):
        p = cfg["proxmox"]
        self.base = f"https://{p['host']}:{p['port']}/api2/json"
        self.node = p["node"]
        self.s = requests.Session()
        self.s.headers["Authorization"] = (
            f"PVEAPIToken={p['token_id']}={p['token_secret']}"
        )
        self.s.verify = p.get("verify_ssl", False)
        if not self.s.verify:
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    def get(self, path):
        r = self.s.get(f"{self.base}{path}", timeout=(5, 20))
        r.raise_for_status()
        return r.json()["data"]

    def fetch(self, panel_cfg):
        status = self.get(f"/nodes/{self.node}/status")
        guests = []
        for kind in ("qemu", "lxc"):
            try:
                for g in self.get(f"/nodes/{self.node}/{kind}"):
                    guests.append({
                        "name": g.get("name", str(g.get("vmid", "?"))),
                        "vmid": int(g.get("vmid", 0)),
                        "status": g.get("status", "unknown"),
                        "kind": "VM" if kind == "qemu" else "CT",
                    })
            except requests.RequestException:
                pass
        guests.sort(key=lambda g: g["vmid"])

        stores = [s for s in self.get(f"/nodes/{self.node}/storage")
                  if s.get("active") and s.get("total")]
        wanted = panel_cfg.get("storages") or []
        if wanted:
            stores = [s for s in stores if s["storage"] in wanted]
        else:
            stores.sort(key=lambda s: s["total"], reverse=True)
        stores = stores[:3]

        netin = netout = 0.0
        try:
            rrd = self.get(f"/nodes/{self.node}/rrddata?timeframe=hour&cf=AVERAGE")
            for point in reversed(rrd):
                if point.get("netin") is not None:
                    netin, netout = point["netin"], point.get("netout", 0.0)
                    break
        except requests.RequestException:
            pass

        return {
            "node": self.node,
            "cpu": status["cpu"],                      # 0..1
            "loadavg": status.get("loadavg", ["?"])[0],
            "mem_used": status["memory"]["used"],
            "mem_total": status["memory"]["total"],
            "uptime": status["uptime"],
            "guests": guests,
            "stores": stores,
            "netin": netin,                            # bytes/s
            "netout": netout,
        }


# ---------------------------------------------------------------- rendering

def human_bytes(n, suffix="B"):
    for unit in ("", "K", "M", "G", "T"):
        if abs(n) < 1024:
            return f"{n:.0f}{unit}{suffix}" if unit in ("", "K") else f"{n:.1f}{unit}{suffix}"
        n /= 1024
    return f"{n:.1f}P{suffix}"


def human_uptime(sec):
    d, rem = divmod(int(sec), 86400)
    h, rem = divmod(rem, 3600)
    m = rem // 60
    return f"{d}d {h}h" if d else f"{h}h {m:02d}m"


def bar(draw, x, y, w, h, frac, label, value_text):
    frac = max(0.0, min(1.0, frac))
    color = GREEN if frac < 0.7 else YELLOW if frac < 0.9 else RED
    draw.text((x, y), label, font=F_SMALL, fill=DIM)
    vw = draw.textlength(value_text, font=F_SMALL)
    draw.text((x + w - vw, y), value_text, font=F_SMALL, fill=FG)
    by = y + 17
    draw.rounded_rectangle((x, by, x + w, by + h), 4, fill=PANEL)
    if frac > 0.01:
        draw.rounded_rectangle((x, by, x + max(8, w * frac), by + h), 4, fill=color)


def render(d, error=None):
    img = Image.new("RGB", (W, H), BG)
    dr = ImageDraw.Draw(img)

    if error:
        dr.text((W // 2 - 90, 20), "PROXMOX PANEL", font=F_TITLE, fill=ACCENT)
        dr.rounded_rectangle((30, 90, W - 30, 230), 8, fill=PANEL)
        dr.text((50, 110), "Cannot reach Proxmox API", font=F_BIG, fill=RED)
        for i, line in enumerate(str(error)[:200].split("\n")[:4]):
            dr.text((50, 145 + i * 18), line[:52], font=F_SMALL, fill=DIM)
        dr.text((50, 280), time.strftime("retrying...  %H:%M:%S"), font=F_SMALL, fill=DIM)
        return img

    # Header
    dr.rectangle((0, 0, W, 34), fill=PANEL)
    dr.text((10, 6), d["node"], font=F_TITLE, fill=ACCENT)
    up = f"up {human_uptime(d['uptime'])}"
    dr.text((W - dr.textlength(up, font=F_MED) - 10, 9), up, font=F_MED, fill=DIM)
    clock = time.strftime("%H:%M")
    dr.text((W / 2 - dr.textlength(clock, font=F_BIG) / 2, 7), clock, font=F_BIG, fill=FG)

    lx, lw = 10, 235  # left column

    # CPU + RAM bars
    bar(dr, lx, 44, lw, 12, d["cpu"], "CPU", f"{d['cpu'] * 100:.0f}%  load {d['loadavg']}")
    mem_frac = d["mem_used"] / d["mem_total"]
    bar(dr, lx, 84, lw, 12,
        mem_frac, "RAM",
        f"{d['mem_used'] / 2**30:.1f} / {d['mem_total'] / 2**30:.0f} GiB")

    # Network
    dr.text((lx, 124), "NETWORK", font=F_SMALL, fill=DIM)
    ay = 146
    dr.polygon([(lx, ay + 3), (lx + 10, ay + 3), (lx + 5, ay + 11)], fill=GREEN)
    dr.text((lx + 16, ay - 5), human_bytes(d["netin"], "B/s"), font=F_BIG, fill=GREEN)
    dr.polygon([(lx + 125, ay + 11), (lx + 135, ay + 11), (lx + 130, ay + 3)], fill=ACCENT)
    dr.text((lx + 141, ay - 5), human_bytes(d["netout"], "B/s"), font=F_BIG, fill=ACCENT)

    # Storage
    y = 175
    dr.text((lx, y), "STORAGE", font=F_SMALL, fill=DIM)
    y += 17
    for s in d["stores"]:
        frac = s["used"] / s["total"]
        color = GREEN if frac < 0.75 else YELLOW if frac < 0.9 else RED
        dr.text((lx, y), s["storage"][:14], font=F_SMALL, fill=FG)
        txt = f"{human_bytes(s['used'])} / {human_bytes(s['total'])}"
        dr.text((lx + lw - dr.textlength(txt, font=F_TINY), y + 1), txt, font=F_TINY, fill=DIM)
        dr.rounded_rectangle((lx, y + 16, lx + lw, y + 24), 3, fill=PANEL)
        if frac > 0.01:
            dr.rounded_rectangle((lx, y + 16, lx + max(6, lw * frac), y + 24), 3, fill=color)
        y += 32

    # Guest list (right column)
    rx = 258
    running = sum(1 for g in d["guests"] if g["status"] == "running")
    dr.text((rx, 44), f"GUESTS  {running}/{len(d['guests'])} running",
            font=F_SMALL, fill=DIM)
    y = 64
    for g in d["guests"]:
        if y > H - 24:
            more = len(d["guests"]) - (y - 64) // 26
            dr.text((rx, y), f"+ {more} more...", font=F_TINY, fill=DIM)
            break
        color = GREEN if g["status"] == "running" else RED if g["status"] == "stopped" else YELLOW
        dr.ellipse((rx, y + 4, rx + 9, y + 13), fill=color)
        dr.text((rx + 16, y), f"{g['vmid']} {g['name'][:18]}", font=F_MED, fill=FG)
        kind_x = W - dr.textlength(g["kind"], font=F_TINY) - 10
        dr.text((kind_x, y + 2), g["kind"], font=F_TINY, fill=DIM)
        y += 26

    return img


# ---------------------------------------------------------------- main

FAKE = {
    "node": "pve", "cpu": 0.34, "loadavg": "1.42",
    "mem_used": 21 * 2**30, "mem_total": 32 * 2**30, "uptime": 1234567,
    "netin": 3.2 * 2**20, "netout": 412 * 2**10,
    "guests": [
        {"vmid": 100, "name": "haos", "status": "running", "kind": "VM"},
        {"vmid": 101, "name": "win11", "status": "stopped", "kind": "VM"},
        {"vmid": 102, "name": "ubuntu-docker", "status": "running", "kind": "VM"},
        {"vmid": 200, "name": "pihole", "status": "running", "kind": "CT"},
        {"vmid": 201, "name": "nginx-proxy", "status": "running", "kind": "CT"},
        {"vmid": 202, "name": "postgres", "status": "running", "kind": "CT"},
        {"vmid": 203, "name": "jellyfin", "status": "stopped", "kind": "CT"},
    ],
    "stores": [
        {"storage": "local-zfs", "used": 412 * 2**30, "total": 900 * 2**30},
        {"storage": "tank", "used": 3.1 * 2**40, "total": 4 * 2**40},
    ],
}


def main():
    if "--test" in sys.argv:
        render(FAKE).save(HERE / "test-frame.png")
        print(f"wrote {HERE / 'test-frame.png'}")
        return

    cfg = load_config()
    pve = Proxmox(cfg)

    if "--once" in sys.argv:
        render(pve.fetch(cfg["panel"])).save(HERE / "test-frame.png")
        print(f"wrote {HERE / 'test-frame.png'}")
        return

    from library.lcd.lcd_comm_rev_a import LcdCommRevA, Orientation
    lcd = LcdCommRevA(com_port=cfg["display"]["com_port"],
                      display_width=320, display_height=480)

    def stop(*_):
        lcd.ScreenOff()
        lcd.closeSerial()
        sys.exit(0)
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    # Note: no lcd.Reset() here! On rev A it re-enumerates the USB device,
    # which makes systemd (BindsTo) kill this service -> endless restart loop.
    lcd.InitializeComm()
    lcd.ScreenOn()
    lcd.SetBrightness(cfg["display"]["brightness"])
    lcd.SetOrientation(Orientation.LANDSCAPE)

    refresh = cfg["display"]["refresh_seconds"]
    while True:
        t0 = time.time()
        try:
            frame = render(pve.fetch(cfg["panel"]))
        except Exception as e:  # noqa: BLE001 - show any API failure on screen
            frame = render(None, error=e)
        lcd.DisplayPILImage(frame)
        time.sleep(max(0.5, refresh - (time.time() - t0)))


if __name__ == "__main__":
    main()
