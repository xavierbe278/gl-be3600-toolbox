# -*- coding: utf-8 -*-
"""
glanim-convert.py - Convert GIF / PNG / JPG into a frame pack for the
GL-BE3600 ST7789 panel driven through /dev/fb0 (76x284 RGB565 little-endian).

The physical panel is 284 wide x 76 high (horizontal bar). The framebuffer
memory is stored as 76 columns x 284 rows (90 degree rotated), so the tool
maps the adapted physical image into that layout according to --orientation.

Usage:
  python glanim-convert.py input.gif -o pack.tar.gz
  python glanim-convert.py input.png --still
  python glanim-convert.py --test-pattern -o test.tar.gz

Options:
  --fit contain|cover|stretch   contain (default), cover, stretch
  --orientation fb90|fb90m|fb270|fb270m|direct
                                 Memory layout mapping, see --test-pattern
  --bg black|white               background for contain mode / transparency
  --fps N                        force frame interval (0 = GIF native delay)
  --rotate 0|90|180|270          rotate source image before adaptation
  --still                        export only the first frame
  --max-frames N                 cap number of frames (default 600)
  --test-pattern                 emit 4 orientation calibration frames
"""
import argparse
import io
import json
import os
import struct
import sys
import tarfile

try:
    from PIL import Image, ImageDraw, ImageSequence, ImageFont
except ImportError:
    sys.exit("Pillow required: python -m pip install Pillow")

PHYS_W, PHYS_H = 284, 76          # physical panel size
FB_W, FB_H = 76, 284              # framebuffer memory size (stride 152 bytes)
FB_BYTES = FB_W * FB_H * 2


def load_font(size):
    for name in ("arial.ttf", "C:/Windows/Fonts/arial.ttf",
                 "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except Exception:
            continue
    return ImageFont.load_default()


def fit_image(src, fit, bg, rotate=0):
    if rotate:
        src = src.rotate(rotate, expand=True)
    src = src.convert("RGBA")
    bg_rgb = (0, 0, 0) if bg == "black" else (255, 255, 255)
    base = Image.new("RGBA", (PHYS_W, PHYS_H), bg_rgb + (255,))

    if fit == "stretch":
        resized = src.resize((PHYS_W, PHYS_H), Image.LANCZOS)
        base.alpha_composite(resized)
        return base.convert("RGB")

    sw, sh = src.size
    scale = min(PHYS_W / sw, PHYS_H / sh) if fit == "contain" \
        else max(PHYS_W / sw, PHYS_H / sh)
    nw, nh = max(1, round(sw * scale)), max(1, round(sh * scale))
    resized = src.resize((nw, nh), Image.LANCZOS)

    if fit == "cover":
        left = (nw - PHYS_W) // 2
        top = (nh - PHYS_H) // 2
        resized = resized.crop((left, top, left + PHYS_W, top + PHYS_H))
        base.alpha_composite(resized)
    else:
        base.alpha_composite(resized, ((PHYS_W - nw) // 2, (PHYS_H - nh) // 2))
    return base.convert("RGB")


def rgb565(r, g, b, bgr=False):
    if bgr:
        r, b = b, r
    c = ((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3)
    return struct.pack("<H", c)


def phys_to_fb(phys, orientation):
    """Map a 284x76 RGB physical image into a 76x284 RGB565LE frame."""
    px = phys.load()
    out = bytearray(FB_BYTES)
    for y_fb in range(FB_H):
        for x_fb in range(FB_W):
            if orientation == "direct":
                # source already expected vertical 76x284 -> resized later
                continue
            if orientation == "fb90":
                p_x, p_y = y_fb, x_fb
            elif orientation == "fb90m":
                p_x, p_y = FB_H - 1 - y_fb, x_fb
            elif orientation == "fb270":
                p_x, p_y = FB_H - 1 - y_fb, FB_W - 1 - x_fb
            elif orientation == "fb270m":
                p_x, p_y = y_fb, FB_W - 1 - x_fb
            else:
                p_x, p_y = y_fb, x_fb
            r, g, b = px[p_x, p_y]
            out[(y_fb * FB_W + x_fb) * 2:(y_fb * FB_W + x_fb) * 2 + 2] = \
                rgb565(r, g, b)
    return bytes(out)


def direct_vertical(vert_img):
    vert_img = vert_img.resize((FB_W, FB_H), Image.LANCZOS).convert("RGB")
    px = vert_img.load()
    out = bytearray(FB_BYTES)
    for y in range(FB_H):
        for x in range(FB_W):
            r, g, b = px[x, y]
            out[(y * FB_W + x) * 2:(y * FB_W + x) * 2 + 2] = rgb565(r, g, b)
    return bytes(out)


def test_pattern():
    """Four orientation calibration frames: quadrant colors, arrows, label."""
    frames = []
    labels = ["fb90", "fb90m", "fb270", "fb270m"]
    for idx, orient in enumerate(labels):
        phys = Image.new("RGB", (PHYS_W, PHYS_H), (20, 20, 20))
        d = ImageDraw.Draw(phys)
        # quadrants: TL red, TR green, BL blue, BR yellow
        d.rectangle((0, 0, PHYS_W // 2, PHYS_H // 2), fill=(220, 30, 30))
        d.rectangle((PHYS_W // 2, 0, PHYS_W, PHYS_H // 2), fill=(30, 200, 60))
        d.rectangle((0, PHYS_H // 2, PHYS_W // 2, PHYS_H), fill=(30, 80, 230))
        d.rectangle((PHYS_W // 2, PHYS_H // 2, PHYS_W, PHYS_H), fill=(230, 220, 30))
        f_big = load_font(40)
        d.text((PHYS_W // 2 - 18, 12), str(idx + 1), font=f_big, fill=(255, 255, 255))
        f_sm = load_font(12)
        d.text((4, 2), orient, font=f_sm, fill=(255, 255, 255))
        # top arrow
        d.polygon([(PHYS_W // 2 - 10, PHYS_H - 18), (PHYS_W // 2 + 10, PHYS_H - 18),
                   (PHYS_W // 2, PHYS_H - 2)], fill=(255, 255, 255))
        if orient == "direct":
            frames.append(direct_vertical(phys))
        else:
            frames.append(phys_to_fb(phys, orient))
    return frames, labels


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("input", nargs="?", help="GIF / PNG / JPG source file")
    ap.add_argument("-o", "--output", default="glanim-pack.tar.gz")
    ap.add_argument("--fit", choices=["contain", "cover", "stretch"], default="contain")
    ap.add_argument("--orientation", choices=["fb90", "fb90m", "fb270", "fb270m", "direct"],
                    default="fb90m")
    ap.add_argument("--bg", choices=["black", "white"], default="black")
    ap.add_argument("--fps", type=float, default=0, help="force fps, 0 = native delay")
    ap.add_argument("--rotate", type=int, choices=[0, 90, 180, 270], default=0)
    ap.add_argument("--still", action="store_true")
    ap.add_argument("--max-frames", type=int, default=600)
    ap.add_argument("--test-pattern", action="store_true")
    args = ap.parse_args()

    frames_meta = []
    frames_bytes = []

    if args.test_pattern:
        frames_bytes, labels = test_pattern()
        for i in range(len(frames_bytes)):
            frames_meta.append({"file": "frame_%04d.rgb565" % (i + 1),
                                "delay_ms": 2000})
        source = "test-pattern"
    else:
        if not args.input:
            sys.exit("input file required unless --test-pattern")
        if not os.path.exists(args.input):
            sys.exit("file not found: " + args.input)

        im = Image.open(args.input)
        durations = []
        count = 0
        for frame in ImageSequence.Iterator(im):
            if count >= args.max_frames:
                break
            phys = fit_image(frame, args.fit, args.bg, args.rotate)
            if args.orientation == "direct":
                frame_bytes = direct_vertical(phys)
            else:
                frame_bytes = phys_to_fb(phys, args.orientation)
            frames_bytes.append(frame_bytes)

            delay = frame.info.get("duration", 100)
            if args.fps > 0:
                delay = round(1000 / args.fps)
            durations.append(max(20, delay))

            frames_meta.append({"file": "frame_%04d.rgb565" % (count + 1),
                                "delay_ms": durations[-1]})
            count += 1
            if args.still:
                break

        source = os.path.basename(args.input)
        im.close()

    # validate every frame size
    for i, b in enumerate(frames_bytes):
        if len(b) != FB_BYTES:
            sys.exit("frame %d size %d != %d" % (i + 1, len(b), FB_BYTES))

    manifest = {
        "width": FB_W, "height": FB_H, "format": "rgb565le",
        "source": source, "orientation": args.orientation,
        "frames": frames_meta
    }

    with tarfile.open(args.output, "w:gz") as tar:
        m = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")
        info = tarfile.TarInfo("manifest.json")
        info.size = len(m)
        tar.addfile(info, io.BytesIO(m))
        for meta, data in zip(frames_meta, frames_bytes):
            info = tarfile.TarInfo(meta["file"])
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))

    print("OK: %d frames -> %s" % (len(frames_bytes), os.path.abspath(args.output)))
    print("manifest: %s" % json.dumps({k: v for k, v in manifest.items()
          if k in ("source", "orientation", "width", "height")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
