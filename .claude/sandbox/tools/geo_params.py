r"""The geometric driver's switches and values in a running test build (see geo_driver.asm).

geo_on: one byte per engine class (50, 100, 150, 200, 250 cc, tuning); geo_par: one set of
NAMES per kart number 0..6 (car+304h). Found by the "GEO1" marker in the exe file.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "tools"))
import patch_200cc as PATCH  # noqa: E402

NAMES = ("d0", "dv", "k", "kc", "rw", "a2", "kb", "vmin", "vmax", "eps", "lat", "on", "cl", "cs", "lead", "lh", "lg", "pf", "pt", "pl", "lc", "ls", "le", "lv", "bx", "lw", "os", "ow", "ob", "ov", "od")
INTS = ("k", "on")
NP = len(NAMES)


def set_size(exe):
    """Dwords per set: the last byte of geo_on (builds before it was there: 12)."""
    data = open(exe, "rb").read()
    off = data.find(b"GEO1")
    return data[off + 4 + 7] or 12


def marker_va(exe):
    data = open(exe, "rb").read()
    off = data.find(b"GEO1")
    assert off > 0 and data.find(b"GEO1", off + 1) < 0, "no single GEO1 marker in %s" % exe
    pe = PATCH.PE(data)
    for name, rva, vsize, roff, rsize in pe.sections():
        if roff <= off < roff + rsize:
            return PATCH.IMAGE_BASE + rva + off - roff
    raise SystemExit("marker outside the sections")


def var_va(exe):
    """Address of geo_varon (4 bytes; geo_var, 7 tables of 512 bytes, follows)."""
    data = open(exe, "rb").read()
    off = data.find(b"GEO2")
    assert off > 0 and data.find(b"GEO2", off + 1) < 0, "no single GEO2 marker in %s" % exe
    pe = PATCH.PE(data)
    for name, rva, vsize, roff, rsize in pe.sections():
        if roff <= off < roff + rsize:
            return PATCH.IMAGE_BASE + rva + off - roff + 4
    raise SystemExit("marker outside the sections")


def watch_va(exe):
    """Address of geo_wdon (8 bytes: the watch per class), then the floats WT, -WA, WD, WS."""
    data = open(exe, "rb").read()
    off = data.find(b"GEO3")
    assert off > 0 and data.find(b"GEO3", off + 1) < 0, "no single GEO3 marker in %s" % exe
    pe = PATCH.PE(data)
    for name, rva, vsize, roff, rsize in pe.sections():
        if roff <= off < roff + rsize:
            return PATCH.IMAGE_BASE + rva + off - roff + 4
    raise SystemExit("marker outside the sections")


def parse(spec):
    """'kc=1.4,a2=40' -> {'kc': 1.4, 'a2': 40.0}"""
    out = {}
    for part in filter(None, spec.split(",")):
        k, v = part.split("=")
        assert k in NAMES, "unknown driver value %r (%s)" % (k, ", ".join(NAMES))
        out[k] = int(v) if k in INTS else float(v)
    return out


def pack_value(name, v):
    return struct.pack("<i" if name in INTS else "<f", v)


def apply(write, read, exe, on=None, common=None, per_kart=None):
    """write(addr, bytes) / read(addr, n) into the game; on = 6 flags or None (keep);
    common = {name: value} for every kart; per_kart = {kart number: {name: value}}."""
    base = marker_va(exe) + 4
    np_ = set_size(exe)
    if on is not None:
        write(base, bytes(on))
    for kart in range(7):
        vals = dict(common or {})
        vals.update((per_kart or {}).get(kart, {}))
        for name, v in vals.items():
            assert NAMES.index(name) < np_, "%s is not in this build" % name
            write(base + 8 + 4 * (np_ * kart + NAMES.index(name)), pack_value(name, v))
    return base


def read_set(read, exe, kart):
    np_ = set_size(exe)
    base = marker_va(exe) + 4 + 8 + 4 * np_ * kart
    raw = read(base, 4 * np_)
    return {n: struct.unpack_from("<i" if n in INTS else "<f", raw, 4 * i)[0] for i, n in enumerate(NAMES[:np_])}
