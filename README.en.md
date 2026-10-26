# GL-BE3600 Toolbox

[中文](README.md) · [English](README.en.md)

Author: **@xavierbe278** · GitHub: [gl-be3600-toolbox](https://github.com/xavierbe278/gl-be3600-toolbox)

> **Open source / research project**  
> This is not official GL.iNet firmware or a plugin. Rooting and modifying the OEM panel can damage your device. Back up first and use at your own risk.

![platform](https://img.shields.io/badge/platform-GL--BE3600-blue)
![LuCI](https://img.shields.io/badge/LuCI-23.05-orange)
![arch](https://img.shields.io/badge/arch-aarch64__cortex--a53__neon--vfpv4-purple)
![license](https://img.shields.io/badge/license-MIT-green)

LuCI plugins for **GL.iNet GL-BE3600**. Feature details, screenshots and full usage are in each plugin README.

---

## Install and use

### One-click install

```sh
wget -O /tmp/glanim-install.sh \
  https://raw.githubusercontent.com/xavierbe278/gl-be3600-toolbox/main/install.sh
sh /tmp/glanim-install.sh
```

The script shows a menu first:

```text
1) Install / update Screen Custom
2) Install / update Fan Control
3) Install / update both
0) Exit
```

Nothing is downloaded until a choice is made.

### Manual install

```sh
opkg install --force-depends --force-reinstall --force-overwrite \
  /tmp/luci-app-glanim_1.9.5-1_aarch64_cortex-a53_neon-vfpv4.ipk \
  /tmp/luci-app-glfanctl_1.0.7-1_aarch64_cortex-a53_neon-vfpv4.ipk

rm -f /tmp/luci-indexcache*
/etc/init.d/uhttpd restart
```

### Entries

- LuCI: **Services → Screen Custom**
- LuCI: **Services → Fan Control**
- Screen service: `/etc/init.d/glanim`
- Fan service: `/etc/init.d/glfanctl`
- Screen status: `/tmp/glanim.status`
- Menu settings: **Advanced & maintenance → Long-press menu**

---

## Plugins

| Plugin | Version | Package | 中文 | English |
|---|---|---|---|---|
| Screen Custom | `1.9.5-1` | [IPK](plugins/screen-custom/releases/luci-app-glanim_1.9.5-1_aarch64_cortex-a53_neon-vfpv4.ipk) | [README](plugins/screen-custom/README.zh-CN.md) | [README](plugins/screen-custom/README.en.md) |
| Fan Control | `1.0.7-1` | [IPK](plugins/fan-control/releases/luci-app-glfanctl_1.0.7-1_aarch64_cortex-a53_neon-vfpv4.ipk) | [README](plugins/fan-control/README.zh-CN.md) | [README](plugins/fan-control/README.en.md) |

- Source: [`plugins/screen-custom/`](plugins/screen-custom/) · [`plugins/fan-control/`](plugins/fan-control/)
- Full package: [zip](https://github.com/xavierbe278/gl-be3600-toolbox/archive/refs/tags/1.9.5.zip) · [tar.gz](https://github.com/xavierbe278/gl-be3600-toolbox/archive/refs/tags/1.9.5.tar.gz)

---

## Supported device

Tested **only on GL.iNet GL-BE3600**.

| Item | Info |
|---|---|
| Model | GL.iNet **GL-BE3600** portable Wi-Fi 7 router |
| Device ID | `GL.iNet BE3600, Inc. IPQ5332/AP-MI04.1-C2` |
| Board | `qcom,ipq5332-ap-mi04.1-c2` |
| SoC | Qualcomm **IPQ5332**, quad-core @ 1.1 GHz |
| RAM / storage | 1 GB DDR4 / 512 MB NAND |
| Wi-Fi | Wi-Fi 7, 2.4 GHz 688 Mbps + 5 GHz 2882 Mbps |
| Ethernet | 1 × 2.5G WAN + 1 × 2.5G LAN |
| OS | OpenWrt **23.05-SNAPSHOT** / GL.iNet 4.x base |
| Kernel | 5.4.213 |
| Target | `ipq53xx/generic` |
| Package arch | `aarch64_cortex-a53_neon-vfpv4` |

> **Not compatible with GL-BE9300 / Flint 3, GL-MT3000, GL-AXT1800 or other models.**

---

## Display and touch

| Item | Info |
|---|---|
| Panel | Color bar touchscreen, ST7789-class controller |
| Resolution | **284 × 76** |
| Framebuffer | `/dev/fb0`, RGB565, 16 bpp |
| fb virtual size | `76,284` (90° from physical) |
| fb stride | 152 bytes |
| Backlight | `/sys/class/backlight/soc:backlight/brightness` |
| Touch | **Hynitron CST816X** |
| Touch node | `/dev/input/event0` |
| Touch correction | `touch_flip_x=1` |
| Polling | 20 Hz |
| Fan hwmon | `/sys/class/hwmon/hwmon0` (`pwmfan`) |

---

## Compatibility

- Packages are `aarch64_cortex-a53_neon-vfpv4` only;
- root / SSH is required;
- framebuffer, touch paths and GPIO can differ on other firmware;
- the physical Toggle switch still selects OEM / third-party screen;
- screen and fan plugins are independent.

---

## Repository layout

```text
.
├── README.md / README.en.md
├── install.sh
├── packages/
├── plugins/
│   ├── screen-custom/
│   └── fan-control/
└── build/
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

Check `/dev/fb0` and the physical Toggle switch.

### Touch direction

Backend → Screen Custom → Touch control: swap X/Y, flip X.

### Wrong architecture

GL-BE3600 requires `aarch64_cortex-a53_neon-vfpv4`.

---

## License

- Code: [MIT License](LICENSE)
- Risk notice: [DISCLAIMER.md](DISCLAIMER.md)
- Changelog: [CHANGELOG.md](CHANGELOG.md)

GL.iNet, LuCI and OpenWrt marks belong to their owners. No GL.iNet closed-source firmware is included.
