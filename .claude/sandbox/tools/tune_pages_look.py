"""Pictures of the four tuning pages with given values (sandbox only; no keyboard, no focus, no mouse).

usage: tune_pages_look.py <out dir> [a,b,c,d,e,f,g,h,i] [--item N]

Opens the tuning page and the pages "Kart", "Welt" and "Gegner" straight from the main menu,
prints their items and saves tuning.png, kart.png, world.png, opp.png. --item selects that item on
the detail pages (the explanation follows the selection).
"""
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ghostlib as G
import ghosttest as T
import classtest as C


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = args[0]
    item = int(sys.argv[sys.argv.index("--item") + 1]) if "--item" in sys.argv else 0
    os.makedirs(out, exist_ok=True)
    T.restore()
    g = G.Game(T.NEW_EXE)
    try:
        C.set_i32(g, 0x10, 5)
        if len(args) > 1 and not args[1].isdigit():
            C.set_tune(g, [int(x) for x in args[1].split(",")])
        for page, name in ((C.PAGE_TUNING, "tuning"), (C.PAGE_KART, "kart"), (C.PAGE_WORLD, "world"), (C.PAGE_OPP, "opp")):
            g.page(page)
            time.sleep(0.6)
            if page != C.PAGE_TUNING:
                g.write(g.menu + 0x148, struct.pack("<i", item))
                time.sleep(0.4)
            for typ, y, text in C.items(g):
                print("%s  %d  y %d  %r" % (name, typ, y, text))
            g.shot(os.path.join(out, name + ".png"))
        g.page(0)
    finally:
        g.kill()


if __name__ == "__main__":
    main()
