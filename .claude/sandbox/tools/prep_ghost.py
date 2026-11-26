"""Unattended test build for the phantom kart changes (sandbox only).

usage: prep_ghost.py <exe (original or patched)> <out exe> [fps cap]

prep_opt's build (windowed, no focus needed, menu page command, injected options keys)
plus a one-shot "menu select" for the result pages and the name entry: write 1.0f to NAME_INJ.
"""
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import prep_fps as P
import prep_opt as PO

# "menu select" reads of the result pages (function 00421970, menu states 0Eh..15h):
# result overlay "Weiter", result list buttons, three more pages, name entry "confirm"
SELECT_SITES = (0x004219E3, 0x00421A8B, 0x00421BDB, 0x00421C4F, 0x00421CA5, 0x004222CA)
NAME_STUB = 0x00593A40          # unused bytes behind the code
NAME_INJ = 0x00884F50           # unused, zero-initialised, writable (slack behind .data)


def name_hook(d):
    a = struct.pack("<I", NAME_INJ)
    PO.put(d, NAME_STUB, bytes([0xD9, 0x05]) + a + bytes([0xC7, 0x05]) + a + bytes(4) + bytes([0xC2, 0x04, 0x00]))
    for site in SELECT_SITES:
        P.patch(d, site, (bytes([0xE8]) + struct.pack("<i", 0x0045C890 - (site + 5))).hex(" "),
                bytes([0xE8]) + struct.pack("<i", NAME_STUB - (site + 5)))


def main():
    src, out = sys.argv[1:3]
    fps = int(sys.argv[3]) if len(sys.argv) > 3 else None
    data = open(src, "rb").read()
    if fps:
        d = P.build(data, "frame", 1.0 / fps - 1e-5, auto=True)
    else:
        d = P.build(data, None, 0.005, auto=True)
    PO.menu_hooks(d)
    name_hook(d)
    open(out, "wb").write(d)
    print("built", out, "cap", fps or "stock (200)")


if __name__ == "__main__":
    main()
