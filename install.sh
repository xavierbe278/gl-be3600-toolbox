#!/bin/sh
# GL-BE3600 Toolbox main installer
# Interactive menu. Downloads only the selected plugin IPK from its releases/
# directory. No full-repository archive.

set -u

REPO="xavierbe278/gl-be3600-toolbox"
BRANCH="main"
API_BASE="https://api.github.com/repos/${REPO}/contents"
RAW_BASE="https://raw.githubusercontent.com/${REPO}/${BRANCH}"
ARCH="aarch64_cortex-a53_neon-vfpv4"
TMP="/tmp/glanim-install"

GLANIM="luci-app-glanim"
FAN="luci-app-glfanctl"
NEED_G=0
NEED_F=0
MODE="install"

say() { echo "[glanim] $*"; }
die() { echo "[glanim] $*" >&2; exit 1; }

show_menu() {
    cat <<'EOF'

========================================
      GL-BE3600 Toolbox 安装器
       Made By @XavierBe278
========================================
  1) 安装 / 更新 屏幕自定义
  2) 安装 / 更新 风扇控制
  3) 安装 / 更新 两个插件
  4) 只检查更新
  0) 退出
========================================
EOF
}

case "${1:-}" in
  --check) MODE="check" ;;
  --force) MODE="force" ;;
  --help|-h)
    echo "用法: $0 [--check|--force]"
    echo "  默认显示交互菜单"
    echo "  --check  只检查两个插件更新"
    echo "  --force  交互选择后强制重装"
    exit 0
    ;;
esac

if [ "$MODE" = "check" ]; then
    NEED_G=1
    NEED_F=1
else
    while :; do
        show_menu
        printf "请选择 [0-4]: "
        if [ -r /dev/tty ]; then
            IFS= read -r choice </dev/tty || exit 0
        else
            IFS= read -r choice || exit 0
        fi
        case "$choice" in
            0|q|Q) say "已退出。"; exit 0 ;;
            1) NEED_G=1; break ;;
            2) NEED_F=1; break ;;
            3) NEED_G=1; NEED_F=1; break ;;
            4) NEED_G=1; NEED_F=1; MODE="check"; break ;;
            *) echo "无效选择，请输入 0、1、2、3 或 4。" ;;
        esac
    done
fi

[ "$(id -u)" = "0" ] || die "请使用 root 运行。"
command -v opkg >/dev/null 2>&1 || die "未找到 opkg；这不是 OpenWrt / GL.iNet 系统。"
[ "$(uname -m)" = "aarch64" ] || die "此安装器仅适用于 aarch64。"

fetch() {
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL --max-time 30 -H "User-Agent: glanim-installer" "$1"
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- --timeout=30 --header="User-Agent: glanim-installer" "$1"
    else
        return 1
    fi
}

download() {
    if command -v curl >/dev/null 2>&1; then
        curl -fL --max-time 180 -o "$2" "$1"
    elif command -v wget >/dev/null 2>&1; then
        wget -q -O "$2" --timeout=180 "$1"
    else
        return 1
    fi
}

installed_version() {
    opkg status "$1" 2>/dev/null | awk -F': ' '/^Version:/{print $2; exit}'
}

version_gt() {
    opkg compare-versions "$1" gt "$2" >/dev/null 2>&1
}

latest_ipk_name() {
    plugin="$1"
    pkg="$2"
    api="${API_BASE}/plugins/${plugin}/releases?ref=${BRANCH}"
    json="$TMP/${plugin}.json"
    fetch "$api" > "$json" 2>/dev/null || return 1
    grep -q '"name"' "$json" 2>/dev/null || return 1

    names=$(sed -n 's/.*"name":[[:space:]]*"\([^"]*\.ipk\)".*/\1/p' "$json" \
        | grep -E "^${pkg}_[^_]+_${ARCH}\.ipk$")
    latest=""
    latest_ver=""
    for name in $names; do
        ver=$(printf '%s\n' "$name" | sed -n "s/^${pkg}_\([^_]*\)_.*/\1/p")
        [ -n "$ver" ] || continue
        if [ -z "$latest" ] || version_gt "$ver" "$latest_ver"; then
            latest="$name"
            latest_ver="$ver"
        fi
    done
    printf '%s\n' "$latest"
}

handle_plugin() {
    plugin="$1"
    pkg="$2"
    say "检查 $pkg ..."

    latest=$(latest_ipk_name "$plugin" "$pkg")
    if [ -z "$latest" ]; then
        say "$pkg: releases/ 下没有找到 $ARCH IPK"
        return 1
    fi

    latest_ver=$(printf '%s\n' "$latest" | sed -n "s/^${pkg}_\([^_]*\)_.*/\1/p")
    current_ver=$(installed_version "$pkg")
    say "$pkg: 已安装 ${current_ver:-无}，releases/ 最新 $latest_ver"

    if [ "$MODE" = "check" ]; then
        if [ -n "$current_ver" ] && ! version_gt "$latest_ver" "$current_ver"; then
            say "$pkg: 无更新"
        else
            say "$pkg: 可更新到 $latest_ver"
        fi
        return 0
    fi

    if [ "$MODE" != "force" ] && [ -n "$current_ver" ] && ! version_gt "$latest_ver" "$current_ver"; then
        say "$pkg: 已是最新，跳过"
        return 0
    fi

    url="${RAW_BASE}/plugins/${plugin}/releases/${latest}"
    ipk="$TMP/$latest"
    say "$pkg: 下载 $latest"
    download "$url" "$ipk" || { say "$pkg: 下载失败"; return 1; }

    size=$(wc -c < "$ipk" 2>/dev/null | tr -d ' ')
    [ "${size:-0}" -gt 1024 ] || { say "$pkg: 下载文件无效"; rm -f "$ipk"; return 1; }

    say "$pkg: 安装 $latest_ver"
    opkg install --force-depends --force-reinstall --force-overwrite "$ipk" \
        || { say "$pkg: 安装失败"; return 1; }
    say "$pkg: 安装完成"
    return 0
}

rm -rf "$TMP"
mkdir -p "$TMP" || die "无法创建 $TMP"

fail=0
if [ "$NEED_G" = "1" ]; then
    handle_plugin "screen-custom" "$GLANIM" || fail=1
fi
if [ "$NEED_F" = "1" ]; then
    handle_plugin "fan-control" "$FAN" || fail=1
fi

if [ "$MODE" != "check" ]; then
    rm -f /tmp/luci-indexcache* 2>/dev/null
    /etc/init.d/uhttpd restart >/dev/null 2>&1
    [ "$NEED_G" = "1" ] && [ -x /etc/init.d/glanim ] && /etc/init.d/glanim restart >/dev/null 2>&1
    [ "$NEED_F" = "1" ] && [ -x /etc/init.d/glfanctl ] && /etc/init.d/glfanctl restart >/dev/null 2>&1
    say "LuCI 缓存已清理"
fi

rm -rf "$TMP"
[ "$fail" = "0" ] || exit 1
say "完成"
