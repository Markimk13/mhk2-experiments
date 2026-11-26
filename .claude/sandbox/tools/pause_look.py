r"""Opens the pause page in a race of the sandbox game and takes a screenshot (sandbox).

usage: pause_look.py <out.png> [--cls 5] [--track 0] [--mode 0] [--exe path] [--tune v1,..,v9] [--phys60 on|off]

Starts a time trial (mode 0) through the test build's command slot, then pauses it the way
the race does on "Escape" (race state +148h, menu SetPage 0Ah / 0Bh) and prints the pause
page's items. No keys, no focus.
"""
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H      # noqa: E402
import ghostlib as G     # noqa: E402
import ghosttest as T    # noqa: E402
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "tools"))
import patch_200cc as P  # noqa: E402

PAUSE_FLAG, PAUSE_MENU, RACE_MODE = 0x148, 0x144, 0x118
MENU_FREEZE = 0x00410EE0     # what the race calls on the menu before it shows the pause page
PAGE_SET = 0x00413DD0
TUNE_VALUES = 0x2E4C         # nine dwords in GameParameters (see the patcher)
PHYS_FLAG = 0x4C             # the 60 FPS switch: bytes "60F" behind the bool


def pause(g):
    st = g.u32(g.u32(0x5E851C) + 4)
    menu = g.u32(st + PAUSE_MENU)
    mode = g.u32(st + RACE_MODE)
    g.write(st + 0xC8, struct.pack("<i", 0))
    g.write(st + 0xCC, struct.pack("<f", 1.0))
    g.write(st + PAUSE_FLAG, b"\x01")
    g.r.call(MENU_FREEZE, ecx=menu)
    page = 0x0B if mode in (2, 4) else 0x0A
    g.r.call(PAGE_SET, ecx=menu, args=(page,))
    time.sleep(0.8)
    return menu, page


def items(g, menu):
    begin, end = struct.unpack("<II", g.read(menu + 0x134, 8))
    n = (end - begin) // 0x54 if begin else 0
    out = []
    for i in range(n):
        e = begin + i * 0x54
        out.append((struct.unpack("<i", g.read(e, 4))[0], G.O.read_str(g.h, e + 8)))
    return out


def main():
    a = sys.argv[1:]

    def opt(name, default):
        if name in a:
            i = a.index(name)
            v = a[i + 1]
            del a[i:i + 2]
            return v
        return default
    cls, track, mode = int(opt("--cls", "5")), int(opt("--track", "0")), int(opt("--mode", "0"))
    exe = opt("--exe", T.NEW_EXE)
    tune = opt("--tune", None)
    phys = opt("--phys60", None)
    g = G.Game(exe)
    try:
        if tune:
            g.write(g.gp + TUNE_VALUES, struct.pack("<9i", *map(int, tune.split(","))))
            for off, magic in ((P.TUNE_MARK, P.TUNE_MAGIC), (P.VALUES8_MARK, P.VALUES8_MAGIC), (P.OPP_MARK, P.OPP_MAGIC)):
                g.write(g.gp + off, struct.pack("<I", magic))     # else the game converts them as an old save
        if phys:
            g.write(g.gp + PHYS_FLAG + 1, b"60F" if phys == "on" else b"\0\0\0")
        g.start_time_trial(cls, track, mode)
        time.sleep(2.0)
        menu, page = pause(g)
        print("page %02Xh" % page)
        for it in items(g, menu):
            print("  ", it)
        g.shot(a[0])
    finally:
        g.kill()


if __name__ == "__main__":
    main()
