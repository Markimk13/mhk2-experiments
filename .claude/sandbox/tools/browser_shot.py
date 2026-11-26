"""Take a picture of the time trial highscore browser (main menu -> Highscore -> Zeitfahren).

usage: browser_shot.py <test exe> <out.png> [menu state, default 17h]

Menu states: 0..0Dh main menu pages, 0Eh..15h result pages, 16h "Highscore" (choose a list),
17h/18h time trial lists, 19h/1Ah championship lists. Sandbox only; no keyboard, no focus.
"""
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ghostlib as G


def main():
    exe, out = sys.argv[1], sys.argv[2]
    state = int(sys.argv[3], 16) if len(sys.argv) > 3 else 0x17
    g = G.Game(exe)
    try:
        g.page(state)
        time.sleep(0.8)
        rows = [t.replace("<font 30px_redoutline><scale 0.5>", "").replace("</scale></font>", "") for _, t in g.menu_items()]
        print("state %Xh, %d items:" % (state, len(rows)), rows, flush=True)
        g.shot(out)
        g.page(0)
    finally:
        g.kill()


if __name__ == "__main__":
    main()
