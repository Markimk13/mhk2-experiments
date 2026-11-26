"""Picture of the tuning page (sandbox only; no keyboard, no focus, no mouse).

usage: tune_shot.py <out.png> [values a,b,c,d,e,f,g] [--item N]

Starts the test build game/ghost_new.exe on the fixtures, writes the seven tuning values (if
given) into GameParameters, opens the tuning page (page 1Dh), selects item N (0 = "Vorlage",
1..7 the values, 8 "Zurücksetzen", 9 "Weiter") and saves a screenshot of the window.
"""
import argparse
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ghostlib as G
import ghosttest as T
import classtest as C


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("values", nargs="?")
    ap.add_argument("--item", type=int, default=9)
    args = ap.parse_args()
    T.restore()
    g = G.Game(T.NEW_EXE)
    try:
        g.page(C.PAGE_TUNING)                   # builds the page; a fresh save gets the defaults
        time.sleep(0.6)
        if args.values:
            C.set_tune(g, [int(v) for v in args.values.split(",")])
            g.page(C.PAGE_TUNING)               # again, so the rows show the values
            time.sleep(0.6)
        g.write(g.menu + 0x148, struct.pack("<i", args.item))
        time.sleep(0.6)
        g.shot(args.out)
        print("\n".join(t for _, _, t in C.items(g)))
        g.page(0)
    finally:
        g.kill()


if __name__ == "__main__":
    main()
