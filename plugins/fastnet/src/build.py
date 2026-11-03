#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build luci-app-fastnet IPK variants (OpenWrt 23.05 / opkg).

Variants
--------
  --version 0.7.7                 plain: single binary, stock-like page
                                  (no iframe, no version switch)
  --version 0.7.6                 plain 0.7.6
  --version 0.7.7 --optimize      plus: both binaries, embedded page,
                                  version switch button

Usage
-----
  python build.py --version 0.7.7
  python build.py --version 0.7.6
  python build.py --version 0.7.7 --optimize

Output: deliverables/luci-app-fastnet_<version>_<arch>.ipk
"""
import io
import os
import shutil
import sys
import tarfile

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "deliverables")
STAGE = os.path.join(HERE, ".stage")

ARCH = "aarch64_cortex-a53_neon-vfpv4"
PKG = "luci-app-fastnet"

DESC_PLAIN = ("FastNet network diagnostics with LuCI page. Plain install: "
              "single core version, no embedded frame and no version switch.")
DESC_PLUS = ("FastNet network diagnostics with LuCI page. Optimized install: "
             "both 0.7.6 and 0.7.7 cores, embedded page and one-click version "
             "switch (only one core runs at a time).")


def ctrl_text(version, plus):
    rev = "2" if plus else "1"
    return (
        "Package: %s\n"
        "Version: %s-%s\n"
        "Depends: libc, luci-compat, rpcd, ubus\n"
        "Architecture: %s\n"
        "Section: luci\n"
        "Priority: optional\n"
        "Title: FastNet%s\n"
        "Maintainer: local\n"
        "Description: %s\n"
    ) % (PKG, version, rev, ARCH,
         " (optimized)" if plus else "", DESC_PLUS if plus else DESC_PLAIN)


def copy_tree(src, dst):
    if not os.path.isdir(src):
        return
    for dirpath, _dirnames, filenames in os.walk(src):
        rel = os.path.relpath(dirpath, src)
        target = os.path.join(dst, rel) if rel != "." else dst
        os.makedirs(target, exist_ok=True)
        for fn in filenames:
            shutil.copy2(os.path.join(dirpath, fn), os.path.join(target, fn))


def add_dir(tar, name):
    ti = tarfile.TarInfo(name)
    ti.mode = 0o755
    ti.uid = ti.gid = 0
    ti.mtime = 0
    ti.type = tarfile.DIRTYPE
    tar.addfile(ti)


def add_file(tar, full, arc, mode):
    with open(full, "rb") as f:
        data = f.read()
    ti = tarfile.TarInfo(arc)
    ti.size = len(data)
    ti.mode = mode
    ti.uid = ti.gid = 0
    ti.mtime = 0
    ti.type = tarfile.REGTYPE
    tar.addfile(ti, io.BytesIO(data))


def mode_for(rel):
    if rel.startswith("etc/init.d/") or rel.startswith("usr/sbin/") or rel.startswith("usr/bin/"):
        return 0o755
    return 0o644


def build(version, plus):
    if os.path.isdir(STAGE):
        shutil.rmtree(STAGE)
    os.makedirs(os.path.join(STAGE, "CONTROL"), exist_ok=True)

    # control files
    with open(os.path.join(STAGE, "CONTROL", "control"), "w", encoding="utf-8", newline="\n") as f:
        f.write(ctrl_text(version, plus))
    for fn in ("conffiles", "postinst", "prerm", "postrm"):
        src = os.path.join(HERE, "common", "CONTROL", fn)
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(STAGE, "CONTROL", fn))

    # common data
    copy_tree(os.path.join(HERE, "common", "etc"), os.path.join(STAGE, "etc"))

    # default version in config
    cfg = os.path.join(STAGE, "etc", "config", "fastnet")
    with open(cfg, "r", encoding="utf-8") as f:
        text = f.read()
    with open(cfg, "w", encoding="utf-8", newline="\n") as f:
        f.write(text.replace("@VERSION@", version))

    # payload
    if plus:
        os.makedirs(os.path.join(STAGE, "usr", "sbin"), exist_ok=True)
        for v in ("0.7.6", "0.7.7"):
            shutil.copy2(os.path.join(HERE, "bin", "FastNet-" + v),
                         os.path.join(STAGE, "usr", "sbin", "FastNet-" + v))
        copy_tree(os.path.join(HERE, "plus", "usr"), os.path.join(STAGE, "usr"))
        copy_tree(os.path.join(HERE, "plus", "www"), os.path.join(STAGE, "www"))
    else:
        os.makedirs(os.path.join(STAGE, "usr", "sbin"), exist_ok=True)
        shutil.copy2(os.path.join(HERE, "bin", "FastNet-" + version),
                     os.path.join(STAGE, "usr", "sbin", "FastNet"))
        copy_tree(os.path.join(HERE, "plain", "usr"), os.path.join(STAGE, "usr"))
        copy_tree(os.path.join(HERE, "plain", "www"), os.path.join(STAGE, "www"))
        # 原版包只带一个核心，postinst 据此把 uci 里的版本号校正成实际安装的版本
        os.makedirs(os.path.join(STAGE, "usr", "share", "fastnet"), exist_ok=True)
        with open(os.path.join(STAGE, "usr", "share", "fastnet", "version.txt"),
                  "w", encoding="utf-8", newline="\n") as f:
            f.write(version + "\n")

    # ---- control.tar.gz ----
    cbuf = io.BytesIO()
    with tarfile.open(fileobj=cbuf, mode="w:gz", format=tarfile.USTAR_FORMAT) as ct:
        add_dir(ct, ".")
        for fn in ("control", "conffiles", "postinst", "prerm", "postrm"):
            p = os.path.join(STAGE, "CONTROL", fn)
            if os.path.exists(p):
                add_file(ct, p, "./" + fn, 0o755 if fn in ("postinst", "prerm", "postrm") else 0o644)

    # ---- data.tar.gz ----
    dbuf = io.BytesIO()
    with tarfile.open(fileobj=dbuf, mode="w:gz", format=tarfile.USTAR_FORMAT) as dt:
        add_dir(dt, ".")
        for dirpath, dirnames, filenames in os.walk(STAGE):
            dirnames[:] = [d for d in dirnames if d != "CONTROL"]
            rel = os.path.relpath(dirpath, STAGE).replace("\\", "/")
            if rel.startswith("CONTROL"):
                continue
            if rel != ".":
                add_dir(dt, "./" + rel + "/")
            for fn in filenames:
                full = os.path.join(dirpath, fn)
                r = (rel + "/" + fn) if rel != "." else fn
                add_file(dt, full, "./" + r, mode_for(r))

    # ---- outer ----
    os.makedirs(OUT, exist_ok=True)
    rev = "2" if plus else "1"
    out_path = os.path.join(OUT, "%s_%s-%s_%s.ipk" % (PKG, version, rev, ARCH))
    outer = io.BytesIO()
    with tarfile.open(fileobj=outer, mode="w:gz", format=tarfile.USTAR_FORMAT) as ot:
        def member(name, payload):
            ti = tarfile.TarInfo("./" + name)
            ti.size = len(payload)
            ti.mode = 0o644
            ti.uid = ti.gid = 0
            ti.mtime = 0
            ti.type = tarfile.REGTYPE
            ot.addfile(ti, io.BytesIO(payload))
        member("debian-binary", b"2.0\n")
        member("data.tar.gz", dbuf.getvalue())
        member("control.tar.gz", cbuf.getvalue())
    with open(out_path, "wb") as f:
        f.write(outer.getvalue())
    print("built:", out_path, "(%.1f MB)" % (os.path.getsize(out_path) / 1048576.0))
    return out_path


if __name__ == "__main__":
    ver = "0.7.7"
    plus = False
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        a = args[i]
        if a == "--version" and i + 1 < len(args):
            ver = args[i + 1]; i += 2; continue
        if a == "--optimize":
            plus = True; i += 1; continue
        if a in ("-h", "--help"):
            print(__doc__); sys.exit(0)
        raise SystemExit("unknown arg: " + a)
    if ver not in ("0.7.6", "0.7.7"):
        raise SystemExit("version must be 0.7.6 or 0.7.7")
    build(ver, plus)
