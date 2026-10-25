# -*- coding: utf-8 -*-
"""
Build OpenWrt .ipk packages locally (no cross-compile toolchain needed).
Usage:
  python build_ipk.py glfanctl
  python build_ipk.py glanim
Output: deliverables/<Package>_<Version>_<Architecture>.ipk
"""
import io
import os
import sys
import tarfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TARGETS = {
    "screen-custom": (os.path.join(ROOT, "plugins", "screen-custom", "src"),
                      os.path.join(ROOT, "plugins", "screen-custom", "releases")),
    "fan-control": (os.path.join(ROOT, "plugins", "fan-control", "src"),
                    os.path.join(ROOT, "plugins", "fan-control", "releases")),
}


def read_control(src_root):
    cfg = {}
    with open(os.path.join(src_root, "CONTROL", "control"), "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if ":" in line:
                k, v = line.split(":", 1)
                cfg[k.strip()] = v.strip()
    return cfg


def add_file(tar, full_path, arcname, mode):
    with open(full_path, "rb") as f:
        data = f.read()
    ti = tarfile.TarInfo(arcname)
    ti.size = len(data)
    ti.mode = mode
    ti.uid = 0
    ti.gid = 0
    ti.mtime = 0
    ti.type = tarfile.REGTYPE
    tar.addfile(ti, io.BytesIO(data))


def add_dir(tar, arcname):
    ti = tarfile.TarInfo(arcname)
    ti.mode = 0o755
    ti.uid = 0
    ti.gid = 0
    ti.mtime = 0
    ti.type = tarfile.DIRTYPE
    tar.addfile(ti)


def mode_for(rel):
    if rel.startswith("etc/init.d/") or rel.startswith("usr/bin/"):
        return 0o755
    return 0o644


def build(src_root, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    ctrl = read_control(src_root)
    pkg = ctrl["Package"]
    ver = ctrl["Version"]
    arch = ctrl["Architecture"]

    # ---- inner control.tar.gz ----
    control_buf = io.BytesIO()
    with tarfile.open(fileobj=control_buf, mode="w:gz",
                      format=tarfile.USTAR_FORMAT) as ct:
        add_dir(ct, ".")
        for fn in ("control", "conffiles", "postinst", "prerm", "postrm"):
            p = os.path.join(src_root, "CONTROL", fn)
            if os.path.exists(p):
                m = 0o755 if fn in ("postinst", "prerm", "postrm") else 0o644
                add_file(ct, p, "./" + fn, m)

    # ---- inner data.tar.gz ----
    data_buf = io.BytesIO()
    with tarfile.open(fileobj=data_buf, mode="w:gz",
                      format=tarfile.USTAR_FORMAT) as dt:
        add_dir(dt, ".")
        for dirpath, dirnames, filenames in os.walk(src_root):
            dirnames[:] = [d for d in dirnames if d != "__pycache__"]
            rel_dir = os.path.relpath(dirpath, src_root).replace("\\", "/")
            if rel_dir == "CONTROL" or rel_dir.startswith("CONTROL/"):
                continue
            if rel_dir != ".":
                add_dir(dt, "./" + rel_dir + "/")
            for fn in filenames:
                if fn.endswith((".orig", ".bak", ".pyc", ".pyo")):
                    continue
                full = os.path.join(dirpath, fn)
                rel = (rel_dir + "/" + fn) if rel_dir != "." else fn
                add_file(dt, full, "./" + rel, mode_for(rel))

    # ---- outer gzip tar shell (this firmware's opkg format) ----
    out_name = "%s_%s_%s.ipk" % (pkg, ver, arch)
    out_path = os.path.join(out_dir, out_name)
    outer = io.BytesIO()
    with tarfile.open(fileobj=outer, mode="w:gz",
                      format=tarfile.USTAR_FORMAT) as ot:
        def outer_member(name, payload, mode=0o644):
            ti = tarfile.TarInfo("./" + name)
            ti.size = len(payload)
            ti.mode = mode
            ti.uid = 0; ti.gid = 0; ti.mtime = 0
            ti.type = tarfile.REGTYPE
            ot.addfile(ti, io.BytesIO(payload))
        outer_member("debian-binary", b"2.0\n")
        outer_member("data.tar.gz", data_buf.getvalue())
        outer_member("control.tar.gz", control_buf.getvalue())
    with open(out_path, "wb") as out:
        out.write(outer.getvalue())
    print("built:", out_path)
    return out_path


if __name__ == "__main__":
    # regenerate zh-cn lmo catalogs before packaging
    sys.path.insert(0, os.path.join(ROOT, "build", "tools"))
    import build_lmo
    build_lmo.generate_all(root=ROOT)

    targets = sys.argv[1:] or list(TARGETS)
    for t in targets:
        if t not in TARGETS:
            raise SystemExit("unknown target: %s (choose from %s)" % (t, ", ".join(TARGETS)))
        build(*TARGETS[t])
