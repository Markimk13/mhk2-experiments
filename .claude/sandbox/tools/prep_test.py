"""Prepare the sandbox: muted settings.dat with test data + a windowed test build of an exe.

usage: prep_test.py <gamedir> <exe to derive the windowed test build from> [--locked]
"""
import os
import struct
import sys

HS_BASE, HS_SIZE = 0x234, 0xB4
CH_BASE, CH_SIZE = 0x8934, 0x8C


def main():
    game, exe = sys.argv[1], sys.argv[2]
    locked = "--locked" in sys.argv
    s = bytearray(open(os.path.join(game, "settings.orig.dat"), "rb").read())
    obj = lambda off: off - 4
    struct.pack_into("<ii", s, obj(0x08), 0, 0)                 # music / sfx volume
    struct.pack_into("<i", s, obj(0x18), 0)                     # resolution 640x480 (fits the default frame)
    struct.pack_into("<i", s, obj(0xFD08), 2 if locked else 3)  # highest unlocked class
    # recognisable 200 cc records in the remapped slots
    e = obj(HS_BASE + 160 * HS_SIZE)                            # class 3, track 0 -> slot 160
    struct.pack_into("<f", s, e + 0x00, 99.99)
    struct.pack_into("<3f", s, e + 0x14, 33.11, 33.22, 33.66)
    s[e + 0x50:e + 0x60] = b"TEST200".ljust(16, b"\0")
    struct.pack_into("<i", s, e + 0xA0, 6)
    c = obj(CH_BASE + 52 * CH_SIZE)                             # class 3, championship 2 -> slot 52
    struct.pack_into("<f", s, c + 0x00, 555.55)
    struct.pack_into("<i", s, c + 0x14, 38)
    s[c + 0x28:c + 0x38] = b"CHAMP200".ljust(16, b"\0")
    struct.pack_into("<i", s, c + 0x78, 6)
    open(os.path.join(game, "settings.dat"), "wb").write(s)

    d = bytearray(open(exe, "rb").read())
    off = 0x0046F8B7 - 0x400000          # .text: file offset == rva
    assert d[off - 3:off + 1] == bytes.fromhex("C6 40 0C 01"), d[off - 3:off + 1].hex()
    d[off] = 0                           # fullscreen flag off -> framed 800x600 window
    # The frame is sized with SM_CXFRAME/SM_CYFRAME, which leaves the client area a few
    # pixels short on current Windows and RenderWare then refuses the 800x600 camera
    # raster. Use SM_CXICON/SM_CYICON (32 px) instead so the client area is big enough.
    for va, old, new in ((0x0046F94A, "6A 20", "6A 0B"), (0x0046F94E, "6A 21", "6A 0C")):
        o = va - 0x400000
        assert d[o:o + 2] == bytes.fromhex(old)
        d[o:o + 2] = bytes.fromhex(new)
    out = os.path.join(game, os.path.splitext(os.path.basename(exe))[0] + ".win.exe")
    open(out, "wb").write(d)
    print("prepared", out, "locked" if locked else "unlocked")


if __name__ == "__main__":
    main()
