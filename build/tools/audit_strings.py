# -*- coding: utf-8 -*-
"""Scan controller + CBI source for translatable strings; list ones missing
from the catalogs (excluding trivial prefixes built up by concatenation)."""
import os, re, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import translations

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# pkg: (catalog, source files)
JOBS = {
    "glfanctl": (translations.GLFANCTL, [
        "controller/glfanctl.lua",
        "model/cbi/glfanctl/main.lua",
    ]),
    "glanim": (translations.GLANIM, [
        "controller/glanim.lua",
        "model/cbi/glanim/main.lua",
    ]),
}

# strings we intentionally leave untranslated (single letters / base-covered)
SKIP = {"T", "P", "Enabled", "Mode", "Status", "Settings", "Name", "Save",
        "Reset", "Cancel", "Save & Apply", "Apply", "Refresh", "Description",
        "Password", "Network", "Hostname"}

pat = re.compile(r'(?:translate|_)\(\s*"((?:[^"\\]|\\.)*)"\s*\)')
escape = re.compile(r'\\(.)')

for pkg, (catalog, rels) in JOBS.items():
    print("== %s ==" % pkg)
    seen = set()
    for rel in rels:
        src = os.path.join(ROOT, pkg, "usr", "lib", "lua", "luci", rel)
        text = open(src, encoding="utf-8").read()
        for m in pat.finditer(text):
            s = escape.sub(r"\1", m.group(1))
            seen.add(s)
    missing = sorted(s for s in seen if s not in catalog and s not in SKIP)
    covered = sorted(s for s in seen if s in catalog)
    for s in covered:
        print("  [ok] %s" % s)
    for s in missing:
        print("  [MISSING] %s" % s)
    if not missing:
        print("  all catalog-covered (generic words rely on base.lmo)")
