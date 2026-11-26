"""Unattended test builds for the options menu / suspension setting (sandbox only).

usage: prep_opt.py <exe (original or patched)> <out exe> [fps cap]

On top of prep_fps' windowed + autonomous changes this adds test-only hooks:
  * CMD_VA: write state+1 there and the menu switches to that page on its own thread
    (1 = options, 0 = main menu, 5 = resolution list)
  * the options page takes "back / select / left / right" from one-shot floats at MENU_INJ
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prep_fps as P

BASE = 0x400000
HOOK_VA = 0x00593940        # unused bytes behind the code
MENU_STUBS = 0x00593980
CMD_VA = 0x00884F20         # unused, zero-initialised, writable (end of .data)
MENU_INJ = 0x00884F10       # back, select, left, right
SITES = (0x0041FB47, 0x0041FB70, 0x0041FD59, 0x0041FE15)


def put(d, va, blob):
    o = va - BASE
    assert not any(d[o:o + len(blob)]), hex(va)
    d[o:o + len(blob)] = blob


def menu_hooks(d):
    # stay "active" when the window loses the focus (the stock frame loop idles then)
    P.patch(d, 0x004728F2, "C6 05 94 4F 5C 00 00", bytes.fromhex("C6 05 94 4F 5C 00 01"))
    # command hook in front of the options updater (called every frame of the menu)
    code = b"\xA1" + struct.pack("<I", CMD_VA) + b"\x85\xC0" + b"\x74\x13"
    code += b"\xC7\x05" + struct.pack("<I", CMD_VA) + b"\0\0\0\0"
    code += b"\x48\x51\x50"
    code += b"\xE8" + struct.pack("<i", 0x00413DD0 - (HOOK_VA + len(code) + 5))
    code += b"\x59"
    assert len(code) == 9 + 0x13, len(code)
    code += b"\xE9" + struct.pack("<i", 0x0041F7B0 - (HOOK_VA + len(code) + 5))
    put(d, HOOK_VA, code)
    P.patch(d, 0x004149B2, (b"\xE8" + struct.pack("<i", 0x0041F7B0 - 0x004149B7)).hex(" "),
            b"\xE8" + struct.pack("<i", HOOK_VA - 0x004149B7))
    for n, site in enumerate(SITES):
        va = MENU_STUBS + 0x20 * n
        a = struct.pack("<I", MENU_INJ + 4 * n)
        put(d, va, b"\xD9\x05" + a + b"\xC7\x05" + a + b"\0\0\0\0" + b"\xC2\x04\x00")
        P.patch(d, site, (b"\xE8" + struct.pack("<i", 0x0045C890 - (site + 5))).hex(" "),
                b"\xE8" + struct.pack("<i", va - (site + 5)))


MOUSE_STUBS = 0x00593A00
MOUSE_INJ = 0x00884F30      # floats: "moved" flag, x, y (back buffer pixels)
WARP_LOG = 0x00884F40       # dwords: number of cursor warps, last x, last y


def mouse_hooks(d):
    """Simulated mouse for the menu; the real cursor is never read or moved."""
    for n, site in enumerate((0x00411810, 0x00411AA1, 0x00411AB6)):
        va = MOUSE_STUBS + 0x10 * n
        put(d, va, bytes([0xD9, 0x05]) + struct.pack("<I", MOUSE_INJ + 4 * n) + bytes([0xC2, 0x04, 0x00]))
        P.patch(d, site, (bytes([0xE8]) + struct.pack("<i", 0x0045C890 - (site + 5))).hex(" "),
                bytes([0xE8]) + struct.pack("<i", va - (site + 5)))
    # 00472CE0 warps the Windows cursor (x, y): only log the request
    stub = bytes([0x8B, 0x44, 0x24, 0x04, 0xA3]) + struct.pack("<I", WARP_LOG + 4)
    stub += bytes([0x8B, 0x44, 0x24, 0x08, 0xA3]) + struct.pack("<I", WARP_LOG + 8)
    stub += bytes([0xFF, 0x05]) + struct.pack("<I", WARP_LOG) + bytes([0xC3])
    P.patch(d, 0x00472CE0, "83 EC 18 8B 0D C8 B0 87 00 8D 44 24 08 50 51 FF 15 44 55 59 00 8B 54 24 1C", stub)


def main():
    args = [a for a in sys.argv[1:] if a not in ("--fresh", "--mouse")]
    fresh = "--fresh" in sys.argv
    src, out = args[:2]
    fps = int(args[2]) if len(args) > 2 else None
    data = open(src, "rb").read()
    if fps:
        d = P.build(data, "frame", 1.0 / fps - 1e-5, auto=True)
    else:
        d = P.build(data, None, 0.005, auto=True)
    menu_hooks(d)
    if "--mouse" in sys.argv:
        mouse_hooks(d)
    if fresh:
        # test-only defaults for a run without settings.dat: muted, 640x480 (fits the test window)
        P.patch(d, 0x004030A5, "89 46 08 89 46 0C", bytes.fromhex("89 5E 08 89 5E 0C"))
        P.patch(d, 0x004030C9, "C7 46 18 01 00 00 00", bytes.fromhex("C7 46 18 00 00 00 00"))
    open(out, "wb").write(d)
    print("built", out, "cap", fps or "stock (200)", "fresh-settings defaults" if fresh else "")


if __name__ == "__main__":
    main()
