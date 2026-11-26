"""Press a menu key in an opt_* test build and trace what the menu does for a moment.

usage: optrace.py <sel|-> <back|select|left|right> [repeat]
"""
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H
import optest as O


def snap(h, m, gp):
    state, _, sel, arrow, timer = struct.unpack("<4if", H.read(h, m + 0x140, 20))
    inj = struct.unpack("<4f", H.read(h, O.MENU_INJ, 16))
    return (state, sel, arrow, round(timer, 2), "%08X" % H.u32(h, gp + 0x4C), inj)


def main():
    h = H.open_proc(0x0438)
    m = O.menu_ptr(h)
    gp = H.u32(h, 0x5E84EC)
    for _ in range(int(sys.argv[3]) if len(sys.argv) > 3 else 1):
        if sys.argv[1] != "-":
            O.wr(h, m + 0x148, struct.pack("<i", int(sys.argv[1])))
            time.sleep(0.05)
        last = snap(h, m, gp)
        print("before", last)
        O.wr(h, O.MENU_INJ + 4 * O.KEYS[sys.argv[2]], struct.pack("<f", 1.0))
        t0 = time.time()
        while time.time() - t0 < 0.25:
            s = snap(h, m, gp)
            if s != last:
                print("  +%3.0f ms" % ((time.time() - t0) * 1000), s)
                last = s
        time.sleep(0.2)


if __name__ == "__main__":
    main()
