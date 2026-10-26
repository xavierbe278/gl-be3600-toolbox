#!/bin/sh
# GL-BE3600 Toolbox one-click installer
# Always installs the latest GitHub Release.
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

[ "$(id -u)" = "0" ] || die "Please run as root."
command -v opkg >/dev/null 2>&1 || die "opkg not found; this is not an OpenWrt/GL.iNet system."

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
        die "Neither curl nor wget is available."
    fi
}

TAG="$(latest_tag)"
if [ -z "$TAG" ]; then
    # Fallback: follow the /releases/latest redirect and take the tag.
    if command -v curl >/dev/null 2>&1; then
        FINAL="$(curl -fsSIL -o /dev/null -w '%{url_effective}' "$WEB/latest" || true)"
        TAG="${FINAL##*/}"
    fi
fi
[ -n "$TAG" ] || die "Could not detect the latest release tag."
TAG="v${TAG#v}"
RELVER="${TAG#v}-1"
say "Latest release: ${TAG}"

rm -rf "$TMP"
mkdir -p "$TMP"
BASE="${WEB}/download/${TAG}"

# Prefer standalone IPK assets when the release provides them.
GIPK="${GLANIM}_${RELVER}_${ARCH}.ipk"
FIPK="${FAN}_1.0.7-1_${ARCH}.ipk"
GURL="${BASE}/${GIPK}"
FURL="${BASE}/${FIPK}"

if download "$GURL" "$TMP/$GIPK" 2>/dev/null && download "$FURL" "$TMP/$FIPK" 2>/dev/null; then
    GFILE="$TMP/$GIPK"
    FFILE="$TMP/$FIPK"
else
    # Packaged release fallback: tar.gz contains both IPKs.
    PACK="gl-be3600-toolbox-${TAG}.tar.gz"
    say "Standalone IPKs not found; downloading ${PACK}"
    download "${BASE}/${PACK}" "$TMP/$PACK"
    tar -xzf "$TMP/$PACK" -C "$TMP"
    ROOT="$TMP/gl-be3600-toolbox"
    GFILE="$(find "$ROOT/plugins/screen-custom/releases" -name "${GLANIM}_${RELVER}_*.ipk" | head -n 1)"
    FFILE="$(find "$ROOT/plugins/fan-control/releases" -name "${FAN}_*.ipk" | sort | tail -n 1)"
fi

[ -n "$GFILE" ] && [ -f "$GFILE" ] || die "Screen plugin IPK not found."
[ -n "$FFILE" ] && [ -f "$FFILE" ] || die "Fan plugin IPK not found."

say "Installing $(basename "$GFILE")"
opkg install --force-depends --force-reinstall --force-overwrite "$GFILE"

say "Installing $(basename "$FFILE")"
opkg install --force-depends --force-reinstall --force-overwrite "$FFILE"

/etc/init.d/glanim enable 2>/dev/null || true
/etc/init.d/glanim restart 2>/dev/null || true
/etc/init.d/glfanctl restart 2>/dev/null || true
rm -rf "$TMP"

say "Done. Open LuCI -> Services -> Screen Custom."
