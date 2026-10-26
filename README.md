# GL-BE3600 Toolbox

[中文](README.md) · [English](README.en.md)

作者：**@xavierbe278** · GitHub：[gl-be3600-toolbox](https://github.com/xavierbe278/gl-be3600-toolbox)

> **开源 / 研究学习项目**  
> 本项目不是 GL.iNet 官方固件或插件。刷机、root、修改原厂管理面板均有风险，请先备份并自行承担后果。

![platform](https://img.shields.io/badge/platform-GL--BE3600-blue)
![LuCI](https://img.shields.io/badge/LuCI-23.05-orange)
![arch](https://img.shields.io/badge/arch-aarch64__cortex--a53__neon--vfpv4-purple)
![license](https://img.shields.io/badge/license-MIT-green)

面向 **GL.iNet GL-BE3600** 的 LuCI 插件集合。各插件的完整功能说明、截图和详细用法请查看对应插件目录。

---

## 安装与使用

### 一键安装

```sh
wget -O /tmp/glanim-install.sh \
  https://raw.githubusercontent.com/xavierbe278/gl-be3600-toolbox/main/install.sh
sh /tmp/glanim-install.sh
```

运行后先显示菜单：

```text
1) 安装 / 更新 屏幕自定义
2) 安装 / 更新 风扇控制
3) 安装 / 更新 两个插件
0) 退出
```

选择后才开始查询 Release 和下载。

### 手动安装

```sh
opkg install --force-depends --force-reinstall --force-overwrite \
  /tmp/luci-app-glanim_1.9.5-1_aarch64_cortex-a53_neon-vfpv4.ipk \
  /tmp/luci-app-glfanctl_1.0.7-1_aarch64_cortex-a53_neon-vfpv4.ipk

rm -f /tmp/luci-indexcache*
/etc/init.d/uhttpd restart
```

### 使用入口

- LuCI：**服务 → 屏幕自定义**
- LuCI：**服务 → 风扇控制**
- 屏幕服务：`/etc/init.d/glanim`
- 风扇服务：`/etc/init.d/glfanctl`
- 屏幕状态：`/tmp/glanim.status`
- 长按菜单配置：**高级与维护 → 长按菜单**

---

## 插件

| 插件 | 版本 | 安装包 | 中文说明 | English |
|---|---|---|---|---|
| 屏幕自定义 / Screen Custom | `1.9.5-1` | [IPK](plugins/screen-custom/releases/luci-app-glanim_1.9.5-1_aarch64_cortex-a53_neon-vfpv4.ipk) | [README](plugins/screen-custom/README.zh-CN.md) | [README](plugins/screen-custom/README.en.md) |
| 风扇控制 / Fan Control | `1.0.7-1` | [IPK](plugins/fan-control/releases/luci-app-glfanctl_1.0.7-1_aarch64_cortex-a53_neon-vfpv4.ipk) | [README](plugins/fan-control/README.zh-CN.md) | [README](plugins/fan-control/README.en.md) |

- 屏幕插件源码与 PC 工具：[`plugins/screen-custom/`](plugins/screen-custom/)
- 风扇插件源码：[`plugins/fan-control/`](plugins/fan-control/)
- 完整包：[zip](https://github.com/xavierbe278/gl-be3600-toolbox/archive/refs/tags/1.9.5.zip) · [tar.gz](https://github.com/xavierbe278/gl-be3600-toolbox/archive/refs/tags/1.9.5.tar.gz)

---

## 适配设备

本项目**只针对 GL.iNet GL-BE3600** 开发和测试。

| 项目 | 信息 |
|---|---|
| 设备型号 | GL.iNet **GL-BE3600**（便携式 Wi-Fi 7 路由器） |
| 设备标识 | `GL.iNet BE3600, Inc. IPQ5332/AP-MI04.1-C2` |
| 主板标识 | `qcom,ipq5332-ap-mi04.1-c2` |
| SoC | Qualcomm **IPQ5332**，四核 @ 1.1 GHz |
| 内存 | 1 GB DDR4（Linux 可见约 908 MB） |
| 存储 | 512 MB NAND Flash |
| 无线 | Wi-Fi 7，2.4 GHz 688 Mbps + 5 GHz 2882 Mbps |
| 网口 | 1 × 2.5G WAN + 1 × 2.5G LAN |
| 其他接口 | USB 3.0、Type-C PD、Reset、Toggle 拨动开关 |
| 系统 | OpenWrt **23.05-SNAPSHOT** / GL.iNet 4.x 基础 |
| 内核 | 5.4.213 |
| OpenWrt target | `ipq53xx/generic` |
| 安装包架构 | `aarch64_cortex-a53_neon-vfpv4` |
| 测试固件 | `OpenWrt 23.05-SNAPSHOT`，`r0-3601c2a49` |

> **不适配 GL-BE9300 / Flint 3、GL-MT3000、GL-AXT1800 等其他机型。**

---

## 屏幕与触摸

### 显示

| 项目 | 信息 |
|---|---|
| 屏幕 | 彩色长条触摸屏，ST7789 类控制器 |
| 分辨率 | **284 × 76** |
| Framebuffer | `/dev/fb0`，RGB565，16 bpp |
| fb 虚拟尺寸 | `76,284`（与屏幕方向相差 90°） |
| fb stride | 152 字节 |
| 背光 | `/sys/class/backlight/soc:backlight/brightness` |
| 亮度 | 0–11 档 |
| 显示服务 | `glanimd` / `glanimdash.py` |

### 触摸

| 项目 | 信息 |
|---|---|
| 触摸芯片 | **Hynitron CST816X** 电容触摸 |
| 设备节点 | `/dev/input/event0` |
| 设备名 | `Hynitron CST816X Touchscreen` |
| 坐标轴 | X/Y 与屏幕方向交换 |
| 方向修正 | `touch_flip_x=1` |
| 轮询频率 | 20 Hz |

### 风扇

| 项目 | 信息 |
|---|---|
| hwmon | `/sys/class/hwmon/hwmon0`，名称 `pwmfan` |
| 控制 | PWM，RPM 反馈 |
| 插件 | `luci-app-glfanctl` |

---

## 兼容性

- 安装包是 `aarch64_cortex-a53_neon-vfpv4` 架构，不能装到其他架构；
- 需要 root / SSH 权限；
- 不同固件版本的 fb、触摸节点和 GPIO 可能不同；
- 物理 Toggle 开关仍可用于切换原厂 / 第三方屏幕；
- 屏幕插件与风扇插件相互独立，可只装其中一个。

---

## 仓库结构

```text
.
├── README.md / README.en.md
├── install.sh
├── packages/                 # zip / tar.gz 完整包
├── plugins/
│   ├── screen-custom/
│   │   ├── src/
│   │   ├── releases/
│   │   ├── images/
│   │   └── README*.md
│   └── fan-control/
│       ├── src/
│       ├── releases/
│       ├── images/
│       └── README*.md
└── build/
```

---

## 从源码构建

```sh
python build/build_ipk.py
python build/build_ipk.py screen-custom
python build/build_ipk.py fan-control
python build/verify_final_ipk.py
```

产物位于：

- `plugins/screen-custom/releases/`
- `plugins/fan-control/releases/`

---

## 常见问题

### 屏幕不显示

```sh
cat /tmp/glanim.status
/etc/init.d/glanim restart
```

确认 `/dev/fb0` 存在、Toggle 开关位置正确。

### 触摸方向错误

后台 **屏幕自定义 → 触屏控制**：交换 X/Y、水平翻转 X。

### 安装报架构不匹配

GL-BE3600 必须使用 `aarch64_cortex-a53_neon-vfpv4`。

---

## 免责声明与许可证

- 代码：[MIT License](LICENSE)
- 风险说明：[DISCLAIMER.md](DISCLAIMER.md)
- 变更记录：[CHANGELOG.md](CHANGELOG.md)

GL.iNet、LuCI、OpenWrt 及相关商标归各自权利人所有；本项目不包含 GL.iNet 闭源固件代码。
