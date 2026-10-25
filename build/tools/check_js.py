# -*- coding: utf-8 -*-
"""Reassemble the injected <script> JS from each CBI model and node --check it.

The Lua model builds js.value as a chain of single-quoted string fragments with
a few interpolated variables. We scan each script line for Lua string tokens
and bare `.. var ..` interpolations, expand the var stubs as bare JS values,
drop the <style> block, then hand the result to `node --check`.
Run: python tools/check_js.py
"""
import os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

MODELS = {
    "glfanctl": ("glfanctl/usr/lib/lua/luci/model/cbi/glfanctl/main.lua",
                 {"status_url": "/cgi-bin/luci/admin/services/glfanctl/status",
                  "save_url": "/cgi-bin/luci/admin/services/glfanctl/save",
                  "is_zh_js": "true"}),
    "glanim": ("glanim/usr/lib/lua/luci/model/cbi/glanim/main.lua",
               {"status_url": "/cgi-bin/luci/admin/services/glanim/status",
                "upload_image_url": "/cgi-bin/luci/admin/services/glanim/upload_image",
                "is_zh_js": "true"}),
}

# Lua single-quoted string token (with escape awareness)
lua_str = re.compile(r"'((?:[^'\\]|\\.)*)'")
# bare interpolation: .. var ..
lua_var = re.compile(r"\.\.\s*([A-Za-z_]\w*)\s*\.\.")


def unescape_lua(body: str) -> str:
    body = body.replace("\\'", "'").replace('\\"', '"')
    body = body.replace("\\\\", "\\")
    return body


def extract_js(lua_text: str, stubs: dict) -> str:
    out, in_script, in_style = [], False, False
    for raw in lua_text.splitlines():
        line = raw.rstrip()
        if "<script>" in line:
            in_script = True
            continue
        if "</script>" in line:
            in_script = False
            continue
        if "<style>" in line:
            in_style = True
            line = line.split("<style>")[0]
        if "</style>" in line:
            in_style = False
            line = line.split("</style>")[-1]
            continue
        if in_style or not in_script:
            continue

        pos = 0
        for m in lua_str.finditer(line):
            # emit any bare interpolation sitting before this string
            seg = line[pos:m.start()]
            for v in lua_var.findall(seg):
                out.append(stubs.get(v, '""'))
            out.append(unescape_lua(m.group(1)))
            pos = m.end()
        # trailing interpolation after the last string
        seg = line[pos:]
        for v in lua_var.findall(seg):
            out.append(stubs.get(v, '""'))
    return "".join(out)


def check_file(path, label):
    global fail
    r = subprocess.run(["node", "--check", path], capture_output=True, text=True)
    if r.returncode == 0:
        print("[OK] %s (%d bytes)" % (label, os.path.getsize(path)))
    else:
        fail += 1
        print("[FAIL] %s" % label)
        print(r.stderr)


fail = 0
for pkg, (rel, stubs) in MODELS.items():
    src = os.path.join(ROOT, rel)
    text = open(src, encoding="utf-8").read()
    js = extract_js(text, stubs)
    if js.strip():
        with tempfile.NamedTemporaryFile("w", suffix=".js", delete=False, encoding="utf-8") as tf:
            tf.write(js)
            js_path = tf.name
        check_file(js_path, "%s inline js (%d bytes)" % (pkg, len(js)))
        os.unlink(js_path)
    else:
        print("[OK] %s inline js (empty, external)" % pkg)
    # external static scripts shipped under www/
    www_root = os.path.join(ROOT, pkg, "www")
    if os.path.isdir(www_root):
        for dirpath, _, filenames in os.walk(www_root):
            for fn in sorted(filenames):
                if fn.endswith(".js"):
                    check_file(os.path.join(dirpath, fn),
                               "%s %s" % (pkg, os.path.relpath(os.path.join(dirpath, fn), www_root)))

sys.exit(1 if fail else 0)
