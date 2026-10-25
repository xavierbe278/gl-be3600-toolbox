# -*- coding: utf-8 -*-
"""Minimal LuCI LMO (Lua Machine Objects) encoder/decoder in pure Python.

Spec: https://github.com/wiki/openwrt/luci/LMO.md
- Payload first: each msgstr written raw, zero-padded to a 4-byte boundary.
- Index after payload: per entry 4x uint32 big-endian:
    key_id (SuperFastHash of msgid), val_id (= plural_num+1, 1 for ordinary),
    file offset of msgstr, length of msgstr.
  Index sorted by key_id ascending (binary search on the reader side).
- Tail: single uint32 big-endian offset where the index table begins.
"""
import os, struct, sys


def _get16(data, i):
    return data[i] | (data[i + 1] << 8)


def sfh_hash(data: bytes, init: int = None) -> int:
    """Paul Hsieh SuperFastHash, 32-bit wrap. Mirrors template_lmo.c sfh_hash."""
    M = 0xFFFFFFFF
    n = len(data)
    if n <= 0:
        return 0
    h = n if init is None else init
    rem = n & 3
    blocks = n >> 2
    i = 0
    for _ in range(blocks):
        h = (h + _get16(data, i)) & M
        tmp = ((_get16(data, i + 2) << 11) ^ h) & M
        h = ((h << 16) ^ tmp) & M
        i += 4
        h = (h + (h >> 11)) & M
    if rem == 3:
        h = (h + _get16(data, i)) & M
        h = (h ^ (h << 16)) & M
        b2 = data[i + 2]
        if b2 >= 128:
            b2 -= 256
        h = (h ^ (b2 << 18)) & M
        h = (h + (h >> 11)) & M
    elif rem == 2:
        h = (h + _get16(data, i)) & M
        h = (h ^ (h << 11)) & M
        h = (h + (h >> 17)) & M
    elif rem == 1:
        b1 = data[i]
        if b1 >= 128:
            b1 -= 256
        h = (h + b1) & M
        h = (h ^ (h << 10)) & M
        h = (h + (h >> 1)) & M
    # avalanching (C mask wraps after each)
    h = (h ^ (h << 3)) & M
    h = (h + (h >> 5)) & M
    h = (h ^ (h << 4)) & M
    h = (h + (h >> 17)) & M
    h = (h ^ (h << 25)) & M
    h = (h + (h >> 6)) & M
    return h


def canon_key(key: str) -> bytes:
    """Whitespace normalization matching lmo_canon_hash (no msgctxt, no plural)."""
    out = []
    prev = " "
    for ch in key:
        if ch.isspace():
            if not prev.isspace():
                out.append(" ")
        else:
            out.append(ch)
        prev = ch
    if out and out[-1].isspace():
        out.pop()
    return "".join(out).encode("utf-8")


def _pad4(n: int) -> int:
    return (4 - (n % 4)) % 4


def encode(entries, out_path: str):
    """entries: list of (msgid, msgstr); writes a valid .lmo."""
    payload = bytearray()
    index = []
    offset = 0
    for msgid, msgstr in entries:
        v = msgstr.encode("utf-8")
        k = canon_key(msgid)
        key_id = sfh_hash(k, len(k))
        val_id = 1  # ordinary msgstr[0]
        index.append((key_id, val_id, offset, len(v), msgid, msgstr))
        payload += v
        payload += b"\x00" * _pad4(len(v))
        offset += len(v) + _pad4(len(v))
    index.sort(key=lambda e: e[0])

    body = bytearray(payload)
    for key_id, val_id, off, length, _, _ in index:
        body += struct.pack(">IIII", key_id, val_id, off, length)
    body += struct.pack(">I", offset)  # index offset = payload size

    with open(out_path, "wb") as f:
        f.write(body)
    return len(index)


def decode(path: str):
    """Return list of (key_id, val_id, offset, length, value) for inspection."""
    b = open(path, "rb").read()
    idx_off = struct.unpack(">I", b[-4:])[0]
    n = (len(b) - idx_off - 4) // 16
    out = []
    for i in range(n):
        off = idx_off + i * 16
        key_id, val_id, voff, vlen = struct.unpack(">IIII", b[off:off + 16])
        value = b[voff:voff + vlen].decode("utf-8", "replace")
        out.append((key_id, val_id, voff, vlen, value))
    return out


def lookup(path: str, key: str):
    """Simulate parser.so translate(): hash canon(key) then binary search index."""
    b = open(path, "rb").read()
    idx_off = struct.unpack(">I", b[-4:])[0]
    n = (len(b) - idx_off - 4) // 16
    target = sfh_hash(canon_key(key), len(canon_key(key)))
    lo, hi = 0, n - 1
    while lo <= hi:
        m = (lo + hi) // 2
        key_id, val_id, voff, vlen = struct.unpack(">IIII", b[idx_off + m * 16:
                                                          idx_off + m * 16 + 16])
        if key_id == target:
            return b[voff:voff + vlen].decode("utf-8", "replace")
        if key_id > target:
            hi = m - 1
        else:
            lo = m + 1
    return None


if __name__ == "__main__":
    # self test: round-trip a tiny catalog
    sample = [
        ("Fan Control", "风扇控制"),
        ("Enabled", "启用"),
        ("Current Status", "当前状态"),
        ("Mode", "模式"),
    ]
    here = os.path.dirname(os.path.abspath(__file__))
    tmp = os.path.join(here, "_selftest.lmo")
    n = encode(sample, tmp)
    print("entries:", n)
    for key, _ in sample:
        print(" lookup %-18s -> %s" % (key, lookup(tmp, key)))
    print(" missing key ->", lookup(tmp, "NotPresent"))
    os.remove(tmp)
