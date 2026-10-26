# GL-BE3600 Toolbox

[中文](README.md) · [English](README.en.md)

Author: **@xavierbe278** · GitHub: [gl-be3600-toolbox](https://github.com/xavierbe278/gl-be3600-toolbox)

> **Open source / research project**  
> This is a community project, not official GL.iNet firmware or a plugin. Rooting, flashing and modifying the OEM admin panel can damage your device. Back up first and use at your own risk. Follow local laws and the GL.iNet / OpenWrt / LuCI licenses.

![platform](https://img.shields.io/badge/platform-GL--BE3600-blue)
![LuCI](https://img.shields.io/badge/LuCI-23.05-orange)
![arch](https://img.shields.io/badge/arch-aarch64__cortex--a53__neon--vfpv4-purple)
![license](https://img.shields.io/badge/license-MIT-green)

LuCI plugins / tools for **GL.iNet GL-BE3600** only.

---

## Supported device

This project is developed and tested **only on GL.iNet GL-BE3600**.

| Item | Info |
|---|---|
| Model | GL.iNet **GL-BE3600** portable Wi-Fi 7 router |
| Device ID | `GL.iNet BE3600, Inc. IPQ5332/AP-MI04.1-C2` |
| Board | `qcom,ipq5332-ap-mi04.1-c2` |
| SoC | Qualcomm **IPQ5332**, quad-core @ 1.1 GHz |
| RAM | 1 GB DDR4 (~908 MB visible to Linux) |
| Storage | 512 MB NAND Flash |
| Wi-Fi | Wi-Fi 7, 2.4 GHz 688 Mbps + 5 GHz 2882 Mbps |
| Ethernet | 1 × 2.5G WAN + 1 × 2.5G LAN |
| Other | USB 3.0, USB-C PD, Reset, Toggle switch |
| OS | OpenWrt **23.05-SNAPSHOT** / GL.iNet 4.x base |
| Kernel | 5.4.213 |
| Target | `ipq53xx/generic` |
| Package arch | `aarch64_cortex-a53_neon-vfpv4` |
| Tested build | `OpenWrt 23.05-SNAPSHOT`, `r0-3601c2a49` |

> **Not compatible with GL-BE9300 / Flint 3, GL-MT3000, GL-AXT1800 or other models.**  
> Their display, touch, GPIO and panel controller are different.

---

## Display, touch and fan

### Display

| Item | Info |
|---|---|
| Panel | Color bar touchscreen, ST7789-class controller |
| Resolution | **284 × 76** |
| Framebuffer | `/dev/fb0` |
| Pixel format | RGB565, 16 bpp |
| fb virtual size | `76,284` (90° from physical) |
| fb stride | 152 bytes |
| Layout | physical 284×76, fb90m 76×284 transposed |
| Backlight | `/sys/class/backlight/soc:backlight/brightness` |
| Brightness | 0–11 |
| Daemon | `glanimd` / `glanimdash.py` |

The plugin handles RGB565 byte order, 90° transpose, physical-to-fb mapping, background/frost/text overlay and the fast path.

### Touch

| Item | Info |
|---|---|
| Controller | **Hynitron CST816X** capacitive touch |
| Node | `/dev/input/event0` |
| Name | `Hynitron CST816X Touchscreen` |
| Axes | X/Y swapped relative to the panel |
| Correction | `touch_flip_x=1` |
| Polling | 20 Hz |
| Gestures | tap, horizontal swipe, vertical swipe, long press |
| Menu | 2–3 pages, 4 buttons per page |
| Language | Follow LuCI / Chinese / English |

### Fan

| Item | Info |
|---|---|
| hwmon | `/sys/class/hwmon/hwmon0`, `pwmfan` |
| Control | PWM |
| Feedback | RPM |
| Modes | OEM PID, curve, fixed PWM, stop |
| Plugin | `luci-app-glfanctl` (separate package) |

---

## Compatibility

- Packages are **aarch64_cortex-a53_neon-vfpv4** only;
- root / SSH is required;
- framebuffer and touch paths may differ on other firmware;
- verify `/dev/fb0` is `76×284 RGB565` before flashing third-party firmware;
- the physical Toggle switch can still switch between OEM and third-party screen;
- screen and fan plugins are independent.

---

## Plugins

| Plugin | Version | Folder | 中文 | English |
|---|---|---|---|---|
| **Screen Custom** | `1.9.5-1` | [`plugins/screen-custom/`](plugins/screen-custom/) | [README](plugins/screen-custom/README.zh-CN.md) | [README](plugins/screen-custom/README.en.md) |
| **Fan Control** | `1.0.7-1` | [`plugins/fan-control/`](plugins/fan-control/) | [README](plugins/fan-control/README.zh-CN.md) | [README](plugins/fan-control/README.en.md) |

### Screen Custom

- 284×76 bar panel;
- frame packs / GIF / still / slideshow;
- dashboard: clock, CPU, memory, temperature, network, uptime, LAN IP;
- custom layout: labels, live values, bars, separators;
- image studio: image / GIF / MP4 backgrounds, URL image, webpage screenshot;
- OpenClash status, node, rates, connections;
- touch gestures and long-press menu:
  - power off / reboot / Wi-Fi;
  - Cat (OpenClash) submenu: mode, best node, restart, stop;
  - fan submenu: auto, curve, manual, stop;
  - brightness submenu: −, +, value, exit;
- menu preview, button queue reorder, menu language;
- frosted glass, content opacity, background history;
- gl-ui OEM panel bridge.

![Screen Custom](plugins/screen-custom/images/screen-page.png)

![Long-press menu](plugins/screen-custom/images/screen-menu.png)

### Fan Control

- OEM PID / temperature curve / fixed PWM / stop;
- large RPM, PWM bar, five temperature zones;
- PWM / RPM / TEMP live chart;
- 10-point curve editor + current-temperature marker;
- independent save, applied immediately.

![Fan Control](plugins/fan-control/images/fan-page.png)

---

## Packages

| Plugin | Package |
|---|---|
| Screen Custom | [luci-app-glanim_1.9.5-1](plugins/screen-custom/releases/luci-app-glanim_1.9.5-1_aarch64_cortex-a53_neon-vfpv4.ipk) |
| Fan Control | [luci-app-glfanctl_1.0.7-1](plugins/fan-control/releases/luci-app-glfanctl_1.0.7-1_aarch64_cortex-a53_neon-vfpv4.ipk) |

### One-click install (latest GitHub Release)

```sh
wget -O /tmp/glanim-install.sh \
  https://raw.githubusercontent.com/xavierbe278/gl-be3600-toolbox/main/install.sh
sh /tmp/glanim-install.sh
```

The script queries the latest release, prefers standalone IPKs, falls back to the tar.gz bundle, installs both plugins and restarts the services.

### Manual install

```sh
opkg install --force-depends --force-reinstall --force-overwrite \
  /tmp/luci-app-glanim_1.9.5-1_aarch64_cortex-a53_neon-vfpv4.ipk \
  /tmp/luci-app-glfanctl_1.0.7-1_aarch64_cortex-a53_neon-vfpv4.ipk

rm -f /tmp/luci-indexcache*
/etc/init.d/uhttpd restart
```

> Packages are unsigned. Download from this repository's Releases and verify `SHA256SUMS`.

---

## Usage

- LuCI: **Services → Screen Custom**
- LuCI: **Services → Fan Control**
- Screen service: `/etc/init.d/glanim`
- Fan service: `/etc/init.d/glfanctl`
- Status: `/tmp/glanim.status`
- Menu settings: **Advanced & maintenance → Long-press menu**

### Long-press menu

- all first-level buttons are single tap;
- power off / reboot / Wi-Fi open a single-button confirmation page, then hold again;
- Cat / fan / brightness open their submenus;
- submenu actions use a hold-to-confirm ring;
- top-right "Exit menu" closes the menu;
- menu auto-closes after 15 s idle, with a 5 s countdown.

---

## Repository layout

```text
.
├── README.md / README.en.md
├── LICENSE
├── DISCLAIMER.md
├── CHANGELOG.md
├── SHA256SUMS
├── install.sh
├── plugins/
│   ├── screen-custom/
│   │   ├── README.md
│   │   ├── README.zh-CN.md
│   │   ├── README.en.md
│   │   ├── images/
│   │   ├── releases/
│   │   ├── src/
│   │   └── tools/glanim-convert.py
│   └── fan-control/
│       ├── README.md
│       ├── README.zh-CN.md
│       ├── README.en.md
│       ├── images/
│       ├── releases/
│       └── src/
└── build/
    ├── build_ipk.py
    ├── verify_final_ipk.py
    ├── deploy.py
    └── tools/
```

---

## Build

```sh
python build/build_ipk.py
python build/build_ipk.py screen-custom
python build/build_ipk.py fan-control
python build/verify_final_ipk.py
```

---

## Troubleshooting

### Blank screen

```sh
cat /tmp/glanim.status
/etc/init.d/glanim restart
```

Check `/dev/fb0`, `76,284` virtual size and the physical Toggle switch.

### Touch direction

Backend → Screen Custom → Touch control: swap X/Y and flip X.

### Wrong architecture

GL-BE3600 requires `aarch64_cortex-a53_neon-vfpv4`.

### Menu language

Advanced & maintenance → Long-press menu: Follow LuCI / Chinese / English.

---

## License

- Code: [MIT License](LICENSE)
- Risk notice: [DISCLAIMER.md](DISCLAIMER.md)
- Changelog: [CHANGELOG.md](CHANGELOG.md)

GL.iNet, LuCI, OpenWrt and related marks belong to their owners. This repository does not include GL.iNet closed-source firmware.
