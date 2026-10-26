# Screen Custom / 屏幕自定义

[中文](README.zh-CN.md) · [English](README.en.md) · [Back to overview](../../README.md)

Author: **@xavierbe278** · GitHub: [gl-be3600-toolbox](https://github.com/xavierbe278/gl-be3600-toolbox)

> **Open source / research & study project**  
> This is a community project, not an official GL.iNet firmware or plugin. Flashing, rooting and modifying the OEM admin panel can damage your device. Back up first and use at your own risk. Follow local laws and the GL.iNet / OpenWrt / LuCI licenses.

![platform](https://img.shields.io/badge/platform-GL--BE3600-blue)
![LuCI](https://img.shields.io/badge/LuCI-23.05-orange)
![license](https://img.shields.io/badge/license-MIT-green)

`luci-app-glanim` **1.8.2-1** — frame packs / GIF / images, live dashboard, OpenClash status/details/node, visual custom layout for the GL-BE3600 284×76 ST7789 bar panel, with an optional GL.iNet gl-ui bridge.

---

### OpenClash and physical switch

- OpenClash status mode: ON/OFF, mode, live RX/TX, total traffic, connections, CPU/MEM;
- three OpenClash pages: status / details / node (country flag, Chinese country name, node type, latency, rate, UDP, connections);
- on-screen ON/OFF touch button for the OpenClash service;
- configurable 2–30 s page rotation; preview tabs lock the page and disable rotation.
- physical switch: ON = glanim, OFF = OEM `gl_screen` (hook in `/etc/rc.button/switch`);
- custom background preview now loads the real background frame, so it is visible and not stretched.

## Screenshots

Plugin page:

![Plugin page](images/screen-page.png)

Panel pages:

![OpenClash status](images/screen-clash-status.png)
![OpenClash details](images/screen-clash-info.png)
![OpenClash node](images/screen-clash-node.png)
![Clock](images/screen-dashboard-clock.png)
![Status](images/screen-dashboard-status.png)
![Custom panel](images/screen-custom.png)

---

## Features

- **GIF loop** — decoded in the browser and uploaded as RGB565 frames; up to **300 frames** (automatic downscale under a pixel budget);
- **Video loop** — MP4(H.264) / WebM is sampled in the browser; up to **300 frames / 60 s**, played back by selecting the GIF loop mode;
- **Still image** — JPG / PNG / GIF / BMP, Cover / Contain / Stretch, 1–3× zoom;
- **Slideshow** — frames play once and stop on the last frame;
- **Dashboard** — clock, CPU, memory, temperature, network, uptime, IP; touch paging;
- **Custom panel** — labels, values, bars, rectangles and separators on a 284×76 canvas;
- **Background media** — solid color / image / GIF / MP4 behind the layout;
- **Webpage / image URL** — direct image or GIF URL; webpage links can be imported via a WordPress mShots screenshot;
- **Background trim** — choose a start frame and frame count (default 300), with an approximate mm:ss range;
- **Recent backgrounds** — keeps the last three uploads for one-click restore under playback mode 1;
- **Live touch drag** — the page follows the finger; release to snap back or switch pages;
- **Animated preview** — multi-frame backgrounds cycle at the configured background fps;
- 5×7 blocky bitmap font with high-contrast colors;

- Independent save, live preview, image studio, atomic frame-pack validation;
- Optional GL.iNet gl-ui integration (display card + fan expand button);
- Restores the OEM `gl_screen` when disabled or removed.

---

## Compatibility

Tested on:

- GL.iNet GL-BE3600 (IPQ5332)
- GL.iNet 4.10.1 (OpenWrt 23.05-SNAPSHOT)
- LuCI Master / Argon
- 284×76 ST7789, `/dev/fb0`, RGB565 little-endian, `fb90m`
- Optional: gl-ui v4.10.1 + `glinjector 3.0.5`

Other firmware versions or panel batches may need adjustments.

---

## Install

```sh
scp releases/luci-app-glanim_1.8.2-1_aarch64_cortex-a53_neon-vfpv4.ipk root@192.168.8.1:/tmp/

ssh root@192.168.8.1
opkg install --force-depends --force-reinstall --force-overwrite \
  /tmp/luci-app-glanim_1.8.2-1_aarch64_cortex-a53_neon-vfpv4.ipk

rm -f /tmp/luci-indexcache*
/etc/init.d/uhttpd restart
```

Open:

```text
http(s)://192.168.8.1/cgi-bin/luci/admin/services/glanim/main
```

> The packages are unsigned, hence `--force-depends` / `--force-overwrite`.  
> Back up `/etc/config/glanim` and `/usr/share/glanim/frames/` before upgrading.

### Restore OEM

- Screen page: **Restore OEM screen**;
- or `opkg remove luci-app-glanim`.

`prerm` stops the plugin, restores `gl_screen`, and removes the gl-ui bridge hooks.

---

## Usage

### Modes

| Mode | Description |
|---|---|
| `gif` | Loop a GIF / video frame pack using manifest delays |
| `still` | Hold one frame |
| `slideshow` | Play once, stop on the last frame |
| `dashboard` | Clock + CPU / memory / temperature / network pages |
| `custom` | User-designed layout |

### Custom panel data sources

| `source` | Value | Example |
|---|---|---|
| `cpu` | CPU usage % | `19` |
| `mem` | Memory usage % | `72` |
| `temp` | SoC max temperature °C | `63` |
| `fan_rpm` | Fan RPM | `1228` |
| `fan_pwm` | Fan PWM % | `14` |
| `rx` / `tx` | Current down/up rate | `5KB` / `1.2MB` |
| `net` | Combined speed text | `DL 5KB UL 2KB` |
| `clock` | 24-hour clock | `21:54:02` |
| `hm` | Hour:minute | `21:54` |
| `date` | Month/day | `10/25` |
| `weekday` | Weekday abbreviation | `SAT` |
| `uptime` | Uptime | `7d 00:43` |
| `ip` / `lan_ip` | LAN IPv4 | `192.168.8.1` |
| `wan_ip` | WAN IPv4 | `192.168.0.2` |
| `iface` | WAN interface | `eth0` |
| `hostname` | Hostname | `GL-BE3600` |

Element types: `text`, `value`, `bar`, `rect`, `line`. Bars support `cpu`, `mem`, `temp`, `fan_pwm`.

> The panel uses an embedded 5×7 bitmap font: uppercase English, digits and symbols only; Chinese is not rendered.  
> The layout is stored as JSON in `glanim.globals.custom_layout`, max 40 elements.

### Background media

1. Load an image / GIF / MP4 in the image studio;
2. Click **Set as custom background**;
3. Frames are stored in `/usr/share/glanim/custom_bg/` and drawn under the layout;
4. Click **Clear background** to return to a solid color.

Background animation defaults to **8 fps**; adjust in UCI:

```sh
uci set glanim.globals.custom_bg_fps='8'   # 1..15
uci commit glanim
/etc/init.d/glanim restart
```

> 8 fps measured at roughly 15% of one CPU core; use 4–6 fps to reduce load.

### Video

- MP4(H.264) / WebM;
- Browser-side frame extraction, up to **300 frames / 60 s**, sampled at 10 fps;
- Select **GIF loop** mode to play it;
- Audio is ignored;
- H.265/HEVC must be converted to H.264 MP4 or WebM first.

### Frame limits

| Channel | Limit | Notes |
|---|---|---|
| Browser GIF / video / background | **300 frames** | Source long side ≤480 px; adaptive downscale under a 24 MP budget |
| PC pack / manual upload | **600 frames** | 43,168 bytes per frame; ~25.9 MB for 600 frames |
| Upload size | 32 MB | Controller and tar validation |
| Custom layout elements | 40 | Clamped by controller and daemon |

### Webpage / image URL

- Direct image/GIF URL: downloaded by the router, decoded by the browser, cropped and applied;
- Webpage URL: enable **web screenshot** to generate a 568×152 image via WordPress mShots;
- Webpage screenshots are a **one-shot import**.

> **Full HTML rendering is not implemented.** Running a browser engine on the router would need hundreds of MB of storage/RAM and significant CPU, which is not suitable for an always-on screen service. If the page can expose a monitoring image (PNG/JPEG), use that image URL as a background or frame pack instead.

---

## GL.iNet gl-ui integration

On install, `postinst`:

1. Appends the bridge script to `/www/gl_home.html`;
2. Appends a loader to `/etc/glinjector/core.js` if glinjector is installed.

Result:

- **System → Display** gets a "Screen Custom" card at the bottom;
- **System → Overview** gets a square expand button in the CPU card header (fan control entry);
- Clicking opens the full LuCI plugin inside a same-page window;
- Uninstall/upgrade removes the hooks.

> This is a DOM enhancement for the closed-source gl-ui, not an official extension API. A future GL.iNet UI change may require selector updates.  
> If the entry disappears after upgrading `glinjector`, reinstall this plugin.  
> If the popup shows the LuCI login page, log in to LuCI once.

---

## Build from source

From the repository root:

```sh
python build/build_ipk.py screen-custom
```

Output: `plugins/screen-custom/releases/luci-app-glanim_1.8.2-1_....ipk`

Layout:

```text
plugins/screen-custom/
├── README.md
├── README.zh-CN.md
├── README.en.md
├── images/
├── releases/
├── src/                 # glanim package source
└── tools/glanim-convert.py
```

PC-side GIF → frame pack:

```sh
python plugins/screen-custom/tools/glanim-convert.py input.gif -o my-pack.tar.gz --max-frames 600
```

---

## License & disclaimer

- Code: [MIT](../../LICENSE)
- Risk notice: [DISCLAIMER.md](../../DISCLAIMER.md)
- Changelog: [CHANGELOG.md](../../CHANGELOG.md)

GL.iNet, LuCI, OpenWrt and their trademarks/firmware assets belong to their respective owners. This repository does not contain GL.iNet closed-source firmware code.
