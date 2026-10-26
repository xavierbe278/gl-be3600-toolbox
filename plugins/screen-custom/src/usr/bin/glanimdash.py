#!/usr/bin/env python3
# glanimdash.py - system information dashboard, touch handling and 5x7 font
# for the GL-BE3600 284x76 horizontal ST7789 panel (fb0 76x284 RGB565LE).
# Stdlib only, shared by /usr/bin/glanimd. Imported for offline unit tests too.

import json
import struct

PHYS_W, PHYS_H = 284, 76
FB_W, FB_H = 76, 284
FB_BYTES = FB_W * FB_H * 2
BL_PATH = "/sys/class/backlight/soc:backlight/brightness"


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
FONT_PACKS = ("classic", "bold", "compact")
CURRENT_FONT = "classic"


def set_font(name):
    global CURRENT_FONT
    CURRENT_FONT = name if name in FONT_PACKS else "classic"
    return CURRENT_FONT


def glyph(ch, font=None):
    font = font or CURRENT_FONT
    cols = FONT.get(ch.upper(), FONT[" "])
    if font == "compact":
        return cols[:4]
    if font == "bold":
        return tuple(((c | (c >> 1) | (c << 1)) & 0x7F) for c in cols)
    return cols


def glyph_width(font=None):
    return 4 if (font or CURRENT_FONT) == "compact" else 5


def glyph_advance(font=None):
    return glyph_width(font) + 1


def text_width(text, scale=1, font=None):
    return len(text) * glyph_advance(font) * scale - scale


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
        self.font = CURRENT_FONT
        self.background = None
        self.bg_dim = 1.0
        self.transparent = False
        self.mask = None
        self.content_alpha = 1.0

    def clear(self, rgb=BG):
        if self.transparent:
            return
        if self.background is not None:
            if self.bg_dim >= 0.999:
                self.buf[:] = self.background
            else:
                f = self.bg_dim
                src = self.background
                for i in range(len(src)):
                    self.buf[i] = int(src[i] * f)
            return
        for i in range(0, len(self.buf), 3):
            self.buf[i] = rgb[0]
            self.buf[i + 1] = rgb[1]
            self.buf[i + 2] = rgb[2]

    def pixel(self, x, y, rgb):
        if 0 <= x < PHYS_W and 0 <= y < PHYS_H:
            o = (y * PHYS_W + x) * 3
            if self.content_alpha < 0.999:
                a = self.content_alpha
                self.buf[o] = int(self.buf[o] * (1 - a) + rgb[0] * a)
                self.buf[o + 1] = int(self.buf[o + 1] * (1 - a) + rgb[1] * a)
                self.buf[o + 2] = int(self.buf[o + 2] * (1 - a) + rgb[2] * a)
            else:
                self.buf[o] = rgb[0]
                self.buf[o + 1] = rgb[1]
                self.buf[o + 2] = rgb[2]
            if self.mask is not None:
                self.mask[y * PHYS_W + x] = 1

    def load_rgb888(self, data):
        """Replace the whole canvas with a pre-decoded 284x76 RGB888 buffer."""
        if data is not None and len(data) == len(self.buf):
            self.buf[:] = data

    def fill_rect(self, x, y, w, h, rgb):
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                self.pixel(xx, yy, rgb)

    def fill_rect_alpha(self, x, y, w, h, rgb, alpha):
        a = max(0.0, min(1.0, alpha))
        for yy in range(y, y + h):
            for xx in range(x, x + w):
                if 0 <= xx < PHYS_W and 0 <= yy < PHYS_H:
                    o = (yy * PHYS_W + xx) * 3
                    self.buf[o] = int(self.buf[o] * (1 - a) + rgb[0] * a)
                    self.buf[o + 1] = int(self.buf[o + 1] * (1 - a) + rgb[1] * a)
                    self.buf[o + 2] = int(self.buf[o + 2] * (1 - a) + rgb[2] * a)

    def draw_text(self, x, y, text, color=WHITE, scale=1, shadow=None):
        if shadow is None:
            shadow = self.background is not None
        if shadow:
            self.draw_text(x + 1, y + 1, text, (0, 0, 0), scale, False)
        cx = x
        w = glyph_width(self.font)
        adv = glyph_advance(self.font)
        for ch in text:
            cols = glyph(ch, self.font)
            for c in range(w):
                bits = cols[c]
                for r in range(GLYPH_H):
                    if (bits >> r) & 1:
                        for sy in range(scale):
                            for sx in range(scale):
                                self.pixel(cx + c * scale + sx,
                                           y + r * scale + sy, color)
            cx += adv * scale
        return cx

    def draw_cjk(self, x, y, text, color=WHITE, scale=1, shadow=None):
        if shadow is None:
            shadow = self.background is not None
        if shadow:
            self.draw_cjk(x + 1, y + 1, text, (0, 0, 0), scale, False)
        cx = x
        for ch in text:
            rows = CJK_FONT.get(ch)
            if not rows:
                self.draw_text(cx, y, ch, color, scale)
                cx += 13 * scale
                continue
            for r in range(len(rows)):
                bits = int(rows[r], 16)
                for c in range(12):
                    if (bits >> c) & 1:
                        for sy in range(scale):
                            for sx in range(scale):
                                self.pixel(cx + c * scale + sx,
                                           y + r * scale + sy, color)
            cx += 13 * scale
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
import math
import array
import time as _time
import subprocess
import socket
import urllib.request
import urllib.parse


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


def _process_running(name):
    try:
        for pid in os.listdir("/proc"):
            if not pid.isdigit():
                continue
            try:
                with open("/proc/" + pid + "/comm") as f:
                    if f.read().strip() == name:
                        return True
            except Exception:
                pass
    except Exception:
        pass
    return False


def _process_stats(name):
    """Return (rss_mb, uptime_seconds) for the first process named name."""
    pid = None
    try:
        for p in os.listdir("/proc"):
            if not p.isdigit():
                continue
            try:
                with open("/proc/" + p + "/comm") as f:
                    if f.read().strip() == name:
                        pid = p
                        break
            except Exception:
                pass
    except Exception:
        return (0, 0)
    if not pid:
        return (0, 0)
    rss = 0
    start_ticks = 0
    try:
        with open("/proc/" + pid + "/status") as f:
            for line in f:
                if line.startswith("VmRSS:"):
                    rss = int(line.split()[1])
                    break
    except Exception:
        pass
    try:
        with open("/proc/" + pid + "/stat") as f:
            fields = f.read().split()
        start_ticks = int(fields[21])
    except Exception:
        pass
    try:
        with open("/proc/uptime") as f:
            total = float(f.read().split()[0])
        hz = os.sysconf("SC_CLK_TCK") or 100
        uptime = max(0, int(total - start_ticks / float(hz)))
    except Exception:
        uptime = 0
    return (max(0, int(round(rss / 1024.0))), uptime)


def fmt_duration(sec):
    sec = max(0, int(sec or 0))
    h, m = sec // 3600, (sec % 3600) // 60
    if h:
        return "%dh%02dm" % (h, m)
    return "%dm" % m


def current_auto(cfg):
    try:
        with open("/tmp/glanim.auto", "r") as f:
            return f.read().strip() == "1"
    except Exception:
        return bool(cfg.get("auto_rotate", True))


def current_blur(cfg):
    try:
        with open("/tmp/glanim.blur", "r") as f:
            return max(0.0, min(100.0, float(f.read().strip())))
    except Exception:
        try:
            return max(0.0, min(100.0, float(cfg.get("bg_blur", 0))))
        except Exception:
            return 0.0


def frost_frame(data, blur):
    """Box-blur + light frost, matching the web preview's blur filter."""
    if blur <= 0 or len(data) < PHYS_W * PHYS_H * 3:
        return data
    radius = max(1, int(round(blur / 100.0 * 4.0)))
    tmp = bytearray(len(data))
    # Horizontal box blur.
    for y in range(PHYS_H):
        row = y * PHYS_W * 3
        for x in range(PHYS_W):
            lo = max(0, x - radius)
            hi = min(PHYS_W - 1, x + radius)
            r = g = b = 0
            for xx in range(lo, hi + 1):
                i = row + xx * 3
                r += data[i]; g += data[i + 1]; b += data[i + 2]
            n = hi - lo + 1
            o = row + x * 3
            tmp[o] = r // n; tmp[o + 1] = g // n; tmp[o + 2] = b // n
    out = bytearray(len(data))
    # Vertical box blur.
    for y in range(PHYS_H):
        lo = max(0, y - radius)
        hi = min(PHYS_H - 1, y + radius)
        for x in range(PHYS_W):
            r = g = b = 0
            for yy in range(lo, hi + 1):
                i = (yy * PHYS_W + x) * 3
                r += tmp[i]; g += tmp[i + 1]; b += tmp[i + 2]
            n = hi - lo + 1
            o = (y * PHYS_W + x) * 3
            out[o] = r // n; out[o + 1] = g // n; out[o + 2] = b // n
    tint = 0.12 * blur / 100.0
    if tint > 0:
        for i in range(len(out)):
            out[i] = int(out[i] * (1.0 - tint) + 235 * tint)
    return bytes(out)


def current_brightness(cfg):
    try:
        with open("/tmp/glanim.brightness", "r") as f:
            return max(0, min(11, int(float(f.read().strip()))))
    except Exception:
        try:
            return max(0, min(11, int(cfg.get("brightness", 4))))
        except Exception:
            return 4


def apply_brightness(value):
    try:
        with open(BL_PATH, "w") as f:
            f.write(str(max(0, min(11, int(value)))))
        return True
    except Exception:
        return False


def current_content_alpha(cfg):
    try:
        with open("/tmp/glanim.content_alpha", "r") as f:
            return max(0.0, min(100.0, float(f.read().strip()))) / 100.0
    except Exception:
        try:
            return max(0.0, min(100.0, float(cfg.get("content_alpha", 100)))) / 100.0
        except Exception:
            return 1.0


def current_mask(cfg):
    try:
        with open("/tmp/glanim.mask", "r") as f:
            return max(0.0, min(100.0, float(f.read().strip())))
    except Exception:
        try:
            return max(0.0, min(100.0, float(cfg.get("bg_mask", 45))))
        except Exception:
            return 45.0


def _conntrack_count():
    try:
        with open("/proc/sys/net/netfilter/nf_conntrack_count") as f:
            return max(0, int(f.read().strip() or 0))
    except Exception:
        pass
    try:
        return max(0, int(os.popen("conntrack -C 2>/dev/null").read().strip() or 0))
    except Exception:
        return 0


def _oc_mode():
    try:
        with open("/etc/config/openclash") as f:
            for line in f:
                line = line.strip()
                if line.startswith("option proxy_mode"):
                    return line.split("'")[1] if "'" in line else "rule"
    except Exception:
        pass
    return "rule"


def fmt_bytes(n):
    n = max(0, int(n or 0))
    if n >= 1024 ** 3:
        return "%.2fGB" % (n / 1024.0 ** 3)
    if n >= 1024 ** 2:
        return "%.1fMB" % (n / 1024.0 ** 2)
    if n >= 1024:
        return "%dKB" % (n // 1024)
    return "%dB" % n


COUNTRY_NAMES = {
    "美国": "US", "中國": "CN", "中国": "CN", "香港": "HK", "台湾": "TW", "台灣": "TW",
    "日本": "JP", "韩国": "KR", "韓國": "KR", "新加坡": "SG", "英国": "GB", "英國": "GB",
    "德国": "DE", "德國": "DE", "法国": "FR", "法國": "FR", "加拿大": "CA", "澳洲": "AU",
    "澳大利亚": "AU", "荷兰": "NL", "荷蘭": "NL", "俄罗斯": "RU", "俄羅斯": "RU",
    "印度": "IN", "土耳其": "TR", "巴西": "BR", "阿根廷": "AR", "马来西亚": "MY",
    "泰國": "TH", "泰国": "TH", "越南": "VN", "菲律宾": "PH", "印尼": "ID",
}
CJK_FONT = {
    '一': ('000', '000', '000', '000', '000', '000', '000', '3ff', '000', '000', '000', '000', '000'),
    '上': ('000', '000', '000', '010', '010', '010', '1f0', '010', '010', '010', '010', '3ff', '000'),
    '下': ('000', '000', '000', '3ff', '010', '010', '070', '0d0', '110', '010', '010', '010', '010'),
    '中': ('000', '000', '000', '030', '030', '1fe', '132', '132', '1fe', '030', '030', '030', '000'),
    '亚': ('000', '000', '000', '3ff', '048', '14a', '14a', '1ce', '0cc', '048', '048', '3ff', '000'),
    '亮': ('000', '000', '000', '010', '3ff', '0fc', '0fc', '000', '3ff', '278', '24c', '1c7', '000'),
    '代': ('000', '000', '000', '0a4', '124', '3e6', '07f', '027', '066', '246', '2c6', '186', '000'),
    '优': ('000', '000', '000', '0a4', '124', '3fe', '063', '063', '052', '252', '24a', '1ce', '000'),
    '俄': ('000', '000', '044', '1fe', '152', '052', '3ff', '3d3', '1fe', '092', '2f2', '31a', '000'),
    '入': ('000', '000', '000', '008', '010', '030', '030', '078', '048', '084', '186', '303', '000'),
    '全': ('000', '000', '000', '030', '058', '084', '3ff', '030', '1fe', '030', '030', '1fe', '000'),
    '兰': ('000', '000', '000', '084', '048', '3ff', '000', '000', '1fe', '000', '000', '3ff', '000'),
    '关': ('000', '000', '000', '0c4', '048', '1fe', '030', '3ff', '030', '048', '08c', '303', '000'),
    '其': ('000', '000', '000', '084', '3ff', '084', '0fc', '0fc', '084', '3ff', '0cc', '303', '000'),
    '再': ('000', '000', '000', '3fe', '030', '1fe', '132', '1fe', '3ff', '102', '102', '0c2', '000'),
    '减': ('000', '000', '180', '183', '3fa', '088', '2f8', '1fa', '1da', '2d7', '3f5', '364', '000'),
    '出': ('000', '000', '030', '132', '132', '132', '1fe', '130', '132', '132', '132', '1fe', '000'),
    '击': ('000', '000', '030', '030', '1fe', '030', '030', '3ff', '030', '132', '132', '1fe', '000'),
    '切': ('000', '000', '002', '3f2', '122', '12f', '122', '122', '12a', '13e', '112', '1c8', '000'),
    '则': ('000', '000', '000', '15e', '15e', '15e', '15e', '15e', '156', '14c', '116', '1f3', '000'),
    '利': ('000', '000', '000', '11c', '14f', '144', '17f', '15c', '156', '147', '105', '1c4', '000'),
    '加': ('000', '000', '000', '004', '3df', '354', '356', '356', '352', '352', '3da', '34d', '000'),
    '动': ('000', '000', '000', '040', '05e', '3e0', '25f', '346', '34a', '32a', '13f', '190', '000'),
    '单': ('000', '000', '084', '048', '1fe', '132', '1fe', '132', '1fe', '030', '3ff', '030', '030'),
    '南': ('000', '000', '000', '030', '3ff', '030', '1fe', '14a', '1fe', '1fe', '132', '1f2', '000'),
    '印': ('000', '000', '000', '1ee', '122', '122', '13e', '122', '122', '13a', '1e7', '020', '000'),
    '即': ('000', '000', '000', '1de', '152', '15e', '152', '15e', '152', '15a', '1fa', '042', '000'),
    '台': ('000', '000', '010', '008', '08c', '1f6', '20f', '000', '1fe', '102', '102', '1fe', '000'),
    '后': ('000', '000', '000', '1e0', '03e', '002', '3fe', '002', '1fa', '10a', '10a', '1f9', '000'),
    '启': ('000', '000', '000', '030', '1fe', '102', '1fe', '002', '1fa', '10a', '10b', '1f9', '000'),
    '回': ('000', '000', '000', '1fe', '102', '17a', '14a', '14a', '14a', '17a', '102', '1fe', '000'),
    '国': ('000', '000', '000', '1fe', '102', '1fe', '132', '1fe', '172', '1fe', '102', '1fe', '000'),
    '土': ('000', '000', '000', '030', '030', '030', '1fe', '030', '030', '030', '030', '3ff', '000'),
    '在': ('000', '000', '000', '008', '3ff', '04c', '044', '1fe', '046', '047', '044', '3fc', '000'),
    '坡': ('000', '000', '000', '042', '3f2', '25f', '052', '1f2', '132', '0df', '0c8', '338', '000'),
    '大': ('000', '000', '030', '030', '030', '3ff', '030', '030', '078', '048', '086', '303', '000'),
    '失': ('000', '000', '000', '024', '026', '1fe', '022', '030', '3ff', '030', '0cc', '303', '000'),
    '宾': ('000', '000', '000', '030', '3ff', '3e3', '03c', '1fc', '044', '3ff', '0cc', '102', '000'),
    '将': ('000', '000', '000', '024', '3f5', '18f', '0e6', '1be', '3fe', '195', '1a4', '0c4', '000'),
    '尼': ('000', '000', '000', '1fe', '102', '1fe', '00a', '10a', '0ca', '23a', '21a', '1f1', '000'),
    '局': ('000', '000', '000', '1fe', '102', '1fe', '1fe', '102', '17a', '14a', '17b', '101', '1c0'),
    '屏': ('000', '000', '000', '1fe', '102', '1fe', '092', '1fe', '092', '3fe', '09b', '089', '000'),
    '已': ('000', '000', '000', '1fe', '100', '102', '1fe', '102', '002', '202', '302', '1fe', '000'),
    '巴': ('000', '000', '000', '1fe', '132', '132', '1fe', '102', '002', '202', '302', '1fe', '000'),
    '幕': ('000', '000', '048', '3ff', '1fe', '1fe', '102', '1fe', '3fe', '3ff', '094', '0d0', '000'),
    '度': ('000', '000', '000', '020', '3fe', '09a', '3fe', '0fa', '1fe', '0d2', '073', '38d', '000'),
    '廷': ('000', '000', '000', '1f7', '046', '042', '1f7', '045', '046', '3f6', '00e', '3f9', '000'),
    '式': ('000', '000', '0e0', '160', '3ff', '060', '040', '05f', '044', '24c', '2bf', '180', '000'),
    '律': ('000', '000', '000', '044', '1f2', '3fd', '146', '1f2', '043', '1fa', '3fa', '042', '000'),
    '德': ('000', '000', '000', '044', '3fa', '1fd', '1ae', '1fa', '3fb', '1da', '29e', '0e2', '000'),
    '扇': ('000', '000', '000', '030', '1fe', '102', '1fe', '1fe', '17a', '1ba', '177', '199', '000'),
    '手': ('000', '000', '1e0', '03e', '030', '1fe', '030', '030', '3ff', '030', '030', '01c', '000'),
    '拿': ('000', '000', '030', '0cc', '37b', '0fc', '0fc', '000', '1fe', '1fe', '3ff', '018', '000'),
    '按': ('000', '000', '042', '042', '3ff', '222', '022', '3fe', '093', '0f2', '0e2', '31b', '000'),
    '换': ('000', '000', '000', '022', '1f2', '097', '1fa', '15e', '153', '3fa', '0a2', '31b', '000'),
    '斯': ('000', '000', '000', '392', '07f', '052', '3de', '15e', '132', '13f', '13a', '121', '000'),
    '新': ('000', '000', '000', '3ff', '032', '02a', '3ff', '124', '13f', '12e', '135', '116', '000'),
    '无': ('000', '000', '000', '1fe', '010', '010', '3ff', '030', '028', '22c', '226', '1c3', '000'),
    '日': ('000', '000', '000', '1fe', '186', '186', '186', '1fe', '186', '186', '186', '1fe', '000'),
    '曲': ('000', '000', '048', '048', '1fe', '14a', '14a', '1fe', '14a', '14a', '14a', '1fe', '000'),
    '本': ('000', '000', '030', '030', '3ff', '030', '078', '07c', '0b4', '132', '3fd', '030', '030'),
    '机': ('000', '000', '004', '0f4', '09f', '096', '096', '09f', '095', '294', '294', '38c', '000'),
    '来': ('000', '000', '000', '030', '1fe', '0b4', '0b4', '078', '3ff', '078', '0b4', '333', '030'),
    '根': ('000', '000', '000', '1f6', '116', '1ff', '116', '1fe', '357', '097', '1f6', '336', '000'),
    '模': ('000', '000', '000', '0a2', '3fa', '0af', '1f2', '1fe', '1f3', '043', '3fa', '3ba', '000'),
    '次': ('000', '000', '030', '012', '3f6', '118', '16c', '066', '062', '093', '199', '30c', '000'),
    '法': ('000', '000', '042', '046', '1f8', '043', '042', '3f8', '022', '092', '19a', '3f9', '000'),
    '泰': ('000', '000', '010', '1fe', '010', '1fe', '018', '3ff', '3ef', '0f8', '136', '018', '000'),
    '港': ('000', '000', '000', '092', '1fe', '091', '3fe', '0f8', '29e', '1fa', '11a', '1f3', '000'),
    '湾': ('000', '000', '000', '022', '3fe', '1e9', '1fa', '100', '1fa', '1fa', '102', '1e3', '000'),
    '澳': ('000', '000', '000', '022', '1fe', '1fb', '1fa', '1f8', '14a', '3fe', '1ba', '30f', '000'),
    '点': ('000', '000', '000', '010', '3f0', '010', '1fe', '102', '1fe', '12a', '14a', '259', '000'),
    '猫': ('000', '000', '000', '0a5', '3fe', '0a7', '3fc', '35e', '3fd', '35c', '3fc', '31f', '000'),
    '理': ('000', '000', '000', '1ff', '152', '1f2', '15f', '1f2', '042', '1f2', '04f', '3f8', '000'),
    '直': ('000', '000', '000', '010', '3ff', '010', '1fe', '1fe', '1fe', '102', '1fe', '3ff', '000'),
    '确': ('000', '000', '000', '020', '1ff', '092', '3fa', '3ff', '25b', '3fa', '25e', '1c8', '000'),
    '线': ('000', '000', '000', '1a4', '022', '3ff', '027', '3fa', '147', '0c0', '2ef', '398', '000'),
    '罗': ('000', '000', '000', '1fe', '14a', '14a', '1fe', '1f8', '08c', '059', '030', '00e', '000'),
    '置': ('000', '000', '000', '1fe', '1fe', '010', '3ff', '1fe', '1fe', '1fe', '1fe', '3ff', '000'),
    '美': ('000', '000', '000', '048', '3ff', '030', '1fe', '3ff', '030', '3ff', '0f8', '387', '000'),
    '耳': ('000', '000', '000', '3ff', '084', '0fc', '084', '0fc', '084', '3fc', '08f', '080', '080'),
    '自': ('000', '000', '000', '010', '1fe', '102', '1fe', '102', '102', '1fe', '102', '1fe', '000'),
    '节': ('000', '000', '000', '048', '3ff', '048', '1fe', '108', '108', '188', '0e8', '008', '000'),
    '英': ('000', '000', '000', '048', '3ff', '030', '1fe', '132', '132', '3ff', '048', '387', '000'),
    '荷': ('000', '000', '000', '048', '3ff', '004', '3fe', '17e', '15f', '17e', '106', '0c6', '000'),
    '菜': ('000', '000', '000', '048', '3ff', '000', '1fe', '096', '0f4', '3ff', '0fc', '333', '030'),
    '菲': ('000', '000', '000', '048', '3ff', '000', '3ce', '048', '1ce', '048', '3cf', '048', '000'),
    '西': ('000', '000', '000', '3ff', '058', '3fe', '34a', '34a', '3c6', '302', '302', '3fe', '000'),
    '规': ('000', '000', '000', '1f4', '15f', '154', '154', '15f', '1d6', '2ee', '2ba', '191', '000'),
    '言': ('000', '000', '000', '030', '3ff', '000', '1fe', '1fe', '000', '1fe', '102', '1fe', '000'),
    '认': ('000', '000', '000', '042', '044', '040', '043', '062', '0e2', '0ae', '116', '308', '000'),
    '设': ('000', '000', '000', '1f2', '314', '018', '003', '1fa', '092', '0ee', '0f6', '318', '000'),
    '语': ('000', '000', '000', '1fa', '026', '1f8', '133', '3fa', '002', '1f2', '11e', '1f6', '000'),
    '调': ('000', '000', '000', '3fe', '348', '3eb', '3fa', '36a', '3ae', '3ae', '3ea', '184', '000'),
    '败': ('000', '000', '040', '03f', '3fb', '13f', '13f', '1df', '0df', '0cc', '1ea', '331', '000'),
    '越': ('000', '000', '000', '144', '3fe', '1e4', '1bf', '0e6', '2be', '3d6', '147', '3f9', '000'),
    '返': ('000', '000', '002', '1fa', '01c', '1f8', '13b', '0ea', '0ca', '1ee', '116', '3fd', '000'),
    '进': ('000', '000', '092', '092', '1fe', '090', '093', '3fa', '092', '09a', '08e', '3fd', '000'),
    '连': ('000', '000', '000', '022', '3fe', '050', '05b', '1fa', '042', '3fa', '046', '3fd', '000'),
    '退': ('000', '000', '000', '1f2', '116', '1f0', '1f3', '132', '0d2', '1f2', '11e', '3f9', '000'),
    '选': ('000', '000', '000', '052', '1fe', '040', '3fb', '0b2', '092', '292', '38e', '3fd', '000'),
    '重': ('000', '000', '000', '1fe', '3ff', '030', '1fe', '1fe', '1fe', '030', '1fe', '3ff', '000'),
    '长': ('000', '000', '000', '084', '064', '014', '004', '3ff', '024', '064', '0dc', '30c', '000'),
    '闭': ('000', '000', '002', '3f4', '303', '323', '3ff', '333', '33b', '327', '333', '1c3', '000'),
    '阿': ('000', '000', '000', '3ff', '107', '177', '157', '157', '15f', '17f', '117', '1c3', '000'),
    '面': ('000', '000', '000', '3ff', '010', '1fe', '14a', '17a', '14a', '17a', '14a', '1fe', '000'),
    '韩': ('000', '000', '000', '044', '3ff', '05f', '1f1', '05f', '3ff', '244', '1df', '044', '000'),
    '页': ('000', '000', '000', '3ff', '010', '1fe', '132', '132', '112', '172', '0c8', '307', '000'),
    '风': ('000', '000', '000', '1fe', '1ca', '1aa', '1b2', '1b2', '1ba', '3ea', '3c7', '301', '000'),
    '香': ('000', '000', '000', '0fe', '030', '3ff', '0cc', '3ff', '084', '0fc', '084', '0fc', '000'),
    '马': ('000', '000', '000', '0fe', '084', '084', '084', '3fc', '300', '1ff', '100', '1e0', '000'),
}
COUNTRY_ZH = {
    'US': '美国',
    'HK': '香港',
    'JP': '日本',
    'SG': '新加坡',
    'TW': '台湾',
    'KR': '韩国',
    'GB': '英国',
    'DE': '德国',
    'FR': '法国',
    'CA': '加拿大',
    'AU': '澳大利亚',
    'NL': '荷兰',
    'RU': '俄罗斯',
    'CN': '中国',
    'IN': '印度',
    'TR': '土耳其',
    'BR': '巴西',
    'AR': '阿根廷',
    'MY': '马来西亚',
    'TH': '泰国',
    'VN': '越南',
    'PH': '菲律宾',
    'ID': '印尼',
}

COUNTRY_FLAGS = {
    "US": ((178, 34, 52), (255, 255, 255), (60, 59, 110)),
    "CN": ((222, 41, 16), (255, 222, 60), (222, 41, 16)),
    "HK": ((222, 41, 16), (255, 255, 255), (222, 41, 16)),
    "TW": ((0, 70, 160), (255, 255, 255), (220, 40, 50)),
    "JP": ((255, 255, 255), (220, 40, 50), (255, 255, 255)),
    "KR": ((255, 255, 255), (30, 30, 30), (200, 40, 60)),
    "SG": ((220, 40, 50), (255, 255, 255), (220, 40, 50)),
    "GB": ((30, 60, 140), (255, 255, 255), (200, 40, 60)),
    "DE": ((30, 30, 30), (220, 40, 50), (255, 210, 40)),
    "FR": ((30, 60, 160), (255, 255, 255), (220, 40, 50)),
    "CA": ((220, 40, 50), (255, 255, 255), (220, 40, 50)),
    "AU": ((20, 50, 130), (255, 255, 255), (220, 40, 50)),
    "NL": ((220, 40, 50), (255, 255, 255), (30, 60, 160)),
    "RU": ((255, 255, 255), (30, 60, 160), (220, 40, 50)),
}


def country_code(name):
    for ch, code in COUNTRY_NAMES.items():
        if ch in name:
            return code
    for ch in name:
        cp = ord(ch)
        if 0x1F1E6 <= cp <= 0x1F1FF:
            # Regional indicator sequence: decode all flags in the name.
            letters = []
            for c2 in name:
                cp2 = ord(c2)
                if 0x1F1E6 <= cp2 <= 0x1F1FF:
                    letters.append(chr(ord("A") + cp2 - 0x1F1E6))
            if len(letters) >= 2:
                return "".join(letters[:2])
    import re
    m = re.search(r"(?<![A-Z])([A-Z]{2})(?![A-Z])", name.upper())
    return m.group(1) if m else ""


def rate_from_name(name):
    import re
    m = re.search(r'(?<![\d.])(\d+(?:\.\d+)?)\s*[xX倍]', name)
    if not m:
        m = re.search(r'[xX]\s*(\d+(?:\.\d+)?)', name)
    if not m:
        return "1x"
    try:
        v = float(m.group(1))
    except Exception:
        return "1x"
    if abs(v - round(v)) < 0.001:
        return "%dx" % int(round(v))
    return ("%.2f" % v).rstrip("0").rstrip(".") + "x"


def clean_node_name(name, cc):
    import re
    ascii_name = re.sub(r"[^A-Za-z0-9. -]+", " ", name)
    ascii_name = " ".join(ascii_name.split())
    if not ascii_name:
        digits = re.findall(r"\d+", name)
        ascii_name = digits[-1] if digits else ""
    if cc and not ascii_name.upper().startswith(cc):
        ascii_name = (cc + " " + ascii_name).strip()
    return ascii_name.upper()[:18]


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
        self._node_at = 0.0
        self._node_data = {}
        self._oc_secret = None
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
    def _clash_node(self):
        """Cached Clash API selected-node information (5 s TTL)."""
        now = _time.time()
        if now - self._node_at < 5.0:
            return self._node_data
        self._node_at = now
        data = {}
        if self._oc_secret is None:
            try:
                self._oc_secret = subprocess.check_output(
                    ["uci", "get", "openclash.config.dashboard_password"],
                    stderr=subprocess.DEVNULL).decode().strip()
            except Exception:
                self._oc_secret = ""
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:9090/proxies",
                headers={"Authorization": "Bearer " + self._oc_secret})
            with urllib.request.urlopen(req, timeout=1.5) as r:
                proxies = json.loads(r.read().decode("utf-8", "replace")).get("proxies", {})
            selected = None
            fallback = None
            for name, p in proxies.items():
                if p.get("type") not in ("Selector", "URLTest", "Fallback", "LoadBalance"):
                    continue
                if not p.get("now"):
                    continue
                if name.upper() == "GLOBAL":
                    fallback = (name, p)
                elif selected is None:
                    selected = (name, p)
            selected = selected or fallback
            if selected:
                group, p = selected
                node_name = p.get("now") or ""
                node = proxies.get(node_name, {})
                hist = node.get("history") or []
                delay = 0
                if hist:
                    try:
                        delay = int(hist[-1].get("delay") or 0)
                    except Exception:
                        delay = 0
                cc = country_code(node_name)
                data = {
                    "oc_group": group.upper()[:16],
                    "oc_group_count": len(p.get("all") or []),
                    "oc_node": clean_node_name(node_name, cc),
                    "oc_country": cc or "--",
                    "oc_node_type": str(node.get("type") or "").upper()[:10],
                    "oc_udp": "YES" if node.get("udp") else "NO",
                    "oc_rate": rate_from_name(node_name),
                    "oc_delay": delay,
                }
        except Exception:
            data = {}
        self._node_data = data
        return data

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
        oc_mem, oc_up_sec = _process_stats("clash")
        return {
            "cpu": cpu_pct if cpu_pct is not None else 0,
            "mem": self._mem(),
            "temp": self._temp(),
            "rx_kbps": rx_kbps or 0,
            "tx_kbps": tx_kbps or 0,
            "rx_total": max(0, int(rx or 0)),
            "tx_total": max(0, int(tx or 0)),
            "conn_count": _conntrack_count(),
            "oc_running": _process_running("clash"),
            "oc_mode": _oc_mode(),
            "oc_mem": oc_mem,
            "oc_uptime": fmt_duration(oc_up_sec),
            **self._clash_node(),
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
    "oc_status", "oc_rx", "oc_tx", "oc_total", "oc_conns", "oc_mode",
    "oc_mem", "oc_uptime",
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
    if source == "oc_status":
        return "ON" if d.get("oc_running") else "OFF"
    if source == "oc_rx":
        return fmt_speed(d.get("rx_kbps", 0))
    if source == "oc_tx":
        return fmt_speed(d.get("tx_kbps", 0))
    if source == "oc_total":
        return fmt_bytes((d.get("rx_total") or 0) + (d.get("tx_total") or 0))
    if source == "oc_conns":
        return str(int(d.get("conn_count") or 0))
    if source == "oc_mode":
        return str(d.get("oc_mode") or "rule").upper()
    if source == "oc_mem":
        return "%dMB" % int(d.get("oc_mem") or 0)
    if source == "oc_uptime":
        return str(d.get("oc_uptime") or "0m")
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
    for px in range(PHYS_W):
        y_fb = FB_H - 1 - px
        base = y_fb * FB_W * 2
        for py in range(PHYS_H):
            bi = base + py * 2
            c = frame[bi] | (frame[bi + 1] << 8)
            r = (c >> 11) & 0x1F
            g = (c >> 5) & 0x3F
            b = c & 0x1F
            o = (py * PHYS_W + px) * 3
            out[o] = (r << 3) | (r >> 2)
            out[o + 1] = (g << 2) | (g >> 4)
            out[o + 2] = (b << 3) | (b >> 2)
    return bytes(out)


def load_custom_background(path, max_frames=600):
    """Load a background frame pack once; return physical RGB888 frames."""
    if not path:
        path = "/usr/share/glanim/custom_bg"
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


def load_custom_background_sources(path, max_frames=300):
    """Read the manifest only. Frames are converted lazily, one at a time."""
    if not path:
        path = "/usr/share/glanim/custom_bg"
    try:
        with open(os.path.join(path, "manifest.json"), "r") as f:
            manifest = json.load(f)
        out = []
        for fr in (manifest.get("frames") or [])[:max_frames]:
            name = fr.get("file") if isinstance(fr, dict) else None
            if not name or "/" in name or ".." in name:
                continue
            fp = os.path.join(path, name)
            if os.path.isfile(fp):
                out.append(fp)
        return out
    except Exception:
        return []


def load_background_source(fp):
    try:
        with open(fp, "rb") as f:
            data = f.read(FB_BYTES)
        if len(data) == FB_BYTES:
            return _bg_frame_to_rgb888(data)
    except Exception:
        pass
    return None


def make_custom_renderer(cfg):
    """Return a renderer that cycles an optional custom background frame pack."""
    sources = load_custom_background_sources(cfg.get("custom_bg_dir"), int(cfg.get("custom_bg_max_frames", 300) or 300))
    cfg["_custom_bg_loaded"] = bool(sources)
    state = {"i": 0}

    def render(canvas, d, cfg2):
        bg = None
        if sources:
            bg = load_background_source(sources[state["i"] % len(sources)])
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


def toggle_openclash():
    """Start/stop OpenClash from the panel button; returns a short label."""
    running = _process_running("clash")
    enable = "0" if running else "1"
    action = "stop" if running else "start"
    script = ("uci set openclash.config.enable=%s; uci commit openclash; "
              "/etc/init.d/openclash %s" % (enable, action))
    try:
        subprocess.Popen(["/bin/sh", "-c", script],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        return "FAILED"
    return "STOPPING" if running else "STARTING"


def render_clash(canvas, d, cfg):
    """OpenClash status with a two-column, separated layout."""
    canvas.clear(BG)
    running = bool(d.get("oc_running"))
    mode = str(d.get("oc_mode") or "rule").upper()

    # Header: accent line + title + mode + state.
    canvas.fill_rect(0, 0, PHYS_W, 1, (44, 52, 70))
    canvas.draw_text(8, 5, "OPENCLASH", WHITE, 1)
    on_label = "ON" if running else "OFF"
    on_color = GREEN if running else RED
    btn_x = PHYS_W - 42
    canvas.fill_rect(btn_x, 1, 34, 13, (18, 22, 32))
    canvas.fill_rect(btn_x, 1, 34, 1, (70, 82, 104))
    canvas.fill_rect(btn_x, 13, 34, 1, (70, 82, 104))
    canvas.fill_rect(btn_x, 1, 1, 13, (70, 82, 104))
    canvas.fill_rect(btn_x + 33, 1, 1, 13, (70, 82, 104))
    on_x = btn_x + (34 - text_width(on_label, 1)) // 2
    canvas.draw_text(on_x, 5, on_label, on_color, 1)
    if running:
        mx = btn_x - 10 - text_width(mode, 1)
        canvas.draw_text(mx, 5, mode, YELLOW, 1)
    canvas.fill_rect(8, 14, PHYS_W - 16, 1, (62, 70, 88))

    if running:
        middle = 186
        # Vertical split and bottom rule.
        canvas.fill_rect(middle, 18, 1, 52, (46, 54, 70))
        canvas.fill_rect(8, 70, PHYS_W - 16, 1, (46, 54, 70))

        rows = [
            ("RX", fmt_speed(d.get("rx_kbps", 0)), "CPU %d%%" % int(d.get("cpu") or 0)),
            ("TX", fmt_speed(d.get("tx_kbps", 0)), "MEM %d%%" % int(d.get("mem") or 0)),
            ("TOTAL", fmt_bytes((d.get("rx_total") or 0) + (d.get("tx_total") or 0)),
             "OC %dMB" % int(d.get("oc_mem") or 0)),
            ("CONN", str(int(d.get("conn_count") or 0)),
             "UP %s" % (d.get("oc_uptime") or "0m")),
        ]
        y = 19
        for label, left_value, right_value in rows:
            canvas.draw_text(8, y, label, (140, 152, 172), 1)
            canvas.draw_text(8 + len(label) * 6 + 6, y, left_value,
                             WHITE if label in ("TOTAL", "CONN") else (120, 220, 255), 1)
            canvas.draw_text(middle + 10, y, right_value,
                             (150, 220, 160) if right_value.startswith(("CPU", "MEM")) else GREY, 1)
            y += 12
    else:
        canvas.draw_text(8, 30, "CLASH OFF", RED, 1)
        canvas.draw_text(8, 46, "SERVICE DISABLED", GREY, 1)
        canvas.fill_rect(8, 62, PHYS_W - 16, 1, (46, 54, 70))

def render_clash_info(canvas, d, cfg):
    """Second OpenClash screen: totals, process and mode details."""
    canvas.clear(BG)
    running = bool(d.get("oc_running"))
    mode = str(d.get("oc_mode") or "rule").upper()
    canvas.fill_rect(0, 0, PHYS_W, 1, (44, 52, 70))
    canvas.draw_text(8, 5, "CLASH INFO", WHITE, 1)
    state = "ON" if running else "OFF"
    btn_x = PHYS_W - 42
    canvas.fill_rect(btn_x, 1, 34, 13, (18, 22, 32))
    canvas.fill_rect(btn_x, 1, 34, 1, (70, 82, 104))
    canvas.fill_rect(btn_x, 13, 34, 1, (70, 82, 104))
    canvas.fill_rect(btn_x, 1, 1, 13, (70, 82, 104))
    canvas.fill_rect(btn_x + 33, 1, 1, 13, (70, 82, 104))
    canvas.draw_text(btn_x + (34 - text_width(state, 1)) // 2, 5,
                     state, GREEN if running else RED, 1)
    canvas.fill_rect(8, 14, PHYS_W - 16, 1, (62, 70, 88))
    if not running:
        canvas.draw_text(8, 30, "CLASH OFF", RED, 1)
        canvas.draw_text(8, 46, "SERVICE DISABLED", GREY, 1)
        return
    middle = 166
    canvas.fill_rect(middle, 18, 1, 52, (46, 54, 70))
    canvas.fill_rect(8, 70, PHYS_W - 16, 1, (46, 54, 70))
    rows = [
        ("DL", fmt_bytes(d.get("rx_total") or 0), "MEM", "%dMB" % int(d.get("oc_mem") or 0)),
        ("UL", fmt_bytes(d.get("tx_total") or 0), "CPU", "%d%%" % int(d.get("cpu") or 0)),
        ("CORE", "CLASH", "UP", d.get("oc_uptime") or "0m"),
        ("CONN", str(int(d.get("conn_count") or 0)), "MODE", mode),
    ]
    y = 19
    for l1, v1, l2, v2 in rows:
        canvas.draw_text(8, y, l1, (140, 152, 172), 1)
        canvas.draw_text(8 + len(l1) * 6 + 6, y, v1, WHITE, 1)
        canvas.draw_text(middle + 10, y, l2, (140, 152, 172), 1)
        canvas.draw_text(middle + 10 + len(l2) * 6 + 6, y, v2, YELLOW if l2 == "MODE" else GREY, 1)
        y += 12


def _flag_rect(canvas, x, y, w, h, rgb):
    canvas.fill_rect(x, y, w, h, rgb)


def _flag_circle(canvas, cx, cy, r, rgb):
    r2 = r * r
    for yy in range(int(cy - r), int(cy + r) + 1):
        for xx in range(int(cx - r), int(cx + r) + 1):
            if (xx - cx) ** 2 + (yy - cy) ** 2 <= r2:
                canvas.pixel(xx, yy, rgb)


def _flag_line(canvas, x1, y1, x2, y2, rgb, width=1):
    dx = x2 - x1
    dy = y2 - y1
    steps = int(max(abs(dx), abs(dy), 1))
    for i in range(steps + 1):
        xx = int(round(x1 + dx * i / steps))
        yy = int(round(y1 + dy * i / steps))
        _flag_rect(canvas, xx - width // 2, yy - width // 2, width, width, rgb)


def _flag_poly(canvas, points, rgb):
    if not points:
        return
    ys = [p[1] for p in points]
    for yy in range(int(min(ys)), int(max(ys)) + 1):
        xs = []
        for i in range(len(points)):
            x1, y1 = points[i]
            x2, y2 = points[(i + 1) % len(points)]
            if (y1 <= yy < y2) or (y2 <= yy < y1):
                xs.append(x1 + (yy - y1) * (x2 - x1) / (y2 - y1))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            _flag_rect(canvas, int(xs[i]), yy, max(1, int(xs[i + 1] - xs[i])), 1, rgb)


def _flag_star(canvas, cx, cy, r, rgb):
    import math
    pts = []
    for i in range(10):
        ang = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.42
        pts.append((cx + math.cos(ang) * rr, cy + math.sin(ang) * rr))
    _flag_poly(canvas, pts, rgb)


def _flag_union_jack(canvas, x, y, w, h):
    blue = (12, 28, 72)
    white = (245, 245, 245)
    red = (190, 32, 44)
    _flag_rect(canvas, x, y, w, h, blue)
    # white diagonals
    _flag_line(canvas, x, y, x + w - 1, y + h - 1, white, 5)
    _flag_line(canvas, x + w - 1, y, x, y + h - 1, white, 5)
    # red diagonals
    _flag_line(canvas, x, y, x + w - 1, y + h - 1, red, 2)
    _flag_line(canvas, x + w - 1, y, x, y + h - 1, red, 2)
    # white cross + red cross
    _flag_rect(canvas, x + w // 2 - 4, y, 8, h, white)
    _flag_rect(canvas, x, y + h // 2 - 4, w, 8, white)
    _flag_rect(canvas, x + w // 2 - 2, y, 4, h, red)
    _flag_rect(canvas, x, y + h // 2 - 2, w, 4, red)


def draw_country_flag(canvas, x, y, cc, scale=3):
    """Draw a simplified but recognisable flag at 54x36."""
    w, h = 18 * scale, 12 * scale
    _flag_rect(canvas, x, y, w, h, (10, 12, 18))
    red = (200, 36, 52)
    white = (245, 245, 245)
    blue = (18, 42, 110)
    black = (20, 20, 24)
    yellow = (245, 200, 48)
    green = (20, 110, 64)

    if cc == "US":
        sh = max(2, h // 13)
        for i in range(13):
            _flag_rect(canvas, x, y + i * h // 13, w, max(2, h // 13), red if i % 2 == 0 else white)
        _flag_rect(canvas, x, y, int(w * 0.45), h // 2, blue)
        for r in range(3):
            for c in range(4):
                _flag_circle(canvas, x + 4 + c * 5, y + 4 + r * 5, 1, white)
    elif cc == "JP":
        _flag_rect(canvas, x, y, w, h, white)
        _flag_circle(canvas, x + w // 2, y + h // 2, 10, red)
    elif cc == "CN":
        _flag_rect(canvas, x, y, w, h, red)
        _flag_star(canvas, x + 10, y + 10, 7, yellow)
        for px, py in ((20, 5), (24, 10), (24, 16), (20, 21)):
            _flag_star(canvas, x + px, y + py, 2, yellow)
    elif cc == "HK":
        _flag_rect(canvas, x, y, w, h, red)
        import math
        for i in range(5):
            ang = -math.pi / 2 + i * 2 * math.pi / 5
            _flag_circle(canvas, x + w // 2 + math.cos(ang) * 6,
                         y + h // 2 + math.sin(ang) * 6, 4, white)
        _flag_circle(canvas, x + w // 2, y + h // 2, 3, white)
    elif cc == "TW":
        _flag_rect(canvas, x, y, w, h, red)
        _flag_rect(canvas, x, y, w // 2, h // 2, blue)
        _flag_circle(canvas, x + w // 4, y + h // 4, 5, white)
        for i in range(8):
            import math
            ang = i * math.pi / 4
            _flag_line(canvas, x + w // 4, y + h // 4,
                       x + w // 4 + math.cos(ang) * 9,
                       y + h // 4 + math.sin(ang) * 9, white, 1)
    elif cc == "KR":
        _flag_rect(canvas, x, y, w, h, white)
        cx, cy, r = x + w // 2, y + h // 2, 9
        for yy in range(cy - r, cy + r + 1):
            for xx in range(cx - r, cx + r + 1):
                if (xx - cx) ** 2 + (yy - cy) ** 2 <= r * r:
                    canvas.pixel(xx, yy, red if yy < cy else blue)
        _flag_circle(canvas, cx - 3, cy - 3, 4, red)
        _flag_circle(canvas, cx + 3, cy + 3, 4, blue)
        for bx, by in ((x + 5, y + 5), (x + w - 12, y + 5),
                       (x + 5, y + h - 8), (x + w - 12, y + h - 8)):
            for j in range(3):
                _flag_rect(canvas, bx, by + j * 3, 8, 1, black)
    elif cc == "GB":
        _flag_union_jack(canvas, x, y, w, h)
    elif cc == "DE":
        for i, col in enumerate((black, red, (240, 190, 40))):
            _flag_rect(canvas, x, y + i * h // 3, w, h // 3, col)
    elif cc == "FR":
        for i, col in enumerate((blue, white, red)):
            _flag_rect(canvas, x + i * w // 3, y, w // 3, h, col)
    elif cc == "NL":
        for i, col in enumerate((red, white, blue)):
            _flag_rect(canvas, x, y + i * h // 3, w, h // 3, col)
    elif cc == "RU":
        for i, col in enumerate((white, blue, red)):
            _flag_rect(canvas, x, y + i * h // 3, w, h // 3, col)
    elif cc == "TH":
        bands = ((red, 6), (white, 6), (blue, 12), (white, 6), (red, 6))
        yy = y
        for col, bh in bands:
            _flag_rect(canvas, x, yy, w, bh, col)
            yy += bh
    elif cc == "ID":
        _flag_rect(canvas, x, y, w, h // 2, red)
        _flag_rect(canvas, x, y + h // 2, w, h - h // 2, white)
    elif cc == "SG":
        _flag_rect(canvas, x, y, w, h // 2, red)
        _flag_rect(canvas, x, y + h // 2, w, h - h // 2, white)
        cx, cy = x + 14, y + 9
        _flag_circle(canvas, cx, cy, 8, white)
        _flag_circle(canvas, cx + 4, cy, 7, red)
        for px, py in ((22, 4), (27, 7), (27, 13), (21, 15), (18, 10)):
            _flag_circle(canvas, x + px, y + py, 1, white)
    elif cc == "CA":
        _flag_rect(canvas, x, y, w, h, white)
        _flag_rect(canvas, x, y, w // 4, h, red)
        _flag_rect(canvas, x + w - w // 4, y, w // 4, h, red)
        _flag_poly(canvas, [(x + w // 2, y + 7), (x + w // 2 - 4, y + 15),
                            (x + w // 2 - 1, y + 15), (x + w // 2 - 4, y + 23),
                            (x + w // 2 + 4, y + 23), (x + w // 2 + 1, y + 15),
                            (x + w // 2 + 4, y + 15)], red)
    elif cc == "AU":
        _flag_rect(canvas, x, y, w, h, blue)
        _flag_union_jack(canvas, x, y, w // 2, h // 2)
        for px, py, r in ((35, 8, 2), (44, 14, 2), (38, 27, 2),
                          (47, 25, 1), (30, 28, 1)):
            _flag_star(canvas, x + px, y + py, r, white)
    elif cc == "IN":
        for i, col in enumerate(((255, 153, 51), white, (19, 136, 8))):
            _flag_rect(canvas, x, y + i * h // 3, w, h // 3, col)
        _flag_circle(canvas, x + w // 2, y + h // 2, 5, (20, 40, 150))
        _flag_circle(canvas, x + w // 2, y + h // 2, 3, white)
    elif cc == "TR":
        _flag_rect(canvas, x, y, w, h, red)
        _flag_circle(canvas, x + 20, y + h // 2, 8, white)
        _flag_circle(canvas, x + 24, y + h // 2, 8, red)
        _flag_star(canvas, x + 35, y + h // 2, 5, white)
    elif cc == "BR":
        _flag_rect(canvas, x, y, w, h, green)
        _flag_poly(canvas, [(x + 27, y + 4), (x + 50, y + 18),
                            (x + 27, y + 32), (x + 4, y + 18)], yellow)
        _flag_circle(canvas, x + 27, y + 18, 7, blue)
        _flag_line(canvas, x + 20, y + 20, x + 34, y + 16, white, 1)
    elif cc == "AR":
        for i, col in enumerate(((120, 190, 235), white, (120, 190, 235))):
            _flag_rect(canvas, x, y + i * h // 3, w, h // 3, col)
        _flag_circle(canvas, x + w // 2, y + h // 2, 4, yellow)
    elif cc == "MY":
        for i in range(14):
            _flag_rect(canvas, x, y + i * h // 14, w, max(1, h // 14),
                       red if i % 2 == 0 else white)
        _flag_rect(canvas, x, y, w // 2, h // 2, blue)
        _flag_circle(canvas, x + 12, y + 9, 5, yellow)
        _flag_circle(canvas, x + 15, y + 9, 4, blue)
        _flag_star(canvas, x + 20, y + 9, 3, yellow)
    elif cc == "VN":
        _flag_rect(canvas, x, y, w, h, red)
        _flag_star(canvas, x + w // 2, y + h // 2, 8, yellow)
    elif cc == "PH":
        _flag_rect(canvas, x, y, w, h // 2, blue)
        _flag_rect(canvas, x, y + h // 2, w, h - h // 2, red)
        _flag_poly(canvas, [(x, y), (x + 22, y + h // 2), (x, y + h)], white)
        _flag_circle(canvas, x + 7, y + h // 2, 3, yellow)
        for py in (7, 29):
            _flag_circle(canvas, x + 17, y + py, 1, yellow)
    else:
        colors = COUNTRY_FLAGS.get(cc, ((58, 66, 84), (90, 100, 120), (58, 66, 84)))
        for i in range(3):
            _flag_rect(canvas, x, y + i * h // 3, w, h // 3, colors[i])

    # thin border
    _flag_rect(canvas, x, y, w, 1, (120, 132, 150))
    _flag_rect(canvas, x, y + h - 1, w, 1, (120, 132, 150))
    _flag_rect(canvas, x, y, 1, h, (120, 132, 150))
    _flag_rect(canvas, x + w - 1, y, 1, h, (120, 132, 150))


def render_clash_node(canvas, d, cfg):
    """Third OpenClash page: selected node, country, type and latency."""
    canvas.clear(BG)
    running = bool(d.get("oc_running"))
    canvas.fill_rect(0, 0, PHYS_W, 1, (44, 52, 70))
    canvas.draw_text(8, 5, "CLASH NODE", WHITE, 1)
    btn_x = PHYS_W - 42
    state = "ON" if running else "OFF"
    canvas.fill_rect(btn_x, 1, 34, 13, (18, 22, 32))
    canvas.fill_rect(btn_x, 1, 34, 1, (70, 82, 104))
    canvas.fill_rect(btn_x, 13, 34, 1, (70, 82, 104))
    canvas.fill_rect(btn_x, 1, 1, 13, (70, 82, 104))
    canvas.fill_rect(btn_x + 33, 1, 1, 13, (70, 82, 104))
    canvas.draw_text(btn_x + (34 - text_width(state, 1)) // 2, 5,
                     state, GREEN if running else RED, 1)
    canvas.fill_rect(8, 14, PHYS_W - 16, 1, (62, 70, 88))
    if not running:
        canvas.draw_text(8, 32, "CLASH OFF", RED, 1)
        canvas.draw_text(8, 48, "NO NODE DATA", GREY, 1)
        return
    cc = str(d.get("oc_country") or "--")
    node = str(d.get("oc_node") or "UNKNOWN")
    if cc and node.upper().startswith(cc + " "):
        node = node[len(cc) + 1:]
    group = str(d.get("oc_group") or "-")
    ntype = str(d.get("oc_node_type") or "-")
    try:
        delay = int(d.get("oc_delay") or 0)
    except Exception:
        delay = 0
    draw_country_flag(canvas, 6, 19, cc, 3)
    nwhite, ngrey, nyellow = (255, 255, 255), (255, 255, 255), (255, 255, 0)
    canvas.draw_text(68, 19, cc, nyellow, 1)
    zh = COUNTRY_ZH.get(cc, "")
    if zh:
        canvas.draw_cjk(68 + len(cc) * 6 + 6, 13, zh, nwhite, 1)
    canvas.draw_text(68, 31, node, nwhite, 1)
    gc = int(d.get("oc_group_count") or 0)
    canvas.draw_text(68, 43, "GROUP " + group + ((" x%d" % gc) if gc else ""), ngrey, 1)
    canvas.draw_text(68, 55, "TYPE " + ntype + "  UDP " + str(d.get("oc_udp") or "NO"), ngrey, 1)
    if delay > 0:
        dcolor = GREEN if delay < 150 else (YELLOW if delay < 300 else RED)
        dtext = "%dms" % delay
    else:
        dcolor = GREY
        dtext = "-"
    canvas.draw_text(68, 67, "DLY " + dtext, dcolor, 1)
    rate = str(d.get("oc_rate") or "1x")
    canvas.draw_text(150, 67, "RATE " + rate, nyellow, 1)
    conn = "CONN %d" % int(d.get("conn_count") or 0)
    canvas.draw_text(PHYS_W - 8 - text_width(conn, 1), 67, conn, ngrey, 1)
    canvas.fill_rect(8, 75, PHYS_W - 16, 1, (46, 54, 70))


def build_pages(cfg):
    """Return ordered list of (key, render_fn) selected by the dashboard flags."""
    if cfg.get("mode") == "custom":
        return [("custom", render_custom)]
    if cfg.get("mode") == "clash":
        return [("clash", render_clash), ("clash_info", render_clash_info),
                ("clash_node", render_clash_node)]
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
        self.start_x = 0
        self.start_y = 0
        self.start_set = False
        self.last_x = -1
        self.last_y = -1
        self.last_gesture = "none"
        self.last_gesture_at = 0.0
        self.last_raw = ""
        self.drag_dx = 0
        self.drag_dy = 0
        self.dragging = False
        self.drag_moved = False
        self.drag_released = False
        self.moved_far = False
        self.tap_id = 0
        self.tap_x = -1
        self.tap_y = -1
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
            self.start_set = False
            self.drag_dx = 0
            self.drag_dy = 0
            self.dragging = False
            self.drag_moved = False
            self.drag_released = False
            self.moved_far = False

    def _press_up(self, gestures):
        """Finger lifted: resolve a tap / long-press gesture from the last point."""
        if not self.active:
            return
        self.active = False
        self.dragging = False
        self.drag_released = self.drag_moved
        if self.raw_x is None:
            return
        px, py = self._normalize(self.raw_x, self.raw_y)
        self.last_x, self.last_y = px, py
        self.last_raw = "%d,%d" % (self.raw_x, self.raw_y)
        now = _time2.monotonic()
        held = now - self.down_at
        if now - self.last_gesture_at < 0.08:
            return
        dx = px - self.start_x if self.start_set else 0
        dy = py - self.start_y if self.start_set else 0
        if held >= LONG_PRESS and not self.moved_far and abs(dx) < 12 and abs(dy) < 12:
            gestures.append("menu")
            self.last_gesture = "menu"
            self.last_gesture_at = now
        elif abs(dy) >= 28 and abs(dy) >= abs(dx) * 1.25:
            g = "swipe_down" if dy > 0 else "swipe_up"
            gestures.append(g)
            self.last_gesture = g
            self.last_gesture_at = now
        elif abs(dx) >= 32 and abs(dx) >= abs(dy) * 1.4:
            g = "swipe_left" if dx < 0 else "swipe_right"
            gestures.append(g)
            self.last_gesture = g
            self.last_gesture_at = now
        elif held <= TAP_MAX:
            self.tap_id += 1
            self.tap_x, self.tap_y = px, py
            g = self._tap_gesture(px, py)
            if g:
                gestures.append(g)
                self.last_gesture = g
                self.last_gesture_at = now

    def _normalize(self, x, y):
        if self.swap_xy:
            x, y = y, x
        px = (x - RAW_X_MIN) * PHYS_W // (RAW_X_MAX - RAW_X_MIN)
        py = (y - RAW_Y_MIN) * PHYS_H // (RAW_Y_MAX - RAW_Y_MIN)
        if self.flip_x:
            px = PHYS_W - 1 - px
        return max(0, min(PHYS_W - 1, px)), max(0, min(PHYS_H - 1, py))

    def _tap_gesture(self, px, py=None):
        if self.action != "next":
            return None
        if py is not None and py <= 26 and px >= PHYS_W - 64:
            return "toggle_clash"
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
                    if not self.start_set:
                        self.start_x, self.start_y = px, py
                        self.start_set = True
                    else:
                        self.drag_dx = px - self.start_x
                        self.drag_dy = py - self.start_y
                        self.dragging = True
                        if abs(self.drag_dx) > 4 or abs(self.drag_dy) > 4:
                            self.drag_moved = True
                        if abs(self.drag_dx) > 12 or abs(self.drag_dy) > 12:
                            self.moved_far = True
        return gestures


def draw_nav(canvas, count=1):
    return


def draw_toast(canvas, text):
    w = min(PHYS_W - 16, text_width(text, 1) + 16)
    x = (PHYS_W - w) // 2
    canvas.fill_rect(x, 57, w, 13, (8, 10, 16))
    canvas.fill_rect(x, 57, w, 1, (120, 132, 156))
    canvas.fill_rect(x, 69, w, 1, (120, 132, 156))
    canvas.draw_text(x + 8, 60, text, WHITE, 1)


def compose_live_drag(cur, other, dx, dy):
    """Compose the current and adjacent page at the finger offset."""
    out = Canvas()
    out.buf = bytearray(PHYS_W * PHYS_H * 3)
    out.font = cur.font
    out.bg_dim = cur.bg_dim
    if abs(dx) >= abs(dy):
        dx = int(max(-PHYS_W, min(PHYS_W, dx)))
        for y in range(PHYS_H):
            for x in range(PHYS_W):
                sx = x - dx
                src = None
                if 0 <= sx < PHYS_W:
                    src = cur
                else:
                    sx2 = sx - PHYS_W if dx < 0 else sx + PHYS_W
                    if 0 <= sx2 < PHYS_W:
                        src = other
                        sx = sx2
                if src is not None:
                    si = (y * PHYS_W + sx) * 3
                    di = (y * PHYS_W + x) * 3
                    out.buf[di:di + 3] = src.buf[si:si + 3]
    else:
        dy = int(max(-PHYS_H, min(PHYS_H, dy)))
        for y in range(PHYS_H):
            sy = y - dy
            if 0 <= sy < PHYS_H:
                si = (sy * PHYS_W) * 3
                di = (y * PHYS_W) * 3
                out.buf[di:di + PHYS_W * 3] = cur.buf[si:si + PHYS_W * 3]
    return out


def load_fb_source(fp):
    try:
        with open(fp, "rb") as f:
            data = f.read(FB_BYTES)
        if len(data) == FB_BYTES:
            return data
    except Exception:
        pass
    return None


_DIM_LUTS = {}


def _dim_lut(dim):
    key = int(round(dim * 100))
    lut = _DIM_LUTS.get(key)
    if lut is not None:
        return lut
    f = key / 100.0
    lut = array.array("H", [0]) * 65536
    for c in range(65536):
        r = int(((c >> 11) & 31) * f)
        g = int(((c >> 5) & 63) * f)
        b = int((c & 31) * f)
        lut[c] = (r << 11) | (g << 5) | b
    _DIM_LUTS[key] = lut
    return lut


_FROST_LUTS = {}


def _frost_tint_lut(blur):
    key = int(round(blur))
    lut = _FROST_LUTS.get(key)
    if lut is not None:
        return lut
    a = 0.28 * key / 100.0
    lut = array.array("H", [0]) * 65536
    for c in range(65536):
        r = int(((c >> 11) & 31) * (1 - a) + 31 * a)
        g = int(((c >> 5) & 63) * (1 - a) + 63 * a)
        b = int((c & 31) * (1 - a) + 31 * a)
        lut[c] = (r << 11) | (g << 5) | b
    _FROST_LUTS[key] = lut
    return lut


_FAST_EFFECTS = {}


_FAST_EFFECTS = {}


def _fast_effect_lut(blur, dim):
    key = (int(round(blur)), int(round(dim * 100)))
    lut = _FAST_EFFECTS.get(key)
    if lut is not None:
        return lut
    a = 0.28 * key[0] / 100.0
    d = key[1] / 100.0
    lut = array.array("H", [0]) * 65536
    for c in range(65536):
        r = ((c >> 11) & 31) * (1 - a) + 31 * a
        g = ((c >> 5) & 63) * (1 - a) + 63 * a
        b = (c & 31) * (1 - a) + 31 * a
        r = int(r * d); g = int(g * d); b = int(b * d)
        lut[c] = (r << 11) | (g << 5) | b
    _FAST_EFFECTS[key] = lut
    return lut


def fast_effect(data, blur, dim):
    """Combine glass tint and background mask with a 16-bit LUT."""
    key = (int(round(blur)), int(round(dim * 100)))
    if key == (0, 100):
        return bytes(data)
    lut = _fast_effect_lut(blur, dim)
    vals = array.array("H")
    vals.frombytes(data)
    return array.array("H", [lut[v] for v in vals]).tobytes()


def frost_fb(data, blur, quality=False):
    """Frost an RGB565 frame.

    Animated backgrounds use a cheap white-glass LUT so the frame loop stays
    smooth. A single-frame background can afford the real block blur.
    """
    if blur <= 0:
        return bytes(data)
    if not quality:
        lut = _frost_tint_lut(blur)
        vals = array.array("H")
        vals.frombytes(data)
        return array.array("H", (lut[v] for v in vals)).tobytes()
    block = 1 + int(blur / 100.0 * 8)
    if block <= 1:
        return bytes(data)
    out = bytearray(len(data))
    tint = 0.10 * blur / 100.0
    for by in range(0, FB_H, block):
        y2 = min(FB_H, by + block)
        for bx in range(0, FB_W, block):
            x2 = min(FB_W, bx + block)
            rr = gg = bb = n = 0
            for y in range(by, y2):
                base = y * FB_W
                for x in range(bx, x2):
                    bi = (base + x) * 2
                    c = data[bi] | (data[bi + 1] << 8)
                    rr += (c >> 11) & 31
                    gg += (c >> 5) & 63
                    bb += c & 31
                    n += 1
            if not n:
                continue
            rc = int(rr / n); gc = int(gg / n); bc = int(bb / n)
            if tint:
                rc = int(rc * (1 - tint) + 31 * tint)
                gc = int(gc * (1 - tint) + 63 * tint)
                bc = int(bc * (1 - tint) + 31 * tint)
            c = (rc << 11) | (gc << 5) | bc
            pair = bytes((c & 255, (c >> 8) & 255)) * (x2 - bx)
            for y in range(by, y2):
                base = (y * FB_W + bx) * 2
                out[base:base + len(pair)] = pair
    return bytes(out)


def blend565(bg, fg, a):
    br = (bg >> 11) & 31; bgc = (bg >> 5) & 63; bb = bg & 31
    fr = (fg >> 11) & 31; fgc = (fg >> 5) & 63; fb = fg & 31
    r = int(br * (1 - a) + fr * a)
    g = int(bgc * (1 - a) + fgc * a)
    b = int(bb * (1 - a) + fb * a)
    return (r << 11) | (g << 5) | b


def dim_fb(data, dim):
    """Dim a raw fb90m RGB565 frame using a 16-bit lookup table."""
    if dim >= 0.999:
        return bytes(data)
    lut = _dim_lut(dim)
    vals = array.array("H")
    vals.frombytes(data)
    out = array.array("H", (lut[v] for v in vals))
    return out.tobytes()


def build_overlay(pages, idx, data, cfg):
    """Render only text/graphics on a transparent physical canvas."""
    ov = Canvas()
    ov.transparent = True
    ov.mask = bytearray(PHYS_W * PHYS_H)
    ov.background = (0, 0, 0)
    pages[idx][1](ov, data, cfg)
    draw_nav(ov, len(pages))
    pixels = []
    for y in range(PHYS_H):
        for x in range(PHYS_W):
            if ov.mask[y * PHYS_W + x]:
                o = (y * PHYS_W + x) * 3
                c = ov.rgb565(ov.buf[o], ov.buf[o + 1], ov.buf[o + 2])
                bi = (FB_H - 1 - x) * FB_W + y
                pixels.append((bi * 2, c))
    return pixels


MENU_LABELS = {
    "poweroff": ("PWR", "关机"),
    "reboot": ("RST", "重启"),
    "wifi": ("WIFI", "无线"),
    "clash": ("CLASH", "猫猫"),
    "brightness": ("LIGHT", "亮度"),
    "fan": ("FAN", "风扇"),
    "next": ("NEXT", "下一页"),
    "back": ("BACK", "上一页"),
    "exit": ("EXIT", "退出"),
    "none": ("", ""),
}
MENU_ACTIONS = set(MENU_LABELS)
MENU_SUBMENUS = {"brightness", "fan", "clash"}
MENU_CONFIRM = {"poweroff", "reboot", "wifi"}
MENU_HOLD = 1.4


def detect_menu_lang():
    for key in ("luci.main.lang", "luci.main.language"):
        try:
            out = subprocess.check_output(["uci", "get", key],
                                          stderr=subprocess.DEVNULL,
                                          timeout=1.0).decode("utf-8", "ignore").strip()
            if out:
                low = out.lower()
                if low.startswith("zh") or "chinese" in low or low.startswith("cn"):
                    return "zh"
                if low.startswith("en"):
                    return "en"
        except Exception:
            pass
    for key in ("LC_ALL", "LC_MESSAGES", "LANG"):
        value = os.environ.get(key, "").lower()
        if value.startswith("zh") or "_cn" in value:
            return "zh"
        if value.startswith("en"):
            return "en"
    return "zh"


def resolve_menu_lang(value):
    if value in ("zh", "en"):
        return value
    return detect_menu_lang()


def build_menu_pages(cfg):
    n = 2
    try:
        n = max(2, min(3, int(cfg.get("menu_pages", 2) or 2)))
    except Exception:
        n = 2
    defaults = {
        1: "poweroff,reboot,wifi,next",
        2: "clash,brightness,fan,back",
        3: "wifi,brightness,clash,exit",
    }
    pages = []
    for i in range(1, n + 1):
        raw = str(cfg.get("menu_page%d" % i, defaults.get(i, "")) or "")
        acts = [x.strip() for x in raw.split(",") if x.strip() in MENU_ACTIONS]
        acts = acts[:4]
        while len(acts) < 4:
            acts.append("none")
        pages.append(acts)
    return pages


def menu_label(action, lang):
    pair = MENU_LABELS.get(action, ("", ""))
    return pair[1] if lang == "zh" else pair[0]


def cjk_width(text, scale=1):
    return max(0, len(text) * 13 * scale - scale)


def menu_hit(px, py, actions):
    for i, action in enumerate(actions):
        if action == "none":
            continue
        cx = 36 + i * 71
        if (px - cx) ** 2 + (py - 44) ** 2 <= 26 * 26:
            return action
    return None


def draw_circle(canvas, cx, cy, r, color, width=1, fill=None):
    r2 = r * r
    inner = max(0, r - width) ** 2
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            d = (x - cx) ** 2 + (y - cy) ** 2
            if d > r2:
                continue
            if fill is not None and d <= r2:
                canvas.pixel(x, y, fill)
            if width > 0 and d > inner:
                canvas.pixel(x, y, color)


def menu_accent(action):
    if action in ("poweroff", "reboot"):
        return (220, 70, 70)
    if action in ("next", "back", "exit"):
        return (240, 190, 60)
    return (90, 150, 255)


PENDING_TEXT = {
    "poweroff": ("即将关机", "POWER OFF SOON"),
    "reboot": ("即将重启", "REBOOT SOON"),
    "wifi": ("即将切换无线", "TOGGLE WIFI"),
    "clash": ("即将切换猫猫", "TOGGLE CLASH"),
    "brightness": ("即将调节亮度", "CHANGE BRIGHTNESS"),
    "fan": ("即将进入风扇设置", "FAN SETTINGS"),
    "exit": ("即将退出菜单", "EXITING MENU"),
}


def mixed_width(text):
    return sum(13 if ch in CJK_FONT else 6 for ch in text) - (1 if text else 0)


def draw_mixed_center(canvas, text, y, color):
    x = (PHYS_W - mixed_width(text)) // 2
    for ch in text:
        if ch in CJK_FONT:
            canvas.draw_cjk(x, y, ch, color, 1)
            x += 13
        else:
            canvas.draw_text(x, y, ch, color, 1)
            x += 6


def pending_text(action, lang):
    pair = PENDING_TEXT.get(action)
    if not pair:
        return ""
    return pair[0] if lang == "zh" else pair[1]


def draw_menu(canvas, actions, lang="zh", page=0, pages=2, pending=None, progress=0.0, notice=None):
    canvas.background = None
    canvas.content_alpha = 1.0
    canvas.clear((8, 10, 16))
    canvas.fill_rect(0, 0, PHYS_W, 1, (44, 52, 70))
    if not notice:
        if lang == "zh":
            canvas.draw_cjk(8, 2, "菜单", WHITE, 1)
            canvas.draw_text(44, 5, "%d/%d" % (page + 1, pages), GREY, 1)
            hint = "退出菜单"
            canvas.draw_cjk(PHYS_W - 8 - cjk_width(hint), 2, hint, (240, 190, 60), 1)
        else:
            canvas.draw_text(8, 5, "MENU  %d/%d" % (page + 1, pages), WHITE, 1)
            hint = "EXIT MENU"
            canvas.draw_text(PHYS_W - 8 - text_width(hint, 1), 5, hint, (240, 190, 60), 1)
    canvas.fill_rect(8, 14, PHYS_W - 16, 1, (62, 70, 88))
    for i, action in enumerate(actions):
        if action == "none":
            continue
        cx = 36 + i * 71
        accent = menu_accent(action)
        draw_circle(canvas, cx, 44, 24, accent, 2, (46, 54, 70))
        draw_circle(canvas, cx, 44, 29, (32, 38, 50), 2)
        label = menu_label(action, lang)
        if pending == action and action in ("next", "back", "exit"):
            label = "退出" if lang == "zh" else "EXIT"
        if not label:
            continue
        if lang == "zh" and all(ch in CJK_FONT for ch in label):
            canvas.draw_cjk(cx - cjk_width(label) // 2, 38, label,
                            WHITE if action not in ("next", "back", "exit") else accent, 1)
        else:
            canvas.draw_text(cx - text_width(label, 1) // 2, 41, label,
                             WHITE if action not in ("next", "back", "exit") else accent, 1)
    if notice:
        draw_mixed_center(canvas, notice, 1, (255, 220, 80))


def draw_progress_ring_fb(data, cx, cy, r, progress, rgb):
    p = max(0.0, min(1.0, progress))
    if p <= 0:
        return
    c = ((rgb[0] & 0xF8) << 8) | ((rgb[1] & 0xFC) << 3) | (rgb[2] >> 3)
    lo = c & 255; hi = (c >> 8) & 255
    for deg in range(0, int(360 * p), 2):
        a = math.radians(deg - 90)
        for rr in range(r - 2, r + 3):
            x = int(round(cx + math.cos(a) * rr))
            y = int(round(cy + math.sin(a) * rr))
            if 0 <= x < PHYS_W and 0 <= y < PHYS_H:
                bi = ((FB_H - 1 - x) * FB_W + y) * 2
                data[bi] = lo; data[bi + 1] = hi


def run_menu_action(action):
    try:
        if action == "poweroff":
            subprocess.Popen(["/bin/sh", "-c", "sync; poweroff"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif action == "reboot":
            subprocess.Popen(["/bin/sh", "-c", "sync; reboot"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif action == "wifi":
            subprocess.Popen(["/bin/sh", "-c",
                              "wifi status 2>/dev/null | grep -q '\"up\": true' && wifi down || wifi up"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif action == "clash":
            toggle_openclash()
        elif action == "brightness":
            vals = [2, 4, 6, 8, 10]
            try:
                cur = int(open("/tmp/glanim.brightness").read().strip())
            except Exception:
                cur = 4
            nxt = vals[(vals.index(cur) + 1) % len(vals)] if cur in vals else 4
            with open("/tmp/glanim.brightness", "w") as f:
                f.write(str(nxt))
            apply_brightness(nxt)
        elif action == "fan":
            subprocess.Popen(["/bin/sh", "-c",
                              "v=$(uci get glfanctl.globals.enabled 2>/dev/null || echo 0); "
                              "if [ \"$v\" = \"1\" ]; then uci set glfanctl.globals.enabled=0; "
                              "else uci set glfanctl.globals.enabled=1; fi; "
                              "uci commit glfanctl; /etc/init.d/glfanctl restart"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


PROXY_MODES = [("rule", "规则", "RULE"), ("global", "全局", "GLOBAL"), ("direct", "直连", "DIRECT")]
PROXY_ITEMS = [("mode", "模式", "MODE"), ("best", "优选", "BEST"), ("restart", "重启", "RESTART"), ("stop", "关闭", "STOP")]


def _clash_secret():
    try:
        return subprocess.check_output(["uci", "get", "openclash.config.dashboard_password"],
                                       stderr=subprocess.DEVNULL, timeout=1.0).decode().strip()
    except Exception:
        return ""


def clash_api(method, path, payload=None, timeout=2.5):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request("http://127.0.0.1:9090" + path, data=data, method=method)
    req.add_header("Authorization", "Bearer " + _clash_secret())
    if data is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode("utf-8", "replace")
    return json.loads(body) if body else {}


def current_clash_mode():
    try:
        mode = str(clash_api("GET", "/configs").get("mode") or "rule")
        if mode in ("rule", "global", "direct"):
            return mode
    except Exception:
        pass
    return "rule"


def set_clash_mode(mode):
    try:
        clash_api("PATCH", "/configs", {"mode": mode})
        return True
    except Exception:
        return False


def best_clash_node():
    try:
        proxies = clash_api("GET", "/proxies").get("proxies", {})
        group = None
        for name, p in proxies.items():
            if p.get("type") in ("Selector", "URLTest", "Fallback", "LoadBalance") and p.get("now"):
                if name.upper() != "GLOBAL":
                    group = name
                    break
        if not group:
            return ""
        q = urllib.parse.quote(group, safe="")
        delays = clash_api("GET", "/group/%s/delay?url=http%%3A%%2F%%2Fwww.gstatic.com%%2Fgenerate_204&timeout=5000" % q, timeout=7.0)
        candidates = [(int(v), k) for k, v in delays.items() if isinstance(v, int) and v > 0]
        if not candidates:
            return ""
        best = min(candidates)[1]
        clash_api("PUT", "/proxies/%s" % q, {"name": best}, timeout=3.0)
        return best
    except Exception:
        return ""


def restart_openclash():
    try:
        subprocess.Popen(["/bin/sh", "-c", "/etc/init.d/openclash restart"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def stop_openclash():
    try:
        subprocess.Popen(["/bin/sh", "-c",
                          "uci set openclash.config.enable=0; uci commit openclash; /etc/init.d/openclash stop"],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def proxy_hit(px, py):
    for i in range(4):
        if (px - (36 + i * 71)) ** 2 + (py - 44) ** 2 <= 26 * 26:
            return i
    return -1


def draw_proxy(canvas, mode, lang="zh", status=""):
    canvas.background = None
    canvas.content_alpha = 1.0
    canvas.clear((8, 10, 16))
    canvas.fill_rect(0, 0, PHYS_W, 1, (44, 52, 70))
    mode_text = next((z if lang == "zh" else e for k, z, e in PROXY_MODES if k == mode), "")
    if lang == "zh":
        canvas.draw_cjk(8, 2, "猫猫", WHITE, 1)
        canvas.draw_cjk(44, 2, mode_text, GREY, 1)
        canvas.draw_cjk(PHYS_W - 8 - cjk_width("返回"), 2, "返回", (240, 190, 60), 1)
    else:
        canvas.draw_text(8, 5, "CLASH", WHITE, 1)
        canvas.draw_text(48, 5, mode_text, GREY, 1)
        canvas.draw_text(PHYS_W - 8 - text_width("BACK", 1), 5, "BACK", (240, 190, 60), 1)
    canvas.fill_rect(8, 14, PHYS_W - 16, 1, (62, 70, 88))
    for i, (key, zh, en) in enumerate(PROXY_ITEMS):
        cx = 36 + i * 71
        accent = (240, 190, 60) if key == "stop" else (90, 150, 255)
        draw_circle(canvas, cx, 44, 24, accent, 2, (46, 54, 70))
        label = zh if lang == "zh" else en
        if lang == "zh":
            canvas.draw_cjk(cx - cjk_width(label) // 2, 38, label, WHITE, 1)
        else:
            canvas.draw_text(cx - text_width(label, 1) // 2, 41, label, WHITE, 1)


FAN_MODES = [
    ("auto", "自动", "AUTO"),
    ("curve", "曲线", "CURVE"),
    ("manual", "手动", "MANUAL"),
    ("stop", "关闭", "STOP"),
]


def current_fan_mode():
    try:
        enabled = subprocess.check_output(["uci", "get", "glfanctl.globals.enabled"],
                                          stderr=subprocess.DEVNULL, timeout=1.0).decode().strip()
        if enabled == "0":
            return "stop"
        mode = subprocess.check_output(["uci", "get", "glfanctl.globals.mode"],
                                       stderr=subprocess.DEVNULL, timeout=1.0).decode().strip()
        if mode in ("auto", "curve", "manual", "stop"):
            return mode
    except Exception:
        pass
    return "auto"


def set_fan_mode(mode):
    if mode not in ("auto", "curve", "manual", "stop"):
        return
    try:
        subprocess.Popen(["/bin/sh", "-c",
                          "uci set glfanctl.globals.enabled=1; "
                          "uci set glfanctl.globals.mode=%s; "
                          "uci commit glfanctl; /etc/init.d/glfanctl restart" % mode],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass


def fan_hit(px, py):
    for i in range(4):
        if (px - (36 + i * 71)) ** 2 + (py - 44) ** 2 <= 26 * 26:
            return i
    return -1


def draw_fan(canvas, mode, lang="zh"):
    canvas.background = None
    canvas.content_alpha = 1.0
    canvas.clear((8, 10, 16))
    canvas.fill_rect(0, 0, PHYS_W, 1, (44, 52, 70))
    if lang == "zh":
        canvas.draw_cjk(8, 2, "风扇", WHITE, 1)
        canvas.draw_cjk(PHYS_W - 8 - cjk_width("返回"), 2, "返回", (240, 190, 60), 1)
    else:
        canvas.draw_text(8, 5, "FAN", WHITE, 1)
        canvas.draw_text(PHYS_W - 8 - text_width("BACK", 1), 5, "BACK", (240, 190, 60), 1)
    canvas.fill_rect(8, 14, PHYS_W - 16, 1, (62, 70, 88))
    for i, (key, zh, en) in enumerate(FAN_MODES):
        cx = 36 + i * 71
        active = key == mode
        accent = (240, 190, 60) if active else (90, 150, 255)
        draw_circle(canvas, cx, 44, 24, accent, 2, (46, 54, 70))
        label = zh if lang == "zh" else en
        if lang == "zh":
            canvas.draw_cjk(cx - cjk_width(label) // 2, 38, label,
                            (255, 220, 80) if active else WHITE, 1)
        else:
            canvas.draw_text(cx - text_width(label, 1) // 2, 41, label,
                             (255, 220, 80) if active else WHITE, 1)


def draw_confirm(canvas, action, lang="zh"):
    canvas.background = None
    canvas.content_alpha = 1.0
    canvas.clear((8, 10, 16))
    canvas.fill_rect(0, 0, PHYS_W, 1, (44, 52, 70))
    label = menu_label(action, lang)
    if lang == "zh":
        canvas.draw_cjk(8, 2, label, WHITE, 1)
        canvas.draw_cjk(103, 2, "再次长按确认", GREY, 1)
        canvas.draw_cjk(PHYS_W - 8 - cjk_width("返回"), 2, "返回", (240, 190, 60), 1)
    else:
        canvas.draw_text(8, 5, label, WHITE, 1)
        canvas.draw_text((PHYS_W - text_width("HOLD AGAIN TO CONFIRM", 1)) // 2, 5,
                         "HOLD AGAIN TO CONFIRM", GREY, 1)
        canvas.draw_text(PHYS_W - 8 - text_width("BACK", 1), 5, "BACK", (240, 190, 60), 1)
    canvas.fill_rect(8, 14, PHYS_W - 16, 1, (62, 70, 88))
    accent = (220, 70, 70) if action in ("poweroff", "reboot") else (90, 150, 255)
    draw_circle(canvas, 142, 48, 24, accent, 2, (46, 54, 70))
    draw_circle(canvas, 142, 48, 29, (32, 38, 50), 2)
    if lang == "zh":
        canvas.draw_cjk(142 - cjk_width(label) // 2, 42, label, WHITE, 1)
    else:
        canvas.draw_text(142 - text_width(label, 1) // 2, 45, label, WHITE, 1)


def draw_brightness(canvas, value, lang="zh"):
    canvas.background = None
    canvas.content_alpha = 1.0
    canvas.clear((8, 10, 16))
    canvas.fill_rect(0, 0, PHYS_W, 1, (44, 52, 70))
    if lang == "zh":
        canvas.draw_cjk(8, 2, "亮度", WHITE, 1)
        canvas.draw_cjk(PHYS_W - 8 - cjk_width("点击加减"), 2, "点击加减", GREY, 1)
    else:
        canvas.draw_text(8, 5, "BRIGHTNESS", WHITE, 1)
        canvas.draw_text(PHYS_W - 8 - text_width("TAP -/+", 1), 5, "TAP -/+", GREY, 1)
    canvas.fill_rect(8, 14, PHYS_W - 16, 1, (62, 70, 88))
    draw_circle(canvas, 50, 40, 20, (90, 150, 255), 2, (46, 54, 70))
    draw_circle(canvas, 234, 40, 20, (90, 150, 255), 2, (46, 54, 70))
    canvas.draw_text(48, 37, "-", WHITE, 2)
    canvas.draw_text(231, 37, "+", WHITE, 2)
    v = str(max(0, min(11, value)))
    canvas.draw_text(PHYS_W // 2 - text_width(v, 2) // 2, 33, v, (255, 220, 80), 2)
    canvas.draw_text(PHYS_W // 2 - text_width("/11", 1) // 2, 52, "/11", GREY, 1)
    canvas.fill_rect(112, 60, 60, 13, (46, 54, 70))
    canvas.fill_rect(112, 60, 60, 1, (120, 132, 156))
    canvas.fill_rect(112, 72, 60, 1, (120, 132, 156))
    label = "退出" if lang == "zh" else "EXIT"
    if lang == "zh":
        canvas.draw_cjk(142 - cjk_width(label) // 2, 61, label, (240, 190, 60), 1)
    else:
        canvas.draw_text(142 - text_width(label, 1) // 2, 66, label, (240, 190, 60), 1)


def adjust_brightness(delta):
    try:
        with open("/tmp/glanim.brightness", "r") as f:
            cur = int(f.read().strip())
    except Exception:
        cur = 4
    val = max(0, min(11, cur + delta))
    with open("/tmp/glanim.brightness", "w") as f:
        f.write(str(val))
    apply_brightness(val)
    try:
        subprocess.Popen(["/bin/sh", "-c",
                          "uci set glanim.globals.brightness=%d; uci commit glanim" % val],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
    return val


def compose_horizontal_fb(cur_fb, other_fb, dx):
    """Compose two fb90m frames with a horizontal physical offset."""
    off = int(max(-FB_H, min(FB_H, abs(dx))))
    if off == 0:
        return bytearray(cur_fb)
    row = FB_W * 2
    out = bytearray(FB_BYTES)
    # fb90m rows run along physical X, reversed; resolve in physical X.
    for x in range(FB_H):
        sx = x - dx
        if sx < 0:
            src = other_fb
            sx += FB_H
        elif sx >= FB_H:
            src = other_fb
            sx -= FB_H
        else:
            src = cur_fb
        orow = (FB_H - 1 - x) * row
        srow = (FB_H - 1 - sx) * row
        out[orow:orow + row] = src[srow:srow + row]
    return out


def render_neighbor_fb(pages, idx, data, cfg, bg_fb, alpha):
    if bg_fb is not None:
        out = bytearray(bg_fb)
        for bi, c in build_overlay(pages, idx, data, cfg):
            if alpha < 0.999:
                bgc = out[bi] | (out[bi + 1] << 8)
                c = blend565(bgc, c, alpha)
            out[bi] = c & 255
            out[bi + 1] = (c >> 8) & 255
        return bytes(out)
    oc = Canvas()
    oc.font = CURRENT_FONT
    oc.content_alpha = alpha
    pages[idx][1](oc, data, cfg)
    draw_nav(oc, len(pages))
    return oc.render_fb()


def compose_vertical_fb(cur_fb, other_fb, dy):
    """Compose two fb90m frames with a vertical physical offset."""
    off = int(max(-PHYS_H, min(PHYS_H, abs(dy))))
    offb = off * 2
    row = FB_W * 2
    out = bytearray(FB_BYTES)
    if off == 0:
        return bytearray(cur_fb)
    for y in range(FB_H):
        ro = y * row
        if dy < 0:
            # current moves up; next page comes from the bottom
            out[ro:ro + row - offb] = cur_fb[ro + offb:ro + row]
            out[ro + row - offb:ro + row] = other_fb[ro:ro + offb]
        else:
            # current moves down; previous page comes from the top
            out[ro:ro + offb] = other_fb[ro + row - offb:ro + row]
            out[ro + offb:ro + row] = cur_fb[ro:ro + row - offb]
    return out


def _write_fb(fb, data):
    try:
        os.lseek(fb, 0, os.SEEK_SET)
        os.write(fb, data)
        return True
    except Exception:
        return False


def animate_slide(fb, old_buf, new_buf, direction, should_stop):
    """Slide old page out and new page in over ~120 ms (row slicing)."""
    steps = 10
    for step in range(1, steps + 1):
        if should_stop():
            return
        off = PHYS_W * step // steps
        cut = (PHYS_W - off) * 3
        tail = off * 3
        out = bytearray(len(old_buf))
        for y in range(PHYS_H):
            ro = y * PHYS_W * 3
            if direction > 0:
                out[ro:ro + cut] = old_buf[ro + tail:ro + PHYS_W * 3]
                out[ro + cut:ro + PHYS_W * 3] = new_buf[ro:ro + tail]
            else:
                out[ro:ro + tail] = new_buf[ro + cut:ro + PHYS_W * 3]
                out[ro + tail:ro + PHYS_W * 3] = old_buf[ro:ro + cut]
        tmp = Canvas()
        tmp.buf = out
        _write_fb(fb, tmp.render_fb())
        _time.sleep(0.012)


def animate_slide_vertical(fb, old_buf, new_buf, direction, should_stop):
    """Vertical mode transition composed directly in fb90m byte rows."""
    if not old_buf or not new_buf:
        return
    oc = Canvas(); oc.buf = bytearray(old_buf)
    nc = Canvas(); nc.buf = bytearray(new_buf)
    old_fb = oc.render_fb()
    new_fb = nc.render_fb()
    steps = 6
    row = FB_W * 2
    for step in range(1, steps + 1):
        if should_stop():
            return
        off = PHYS_H * step // steps
        offb = off * 2
        out = bytearray(FB_BYTES)
        for y in range(FB_H):
            ro = y * row
            old_row = old_fb[ro:ro + row]
            new_row = new_fb[ro:ro + row]
            if direction > 0:
                out[ro:ro + offb] = new_row[:offb]
                out[ro + offb:ro + row] = old_row[offb:]
            else:
                out[ro:ro + row - offb] = old_row[offb:]
                out[ro + row - offb:ro + row] = new_row[:offb]
        _write_fb(fb, out)
        _time.sleep(0.012)


def run_dashboard(cfg, fb, should_stop, write_status, exit_requested):
    """Main dashboard loop. Returns a short reason string when it stops.

    cfg         : resolved glanim globals (dashboard/touch flags)
    fb          : already opened /dev/fb0 descriptor
    should_stop : callable -> bool, true when SIGTERM requested
    write_status: callable(**kw) writing /tmp/glanim.status
    exit_requested: callable(), raised by long-press touch to leave OEM screen
    """
    set_font(cfg.get("font_pack", "classic"))
    bg_sources = []
    if cfg.get("mode") in ("dashboard", "custom", "clash"):
        bg_sources = load_custom_background_sources(cfg.get("custom_bg_dir"), int(cfg.get("custom_bg_max_frames", 300) or 300))
    cfg["_custom_bg_loaded"] = bool(bg_sources)
    bg_cache = {}
    bg_fb_cache = {}
    overlay_pixels = []
    overlay_key = None
    bg_blur_last = -1.0
    pages = build_pages(cfg)
    if not pages:
        write_status(error="no dashboard item selected")
        return "empty"

    mode_order = ["dashboard", "clash", "custom"]
    col = Collector()
    col.prime()

    touch = TouchReader(
        enabled=cfg.get("touch_enable", True),
        action=cfg.get("touch_action", "next"),
        swap_xy=cfg.get("touch_swap_xy", False),
        flip_x=cfg.get("touch_flip_x", False))
    touch.open()

    interval = max(2, int(cfg.get("dash_interval", "5") or 5))
    animating = bool(bg_sources)
    try:
        bg_fps = int(cfg.get("custom_bg_fps", "8") or 8)
    except Exception:
        bg_fps = 8
    bg_fps = max(1, min(15, bg_fps))
    # Poll touch at 20 Hz even when the panel itself refreshes at 1-8 fps.
    # Keeping the old "sleep for one background frame" was what made touch
    # feel delayed: the input device was only drained once per 125-1000 ms.
    frame_interval = 1.0 / 20.0
    bg_interval = (1.0 / bg_fps) if animating else 0.0
    next_bg_at = 0.0
    next_render_at = 0.0
    last_data = 0.0
    last_status = 0.0
    idx = 0
    switch_at = _time.time()
    canvas = Canvas()
    canvas.font = CURRENT_FONT
    canvas.bg_dim = 1.0 - current_mask(cfg) / 100.0
    bg_index = 0
    data = col.snapshot()
    last_data = _time.time()
    oc_toast_until = 0.0
    oc_toast_text = ""
    last_brightness = -1
    last_fb = None
    last_bg_fb = None
    vertical_key = None
    vertical_other_fb = None
    horizontal_key = None
    horizontal_other_fb = None
    menu_open = False
    brightness_open = False
    brightness_value = 5
    brightness_key = None
    fan_open = False
    fan_mode = "auto"
    fan_key = None
    fan_base = None
    fan_hold = None
    fan_hold_start = 0.0
    proxy_open = False
    proxy_mode = "rule"
    proxy_status = ""
    proxy_key = None
    proxy_base = None
    proxy_hold = None
    proxy_hold_start = 0.0
    confirm_open = False
    confirm_action = ""
    confirm_key = None
    confirm_base = None
    confirm_hold_start = 0.0
    last_menu_tap = -1
    menu_suppress_until = 0.0
    menu_pages = build_menu_pages(cfg)
    menu_lang = resolve_menu_lang(cfg.get("menu_lang", "auto"))
    menu_page = 0
    menu_base_key = None
    menu_base = None
    menu_last_touch = _time.time()
    menu_hold_action = None
    menu_hold_start = 0.0

    while not should_stop():
        old_buf = None
        slide_vdir = 0
        gestures = touch.poll()
        force_render = bool(gestures) or touch.drag_released
        menu_was_open = menu_open
        if menu_open:
            now = _time.time()
            if confirm_open:
                ckey = (confirm_action, menu_lang)
                if ckey != confirm_key:
                    draw_confirm(canvas, confirm_action, menu_lang)
                    confirm_base = bytes(canvas.render_fb())
                    confirm_key = ckey
                if touch.tap_id != last_menu_tap:
                    last_menu_tap = touch.tap_id
                    if touch.tap_x > 225 and touch.tap_y < 18:
                        confirm_open = False
                        menu_base_key = None
                        menu_last_touch = now
                if confirm_open and not touch.active:
                    confirm_hold_start = 0.0
                if confirm_open and touch.active:
                    if (touch.last_x - 142) ** 2 + (touch.last_y - 48) ** 2 <= 30 * 30:
                        if confirm_hold_start <= 0:
                            confirm_hold_start = now
                        progress = min(1.0, max(0.0, (now - confirm_hold_start) / MENU_HOLD))
                        if progress >= 1.0:
                            run_menu_action(confirm_action)
                            menu_open = False
                            confirm_open = False
                            menu_suppress_until = _time.time() + 5.0
                            force_render = True
                            gestures = []
                        else:
                            out = bytearray(confirm_base)
                            draw_progress_ring_fb(out, 142, 48, 29, progress, menu_accent(confirm_action))
                            _write_fb(fb, out)
                            _time.sleep(0.05)
                            continue
                    else:
                        confirm_hold_start = 0.0
                if menu_open:
                    _write_fb(fb, confirm_base)
                    _time.sleep(0.05)
                    continue
            if fan_open:
                fkey = (fan_mode, menu_lang)
                if fkey != fan_key:
                    draw_fan(canvas, fan_mode, menu_lang)
                    fan_base = bytes(canvas.render_fb())
                    fan_key = fkey
                if touch.tap_id != last_menu_tap:
                    last_menu_tap = touch.tap_id
                    if touch.tap_x > 225 and touch.tap_y < 18:
                        fan_open = False
                        fan_hold = None
                        menu_base_key = None
                        menu_last_touch = now
                if fan_open and not touch.active:
                    fan_hold = None
                if fan_open and touch.active:
                    fi = fan_hit(touch.last_x, touch.last_y)
                    if fi >= 0:
                        if fi != fan_hold:
                            fan_hold = fi
                            fan_hold_start = now
                        progress = min(1.0, max(0.0, (now - fan_hold_start) / MENU_HOLD))
                        if progress >= 1.0:
                            fan_mode = FAN_MODES[fi][0]
                            set_fan_mode(fan_mode)
                            fan_hold = None
                            fan_key = None
                            menu_last_touch = now
                        else:
                            out = bytearray(fan_base)
                            draw_progress_ring_fb(out, 36 + fi * 71, 44, 29, progress, (90, 150, 255))
                            _write_fb(fb, out)
                            _time.sleep(0.05)
                            continue
                    else:
                        fan_hold = None
                if fan_open:
                    _write_fb(fb, fan_base)
                    _time.sleep(0.05)
                    continue
            if proxy_open:
                pkey = (proxy_mode, proxy_status, menu_lang)
                if pkey != proxy_key:
                    draw_proxy(canvas, proxy_mode, menu_lang, proxy_status)
                    proxy_base = bytes(canvas.render_fb())
                    proxy_key = pkey
                if touch.tap_id != last_menu_tap:
                    last_menu_tap = touch.tap_id
                    if touch.tap_x > 225 and touch.tap_y < 18:
                        proxy_open = False
                        proxy_hold = None
                        menu_base_key = None
                        menu_last_touch = now
                if proxy_open and not touch.active:
                    proxy_hold = None
                if proxy_open and touch.active:
                    pi = proxy_hit(touch.last_x, touch.last_y)
                    if pi >= 0:
                        if pi != proxy_hold:
                            proxy_hold = pi
                            proxy_hold_start = now
                        progress = min(1.0, max(0.0, (now - proxy_hold_start) / MENU_HOLD))
                        if progress >= 1.0:
                            key = PROXY_ITEMS[pi][0]
                            if key == "mode":
                                order = ["rule", "global", "direct"]
                                nxt = order[(order.index(proxy_mode) + 1) % 3] if proxy_mode in order else "rule"
                                set_clash_mode(nxt)
                                proxy_mode = nxt
                                proxy_status = ""
                            elif key == "best":
                                proxy_status = "已优选" if best_clash_node() else "优选失败"
                            elif key == "restart":
                                restart_openclash()
                                proxy_status = "重启中"
                            else:
                                stop_openclash()
                                proxy_status = "关闭中"
                            proxy_hold = None
                            proxy_key = None
                            menu_last_touch = now
                        else:
                            out = bytearray(proxy_base)
                            draw_progress_ring_fb(out, 36 + pi * 71, 44, 29, progress, (90, 150, 255))
                            _write_fb(fb, out)
                            _time.sleep(0.05)
                            continue
                    else:
                        proxy_hold = None
                if proxy_open:
                    _write_fb(fb, proxy_base)
                    _time.sleep(0.05)
                    continue
            if brightness_open:
                if touch.tap_id != last_menu_tap:
                    last_menu_tap = touch.tap_id
                    tx, ty = touch.tap_x, touch.tap_y
                    if 100 <= tx <= 184 and ty >= 58:
                        brightness_open = False
                        menu_base_key = None
                        menu_last_touch = now
                    elif tx < 95:
                        brightness_value = adjust_brightness(-1)
                        menu_last_touch = now
                    elif tx > 189:
                        brightness_value = adjust_brightness(1)
                        menu_last_touch = now
                bkey = (brightness_value, menu_lang)
                if bkey != brightness_key:
                    draw_brightness(canvas, brightness_value, menu_lang)
                    _write_fb(fb, canvas.render_fb())
                    brightness_key = bkey
                _time.sleep(0.05)
                continue
            actions = menu_pages[menu_page]
            pending = None
            progress = 0.0
            # A long press on a submenu button must open it without a ring.
            if "menu" in gestures and not touch.active:
                act = menu_hit(touch.last_x, touch.last_y, actions)
                gestures.remove("menu")
                if act == "brightness":
                    brightness_value = current_brightness(cfg)
                    brightness_open = True
                    menu_last_touch = now
                elif act == "fan":
                    fan_mode = current_fan_mode()
                    fan_open = True
                    fan_key = None
                    menu_last_touch = now
                elif act == "clash":
                    proxy_mode = current_clash_mode()
                    proxy_status = ""
                    proxy_open = True
                    proxy_key = None
                    proxy_hold = None
                    menu_last_touch = now
                elif act in MENU_CONFIRM:
                    confirm_action = act
                    confirm_open = True
                    confirm_key = None
                    confirm_hold_start = 0.0
                    menu_last_touch = now
            if touch.active:
                menu_last_touch = now
            if touch.tap_id != last_menu_tap:
                menu_last_touch = now
                last_menu_tap = touch.tap_id
                if touch.tap_x > 220 and touch.tap_y < 18:
                    menu_open = False
                    menu_suppress_until = _time.time() + 5.0
                    force_render = True
                    gestures = []
                    tap_action = None
                else:
                    tap_action = menu_hit(touch.tap_x, touch.tap_y, actions)
                if not tap_action:
                    if touch.tap_x > PHYS_W - 70 and actions[3] in ("next", "exit"):
                        tap_action = actions[3]
                    elif touch.tap_x < 70 and actions[0] in ("back", "exit"):
                        tap_action = actions[0]
                if tap_action == "brightness":
                    brightness_value = current_brightness(cfg)
                    brightness_open = True
                    menu_last_touch = now
                elif tap_action == "fan":
                    fan_mode = current_fan_mode()
                    fan_open = True
                    fan_key = None
                    menu_last_touch = now
                elif tap_action == "clash":
                    proxy_mode = current_clash_mode()
                    proxy_status = ""
                    proxy_open = True
                    proxy_key = None
                    proxy_hold = None
                    menu_last_touch = now
                elif tap_action in MENU_CONFIRM:
                    confirm_action = tap_action
                    confirm_open = True
                    confirm_key = None
                    confirm_hold_start = 0.0
                    menu_last_touch = now

                elif tap_action in ("next", "back", "exit"):
                    if tap_action == "next" and menu_page + 1 < len(menu_pages):
                        menu_page += 1
                        actions = menu_pages[menu_page]
                    elif tap_action == "back" and menu_page > 0:
                        menu_page -= 1
                        actions = menu_pages[menu_page]
                    else:
                        menu_open = False
                        menu_suppress_until = _time.time() + 5.0
                        force_render = True
                        gestures = []
            if menu_open and touch.active:
                pending = menu_hit(touch.last_x, touch.last_y, actions)
                if pending in MENU_SUBMENUS or pending in MENU_CONFIRM:
                    pending = None
                if not pending:
                    menu_hold_action = None
            if menu_open:
                idle = now - menu_last_touch
                if idle >= 15.0:
                    menu_open = False
                    menu_suppress_until = _time.time() + 5.0
                    force_render = True
                    gestures = []
                else:
                    notice = ""
                    if pending and pending not in ("next", "back"):
                        notice = pending_text(pending, menu_lang)
                    elif not pending and idle >= 10.0:
                        left = max(1, int(math.ceil(15.0 - idle)))
                        notice = ("即将在 %ds 后关闭菜单页面" % left) if menu_lang == "zh" else ("MENU CLOSES IN %ds" % left)
                    key = (menu_page, menu_lang, tuple(actions),
                           pending if pending in ("next", "back", "exit") else None,
                           notice)
                    if key != menu_base_key:
                        menu_canvas = Canvas()
                        draw_menu(menu_canvas, actions, menu_lang, menu_page,
                                  len(menu_pages), pending, 0.0, notice)
                        menu_base = bytes(menu_canvas.render_fb())
                        menu_base_key = key
                        if pending:
                            menu_hold_action = pending
                            menu_hold_start = _time.time()
                        else:
                            menu_hold_action = None
                    if menu_open and pending:
                        if pending != menu_hold_action:
                            menu_hold_action = pending
                            menu_hold_start = _time.time()
                        progress = min(1.0, max(0.0, (_time.time() - menu_hold_start) / MENU_HOLD))
                        if progress >= 1.0:
                            if pending not in ("next", "back", "exit"):
                                run_menu_action(pending)
                            menu_open = False
                            menu_suppress_until = _time.time() + 5.0
                            force_render = True
                            gestures = []
                    if menu_open:
                        out = bytearray(menu_base)
                        if pending and progress > 0:
                            slot = actions.index(pending)
                            draw_progress_ring_fb(out, 36 + slot * 71, 44, 29,
                                                  progress, menu_accent(pending))
                        _write_fb(fb, out)
                        _time.sleep(0.05)
                        continue
        else:
            for g in gestures:
                if g == "menu" and _time.time() >= menu_suppress_until:
                    menu_open = True
                    menu_page = 0
                    menu_base_key = None
                    menu_lang = resolve_menu_lang(cfg.get("menu_lang", "auto"))
                    menu_last_touch = _time.time()
                    last_menu_tap = touch.tap_id
                    gestures = []
                    break
        if menu_open:
            _time.sleep(0.05)
            continue
        if menu_was_open:
            gestures = []
        for g in gestures:
            if g == "exit":
                exit_requested()
                touch.close()
                return "exit"
            if g == "next" or g == "swipe_left":
                # Page changes are instant; no horizontal animation.
                idx = (idx + 1) % len(pages)
                switch_at = _time.time()
            elif g == "prev" or g == "swipe_right":
                idx = (idx - 1) % len(pages)
                switch_at = _time.time()
            elif g in ("swipe_up", "swipe_down"):
                cur = cfg.get("mode")
                if cur in mode_order:
                    pos = mode_order.index(cur)
                    step = -1 if g == "swipe_up" else 1
                    next_mode = mode_order[(pos + step) % len(mode_order)]
                else:
                    next_mode = "clash"
                if next_mode != cur:
                    if not touch.drag_moved:
                        old_buf = bytes(canvas.buf)
                    cfg["mode"] = next_mode
                    pages = build_pages(cfg)
                    idx = 0
                    slide_vdir = 0 if touch.drag_moved else (-1 if g == "swipe_up" else 1)
                    switch_at = _time.time()
                    script = ("uci set glanim.globals.mode='%s'; uci commit glanim"
                              % next_mode)
                    try:
                        subprocess.Popen(["/bin/sh", "-c", script],
                                         stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL)
                    except Exception:
                        pass
            elif g == "toggle_clash" and cfg.get("mode") == "clash":
                if _time.time() >= oc_toast_until:
                    oc_toast_text = toggle_openclash()
                    oc_toast_until = _time.time() + 2.5

        now = _time.time()
        paused = touch.active
        if not current_auto(cfg):
            try:
                with open("/tmp/glanim.page", "r") as pf:
                    wanted = pf.read().strip()
                keys = [p[0] for p in pages]
                if wanted in keys:
                    idx = keys.index(wanted)
                    switch_at = now
                    force_render = True
                os.remove("/tmp/glanim.page")
            except Exception:
                pass
        # Inside a panel, pages rotate silently (no slide animation).
        if (len(pages) > 1 and current_auto(cfg) and not paused
                and now - switch_at >= interval):
            idx = (idx + 1) % len(pages)
            switch_at = now
            force_render = True

        if now - last_data >= 1.0 and not paused:
            data = col.snapshot()
            last_data = now
        need_render = (force_render or touch.dragging or old_buf is not None
                       or now >= next_render_at)
        if need_render:
            canvas.bg_dim = 1.0 - current_mask(cfg) / 100.0
            canvas.content_alpha = current_content_alpha(cfg)
            if (touch.dragging and last_fb is not None
                    and abs(touch.drag_dx) > 2
                    and abs(touch.drag_dx) > abs(touch.drag_dy)):
                dx = int(touch.drag_dx)
                oi = (idx + (1 if dx < 0 else -1)) % len(pages)
                hkey = (idx, oi, id(data), id(last_bg_fb))
                if hkey != horizontal_key:
                    horizontal_other_fb = render_neighbor_fb(
                        pages, oi, data, cfg, last_bg_fb, canvas.content_alpha)
                    horizontal_key = hkey
                if horizontal_other_fb is not None:
                    _write_fb(fb, compose_horizontal_fb(last_fb, horizontal_other_fb, dx))
                    _time.sleep(0.05)
                    continue
            if (touch.dragging and last_fb is not None
                    and abs(touch.drag_dy) > 2
                    and abs(touch.drag_dy) >= abs(touch.drag_dx)):
                dy = int(touch.drag_dy)
                cur_mode = cfg.get("mode")
                if cur_mode in mode_order:
                    pos = mode_order.index(cur_mode)
                    step = -1 if dy < 0 else 1
                    other_mode = mode_order[(pos + step) % len(mode_order)]
                else:
                    other_mode = "clash"
                vkey = (cur_mode, other_mode, id(data), id(canvas.background), id(last_bg_fb))
                if vkey != vertical_key:
                    other_cfg = dict(cfg)
                    other_cfg["mode"] = other_mode
                    other_pages = build_pages(other_cfg)
                    if other_pages:
                        vertical_other_fb = render_neighbor_fb(
                            other_pages, 0, data, other_cfg,
                            last_bg_fb, canvas.content_alpha)
                        vertical_key = vkey
                if vertical_other_fb is not None:
                    _write_fb(fb, compose_vertical_fb(last_fb, vertical_other_fb, dy))
                    _time.sleep(0.05)
                    continue
            live_b = current_brightness(cfg)
            if live_b != last_brightness:
                apply_brightness(live_b)
                last_brightness = live_b
            fast_ok = False
            last_bg_fb = None
            blur_now = current_blur(cfg)
            if (bg_sources and not touch.dragging
                    and old_buf is None and now >= oc_toast_until):
                if now >= next_bg_at and not paused:
                    bg_index += 1
                    next_bg_at = now + bg_interval
                fi = (bg_index - 1) % len(bg_sources) if bg_index else 0
                raw = load_fb_source(bg_sources[fi])
                if raw:
                    key = (idx, id(data), int(canvas.bg_dim * 100))
                    if overlay_key != key:
                        overlay_pixels = build_overlay(pages, idx, data, cfg)
                        overlay_key = key
                    dim_key = (fi, int(canvas.bg_dim * 100), int(blur_now))
                    if dim_key not in bg_fb_cache:
                        if len(bg_sources) == 1 and blur_now > 0:
                            base = frost_fb(raw, blur_now, quality=True)
                            bg_fb_cache[dim_key] = dim_fb(base, canvas.bg_dim)
                        else:
                            bg_fb_cache[dim_key] = fast_effect(raw, blur_now, canvas.bg_dim)
                    out = bytearray(bg_fb_cache[dim_key])
                    last_bg_fb = bytes(out)
                    ca = canvas.content_alpha
                    for bi, c in overlay_pixels:
                        if ca < 0.999:
                            bgc = out[bi] | (out[bi + 1] << 8)
                            c = blend565(bgc, c, ca)
                        out[bi] = c & 255
                        out[bi + 1] = (c >> 8) & 255
                    _write_fb(fb, out)
                    last_fb = bytes(out)
                    fast_ok = True
            if fast_ok:
                pass
            else:
                if bg_sources:
                    blur = current_blur(cfg)
                    if blur != bg_blur_last:
                        bg_cache.clear()
                        bg_blur_last = blur
                    if now >= next_bg_at and not paused:
                        bg_index += 1
                        next_bg_at = now + bg_interval
                    fi = (bg_index - 1) % len(bg_sources) if bg_index else 0
                    if fi not in bg_cache:
                        frame = load_background_source(bg_sources[fi])
                        if frame is not None:
                            bg_cache[fi] = frost_frame(frame, blur)
                    canvas.background = bg_cache.get(fi)
                else:
                    canvas.background = None
                pages[idx][1](canvas, data, cfg)
                draw_nav(canvas, len(pages))
                if now < oc_toast_until:
                    draw_toast(canvas, oc_toast_text)
                live = None
                if touch.dragging and touch.drag_moved:
                    odx, ody = touch.drag_dx, touch.drag_dy
                    other = canvas
                    if abs(odx) >= abs(ody):
                        oi = (idx + (1 if odx < 0 else -1)) % len(pages)
                        other = Canvas()
                        other.font = canvas.font
                        other.bg_dim = canvas.bg_dim
                        other.background = canvas.background
                        pages[oi][1](other, data, cfg)
                        draw_nav(other, len(pages))
                    live = compose_live_drag(canvas, other, odx, ody)
                if live is not None:
                    _write_fb(fb, live.render_fb())
                elif old_buf is not None and slide_vdir:
                    animate_slide_vertical(fb, old_buf, bytes(canvas.buf), slide_vdir, should_stop)
                else:
                    frame_fb = canvas.render_fb()
                    _write_fb(fb, frame_fb)
                    last_fb = bytes(frame_fb)
            next_render_at = now + (bg_interval if animating else 1.0)
            touch.drag_released = False

        if now - last_status >= 1.0:
            write_status(
                page=pages[idx][0],
                mode=cfg.get("mode", ""),
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
                rx_total=data.get("rx_total", 0), tx_total=data.get("tx_total", 0),
                conn_count=data.get("conn_count", 0),
                oc_running="1" if data.get("oc_running") else "0",
                oc_mode=data.get("oc_mode", ""),
                oc_mem=data.get("oc_mem", 0),
                oc_uptime=data.get("oc_uptime", ""),
                oc_group=data.get("oc_group", ""),
                oc_group_count=data.get("oc_group_count", 0),
                oc_node=data.get("oc_node", ""),
                oc_country=data.get("oc_country", ""),
                oc_node_type=data.get("oc_node_type", ""),
                oc_udp=data.get("oc_udp", ""),
                oc_rate=data.get("oc_rate", "1x"),
                oc_delay=data.get("oc_delay", 0),
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
