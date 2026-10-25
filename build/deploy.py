# -*- coding: utf-8 -*-
"""Deploy helper: upload ipk, extract locally, syntax-check on router, install.

Credentials are read from environment variables so no password is committed:
  ROUTER_HOST  (default 192.168.8.1)
  ROUTER_USER  (default root)
  ROUTER_PASS  (required)
"""
import io, os, sys, tarfile, glob, stat, paramiko

HOST = os.environ.get("ROUTER_HOST", "192.168.8.1")
USER = os.environ.get("ROUTER_USER", "root")
PASS = os.environ.get("ROUTER_PASS", "")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EXTRACT = os.path.join(HERE, "extract")

PKG_DIRS = [
    os.path.join(ROOT, "plugins", "screen-custom", "releases"),
    os.path.join(ROOT, "plugins", "fan-control", "releases"),
]
PKGS = [
    "luci-app-glfanctl_1.0.4-1_aarch64_cortex-a53_neon-vfpv4.ipk",
    "luci-app-glanim_1.3.3-1_aarch64_cortex-a53_neon-vfpv4.ipk",
]


def pkg_path(name):
    for d in PKG_DIRS:
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    raise SystemExit("package not found: " + name)


def connect():
    if not PASS:
        raise SystemExit("Set ROUTER_PASS before using deploy.py")
    c = paramiko.SSHClient(); c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, port=22, username=USER, password=PASS,
              timeout=15, allow_agent=False, look_for_keys=False)
    return c


def run(c, cmd, t=120):
    stdin, stdout, stderr = c.exec_command(cmd, timeout=t)
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    code = stdout.channel.recv_exit_status()
    if out: print(out)
    if err: print("[stderr]", err)
    print("EXIT=%d" % code)
    return code


def local_extract():
    if os.path.exists(EXTRACT):
        for f in glob.glob(EXTRACT + "/**/*", recursive=True):
            if os.path.isfile(f): os.remove(f)
    os.makedirs(EXTRACT, exist_ok=True)
    for ipk in PKGS:
        data = open(pkg_path(ipk), "rb").read()
        outer = tarfile.open(fileobj=io.BytesIO(data), mode="r:gz")
        inner_buffers = {}
        for member in outer.getmembers():
            inner_buffers[member.name.lstrip("./")] = \
                outer.extractfile(member).read()
        for tar_name in ("control.tar.gz", "data.tar.gz"):
            t = tarfile.open(fileobj=io.BytesIO(inner_buffers[tar_name]),
                             mode="r:gz")
            for member in t.getmembers():
                if member.isdir(): continue
                rel = member.name.lstrip("./")
                if rel in ("control", "conffiles", "postinst", "prerm", "postrm"):
                    out = os.path.join(EXTRACT, "control", rel)
                else:
                    out = os.path.join(EXTRACT, rel)
                os.makedirs(os.path.dirname(out), exist_ok=True)
                with open(out, "wb") as f:
                    f.write(t.extractfile(member).read())
                if member.mode & 0o111:
                    os.chmod(out, 0o755)
    print("extracted to", EXTRACT)


def sftp_upload_dir(sftp, local, remote):
    for dirpath, dirnames, filenames in os.walk(local):
        rel = os.path.relpath(dirpath, local).replace("\\", "/")
        rdir = remote if rel == "." else remote + "/" + rel
        try: sftp.mkdir(rdir)
        except IOError: pass
        for fn in filenames:
            sftp.put(os.path.join(dirpath, fn), rdir + "/" + fn)


def upload():
    c = connect(); s = c.open_sftp()
    for name in PKGS:
        s.put(pkg_path(name), "/tmp/" + name)
        print("uploaded /tmp/" + name)
    s.close(); c.close()


CHECK = r"""
echo "--- shell syntax ---"
sh -n /tmp/ipk-extract/etc/init.d/glfanctl && echo "glfanctl init OK"
sh -n /tmp/ipk-extract/usr/bin/glfanctl && echo "glfanctl daemon OK"
sh -n /tmp/ipk-extract/etc/init.d/glanim && echo "glanim init OK"
echo "--- python syntax ---"
python3 -m py_compile /tmp/ipk-extract/usr/bin/glanimd && echo "glanimd OK"
python3 -m py_compile /tmp/ipk-extract/usr/bin/glanimdash.py && echo "glanimdash OK"
echo "--- lua loadfile syntax check ---"
for l in /tmp/ipk-extract/usr/lib/lua/luci/controller/glfanctl.lua \
         /tmp/ipk-extract/usr/lib/lua/luci/controller/glanim.lua \
         /tmp/ipk-extract/usr/lib/lua/luci/model/cbi/glfanctl/main.lua \
         /tmp/ipk-extract/usr/lib/lua/luci/model/cbi/glanim/main.lua; do
  lua -e "assert(loadfile('$l')); print('OK', '$l')"
done
echo "--- json ---"
for j in /tmp/ipk-extract/usr/share/rpcd/acl.d/*.json; do
  python3 -c "import json;json.load(open('$j'));print('OK','$j')"
done
"""


def check():
    local_extract()
    c = connect(); s = c.open_sftp()
    run(c, "rm -rf /tmp/ipk-extract && mkdir -p /tmp/ipk-extract", 30)
    sftp_upload_dir(s, EXTRACT, "/tmp/ipk-extract")
    s.close()
    run(c, CHECK, 90)
    c.close()


INSTALL = r"""
opkg install --force-depends --force-reinstall --force-overwrite /tmp/luci-app-glfanctl_1.0.4-1_aarch64_cortex-a53_neon-vfpv4.ipk
opkg install --force-depends --force-reinstall --force-overwrite /tmp/luci-app-glanim_1.3.3-1_aarch64_cortex-a53_neon-vfpv4.ipk
echo ====================
opkg list-installed | grep -E 'glfanctl|glanim'
"""


def install():
    c = connect()
    run(c, INSTALL, 180)
    c.close()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    if mode in ("upload", "all"): upload()
    if mode in ("check", "all"): check()
    if mode in ("install", "all"): install()
