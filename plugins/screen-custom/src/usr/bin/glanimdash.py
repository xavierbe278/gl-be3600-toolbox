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
import array
import time as _time
import subprocess
import socket
import urllib.request


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
    '中': ('000', '000', '000', '030', '030', '1fe', '132', '132', '1fe', '030', '030', '030', '000'),
    '亚': ('000', '000', '000', '3ff', '048', '14a', '14a', '1ce', '0cc', '048', '048', '3ff', '000'),
    '俄': ('000', '000', '044', '1fe', '152', '052', '3ff', '3d3', '1fe', '092', '2f2', '31a', '000'),
    '兰': ('000', '000', '000', '084', '048', '3ff', '000', '000', '1fe', '000', '000', '3ff', '000'),
    '其': ('000', '000', '000', '084', '3ff', '084', '0fc', '0fc', '084', '3ff', '0cc', '303', '000'),
    '利': ('000', '000', '000', '11c', '14f', '144', '17f', '15c', '156', '147', '105', '1c4', '000'),
    '加': ('000', '000', '000', '004', '3df', '354', '356', '356', '352', '352', '3da', '34d', '000'),
    '南': ('000', '000', '000', '030', '3ff', '030', '1fe', '14a', '1fe', '1fe', '132', '1f2', '000'),
    '印': ('000', '000', '000', '1ee', '122', '122', '13e', '122', '122', '13a', '1e7', '020', '000'),
    '台': ('000', '000', '010', '008', '08c', '1f6', '20f', '000', '1fe', '102', '102', '1fe', '000'),
    '国': ('000', '000', '000', '1fe', '102', '1fe', '132', '1fe', '172', '1fe', '102', '1fe', '000'),
    '土': ('000', '000', '000', '030', '030', '030', '1fe', '030', '030', '030', '030', '3ff', '000'),
    '坡': ('000', '000', '000', '042', '3f2', '25f', '052', '1f2', '132', '0df', '0c8', '338', '000'),
    '大': ('000', '000', '030', '030', '030', '3ff', '030', '030', '078', '048', '086', '303', '000'),
    '宾': ('000', '000', '000', '030', '3ff', '3e3', '03c', '1fc', '044', '3ff', '0cc', '102', '000'),
    '尼': ('000', '000', '000', '1fe', '102', '1fe', '00a', '10a', '0ca', '23a', '21a', '1f1', '000'),
    '巴': ('000', '000', '000', '1fe', '132', '132', '1fe', '102', '002', '202', '302', '1fe', '000'),
    '度': ('000', '000', '000', '020', '3fe', '09a', '3fe', '0fa', '1fe', '0d2', '073', '38d', '000'),
    '廷': ('000', '000', '000', '1f7', '046', '042', '1f7', '045', '046', '3f6', '00e', '3f9', '000'),
    '律': ('000', '000', '000', '044', '1f2', '3fd', '146', '1f2', '043', '1fa', '3fa', '042', '000'),
    '德': ('000', '000', '000', '044', '3fa', '1fd', '1ae', '1fa', '3fb', '1da', '29e', '0e2', '000'),
    '拿': ('000', '000', '030', '0cc', '37b', '0fc', '0fc', '000', '1fe', '1fe', '3ff', '018', '000'),
    '斯': ('000', '000', '000', '392', '07f', '052', '3de', '15e', '132', '13f', '13a', '121', '000'),
    '新': ('000', '000', '000', '3ff', '032', '02a', '3ff', '124', '13f', '12e', '135', '116', '000'),
    '日': ('000', '000', '000', '1fe', '186', '186', '186', '1fe', '186', '186', '186', '1fe', '000'),
    '本': ('000', '000', '030', '030', '3ff', '030', '078', '07c', '0b4', '132', '3fd', '030', '030'),
    '来': ('000', '000', '000', '030', '1fe', '0b4', '0b4', '078', '3ff', '078', '0b4', '333', '030'),
    '根': ('000', '000', '000', '1f6', '116', '1ff', '116', '1fe', '357', '097', '1f6', '336', '000'),
    '法': ('000', '000', '042', '046', '1f8', '043', '042', '3f8', '022', '092', '19a', '3f9', '000'),
    '泰': ('000', '000', '010', '1fe', '010', '1fe', '018', '3ff', '3ef', '0f8', '136', '018', '000'),
    '港': ('000', '000', '000', '092', '1fe', '091', '3fe', '0f8', '29e', '1fa', '11a', '1f3', '000'),
    '湾': ('000', '000', '000', '022', '3fe', '1e9', '1fa', '100', '1fa', '1fa', '102', '1e3', '000'),
    '澳': ('000', '000', '000', '022', '1fe', '1fb', '1fa', '1f8', '14a', '3fe', '1ba', '30f', '000'),
    '罗': ('000', '000', '000', '1fe', '14a', '14a', '1fe', '1f8', '08c', '059', '030', '00e', '000'),
    '美': ('000', '000', '000', '048', '3ff', '030', '1fe', '3ff', '030', '3ff', '0f8', '387', '000'),
    '耳': ('000', '000', '000', '3ff', '084', '0fc', '084', '0fc', '084', '3fc', '08f', '080', '080'),
    '英': ('000', '000', '000', '048', '3ff', '030', '1fe', '132', '132', '3ff', '048', '387', '000'),
    '荷': ('000', '000', '000', '048', '3ff', '004', '3fe', '17e', '15f', '17e', '106', '0c6', '000'),
    '菲': ('000', '000', '000', '048', '3ff', '000', '3ce', '048', '1ce', '048', '3cf', '048', '000'),
    '西': ('000', '000', '000', '3ff', '058', '3fe', '34a', '34a', '3c6', '302', '302', '3fe', '000'),
    '越': ('000', '000', '000', '144', '3fe', '1e4', '1bf', '0e6', '2be', '3d6', '147', '3f9', '000'),
    '阿': ('000', '000', '000', '3ff', '107', '177', '157', '157', '15f', '17f', '117', '1c3', '000'),
    '韩': ('000', '000', '000', '044', '3ff', '05f', '1f1', '05f', '3ff', '244', '1df', '044', '000'),
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
        if now - self.last_gesture_at < 0.35:
            return
        dx = px - self.start_x if self.start_set else 0
        dy = py - self.start_y if self.start_set else 0
        if held >= LONG_PRESS:
            gestures.append("exit")
            self.last_gesture = "exit"
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
    """Fast 5-frame vertical mode transition."""
    steps = 5
    rb = PHYS_W * 3
    for step in range(1, steps + 1):
        if should_stop():
            return
        off = PHYS_H * step // steps
        out = bytearray(len(old_buf))
        for y in range(PHYS_H):
            ro = y * rb
            if direction > 0:
                # Finger down: old slides down, new arrives from the top.
                if y < off:
                    src = (PHYS_H - off + y) * rb
                    out[ro:ro + rb] = new_buf[src:src + rb]
                else:
                    src = (y - off) * rb
                    out[ro:ro + rb] = old_buf[src:src + rb]
            else:
                # Finger up: old slides up, new arrives from the bottom.
                if y < PHYS_H - off:
                    src = (y + off) * rb
                    out[ro:ro + rb] = old_buf[src:src + rb]
                else:
                    src = (y - (PHYS_H - off)) * rb
                    out[ro:ro + rb] = new_buf[src:src + rb]
        tmp = Canvas()
        tmp.buf = out
        _write_fb(fb, tmp.render_fb())
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

    while not should_stop():
        old_buf = None
        slide_vdir = 0
        gestures = touch.poll()
        force_render = bool(gestures) or touch.drag_released
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
        if (len(pages) > 1 and current_auto(cfg)
                and now - switch_at >= interval):
            idx = (idx + 1) % len(pages)
            switch_at = now
            force_render = True

        if now - last_data >= 1.0:
            data = col.snapshot()
            last_data = now
        need_render = (force_render or touch.dragging or old_buf is not None
                       or now >= next_render_at)
        if need_render:
            canvas.bg_dim = 1.0 - current_mask(cfg) / 100.0
            canvas.content_alpha = current_content_alpha(cfg)
            live_b = current_brightness(cfg)
            if live_b != last_brightness:
                apply_brightness(live_b)
                last_brightness = live_b
            fast_ok = False
            blur_now = current_blur(cfg)
            if (bg_sources and not touch.dragging
                    and old_buf is None and now >= oc_toast_until):
                if now >= next_bg_at:
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
                    ca = canvas.content_alpha
                    for bi, c in overlay_pixels:
                        if ca < 0.999:
                            bgc = out[bi] | (out[bi + 1] << 8)
                            c = blend565(bgc, c, ca)
                        out[bi] = c & 255
                        out[bi + 1] = (c >> 8) & 255
                    _write_fb(fb, out)
                    fast_ok = True
            if fast_ok:
                pass
            else:
                if bg_sources:
                    blur = current_blur(cfg)
                    if blur != bg_blur_last:
                        bg_cache.clear()
                        bg_blur_last = blur
                    if now >= next_bg_at:
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
                    _write_fb(fb, canvas.render_fb())
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
