# GL-BE3600 Toolbox

[中文](README.md) · [English](README.en.md)

作者：**@xavierbe278** · GitHub：[gl-be3600-toolbox](https://github.com/xavierbe278/gl-be3600-toolbox)

> **开源 / 研究学习项目**  
> 本项目以开源方式发布，主要用于个人研究、学习和自用。它不是 GL.iNet 官方固件或官方插件，不提供任何形式的担保；刷机、root、修改原厂管理面板均有风险，请先备份并自行承担后果。请遵守当地法律法规以及 GL.iNet / OpenWrt / LuCI 的许可协议。

![platform](https://img.shields.io/badge/platform-GL--BE3600-blue)
![LuCI](https://img.shields.io/badge/LuCI-23.05-orange)
![license](https://img.shields.io/badge/license-MIT-green)

面向 **GL.iNet GL-BE3600** 的 LuCI 插件 / 工具集合。  
每个插件是一个独立子目录，放在 `plugins/` 下，各自有源码、安装包、截图和中英文说明。

## 插件列表

| 插件 | 版本 | 目录 | 中文 | English |
|---|---|---|---|---|
| **屏幕自定义 / Screen Custom** | `1.8.2-1` | [`plugins/screen-custom/`](plugins/screen-custom/) | [README](plugins/screen-custom/README.zh-CN.md) | [README](plugins/screen-custom/README.en.md) |
| **风扇控制 / Fan Control** | `1.0.7-1` | [`plugins/fan-control/`](plugins/fan-control/) | [README](plugins/fan-control/README.zh-CN.md) | [README](plugins/fan-control/README.en.md) |

### 屏幕自定义

- 284×76 ST7789 长条屏；
- GIF / 静态图 / 幻灯片 / 系统面板 / 自定义面板；
- 图片 / GIF / MP4 背景；
- 视频循环播放（浏览器取帧，路由器只播放 RGB565 帧）；
- 图片工坊、URL 图片 / 网页截图、5×7 方块点阵字体；
- OpenClash 状态页（状态 / 速率 / 流量 / 连接数 / CPU / 内存）与服务开关；
- 物理拨动开关切换官方 / 第三方屏幕；
- 可选 gl-ui：显示管理卡片 + 概览风扇展开按钮。

![屏幕自定义](plugins/screen-custom/images/screen-page.png)

### 风扇控制

- 原厂 PID / 温度曲线 / 固定 PWM / 停转；
- 大号 RPM、PWM 进度条、五路温度；
- PWM / RPM / TEMP 实时曲线；
- 10 档曲线编辑器 + 当前温度标记；
- 独立保存，保存即应用。

![风扇控制](plugins/fan-control/images/fan-page.png)

## 安装包

| 插件 | 安装包 |
|---|---|
| 屏幕自定义 | [luci-app-glanim_1.8.2-1](plugins/screen-custom/releases/luci-app-glanim_1.8.2-1_aarch64_cortex-a53_neon-vfpv4.ipk) |
| 风扇控制 | [luci-app-glfanctl_1.0.7-1](plugins/fan-control/releases/luci-app-glfanctl_1.0.7-1_aarch64_cortex-a53_neon-vfpv4.ipk) |

快速安装：

```sh
opkg install --force-depends --force-reinstall --force-overwrite \
  /tmp/luci-app-glanim_1.8.2-1_aarch64_cortex-a53_neon-vfpv4.ipk \
  /tmp/luci-app-glfanctl_1.0.7-1_aarch64_cortex-a53_neon-vfpv4.ipk

rm -f /tmp/luci-indexcache*
/etc/init.d/uhttpd restart
```

> 两个插件独立安装；gl-ui 原厂面板桥接随 **屏幕插件 1.8.2** 安装。只装风扇插件不会出现原厂入口。  
> 安装包未签名，请从本仓库 Releases 下载并核对 `SHA256SUMS`。

## 仓库结构

```text
.
├── README.md / README.en.md       # 总览
├── LICENSE
├── DISCLAIMER.md
├── CHANGELOG.md
├── SHA256SUMS
├── plugins/
│   ├── screen-custom/
│   │   ├── README.md              # 中文默认
│   │   ├── README.zh-CN.md
│   │   ├── README.en.md
│   │   ├── images/
│   │   ├── releases/
│   │   ├── src/                   # glanim 源码
│   │   └── tools/glanim-convert.py
│   └── fan-control/
│       ├── README.md
│       ├── README.zh-CN.md
│       ├── README.en.md
│       ├── images/
│       ├── releases/
│       └── src/                   # glfanctl 源码
└── build/
    ├── build_ipk.py
    ├── verify_final_ipk.py
    ├── deploy.py
    └── tools/
```

## 添加新插件

建议每个插件保持同样的结构：

```text
plugins/<plugin-name>/
├── README.md
├── README.zh-CN.md
├── README.en.md
├── images/
├── releases/
├── src/              # OpenWrt 包源码（CONTROL、etc、usr、www）
└── tools/            # 可选：PC 端工具
```

然后在 `build/build_ipk.py` 的 `TARGETS` 中注册：

```python
"<plugin-name>": (
    os.path.join(ROOT, "plugins", "<plugin-name>", "src"),
    os.path.join(ROOT, "plugins", "<plugin-name>", "releases"),
),
```

## 从源码构建

```sh
python build/build_ipk.py              # 构建全部插件
python build/build_ipk.py screen-custom
python build/build_ipk.py fan-control
```

产物：

- `plugins/screen-custom/releases/`
- `plugins/fan-control/releases/`

校验：

```sh
python build/verify_final_ipk.py
```

## 免责声明与许可证

- 代码：[MIT License](LICENSE)
- 风险说明：[DISCLAIMER.md](DISCLAIMER.md)
- 变更记录：[CHANGELOG.md](CHANGELOG.md)

GL.iNet、GL.iNet 标识、LuCI、OpenWrt 及相关商标、固件资源归各自权利人所有；本项目不包含 GL.iNet 闭源固件代码。

本项目主要面向**研究与学习**；请勿用于违反当地法律法规或损害他人设备的用途。
