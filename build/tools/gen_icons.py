# -*- coding: utf-8 -*-
"""Generate the 256x256 LuCI / VUM app-icons for both plugins.

Drawn at 4x and downsampled with LANCZOS for clean edges. The screen icon now
mirrors the wide 284x76 panel (blocky digits + three progress bars), and the
fan icon mirrors the new dashboard (fan + speed arc + live curve).
"""
import os
import sys
from PIL import Image, ImageDraw

SIZE = 256
SS = 4
N = SIZE * SS
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "glanim", "usr", "bin"))
try:
    import glanimdash
    FONT = glanimdash.FONT
except Exception:
    FONT = {}


def diagonal_gradient(top, bottom):
    img = Image.new("RGB", (N, N))
    px = img.load()
    for y in range(N):
        for x in range(N):
            t = (x + y) / (2.0 * (N - 1))
            px[x, y] = (
                round(top[0] + (bottom[0] - top[0]) * t),
                round(top[1] + (bottom[1] - top[1]) * t),
                round(top[2] + (bottom[2] - top[2]) * t),
            )
    return img


def card(top, bottom):
    gradient = diagonal_gradient(top, bottom)
    mask = Image.new("L", (N, N), 0)
    md = ImageDraw.Draw(mask)
    md.rounded_rectangle([18 * SS, 18 * SS, N - 18 * SS, N - 18 * SS],
                         radius=58 * SS, fill=255)
    out = Image.new("RGBA", (N, N), (0, 0, 0, 0))
    out.paste(gradient, (0, 0), mask)
    return out


def save_icon(canvas, path):
    canvas.resize((SIZE, SIZE), Image.LANCZOS).save(path, "PNG")


def draw_pixel_text(d, text, x, y, scale, color):
    cx = x
    for ch in text.upper():
        cols = FONT.get(ch, FONT.get(" ", (0, 0, 0, 0, 0)))
        for c in range(5):
            bits = cols[c] if c < len(cols) else 0
            for r in range(7):
                if (bits >> r) & 1:
                    d.rectangle([cx + c * scale, y + r * scale,
                                 cx + (c + 1) * scale - 1, y + (r + 1) * scale - 1],
                                fill=color)
        cx += 6 * scale


def make_fan(path):
    canvas = card((91, 108, 255), (139, 92, 246))
    cx = cy = 128 * SS
    # 4 blades
    for angle in (0, 90, 180, 270):
        leaf = Image.new("RGBA", (N, N), (0, 0, 0, 0))
        ld = ImageDraw.Draw(leaf)
        ld.ellipse([cx + 22 * SS, cy - 21 * SS, cx + 78 * SS, cy + 21 * SS],
                   fill=(255, 255, 255, 238))
        leaf = leaf.rotate(angle, center=(cx, cy), resample=Image.BICUBIC)
        canvas = Image.alpha_composite(canvas, leaf)
    d = ImageDraw.Draw(canvas)
    # guard ring
    d.ellipse([cx - 80 * SS, cy - 80 * SS, cx + 80 * SS, cy + 80 * SS],
              outline=(255, 255, 255, 210), width=7 * SS)
    # hub
    d.ellipse([cx - 22 * SS, cy - 22 * SS, cx + 22 * SS, cy + 22 * SS],
              fill=(255, 255, 255, 248))
    d.ellipse([cx - 9 * SS, cy - 9 * SS, cx + 9 * SS, cy + 9 * SS],
              fill=(91, 108, 255, 255))
    # speed arc + ticks
    d.arc([cx - 92 * SS, cy - 92 * SS, cx + 92 * SS, cy + 92 * SS],
          start=38, end=142, fill=(94, 234, 212, 245), width=6 * SS)
    for x in (56, 72, 88):
        d.rectangle([x * SS, 214 * SS, (x + 8) * SS, 219 * SS],
                    fill=(255, 255, 255, 190))
    save_icon(canvas, path)


def make_screen(path):
    canvas = card((20, 184, 166), (99, 102, 241))
    d = ImageDraw.Draw(canvas)
    # wide 284x76-ish panel
    panel = [34 * SS, 76 * SS, 222 * SS, 180 * SS]
    d.rounded_rectangle(panel, radius=18 * SS, fill=(255, 255, 255, 245))
    inner = [41 * SS, 83 * SS, 215 * SS, 173 * SS]
    d.rounded_rectangle(inner, radius=13 * SS, fill=(10, 12, 18, 255))

    # blocky "88" (the actual 5x7 panel font)
    draw_pixel_text(d, "88", 54 * SS, 98 * SS, 5 * SS, (244, 247, 255, 255))
    draw_pixel_text(d, "CPU", 54 * SS, 140 * SS, 2 * SS, (190, 202, 218, 255))

    # three bars
    bars = [
        (128, 101, 0.78, (60, 210, 110)),
        (128, 121, 0.56, (240, 190, 60)),
        (128, 141, 0.34, (230, 70, 70)),
    ]
    for x, y, pct, col in bars:
        d.rounded_rectangle([x * SS, y * SS, 204 * SS, (y + 13) * SS],
                            radius=6 * SS, fill=(38, 42, 54, 255))
        d.rounded_rectangle([x * SS, y * SS, (x + int(76 * pct)) * SS, (y + 13) * SS],
                            radius=6 * SS, fill=col + (255,))
    # palette swatches
    colors = [(239, 68, 68), (250, 204, 21), (59, 130, 246), (34, 197, 94)]
    for i, col in enumerate(colors):
        x = 54 + i * 17
        d.rounded_rectangle([x * SS, 158 * SS, (x + 11) * SS, 168 * SS],
                            radius=4 * SS, fill=col + (255,))
    # small editor cursor / accent
    d.rectangle([188 * SS, 154 * SS, 206 * SS, 157 * SS], fill=(94, 234, 212, 255))
    d.rectangle([202 * SS, 154 * SS, 205 * SS, 168 * SS], fill=(94, 234, 212, 255))
    save_icon(canvas, path)


def main():
    targets = [
        (make_fan, "glfanctl", "glfanctl.png"),
        (make_screen, "glanim", "glanim.png"),
    ]
    for fn, pkg, name in targets:
        out_dir = os.path.join(ROOT, pkg, "www", "luci-static",
                               "resources", "app-icons")
        os.makedirs(out_dir, exist_ok=True)
        p = os.path.join(out_dir, name)
        fn(p)
        prev_dir = os.path.join(ROOT, "ref-icons")
        os.makedirs(prev_dir, exist_ok=True)
        Image.open(p).save(os.path.join(prev_dir, "preview-" + name), "PNG")
        print("wrote", p)


if __name__ == "__main__":
    main()
