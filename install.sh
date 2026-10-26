#!/bin/sh
# GL-BE3600 Toolbox installer
# Interactive menu; nothing is downloaded until a choice is made.
set -e

REPO="xavierbe278/gl-be3600-toolbox"
API="https://api.github.com/repos/${REPO}/releases/latest"
WEB="https://github.com/${REPO}/releases"
TMP="/tmp/glanim-install"
GLANIM="luci-app-glanim"
FAN="luci-app-glfanctl"
ARCH="aarch64_cortex-a53_neon-vfpv4"

say() { echo "[glanim] $*"; }
die() { echo "[glanim] $*" >&2; exit 1; }

show_menu() {
    cat <<'EOF'

========================================
      GL-BE3600 Toolbox 安装器
========================================
  1) 安装 / 更新 屏幕自定义
  2) 安装 / 更新 风扇控制
  3) 安装 / 更新 两个插件
  0) 退出
========================================
EOF
}

NEED_G=0
NEED_F=0
while :; do
    show_menu
    printf "请选择 [0-3]: "
    if [ -r /dev/tty ]; then
        IFS= read -r choice </dev/tty || exit 0
    else
        IFS= read -r choice || exit 0
    fi
    case "$choice" in
        0|q|Q)
            say "已退出。"
            exit 0
            ;;
        1)
            NEED_G=1
            NEED_F=0
            break
            ;;
        2)
            NEED_G=0
            NEED_F=1
            break
            ;;
        3)
            NEED_G=1
            NEED_F=1
            break
            ;;
        *)
            echo "无效选择，请输入 0、1、2 或 3。"
            ;;
    esac
done

[ "$(id -u)" = "0" ] || die "请使用 root 运行。"
command -v opkg >/dev/null 2>&1 || die "未找到 opkg；这不是 OpenWrt / GL.iNet 系统。"

latest_tag() {
    if command -v curl >/dev/null 2>&1; then
        curl -fsSL -H "User-Agent: glanim-installer" "$API" \
            | sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' \
            | head -n 1
    elif command -v wget >/dev/null 2>&1; then
        wget -qO- --header="User-Agent: glanim-installer" "$API" \
            | sed -n 's/.*"tag_name"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' \
            | head -n 1
    fi
}

download() {
    url="$1"; out="$2"
    if command -v curl >/dev/null 2>&1; then
        curl -fL "$url" -o "$out"
    elif command -v wget >/dev/null 2>&1; then
        wget -O "$out" "$url"
    else
        die "系统里没有 curl 或 wget。"
    fi
}

say "正在查询最新 Release..."
TAG="$(latest_tag)"
if [ -z "$TAG" ]; then
    if command -v curl >/dev/null 2>&1; then
        FINAL="$(curl -fsSIL -o /dev/null -w '%{url_effective}' "$WEB/latest" || true)"
        TAG="${FINAL##*/}"
    fi
fi
[ -n "$TAG" ] || die "无法获取最新 Release 版本。"
TAG="v${TAG#v}"
RELVER="${TAG#v}-1"
say "最新版本：${TAG}"

rm -rf "$TMP"
mkdir -p "$TMP"
BASE="${WEB}/download/${TAG}"

GIPK="${GLANIM}_${RELVER}_${ARCH}.ipk"
FIPK="${FAN}_1.0.7-1_${ARCH}.ipk"
GURL="${BASE}/${GIPK}"
FURL="${BASE}/${FIPK}"

GFILE=""
FFILE=""
MISSING=0

if [ "$NEED_G" = "1" ]; then
    if download "$GURL" "$TMP/$GIPK" 2>/dev/null; then
        GFILE="$TMP/$GIPK"
    else
        MISSING=1
    fi
fi
if [ "$NEED_F" = "1" ]; then
    if download "$FURL" "$TMP/$FIPK" 2>/dev/null; then
        FFILE="$TMP/$FIPK"
    else
        MISSING=1
    fi
fi

if [ "$MISSING" = "1" ] || [ -z "$GFILE$FFILE" ]; then
    PACK="gl-be3600-toolbox-${TAG}.tar.gz"
    say "独立 IPK 不完整，下载完整包 ${PACK}"
    download "${BASE}/${PACK}" "$TMP/$PACK"
    tar -xzf "$TMP/$PACK" -C "$TMP"
    ROOT="$TMP/gl-be3600-toolbox"
    if [ "$NEED_G" = "1" ]; then
        GFILE="$(find "$ROOT/plugins/screen-custom/releases" -name "${GLANIM}_${RELVER}_*.ipk" | head -n 1)"
    fi
    if [ "$NEED_F" = "1" ]; then
        FFILE="$(find "$ROOT/plugins/fan-control/releases" -name "${FAN}_*.ipk" | sort | tail -n 1)"
    fi
fi

if [ "$NEED_G" = "1" ]; then
    [ -n "$GFILE" ] && [ -f "$GFILE" ] || die "没有找到屏幕插件 IPK。"
    say "安装 $(basename "$GFILE")"
    opkg install --force-depends --force-reinstall --force-overwrite "$GFILE"
    /etc/init.d/glanim enable 2>/dev/null || true
    /etc/init.d/glanim restart 2>/dev/null || true
fi

if [ "$NEED_F" = "1" ]; then
    [ -n "$FFILE" ] && [ -f "$FFILE" ] || die "没有找到风扇插件 IPK。"
    say "安装 $(basename "$FFILE")"
    opkg install --force-depends --force-reinstall --force-overwrite "$FFILE"
    /etc/init.d/glfanctl enable 2>/dev/null || true
    /etc/init.d/glfanctl restart 2>/dev/null || true
fi

rm -rf "$TMP"
say "安装完成。"
