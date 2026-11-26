"""Simulated-mouse test of the options page (needs a build from prep_opt.py --mouse).

usage: mousetest.py <exe>

Finds where the menu sees the new switch and its two arrows, clicks each, and checks the
switch, the "keep the cursor on the arrow" request and "Zurück". Nothing touches the real mouse.
"""
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H
import optest as O

MOUSE_INJ = 0x00884F30
WARP_LOG = 0x00884F40
OK = True


def check(label, got, want):
    global OK
    good = got == want
    OK &= good
    print(f"  {'ok  ' if good else 'FAIL'} {label}: {got!r}" + ("" if good else f"  (expected {want!r})"))


def main():
    O.start(sys.argv[1])
    h = H.open_proc(0x0438)
    gp = H.u32(h, 0x5E84EC)
    O.wr(h, O.CMD_VA, struct.pack("<i", 2))          # options page
    time.sleep(0.5)
    m = O.menu_ptr(h)

    def mouse(x, y):
        O.wr(h, MOUSE_INJ, struct.pack("<3f", 1.0, x, y))
        time.sleep(0.04)
        return struct.unpack("<ii", H.read(h, m + 0x148, 8))

    def flag():
        return "%06X" % (H.u32(h, gp + 0x4C) >> 8)

    def text(i):
        return O.read_str(h, H.u32(h, m + 0x134) + i * 0x54 + 8)

    def warps():
        return struct.unpack("<3i", H.read(h, WARP_LOG, 12))

    def click():
        O.wr(h, O.MENU_INJ + 4, struct.pack("<f", 1.0))
        time.sleep(0.15)

    # map the page: which item / arrow does the menu report under each point?
    hits = {}
    for y in range(90, 470, 6):
        for x in range(180, 470, 6):
            sel, arrow = mouse(float(x), float(y))
            if sel >= 0:
                hits.setdefault((sel, arrow), []).append((x, y))
    for key in sorted(hits):
        pts = hits[key]
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        print(f"  item {key[0]} arrow {key[1]:2d}: x {min(xs)}..{max(xs)}  y {min(ys)}..{max(ys)}  ({text(key[0])!r})")
    check("the new switch can be hovered", any(k[0] == 8 for k in hits), True)
    check("both arrows of the switch are found", (8, 1) in hits and (8, 2) in hits, True)
    check("the heading is not selectable", any(k[0] == 7 for k in hits), False)

    def centre(key):
        pts = hits[key]
        return sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts)

    for arrow in (1, 2):
        x, y = centre((8, arrow))
        before, w0 = flag(), warps()[0]
        check(f"hover arrow {arrow}", mouse(x, y), (8, arrow))
        click()
        after = flag()
        check(f"click on arrow {arrow} flips the switch", after != before, True)
        check(f"text follows ({after})", text(8), "An" if after == "463036" else "Aus")
        w = warps()
        check("the cursor is asked to follow the arrow once", w[0] - w0, 1)
        print(f"       (requested cursor position {w[1]}, {w[2]}; clicked at {x:.0f}, {y:.0f})")
    if (8, 0) in hits:
        x, y = centre((8, 0))
        before, w0 = flag(), warps()[0]
        mouse(x, y)
        click()
        check("click on the value itself flips it too", flag() != before, True)
        check("... without moving the cursor", warps()[0] - w0, 0)
    # stock item with arrows still behaves
    if (6, 1) in hits:
        x, y = centre((6, 1))
        mouse(x, y)
        click()
        check("quality: click on the left arrow", text(6), "Mittel")
        x, y = centre((6, 2))
        mouse(x, y)
        click()
        # the first click's warp request is not carried out here, so hover again before judging
        if text(6) != "Hoch":
            mouse(x, y)
            click()
        check("quality: click on the right arrow", text(6), "Hoch")
    back = [k for k in hits if k[0] == 9]
    check("'Zurück' can be hovered", bool(back), True)
    if back:
        x, y = centre(back[0])
        mouse(x, y)
        click()
        time.sleep(0.3)
        check("click on 'Zurück' returns to the main menu", H.u32(h, O.menu_ptr(h) + 0x140), 0)
    O.wr(h, MOUSE_INJ, struct.pack("<3f", 0.0, 0.0, 0.0))
    print("ALL OK" if OK else "FAILURES")
    H.kernel32.TerminateProcess(H.open_proc(0x0001), 0)


if __name__ == "__main__":
    try:
        main()
    except BaseException as e:
        try:
            if H.alive():
                H.kernel32.TerminateProcess(H.open_proc(0x0001), 0)
        except Exception:
            pass
        if not isinstance(e, SystemExit) or e.code not in (None, 0):
            raise
