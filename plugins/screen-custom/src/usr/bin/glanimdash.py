#!/usr/bin/env python3
# glanimdash.py - system information dashboard, touch handling and 5x7 font
# for the GL-BE3600 284x76 horizontal ST7789 panel (fb0 76x284 RGB565LE).
# Stdlib only, shared by /usr/bin/glanimd. Imported for offline unit tests too.

import json
import struct

PHYS_W, PHYS_H = 284, 76
FB_W, FB_H = 76, 284
FB_BYTES = FB_W * FB_H * 2


# --------------------------------------------------------------------------
# 5x7 bitmap font. Each glyph = 5 column bytes; bit 0 = top row. Columns are
# left -> right. Only uppercase / digits / symbols are provided; text is
# upper-cased before drawing (the tiny panel cannot render Chinese).
# --------------------------------------------------------------------------
FONT = {
    " ": (0x00, 0x00, 0x00, 0x00, 0x00),
    "0": (0x3E, 0x51, 0x49, 0x45, 0x3E),
    "1": (0x00, 0x42, 0x7F, 0x40, 0x00),
    "2": (0x42, 0x61, 0x51, 0x49, 0x46),
    "3": (0x21, 0x45, 0x49, 0x49, 0x36),
    "4": (0x18, 0x14, 0x12, 0x7F, 0x10),
    "5": (0x27, 0x45, 0x45, 0x45, 0x39),
    "6": (0x3C, 0x4A, 0x49, 0x49, 0x30),
    "7": (0x01, 0x71, 0x09, 0x05, 0x03),
    "8": (0x36, 0x49, 0x49, 0x49, 0x36),
    "9": (0x06, 0x49, 0x49, 0x29, 0x1E),
    "A": (0x7E, 0x11, 0x11, 0x11, 0x7E),
    "B": (0x7F, 0x49, 0x49, 0x49, 0x36),
    "C": (0x3E, 0x41, 0x41, 0x41, 0x22),
    "D": (0x7F, 0x41, 0x41, 0x22, 0x1C),
    "E": (0x7F, 0x49, 0x49, 0x49, 0x41),
    "F": (0x7F, 0x09, 0x09, 0x09, 0x01),
    "G": (0x3E, 0x41, 0x49, 0x49, 0x7A),
    "H": (0x7F, 0x08, 0x08, 0x08, 0x7F),
    "I": (0x41, 0x41, 0x7F, 0x41, 0x41),
    "J": (0x21, 0x41, 0x41, 0x41, 0x3E),
    "K": (0x7F, 0x08, 0x14, 0x22, 0x41),
    "L": (0x7F, 0x40, 0x40, 0x40, 0x40),
    "M": (0x7F, 0x02, 0x0C, 0x02, 0x7F),
    "N": (0x7F, 0x04, 0x08, 0x10, 0x7F),
    "O": (0x3E, 0x41, 0x41, 0x41, 0x3E),
    "P": (0x7F, 0x09, 0x09, 0x09, 0x06),
    "Q": (0x3E, 0x41, 0x51, 0x21, 0x5E),
    "R": (0x7F, 0x09, 0x19, 0x29, 0x46),
    "S": (0x26, 0x49, 0x49, 0x49, 0x32),
    "T": (0x01, 0x01, 0x7F, 0x01, 0x01),
    "U": (0x3F, 0x40, 0x40, 0x40, 0x3F),
    "V": (0x1F, 0x20, 0x40, 0x20, 0x1F),
    "W": (0x3F, 0x40, 0x38, 0x40, 0x3F),
    "X": (0x63, 0x14, 0x08, 0x14, 0x63),
    "Y": (0x07, 0x08, 0x70, 0x08, 0x07),
    "Z": (0x61, 0x51, 0x49, 0x45, 0x43),
    ":": (0x00, 0x36, 0x36, 0x00, 0x00),
    ".": (0x00, 0x00, 0x00, 0x30, 0x30),
    "%": (0x23, 0x13, 0x08, 0x64, 0x62),
    "-": (0x00, 0x08, 0x08, 0x08, 0x00),
    "/": (0x40, 0x20, 0x10, 0x08, 0x04),
    "(": (0x00, 0x07, 0x08, 0x08, 0x00),
    ")": (0x00, 0x70, 0x08, 0x08, 0x00),
    "+": (0x08, 0x08, 0x7F, 0x08, 0x08),
    "(": (0x00, 0x07, 0x08, 0x08, 0x00),
    "_": (0x40, 0x40, 0x40, 0x40, 0x40),
    ">": (0x44, 0x28, 0x10, 0x28, 0x44),
    "<": (0x11, 0x22, 0x44, 0x22, 0x11),
    "=": (0x08, 0x08, 0x08, 0x08, 0x08),
}

GLYPH_W, GLYPH_H = 5, 7
ADVANCE = 6  # 5 px glyph + 1 px gap per scale unit


def glyph(ch):
    return FONT.get(ch.upper(), FONT[" "])


def text_width(text, scale=1):
    return len(text) * ADVANCE * scale - scale  # drop trailing gap


# --------------------------------------------------------------------------
# Physical RGB canvas (284 x 76). Pixels stored as a flat bytearray RGB.
# --------------------------------------------------------------------------
BG = (10, 12, 18)
WHITE = (235, 240, 250)
GREY = (190, 202, 218)
GREEN = (60, 210, 110)
YELLOW = (240, 190, 60)
RED = (230, 70, 70)
BLUE = (70, 150, 235)


class Canvas:
    def __init__(self):
        self.buf = bytearray(PHYS_W * PHYS_H * 3)

    def clear(self, rgb=BG):
        for i in range(0, len(self.buf), 3):
            self.buf[i] = rgb[0]
            self.buf[i + 1] = rgb[1]
            self.buf[i + 2] = rgb[2]

    def pixel(self, x, y, rgb):
        if 0 <= x < PHYS_W and 0 <= y < PHYS_H:
            o = (y * PHYS_W + x) * 3
            self.buf[o] = rgb[0]
            self.buf[o + 1] = rgb[1]
            self.buf[o + 2] = rgb[2]

    def load_rgb888(self, data):
        """Replace the whole canvas with a pre-decoded 284x76 RGB888 buffer."""
        if data is not None and len(data) == len(self.buf):
            self.buf[:] = data

    def fill_rect(self, x, y, w, h, rgb):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.pixel(xx, yy, rgb)

    def draw_text(self, x, y, text, color=WHITE, scale=1):
        cx = x
        for ch in text:
            cols = glyph(ch)
            for c in range(GLYPH_W):
                bits = cols[c]
                for r in range(GLYPH_H):
                    if (bits >> r) & 1:
                        for sy in range(scale):
                            for sx in range(scale):
                                self.pixel(cx + c * scale + sx,
                                           y + r * scale + sy, color)
            cx += ADVANCE * scale
        return cx

    def draw_bar(self, x, y, w, h, pct, color=GREEN, track=(38, 42, 54)):
        pct = max(0, min(100, pct))
        self.fill_rect(x, y, w, h, track)
        fw = int(w * pct / 100)
        if fw > 0:
            self.fill_rect(x, y, fw, h, color)

    def rgb565(self, r, g, b):
        return ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)

    def render_fb(self):
        """Map the physical 284x76 buffer into the 76x284 fb90m layout.

        fb90m (PC tool phys_to_fb): p_x = FB_H - 1 - y_fb, p_y = x_fb.
        Inverse: y_fb = FB_H - 1 - p_x, x_fb = p_y.
        """
        out = bytearray(FB_BYTES)
        for px in range(PHYS_W):
            for py in range(PHYS_H):
                pi = (py * PHYS_W + px) * 3
                r, g, b = self.buf[pi], self.buf[pi + 1], self.buf[pi + 2]
                y_fb = FB_H - 1 - px
                x_fb = py
                bi = (y_fb * FB_W + x_fb) * 2
                c = self.rgb565(r, g, b)
                out[bi] = c & 0xFF
                out[bi + 1] = (c >> 8) & 0xFF
        return bytes(out)


def bar_color(pct):
    if pct >= 80:
        return RED
    if pct >= 55:
        return YELLOW
    return GREEN


# --------------------------------------------------------------------------
# System statistics collector. File paths are overridable for offline tests.
# --------------------------------------------------------------------------
import os
import time as _time
import subprocess
import socket


WEEKDAYS = ["SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"]


def _read_lines(path):
    try:
        with open(path) as f:
            return f.readlines()
    except Exception:
        return []


def _first_field(path, key):
    for line in _read_lines(path):
        if line.startswith(key):
            parts = line.split()
            return parts[1] if len(parts) > 1 else None
    return None


def _read_int(path, default=0):
    try:
        with open(path) as f:
            return int(f.read().strip())
    except Exception:
        return default


def _hostname():
    try:
        with open("/proc/sys/kernel/hostname") as f:
            name = f.read().strip()
            if name:
                return name
    except Exception:
        pass
    try:
        return socket.gethostname() or "router"
    except Exception:
        return "router"


class Collector:
    def __init__(self, root="", proc_net_dev=None, proc_stat=None,
                 meminfo=None, thermal=None,
                 uptime=None, iface=None, time_fn=_time.localtime,
                 clock=_time.time):
        self.root = root
        self.path_stat = proc_stat or (root + "/proc/stat")
        self.path_netdev = proc_net_dev or (root + "/proc/net/dev")
        self.path_mem = meminfo or (root + "/proc/meminfo")
        self.path_uptime = uptime or (root + "/proc/uptime")
        self.thermal = thermal or (root + "/sys/class/thermal")
        self.iface = iface
        self.time_fn = time_fn
        self.clock = clock
        self._cpu = None
        self._net = None
        self._t0 = None

    # ---- helpers ----
    def _cpu_times(self):
        for line in _read_lines(self.path_stat):
            if line.startswith("cpu "):
                v = [int(x) for x in line.split()[1:]]
                idle = v[3] + (v[4] if len(v) > 4 else 0)
                total = sum(v)
                return total, idle
        return None, None

    def _net_bytes(self, iface):
        for line in _read_lines(self.path_netdev):
            iface = iface or ""
            if line.strip().startswith(iface + ":"):
                v = line.split(":")[1].split()
                return int(v[0]), int(v[8])
        return None, None

    def _default_iface(self):
        if self.iface:
            return self.iface
        route = self.root + "/proc/net/route"
        for line in _read_lines(route):
            parts = line.split()
            if parts and parts[1] == "00000000":
                return parts[0]
        return "eth0"

    def _mem(self):
        total = _first_field(self.path_mem, "MemTotal:")
        avail = _first_field(self.path_mem, "MemAvailable:")
        if not total:
            return None
        total = int(total)
        avail = int(avail) if avail else total
        return max(0, min(100, (total - avail) * 100 // total))

    def _temp(self):
        best = None
        try:
            for name in sorted(os.listdir(self.thermal)):
                if name.startswith("thermal_zone"):
                    lines = _read_lines(self.thermal + "/" + name + "/temp")
                    if lines:
                        c = int(lines[0].strip()) // 1000
                        if best is None or c > best:
                            best = c
        except Exception:
            pass
        return best if best is not None else 0

    def _uptime_text(self):
        v = _read_lines(self.path_uptime)
        if not v:
            return ""
        sec = int(float(v[0].split()[0]))
        d = sec // 86400
        h = (sec % 86400) // 3600
        m = (sec % 3600) // 60
        return ("%dd %02d:%02d" % (d, h, m)) if d > 0 else "%02d:%02d" % (h, m)

    def _ip(self, iface):
        try:
            out = subprocess.check_output(
                ["ip", "-4", "addr", "show", iface],
                stderr=subprocess.DEVNULL).decode()
            for line in out.splitlines():
                if "inet " in line:
                    return line.split()[1].split("/")[0]
        except Exception:
            pass
        return ""

    # ---- snapshot ----
    def prime(self):
        self._cpu = self._cpu_times()
        rx, tx = self._net_bytes(self._default_iface())
        self._net = (rx, tx)
        self._t0 = self.clock()

    def snapshot(self):
        now = self.clock()
        dt = max(0.1, now - (self._t0 or now))
        self._t0 = now

        cpu_pct = None
        ct = self._cpu_times()
        if ct[0] and self._cpu and ct[0] != self._cpu[0]:
            busy = (ct[0] - self._cpu[0]) - (ct[1] - self._cpu[1])
            cpu_pct = max(0, min(100, busy * 100 // (ct[0] - self._cpu[0])))
        self._cpu = ct

        iface = self._default_iface()
        rx, tx = self._net_bytes(iface)
        rx_kbps = tx_kbps = None
        if rx is not None and self._net[0] is not None:
            rx_kbps = max(0, int((rx - self._net[0]) / dt / 1024))
            tx_kbps = max(0, int((tx - self._net[1]) / dt / 1024))
        self._net = (rx, tx)

        lt = self.time_fn()
        lan_ip = self._ip("br-lan")
        wan_ip = self._ip(iface)
        pwm_raw = _read_int("/sys/class/hwmon/hwmon0/pwm1", 0)
        fan_rpm = _read_int("/sys/class/hwmon/hwmon0/fan1_input", 0)
        return {
            "cpu": cpu_pct if cpu_pct is not None else 0,
            "mem": self._mem(),
            "temp": self._temp(),
            "rx_kbps": rx_kbps or 0,
            "tx_kbps": tx_kbps or 0,
            "iface": iface,
            "clock": "%02d:%02d:%02d" % (lt.tm_hour, lt.tm_min, lt.tm_sec),
            "hm": "%02d:%02d" % (lt.tm_hour, lt.tm_min),
            "date": "%02d/%02d" % (lt.tm_mon, lt.tm_mday),
            "weekday": WEEKDAYS[lt.tm_wday],
            "uptime": self._uptime_text(),
            "ip": lan_ip,
            "lan_ip": lan_ip,
            "wan_ip": wan_ip,
            "hostname": _hostname(),
            "fan_rpm": max(0, fan_rpm),
            "fan_pwm": max(0, min(100, int(round(pwm_raw * 100.0 / 255.0)))),
            "fan_raw_pwm": max(0, min(255, pwm_raw)),
        }


def fmt_speed(kbps):
    """KB/s -> compact label."""
    if kbps >= 1024:
        return "%.1fMB" % (kbps / 1024)
    return "%dKB" % kbps


# --------------------------------------------------------------------------
# Page rendering. Each page returns a draw(canvas, data) closure.
# --------------------------------------------------------------------------
def temp_color(t):
    if t >= 70:
        return RED
    if t >= 50:
        return YELLOW
    return GREEN


def _row_bar(canvas, y, label, pct, value_text, color, bar_w=138):
    canvas.draw_text(8, y + 2, label, GREY, 1)
    canvas.draw_bar(46, y, bar_w, 11, pct, color)
    tw = text_width(value_text, 1)
    canvas.draw_text(PHYS_W - tw - 8, y + 2, value_text, WHITE, 1)


def render_clock(canvas, d, cfg):
    canvas.clear()
    # top row: date / weekday left, uptime right
    canvas.draw_text(8, 3, "%s %s" % (d["date"], d["weekday"]), GREY, 1)
    if cfg.get("show_uptime"):
        u = "UP " + d["uptime"]
        canvas.draw_text(PHYS_W - text_width(u, 1) - 8, 3, u, GREY, 1)

    # big clock HH:MM centered
    clock = d["hm"]
    w = text_width(clock, 3)
    x = (PHYS_W - w) // 2
    canvas.draw_text(x, 21, clock, WHITE, 3)
    # seconds next to the big clock, small
    sec = d["clock"].split(":")[-1]
    canvas.draw_text(x + w + 10, 33, sec, GREY, 1)

    if cfg.get("show_ip") and d["ip"]:
        canvas.draw_text((PHYS_W - text_width(d["ip"], 1)) // 2, 57, d["ip"], GREY, 1)


def render_status(canvas, d, cfg):
    canvas.clear()
    canvas.draw_text(8, 3, "STATUS", GREY, 1)
    if d["iface"]:
        t = d["iface"].upper()
        canvas.draw_text(PHYS_W - text_width(t, 1) - 8, 3, t, GREY, 1)

    y = 13
    if cfg.get("show_cpu"):
        _row_bar(canvas, y, "CPU", d["cpu"], "%3d%%" % d["cpu"], bar_color(d["cpu"]))
        y += 16
    if cfg.get("show_mem"):
        _row_bar(canvas, y, "MEM", d["mem"], "%3d%%" % d["mem"], bar_color(d["mem"]))
        y += 16
    if cfg.get("show_temp"):
        _row_bar(canvas, y, "TMP", d["temp"], "%dC" % d["temp"], temp_color(d["temp"]))
        y += 16

    if cfg.get("show_net"):
        line = "DL %s UL %s" % (fmt_speed(d["rx_kbps"]), fmt_speed(d["tx_kbps"]))
        canvas.draw_text(8, 62, line, WHITE, 1)
    if cfg.get("show_ip") and d["ip"]:
        canvas.draw_text(PHYS_W - text_width(d["ip"], 1) - 8, 62, d["ip"], GREY, 1)


def _hex_rgb(value, default=WHITE):
    if not isinstance(value, str):
        return default
    value = value.strip()
    if len(value) == 7 and value[0] == "#":
        try:
            return (int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16))
        except ValueError:
            pass
    return default


CUSTOM_SOURCES = {
    "cpu", "mem", "temp", "rx", "tx", "net", "iface",
    "ip", "lan_ip", "wan_ip", "hostname", "uptime",
    "clock", "hm", "date", "weekday", "fan_rpm", "fan_pwm",
}


def _custom_value(source, d):
    """Return a display string for one custom element source."""
    if source == "cpu":
        return str(int(d.get("cpu", 0)))
    if source == "mem":
        return str(int(d.get("mem") or 0))
    if source == "temp":
        return str(int(d.get("temp") or 0))
    if source == "rx":
        return fmt_speed(d.get("rx_kbps", 0))
    if source == "tx":
        return fmt_speed(d.get("tx_kbps", 0))
    if source == "net":
        return "DL %s UL %s" % (fmt_speed(d.get("rx_kbps", 0)),
                                fmt_speed(d.get("tx_kbps", 0)))
    if source == "fan_rpm":
        return str(int(d.get("fan_rpm", 0)))
    if source == "fan_pwm":
        return str(int(d.get("fan_pwm", 0)))
    if source in ("ip", "lan_ip"):
        return str(d.get("lan_ip") or d.get("ip") or "")
    if source == "wan_ip":
        return str(d.get("wan_ip") or "")
    if source == "iface":
        return str(d.get("iface") or "")
    if source == "hostname":
        return str(d.get("hostname") or "")
    if source == "uptime":
        return str(d.get("uptime") or "")
    if source == "clock":
        return str(d.get("clock") or "")
    if source == "hm":
        return str(d.get("hm") or "")
    if source == "date":
        return str(d.get("date") or "")
    if source == "weekday":
        return str(d.get("weekday") or "")
    return ""


def _custom_bar_value(source, d):
    if source == "cpu":
        return float(d.get("cpu", 0))
    if source == "mem":
        return float(d.get("mem") or 0)
    if source == "temp":
        return float(d.get("temp") or 0)
    if source == "fan_pwm":
        return float(d.get("fan_pwm", 0))
    return 0.0


def _clamp_int(v, lo, hi, default):
    try:
        v = int(v)
    except (TypeError, ValueError):
        v = default
    return max(lo, min(hi, v))


def custom_default_layout():
    return {
        "bg": "#0a0c12",
        "elements": [
            {"type": "text", "x": 6, "y": 4, "size": 1, "color": "#c2ccdc", "text": "CPU"},
            {"type": "bar", "x": 36, "y": 3, "w": 150, "h": 8, "source": "cpu", "color": "auto"},
            {"type": "value", "x": 192, "y": 3, "size": 1, "color": "#eef2fa", "source": "cpu", "suffix": "%"},
            {"type": "text", "x": 6, "y": 28, "size": 1, "color": "#c2ccdc", "text": "MEM"},
            {"type": "bar", "x": 36, "y": 27, "w": 150, "h": 8, "source": "mem", "color": "auto"},
            {"type": "value", "x": 192, "y": 27, "size": 1, "color": "#eef2fa", "source": "mem", "suffix": "%"},
            {"type": "text", "x": 6, "y": 52, "size": 1, "color": "#c2ccdc", "text": "TMP"},
            {"type": "bar", "x": 36, "y": 51, "w": 150, "h": 8, "source": "temp", "color": "auto"},
            {"type": "value", "x": 192, "y": 51, "size": 1, "color": "#eef2fa", "source": "temp", "suffix": "C"},
            {"type": "value", "x": 232, "y": 4, "size": 1, "color": "#eef2fa", "source": "fan_rpm", "suffix": " RPM"},
            {"type": "value", "x": 232, "y": 28, "size": 1, "color": "#c2ccdc", "source": "clock"},
            {"type": "value", "x": 232, "y": 52, "size": 1, "color": "#c2ccdc", "source": "date"},
        ],
    }


def _bg_frame_to_rgb888(frame):
    """Convert one 76x284 fb90m RGB565LE frame to physical 284x76 RGB888."""
    out = bytearray(PHYS_W * PHYS_H * 3)
    if not isinstance(frame, (bytes, bytearray)) or len(frame) < FB_BYTES:
        return bytes(out)
    o = 0
    for px in range(PHYS_W):
        y_fb = FB_H - 1 - px
        base = y_fb * FB_W * 2
        for py in range(PHYS_H):
            bi = base + py * 2
            c = frame[bi] | (frame[bi + 1] << 8)
            r = (c >> 11) & 0x1F
            g = (c >> 5) & 0x3F
            b = c & 0x1F
            out[o] = (r << 3) | (r >> 2)
            out[o + 1] = (g << 2) | (g >> 4)
            out[o + 2] = (b << 3) | (b >> 2)
            o += 3
    return bytes(out)


def load_custom_background(path, max_frames=600):
    """Load a background frame pack once; return physical RGB888 frames."""
    if not path:
        return []
    try:
        with open(os.path.join(path, "manifest.json"), "r") as f:
            manifest = json.load(f)
        frames = manifest.get("frames") or []
        out = []
        for fr in frames[:max_frames]:
            name = fr.get("file") if isinstance(fr, dict) else None
            if not name or "/" in name or ".." in name:
                continue
            fp = os.path.join(path, name)
            with open(fp, "rb") as f:
                data = f.read(FB_BYTES)
            if len(data) == FB_BYTES:
                out.append(_bg_frame_to_rgb888(data))
        return out
    except Exception:
        return []


def make_custom_renderer(cfg):
    """Return a renderer that cycles an optional custom background frame pack."""
    frames = load_custom_background(cfg.get("custom_bg_dir"), 600)
    cfg["_custom_bg_loaded"] = bool(frames)
    state = {"i": 0}

    def render(canvas, d, cfg2):
        bg = None
        if frames:
            bg = frames[state["i"] % len(frames)]
            state["i"] += 1
        render_custom(canvas, d, cfg2, bg)

    return render


def render_custom(canvas, d, cfg, background=None):
    """Render the user-defined layout stored in cfg['custom_layout'].

    Every field is clamped again here: the layout is user JSON and must never
    be able to draw outside the 284x76 canvas or crash the daemon.
    """
    layout = cfg.get("custom_layout")
    if not isinstance(layout, dict):
        layout = custom_default_layout()
    if background is not None:
        canvas.load_rgb888(background)
    else:
        canvas.clear(_hex_rgb(layout.get("bg"), BG))
    elements = layout.get("elements")
    if not isinstance(elements, list):
        elements = custom_default_layout()["elements"]

    for el in elements[:64]:
        if not isinstance(el, dict):
            continue
        etype = el.get("type")
        if etype not in ("text", "value", "bar", "rect", "line"):
            continue
        x = _clamp_int(el.get("x"), 0, PHYS_W - 1, 0)
        y = _clamp_int(el.get("y"), 0, PHYS_H - 1, 0)
        size = _clamp_int(el.get("size"), 1, 3, 1)
        color = _hex_rgb(el.get("color"), WHITE)
        align = el.get("align") if el.get("align") in ("left", "center", "right") else "left"

        if etype == "text":
            text = str(el.get("text") or "")[:64]
            if not text:
                continue
            tw = text_width(text, size)
            if align == "center":
                x = x - tw // 2
            elif align == "right":
                x = x - tw
            canvas.draw_text(x, y, text, color, size)
            continue

        if etype == "value":
            src = el.get("source")
            if src not in CUSTOM_SOURCES:
                continue
            text = str(el.get("prefix") or "") + _custom_value(src, d) + str(el.get("suffix") or "")
            text = text[:64]
            tw = text_width(text, size)
            if align == "center":
                x = x - tw // 2
            elif align == "right":
                x = x - tw
            canvas.draw_text(x, y, text, color, size)
            continue

        if etype == "bar":
            src = el.get("source")
            if src not in ("cpu", "mem", "temp", "fan_pwm"):
                continue
            w = _clamp_int(el.get("w"), 1, PHYS_W, 120)
            h = _clamp_int(el.get("h"), 1, PHYS_H, 8)
            pct = _custom_bar_value(src, d)
            c = color
            if el.get("color") == "auto":
                c = temp_color(pct) if src == "temp" else bar_color(pct)
            canvas.draw_bar(x, y, w, h, pct, c)
            if el.get("show_value"):
                text = str(el.get("prefix") or "") + _custom_value(src, d) + str(el.get("suffix") or "")
                tx = x + w + 5
                if tx + text_width(text, 1) <= PHYS_W:
                    canvas.draw_text(tx, y + 1, text, WHITE, 1)
            continue

        if etype == "rect":
            w = _clamp_int(el.get("w"), 1, PHYS_W, 20)
            h = _clamp_int(el.get("h"), 1, PHYS_H, 2)
            canvas.fill_rect(x, y, w, h, color)
            continue

        if etype == "line":
            w = _clamp_int(el.get("w"), 1, PHYS_W, 100)
            canvas.fill_rect(x, y, w, 1, color)


def build_pages(cfg):
    """Return ordered list of (key, render_fn) selected by the dashboard flags."""
    if cfg.get("mode") == "custom":
        return [("custom", make_custom_renderer(cfg))]
    pages = []
    if cfg.get("show_time"):
        pages.append(("clock", render_clock))
    if cfg.get("show_cpu") or cfg.get("show_mem") or cfg.get("show_temp") or cfg.get("show_net"):
        pages.append(("status", render_status))
    return pages


# --------------------------------------------------------------------------
# CST816X capacitive touch (/dev/input/event0). Single-touch ABS protocol.
# struct input_event on aarch64: timeval (2x Q) + type H + code H + value i.
# --------------------------------------------------------------------------
import time as _time2

EV_SYN, EV_KEY, EV_ABS = 0, 1, 3
SYN_REPORT = 0
BTN_TOUCH = 330
ABS_X, ABS_Y = 0, 1
MT_X, MT_Y = 57, 56
EV_FMT = "=QQHHi"
EVENT_SZ = struct.calcsize(EV_FMT)
LONG_PRESS = 1.5
TAP_MAX = 0.35

# CST816X on this board does NOT emit BTN_TOUCH. Finger presence rides MT_X(57):
# 0 = down / tracking, -1 = lifted. The driver swaps axes: the real horizontal
# value arrives on ABS_Y(1) and the real vertical value on ABS_X(0). Fixed raw
# ranges below match the 284x76 panel so a single tap is not stretched by the
# running min/max adaptive normalization.
RAW_X_MIN, RAW_X_MAX = 0, 280
RAW_Y_MIN, RAW_Y_MAX = 0, 71


class TouchReader:
    def __init__(self, dev="/dev/input/event0", enabled=True, action="next",
                 swap_xy=False, flip_x=False):
        self.dev = dev
        self.enabled = enabled
        self.action = action  # next | wake | none
        self.swap_xy = swap_xy
        self.flip_x = flip_x
        self.fd = None
        self.available = False
        self.active = False
        self.raw_x = None
        self.raw_y = None
        self.down_at = 0.0
        self.last_x = -1
        self.last_y = -1
        self.last_gesture = "none"
        self.last_raw = ""
        # Raw observed extremes, used only for on-screen calibration feedback.
        self.rx_min, self.rx_max = 10 ** 9, -10 ** 9
        self.ry_min, self.ry_max = 10 ** 9, -10 ** 9
        self.samples = 0

    def open(self):
        if not self.enabled or self.action == "none":
            return False
        try:
            self.fd = os.open(self.dev, os.O_RDONLY | os.O_NONBLOCK)
            self.available = True
            return True
        except Exception:
            self.available = False
            return False

    def close(self):
        if self.fd is not None:
            try:
                os.close(self.fd)
            except Exception:
                pass
            self.fd = None
        self.available = False

    def _read(self):
        if self.fd is None:
            return b""
        try:
            return os.read(self.fd, 128 * EVENT_SZ)
        except (BlockingIOError, OSError):
            return b""

    def _observe_range(self, x, y):
        if x < self.rx_min:
            self.rx_min = x
        if x > self.rx_max:
            self.rx_max = x
        if y < self.ry_min:
            self.ry_min = y
        if y > self.ry_max:
            self.ry_max = y
        self.samples += 1

    def range_text(self):
        if self.samples == 0:
            return "-"
        return "%d..%d / %d..%d n=%d" % (
            self.rx_min, self.rx_max, self.ry_min, self.ry_max, self.samples)

    def _press_down(self):
        if not self.active:
            self.active = True
            self.down_at = _time2.monotonic()

    def _press_up(self, gestures):
        """Finger lifted: resolve a tap / long-press gesture from the last point."""
        if not self.active:
            return
        self.active = False
        if self.raw_x is None:
            return
        px, py = self._normalize(self.raw_x, self.raw_y)
        self.last_x, self.last_y = px, py
        self.last_raw = "%d,%d" % (self.raw_x, self.raw_y)
        held = _time2.monotonic() - self.down_at
        if held >= LONG_PRESS:
            gestures.append("exit")
            self.last_gesture = "exit"
        elif held <= TAP_MAX:
            g = self._tap_gesture(px)
            if g:
                gestures.append(g)
                self.last_gesture = g

    def _normalize(self, x, y):
        if self.swap_xy:
            x, y = y, x
        px = (x - RAW_X_MIN) * PHYS_W // (RAW_X_MAX - RAW_X_MIN)
        py = (y - RAW_Y_MIN) * PHYS_H // (RAW_Y_MAX - RAW_Y_MIN)
        if self.flip_x:
            px = PHYS_W - 1 - px
        return max(0, min(PHYS_W - 1, px)), max(0, min(PHYS_H - 1, py))

    def _tap_gesture(self, px):
        if self.action != "next":
            return None
        # left third = previous, middle/right = next
        return "prev" if px < PHYS_W // 3 else "next"

    def poll(self):
        """Return pending gestures: 'next' | 'prev' | 'exit'. Non-blocking."""
        gestures = []
        if not self.available:
            return gestures
        data = self._read()
        if not data:
            return gestures
        for i in range(0, len(data) - EVENT_SZ + 1, EVENT_SZ):
            _sec, _us, etype, code, value = struct.unpack(EV_FMT, data[i:i + EVENT_SZ])
            if etype == EV_KEY and code == BTN_TOUCH:
                # Legacy protocol: finger down / up key events.
                if value:
                    self._press_down()
                else:
                    self._press_up(gestures)
            elif etype == EV_ABS:
                if code == ABS_Y:
                    # Driver swapped axes: this value is the horizontal position.
                    self.raw_x = value
                    self._observe_range(value, self.raw_y or 0)
                elif code == ABS_X:
                    # This value is the vertical position.
                    self.raw_y = value
                    self._observe_range(self.raw_x or 0, value)
                elif code == MT_X:
                    # Present flag shared on MT_X: 0 = down, -1 = lifted.
                    if value == -1:
                        self._press_up(gestures)
                    else:
                        self._press_down()
            elif etype == EV_SYN and code == SYN_REPORT and self.active:
                if self.raw_x is not None:
                    px, py = self._normalize(self.raw_x, self.raw_y)
                    self.last_x, self.last_y = px, py
        return gestures


def run_dashboard(cfg, fb, should_stop, write_status, exit_requested):
    """Main dashboard loop. Returns a short reason string when it stops.

    cfg         : resolved glanim globals (dashboard/touch flags)
    fb          : already opened /dev/fb0 descriptor
    should_stop : callable -> bool, true when SIGTERM requested
    write_status: callable(**kw) writing /tmp/glanim.status
    exit_requested: callable(), raised by long-press touch to leave OEM screen
    """
    pages = build_pages(cfg)
    if not pages:
        write_status(error="no dashboard item selected")
        return "empty"

    col = Collector()
    col.prime()

    touch = TouchReader(
        enabled=cfg.get("touch_enable", True),
        action=cfg.get("touch_action", "next"),
        swap_xy=cfg.get("touch_swap_xy", False),
        flip_x=cfg.get("touch_flip_x", False))
    touch.open()

    interval = max(2, int(cfg.get("dash_interval", "5") or 5))
    animating = bool(cfg.get("mode") == "custom" and cfg.get("_custom_bg_loaded"))
    try:
        bg_fps = int(cfg.get("custom_bg_fps", "8") or 8)
    except Exception:
        bg_fps = 8
    bg_fps = max(1, min(15, bg_fps))
    frame_interval = (1.0 / bg_fps) if animating else 1.0
    last_data = 0.0
    last_status = 0.0
    idx = 0
    switch_at = _time.time()
    canvas = Canvas()
    data = col.snapshot()
    last_data = _time.time()

    while not should_stop():
        for g in touch.poll():
            if g == "exit":
                exit_requested()
                touch.close()
                return "exit"
            if g == "next":
                idx = (idx + 1) % len(pages)
                switch_at = _time.time()
            elif g == "prev":
                idx = (idx - 1) % len(pages)
                switch_at = _time.time()

        now = _time.time()
        if len(pages) > 1 and now - switch_at >= interval:
            idx = (idx + 1) % len(pages)
            switch_at = now

        if now - last_data >= 1.0:
            data = col.snapshot()
            last_data = now
        pages[idx][1](canvas, data, cfg)
        frame = canvas.render_fb()
        try:
            os.lseek(fb, 0, os.SEEK_SET)
            os.write(fb, frame)
        except Exception as e:
            write_status(error="fb write: %s" % e)

        if now - last_status >= 1.0:
            write_status(
                page=pages[idx][0],
                page_count=len(pages),
                touch_present="1" if touch.available else "0",
                touch_action=cfg.get("touch_action", "next"),
                touch_x=touch.last_x,
                touch_y=touch.last_y,
                touch_gesture=touch.last_gesture,
                touch_raw=touch.last_raw,
                touch_range=touch.range_text(),
                cpu=data["cpu"], mem=data["mem"], temp=data["temp"],
                rx_kbps=data["rx_kbps"], tx_kbps=data["tx_kbps"],
                net_iface=data["iface"], ip=data["ip"],
                lan_ip=data.get("lan_ip", ""), wan_ip=data.get("wan_ip", ""),
                hostname=data.get("hostname", ""),
                fan_rpm=data.get("fan_rpm", 0), fan_pwm=data.get("fan_pwm", 0),
                clock=data["clock"], date=data["date"], weekday=data["weekday"],
                uptime=data["uptime"], error="")
            last_status = now

        # frame tick; background animation wakes at the configured fps.
        slept = 0.0
        while slept < frame_interval and not should_stop():
            step = min(0.1, frame_interval - slept)
            _time.sleep(step)
            slept += step

    touch.close()
    return "stop"
