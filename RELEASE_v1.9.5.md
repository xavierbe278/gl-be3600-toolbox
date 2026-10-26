本次更新重点升级长按菜单、二级控制与触控交互。

## 长按菜单

- 菜单后台改为左右布局：左侧屏幕预览，右侧当前页按钮队列。
- 一次只显示当前 1 页，顶部页码同时切换预览和按钮列表。
- 每页 4 个按钮支持下拉选择功能、拖动排序和上下箭头排序，预览实时同步。
- 菜单语言支持：跟随 LuCI、中文、English。
- 一级菜单全部单击进入；关机、重启、WiFi 进入中央单按钮确认页，再次长按才执行。
- 菜单 15 秒无操作自动关闭，最后 5 秒顶部显示倒计时。
- 一级菜单右上角“退出菜单”可直接关闭。

## 二级控制

- 新增**猫猫（OpenClash）**二级菜单：
  - 模式：规则 / 全局 / 直连循环；
  - 优选节点；
  - 重启 OpenClash；
  - 关闭 OpenClash。
- **风扇**二级菜单提供四个模式：
  - 自动；
  - 曲线；
  - 手动；
  - 关闭。
- **亮度**二级菜单提供：减、加、当前亮度数值、退出。
- 二级菜单动作使用确认环，一级入口保持单击进入。

## 显示与触控

- 上下、左右滑动使用 fb90m 相邻页拼接，拖动过程连续显示下一页内容。
- 滑动期间暂停背景动画、状态刷新和自动轮换。
- 图片工坊保持常驻，自定义背景随时可用。
- 自定义布局可用数据固定两列、限高滚动，数值刷新不再造成按钮跳动。
- 菜单预览使用 DOM 渲染，配置修改后同步刷新。

## 下载

### 屏幕插件

- [luci-app-glanim_1.9.5-1_aarch64_cortex-a53_neon-vfpv4.ipk](https://raw.githubusercontent.com/xavierbe278/gl-be3600-toolbox/main/plugins/screen-custom/releases/luci-app-glanim_1.9.5-1_aarch64_cortex-a53_neon-vfpv4.ipk)

### 风扇插件

- [luci-app-glfanctl_1.0.7-1_aarch64_cortex-a53_neon-vfpv4.ipk](https://raw.githubusercontent.com/xavierbe278/gl-be3600-toolbox/main/plugins/fan-control/releases/luci-app-glfanctl_1.0.7-1_aarch64_cortex-a53_neon-vfpv4.ipk)

### 完整包

- [gl-be3600-toolbox-v1.9.5.zip](https://github.com/xavierbe278/gl-be3600-toolbox/archive/refs/tags/1.9.5.zip)
- [gl-be3600-toolbox-v1.9.5.tar.gz](https://github.com/xavierbe278/gl-be3600-toolbox/archive/refs/tags/1.9.5.tar.gz)

本项目为社区开源项目，不是 GL.iNet 官方固件或插件。
