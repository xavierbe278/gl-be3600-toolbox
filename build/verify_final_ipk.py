# -*- coding: utf-8 -*-
"""Local structural audit of the final ipk packages (gzip tar shell)."""
import io, os, tarfile, glob, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RELEASE_DIRS = [
    os.path.join(ROOT, "plugins", "screen-custom", "releases"),
    os.path.join(ROOT, "plugins", "fan-control", "releases"),
]

EXPECT = {
    "luci-app-glfanctl": [
        "./etc/config/glfanctl",
        "./etc/init.d/glfanctl",
        "./usr/bin/glfanctl",
        "./usr/lib/lua/luci/controller/glfanctl.lua",
        "./usr/lib/lua/luci/model/cbi/glfanctl/main.lua",
        "./usr/share/rpcd/acl.d/luci-app-glfanctl.json",
        "./usr/lib/lua/luci/i18n/glfanctl.zh-cn.lmo",
        "./www/luci-static/resources/app-icons/glfanctl.png",
        "./www/luci-static/resources/glfanctl/glfanctl.js",
        "./www/luci-static/resources/glfanctl/glfanctl.css",
    ],
    "luci-app-glanim": [
        "./etc/config/glanim",
        "./etc/init.d/glanim",
        "./usr/bin/glanimd",
        "./usr/bin/glanimdash.py",
        "./usr/lib/lua/luci/controller/glanim.lua",
        "./usr/lib/lua/luci/model/cbi/glanim/main.lua",
        "./usr/share/glanim/frames/",
        "./usr/share/rpcd/acl.d/luci-app-glanim.json",
        "./usr/lib/lua/luci/i18n/glanim.zh-cn.lmo",
        "./www/luci-static/resources/app-icons/glanim.png",
        "./www/luci-static/resources/glanim/glanim.js",
        "./www/luci-static/resources/glanim/glanim.css",
        "./www/luci-static/resources/glui-bridge/glui-bridge.js",
        "./www/luci-static/resources/glui-bridge/glui-bridge.css",
    ],
}
CONTROL_MEMBERS = ["control", "conffiles", "postinst", "prerm", "postrm"]

ok_all = True
for ipk in sorted(p for d in RELEASE_DIRS for p in glob.glob(os.path.join(d, "*.ipk"))):
    print("===", os.path.basename(ipk), os.path.getsize(ipk), "bytes")
    outer = tarfile.open(ipk, mode="r:gz")
    omembers = outer.getmembers()
    names = {m.name.lstrip("./"): m for m in omembers}
    for must in ("debian-binary", "data.tar.gz", "control.tar.gz"):
        assert must in names, "missing outer member " + must
    ctrl = tarfile.open(fileobj=io.BytesIO(
        outer.extractfile("./control.tar.gz").read()), mode="r:gz")
    cnames = {m.name.lstrip("./"): m for m in ctrl.getmembers()}
    for c in CONTROL_MEMBERS:
        assert c in cnames, "control missing " + c
    control_text = ctrl.extractfile(cnames["control"]).read().decode()
    fields = {}
    for line in control_text.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            fields[k.strip()] = v.strip()
    print("  package:", fields.get("Package"), fields.get("Version"),
          "arch:", fields.get("Architecture"), "depends:", fields.get("Depends"))

    data = tarfile.open(fileobj=io.BytesIO(
        outer.extractfile("./data.tar.gz").read()), mode="r:gz")
    dnames = {m.name.lstrip("./"): m for m in data.getmembers()}
    FORBIDDEN = (".orig", ".bak", ".pyc", ".pyo")
    leaks = [n for n in dnames if n.endswith(FORBIDDEN) or "__pycache__" in n]
    for n in leaks:
        ok_all = False
        print("  [BAD] forbidden leftover:", n)
    for want in EXPECT[fields["Package"]]:
        w = want.lstrip("./")
        if w.endswith("/"):
            present = any(n.startswith(w) for n in dnames)
        else:
            present = w in dnames
        flag = "OK " if present else "MISS"
        if not present: ok_all = False
        print("  [%s] %s" % (flag, want))
        if present and not w.endswith("/"):
            mode = oct(dnames[w].mode)
            print("        mode=%s" % mode)
    outer.close(); ctrl.close(); data.close()

print("\nRESULT:", "ALL PACKAGES COMPLETE" if ok_all else "MISSING FILES")
sys.exit(0 if ok_all else 1)
