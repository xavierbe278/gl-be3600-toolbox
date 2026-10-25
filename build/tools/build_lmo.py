# -*- coding: utf-8 -*-
"""Generate zh-cn .lmo catalogs into the plugin source trees, with round-trip check.
Called automatically by build_ipk.py before packaging."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lmo, translations

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

TARGETS = {
    "glfanctl": ("plugins/fan-control/src", translations.GLFANCTL),
    "glanim": ("plugins/screen-custom/src", translations.GLANIM),
}


def generate_all(verbose=True, root=None):
    root = root or ROOT
    fail = 0
    for pkg, (src_dir, catalog) in TARGETS.items():
        out_dir = os.path.join(root, src_dir, "usr", "lib", "lua", "luci", "i18n")
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, "%s.zh-cn.lmo" % pkg)

        entries = list(catalog.items())
        n = lmo.encode(entries, out_path)

        for msgid, msgstr in entries:
            got = lmo.lookup(out_path, msgid)
            if got != msgstr:
                fail += 1
                if verbose:
                    print("MISMATCH [%s] %r -> %r (got %r)"
                          % (pkg, msgid, msgstr, got))
        if verbose:
            print("%s: %d entries -> %s" % (pkg, n, out_path))
    if fail:
        raise SystemExit("FAILED: %d lmo mismatches" % fail)
    if verbose:
        print("ALL LMO ROUND-TRIP OK")
    return fail


if __name__ == "__main__":
    generate_all()
