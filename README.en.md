# GL-BE3600 Toolbox

[中文](README.md) · [English](README.en.md)

Author: **@xavierbe278** · GitHub: [gl-be3600-toolbox](https://github.com/xavierbe278/gl-be3600-toolbox)

> **Open source / research & study project**  
> This is a community project, not an official GL.iNet firmware or plugin. Flashing, rooting and modifying the OEM admin panel can damage your device. Back up first and use at your own risk. Follow local laws and the GL.iNet / OpenWrt / LuCI licenses.

![platform](https://img.shields.io/badge/platform-GL--BE3600-blue)
![LuCI](https://img.shields.io/badge/LuCI-23.05-orange)
![license](https://img.shields.io/badge/license-MIT-green)

A collection of LuCI plugins / tools for **GL.iNet GL-BE3600**.  
Each plugin is an independent subfolder under `plugins/`, with source, packages, screenshots and bilingual docs.

## Plugins

| Plugin | Version | Folder | 中文 | English |
|---|---|---|---|---|
| **Screen Custom** | `1.8.2-1` | [`plugins/screen-custom/`](plugins/screen-custom/) | [README](plugins/screen-custom/README.zh-CN.md) | [README](plugins/screen-custom/README.en.md) |
| **Fan Control** | `1.0.7-1` | [`plugins/fan-control/`](plugins/fan-control/) | [README](plugins/fan-control/README.zh-CN.md) | [README](plugins/fan-control/README.en.md) |

### Screen Custom

- 284×76 ST7789 bar panel;
- GIF / still / slideshow / dashboard / custom layout;
- image / GIF / MP4 background;
- video loop playback (browser extracts frames; router only plays RGB565);
- image studio, URL image / webpage screenshot, 5×7 blocky font;
- OpenClash status page (state / rates / total traffic / connections / CPU / MEM) and service switch;
- physical switch toggles OEM / third-party screen;
- optional gl-ui: display card + overview fan expand button.

![Screen Custom](plugins/screen-custom/images/screen-page.png)

### Fan Control

- OEM PID / temperature curve / fixed PWM / stop;
- large RPM, PWM bar, five temperature zones;
- PWM / RPM / TEMP live chart;
- 10-point curve editor + current-temperature marker;
- independent save, applied immediately.

![Fan Control](plugins/fan-control/images/fan-page.png)

## Packages

| Plugin | Package |
|---|---|
| Screen Custom | [luci-app-glanim_1.8.2-1](plugins/screen-custom/releases/luci-app-glanim_1.8.2-1_aarch64_cortex-a53_neon-vfpv4.ipk) |
| Fan Control | [luci-app-glfanctl_1.0.7-1](plugins/fan-control/releases/luci-app-glfanctl_1.0.7-1_aarch64_cortex-a53_neon-vfpv4.ipk) |

Quick install:

```sh
opkg install --force-depends --force-reinstall --force-overwrite \
  /tmp/luci-app-glanim_1.8.2-1_aarch64_cortex-a53_neon-vfpv4.ipk \
  /tmp/luci-app-glfanctl_1.0.7-1_aarch64_cortex-a53_neon-vfpv4.ipk

rm -f /tmp/luci-indexcache*
/etc/init.d/uhttpd restart
```

> The gl-ui bridge ships with **Screen Custom 1.8.2**; installing only the fan plugin will not add the OEM entry.  
> Packages are unsigned; download from this repository's Releases and verify `SHA256SUMS`.

## Repository layout

```text
.
├── README.md / README.en.md
├── LICENSE
├── DISCLAIMER.md
├── CHANGELOG.md
├── SHA256SUMS
├── plugins/
│   ├── screen-custom/
│   │   ├── README.md
│   │   ├── README.zh-CN.md
│   │   ├── README.en.md
│   │   ├── images/
│   │   ├── releases/
│   │   ├── src/                   # glanim source
│   │   └── tools/glanim-convert.py
│   └── fan-control/
│       ├── README.md
│       ├── README.zh-CN.md
│       ├── README.en.md
│       ├── images/
│       ├── releases/
│       └── src/                   # glfanctl source
└── build/
    ├── build_ipk.py
    ├── verify_final_ipk.py
    ├── deploy.py
    └── tools/
```

## Adding a plugin

Keep the same structure:

```text
plugins/<plugin-name>/
├── README.md
├── README.zh-CN.md
├── README.en.md
├── images/
├── releases/
├── src/              # OpenWrt package source (CONTROL, etc, usr, www)
└── tools/            # optional PC-side tools
```

Register it in `build/build_ipk.py`:

```python
"<plugin-name>": (
    os.path.join(ROOT, "plugins", "<plugin-name>", "src"),
    os.path.join(ROOT, "plugins", "<plugin-name>", "releases"),
),
```

## Build from source

```sh
python build/build_ipk.py              # all plugins
python build/build_ipk.py screen-custom
python build/build_ipk.py fan-control
```

Outputs:

- `plugins/screen-custom/releases/`
- `plugins/fan-control/releases/`

Verify:

```sh
python build/verify_final_ipk.py
```

## Disclaimer & license

- Code: [MIT License](LICENSE)
- Risk notice: [DISCLAIMER.md](DISCLAIMER.md)
- Changelog: [CHANGELOG.md](CHANGELOG.md)

GL.iNet, the GL.iNet logo, LuCI, OpenWrt and related trademarks/firmware assets belong to their respective owners. This repository does not contain GL.iNet closed-source firmware code.

This project is mainly for **research and study**. Do not use it for illegal purposes or to harm devices/networks you do not own.
