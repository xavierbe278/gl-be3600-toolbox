# GL-BE3600 Toolbox

[中文](README.md) · [English](README.en.md)

作者：**@xavierbe278** · GitHub：[gl-be3600-toolbox](https://github.com/xavierbe278/gl-be3600-toolbox)

> **开源 / 研究学习项目**  
> 本项目以开源方式发布，主要用于个人研究、学习和自用。它不是 GL.iNet 官方固件或官方插件，不提供任何形式的担保。刷机、root、修改原厂管理面板均有风险，请先备份并自行承担后果。请遵守当地法律法规以及 GL.iNet / OpenWrt / LuCI 的许可协议。

![platform](https://img.shields.io/badge/platform-GL--BE3600-blue)
![LuCI](https://img.shields.io/badge/LuCI-23.05-orange)
![arch](https://img.shields.io/badge/arch-aarch64__cortex--a53__neon--vfpv4-purple)
![license](https://img.shields.io/badge/license-MIT-green)

面向 **GL.iNet GL-BE3600** 的 LuCI 插件 / 工具集合。  
每个插件是 `plugins/` 下的独立子目录，包含源码、IPK、截图和中英文说明。

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
| 其他接口 | USB 3.0、Type-C PD 供电、Reset、Toggle 拨动开关 |
| 系统 | OpenWrt **23.05-SNAPSHOT** / GL.iNet 4.x 基础 |
| 内核 | 5.4.213 |
| OpenWrt target | `ipq53xx/generic` |
| 安装包架构 | `aarch64_cortex-a53_neon-vfpv4` |
| 测试固件 | GL-BE3600，`OpenWrt 23.05-SNAPSHOT`，`r0-3601c2a49` |

> **不适配 GL-BE9300 / Flint 3、GL-MT3000、GL-AXT1800 等其他机型。**  
> 这些机器的屏幕、触摸、GPIO 和显示控制器不同，直接安装不会正常工作。

---

## 屏幕与触摸硬件

### 显示

| 项目 | 信息 |
|---|---|
| 屏幕类型 | 彩色长条触摸屏，ST7789 类控制器 |
| 分辨率 | **284 × 76** |
| Framebuffer | `/dev/fb0` |
| 像素格式 | RGB565，16 bpp |
| fb 虚拟尺寸 | `76,284`（与屏幕方向相差 90°） |
| fb stride | 152 字节 |
| 实际布局 | 物理 284×76，fb90m 为 76×284 转置布局 |
| 背光 | `/sys/class/backlight/soc:backlight/brightness` |
| 亮度范围 | 0–11 档（插件提供亮度二级菜单） |
| 显示服务 | `glanimd`，渲染进程 `glanimdash.py` |

插件会自行处理：

- RGB565 字节序；
- 90° 转置；
- 物理坐标到 fb 坐标映射；
- 背景、磨砂、文字、图形叠加；
- 动态帧率与触摸轮询。

### 触摸

| 项目 | 信息 |
|---|---|
| 触摸芯片 | **Hynitron CST816X** 电容触摸 |
| 设备节点 | `/dev/input/event0` |
| 设备名 | `Hynitron CST816X Touchscreen` |
| 坐标轴 | X/Y 与屏幕方向交换 |
| 方向修正 | `touch_flip_x=1` |
| 轮询频率 | 20 Hz |
| 手势 | 点击、左右滑、上下滑、长按 |
| 长按菜单 | 支持 2–3 页、每页 4 个按钮 |
| 菜单语言 | 跟随 LuCI / 中文 / English |

### 风扇

| 项目 | 信息 |
|---|---|
| hwmon | `/sys/class/hwmon/hwmon0`，名称 `pwmfan` |
| 控制方式 | PWM |
| 反馈 | RPM |
| 模式 | 原厂 PID、温度曲线、固定 PWM、停转 |
| 插件 | `luci-app-glfanctl`（独立安装包） |

---

## 兼容性说明

- 安装包是 **aarch64_cortex-a53_neon-vfpv4** 架构，不能装到 ARMv7 / MIPS 路由器；
- 需要 root / SSH 权限；
- 不同 GL.iNet 固件版本的 `/dev/fb0`、触摸节点和 GPIO 可能不同；
- 刷第三方固件前请确认 framebuffer 仍为 `76×284 RGB565`；
- 本项目不修改 GL.iNet 闭源固件本体，只替换屏幕服务的显示内容；
- 设备上的物理 Toggle 拨动开关仍可用于切换原厂 / 第三方屏幕；
- 屏幕插件与风扇插件相互独立，可只装其中一个。

---

## 插件列表

| 插件 | 版本 | 目录 | 中文 | English |
|---|---|---|---|---|
| **屏幕自定义 / Screen Custom** | `1.9.5-1` | [`plugins/screen-custom/`](plugins/screen-custom/) | [README](plugins/screen-custom/README.zh-CN.md) | [README](plugins/screen-custom/README.en.md) |
| **风扇控制 / Fan Control** | `1.0.7-1` | [`plugins/fan-control/`](plugins/fan-control/) | [README](plugins/fan-control/README.zh-CN.md) | [README](plugins/fan-control/README.en.md) |

### 屏幕自定义

- 284×76 长条屏渲染；
- 帧包 / GIF / 静态图 / 幻灯片；
- 系统面板：时钟、CPU、内存、温度、网速、运行时长、局域网 IP；
- 自定义布局：标签、实时数值、进度条、分隔线；
- 图片工坊：图片 / GIF / MP4 背景、URL 图片、网页截图；
- OpenClash 状态、节点、速率、连接数；
- 触摸手势与长按菜单：
  - 关机 / 重启 / WiFi；
  - 猫猫（OpenClash）二级菜单：模式、优选、重启、关闭；
  - 风扇二级菜单：自动、曲线、手动、关闭；
  - 亮度二级菜单：减、加、数值、退出；
- 菜单预览、按钮队列排序、菜单语言；
- 磨砂玻璃、状态透明度、背景历史；
- gl-ui 原厂面板桥接。

![屏幕自定义](plugins/screen-custom/images/screen-page.png)

![长按菜单](plugins/screen-custom/images/screen-menu.png)

### 风扇控制

- 原厂 PID / 温度曲线 / 固定 PWM / 停转；
- 大号 RPM、PWM 进度条、五路温度；
- PWM / RPM / TEMP 实时曲线；
- 10 档曲线编辑器 + 当前温度标记；
- 独立保存，保存即应用。

![风扇控制](plugins/fan-control/images/fan-page.png)

---

## 安装包

| 插件 | 安装包 |
|---|---|
| 屏幕自定义 | [luci-app-glanim_1.9.5-1](plugins/screen-custom/releases/luci-app-glanim_1.9.5-1_aarch64_cortex-a53_neon-vfpv4.ipk) |
| 风扇控制 | [luci-app-glfanctl_1.0.7-1](plugins/fan-control/releases/luci-app-glfanctl_1.0.7-1_aarch64_cortex-a53_neon-vfpv4.ipk) |

### 一键安装（自动获取最新 GitHub Release）

```sh
wget -O /tmp/glanim-install.sh \
  https://raw.githubusercontent.com/xavierbe278/gl-be3600-toolbox/main/install.sh
sh /tmp/glanim-install.sh
```

安装脚本会：

1. 查询最新 Release；
2. 优先下载对应架构 IPK；
3. Release 没有独立 IPK 时下载 `gl-be3600-toolbox-vX.Y.Z.tar.gz` 解包；
4. 安装屏幕插件和风扇插件；
5. 重启 `glanim` / `glfanctl`。

### 手动安装

```sh
opkg install --force-depends --force-reinstall --force-overwrite \
  /tmp/luci-app-glanim_1.9.5-1_aarch64_cortex-a53_neon-vfpv4.ipk \
  /tmp/luci-app-glfanctl_1.0.7-1_aarch64_cortex-a53_neon-vfpv4.ipk

rm -f /tmp/luci-indexcache*
/etc/init.d/uhttpd restart
```

> 两个插件独立安装；gl-ui 原厂面板桥接随 **屏幕插件 1.9.5** 安装。只装风扇插件不会出现原厂入口。  
> 安装包未签名，请从本仓库 Releases 下载并核对 `SHA256SUMS`。

---

## 使用入口

- LuCI：**服务 → 屏幕自定义**
- LuCI：**服务 → 风扇控制**
- 屏幕服务：`/etc/init.d/glanim`
- 风扇服务：`/etc/init.d/glfanctl`
- 状态文件：`/tmp/glanim.status`
- 菜单配置：后台 **高级与维护 → 长按菜单**

### 长按菜单

- 一级菜单全部单击进入；
- 关机 / 重启 / WiFi：单击进入单按钮确认页，再长按确认；
- 猫猫 / 风扇 / 亮度：单击进入二级菜单；
- 二级菜单动作带确认环；
- 右上角“退出菜单”可直接关闭；
- 菜单 15 秒无操作自动关闭，最后 5 秒倒计时。

---

## 仓库结构

```text
.
├── README.md / README.en.md       # 总览、硬件适配说明
├── LICENSE
├── DISCLAIMER.md
├── CHANGELOG.md
├── SHA256SUMS
├── install.sh                     # 通用最新版安装脚本
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

---

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

---

## 常见问题

### 屏幕黑屏 / 不显示

```sh
cat /tmp/glanim.status
/etc/init.d/glanim restart
```

确认：

- `/dev/fb0` 存在；
- 分辨率是 `76,284`；
- 物理 Toggle 开关没有切回原厂屏幕；
- `gl_screen` 原厂屏幕服务状态符合预期。

### 触摸方向错误

后台 **服务 → 屏幕自定义 → 触屏控制**：

- 交换 X/Y；
- 水平翻转 X；
- 查看实时触摸坐标。

### 安装报架构不匹配

GL-BE3600 必须使用：

```text
aarch64_cortex-a53_neon-vfpv4
```

### 菜单语言

后台 **高级与维护 → 长按菜单**：

- 跟随 LuCI 语言；
- 中文；
- English。

---

## 免责声明与许可证

- 代码：[MIT License](LICENSE)
- 风险说明：[DISCLAIMER.md](DISCLAIMER.md)
- 变更记录：[CHANGELOG.md](CHANGELOG.md)

GL.iNet、GL.iNet 标识、LuCI、OpenWrt 及相关商标、固件资源归各自权利人所有；本项目不包含 GL.iNet 闭源固件代码。

本项目主要面向**研究与学习**；请勿用于违反当地法律法规或损害他人设备的用途。
