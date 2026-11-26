"""Open a menu page straight from the main menu, print its items and save a screenshot
(sandbox only; no keyboard, no focus, no mouse).

usage: page_look.py <page hex> <out.png> [exe]
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ghostlib as G
import ghosttest as T
import classtest as C


def main():
    page = int(sys.argv[1], 16)
    out = sys.argv[2]
    exe = sys.argv[3] if len(sys.argv) > 3 else T.NEW_EXE
    T.restore()
    g = G.Game(exe)
    try:
        g.page(page)
        time.sleep(0.8)
        print("page %02X, state %02X" % (page, g.menu_state()))
        for n, (typ, y, text) in enumerate(C.items(g)):
            print("%2d type %d y %4d  %r" % (n, typ, y, text))
        g.shot(out)
        g.page(0)
        time.sleep(0.3)
    finally:
        g.kill()


if __name__ == "__main__":
    main()
