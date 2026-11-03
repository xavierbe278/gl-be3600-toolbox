# luci-app-fastnet（三变体插件）

FastNet 网络体检工具的 opkg 插件，面向 iStore / OpenWrt 23.05（192.168.8.1）这类 opkg 设备。

## 三个变体

| 构建命令 | 产物版本 | 内容 |
|---|---|---|
| `python build.py --version 0.7.7` | `0.7.7-1` | **原版**：单个 0.7.7 核心，页面只有状态与设置，**无内嵌、无版本切换** |
| `python build.py --version 0.7.6` | `0.7.6-1` | **原版**：单个 0.7.6 核心，同上 |
| `python build.py --version 0.7.7 --optimize` | `0.7.7-2` | **优化版**：0.7.6 + 0.7.7 双核心、内嵌页面、一键切换（同一时间只跑一个） |

默认（不带 `--optimize`）就是原版直接安装。

产物输出到 `deliverables/luci-app-fastnet_<版本>_aarch64_cortex-a53_neon-vfpv4.ipk`。

## 目录结构

```
fastnet/
├── build.py                 构建脚本（自包含，不依赖 ../build_ipk.py）
├── bin/
│   ├── FastNet-0.7.6        官方 0.7.6（sha256 a4a56d2a…2415c7）
│   └── FastNet-0.7.7        sha256 f9860a37…db4119
├── common/                  三个变体共用
│   ├── CONTROL/             conffiles / postinst / prerm / postrm
│   └── etc/
│       ├── config/fastnet   version 由构建时注入
│       └── init.d/fastnet   按 uci version 选核心，带版本回退
├── plain/                   原版变体的 LuCI 文件（状态 + 设置）
└── plus/                    优化版变体的 LuCI 文件（状态 + 设置 + 切换 + 内嵌）
```

## 安装与验证

```sh
# 设备上
opkg install /tmp/luci-app-fastnet_0.7.7-1_aarch64_cortex-a53_neon-vfpv4.ipk
# 从原版升到优化版
opkg install /tmp/luci-app-fastnet_0.7.7-2_aarch64_cortex-a53_neon-vfpv4.ipk
```

- 三个变体同名 `luci-app-fastnet`，互相替换；`0.7.7-1 → 0.7.7-2` 是正常升级，降级需 `--force-downgrade`。
- 原版包会在 `/usr/share/fastnet/version.txt` 写入实际核心版本，postinst 据此校正 `/etc/config/fastnet` 的 `version`（避免 conffiles 保留旧值导致 UI 显示与实际不符）。
- 老版本共用的 `/etc/config/fastnet` 属于 conffiles：若与包内默认值不同，opkg 会把新文件放到 `/etc/config/fastnet-opkg`，原配置保留。

## 已知问题：切换/重装后可能延迟约 1 分钟才起来

FastNet 绑定端口时没有设置 `SO_REUSEADDR`。若重启瞬间还有旧连接处于 TIME_WAIT（约 60 秒），新实例会 `bind: address already in use` 直接退出。
init 脚本已把 procd respawn 放宽为 `3600 5 30`（约 150 秒），服务会自己等到端口释放后拉起，期间页面显示“已停止”属正常现象。

## 卸载

```sh
opkg remove luci-app-fastnet
```
prerm 会停服务并 disable，postrm 清 LuCI 缓存。
