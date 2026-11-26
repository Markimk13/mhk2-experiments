"""Drive an opt_* test build without keyboard or focus.

    optest.py start <exe>          launch and wait for the menu
    optest.py page <state>         switch menu page (1 = options, 0 = main menu)
    optest.py sel <index>          set the selected item
    optest.py press <back|select|left|right> [n]
    optest.py info                 menu state, selected item, item list, physics flag
    optest.py shot <png>           screenshot of the game window's own surface
"""
import ctypes
import ctypes.wintypes as wt
import os
import struct
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H

CMD_VA = 0x00884F20
MENU_INJ = 0x00884F10
KEYS = {"back": 0, "select": 1, "left": 2, "right": 3}


def wr(h, addr, data):
    n = ctypes.c_size_t()
    assert H.kernel32.WriteProcessMemory(h, ctypes.c_void_p(addr), data, len(data), ctypes.byref(n))


def menu_ptr(h):
    return H.u32(h, H.u32(h, 0x5E851C) + 4)


def init_count(log):
    try:
        return open(log, "r", encoding="latin-1").read().count("GameMK2::Init done")
    except OSError:
        return 0


def launch(exe):
    """Start the game without letting its window take the keyboard focus."""
    # SW_SHOWNOACTIVATE (MFC passes it on to its frame window); the window may still take the
    # foreground once: focusguard.py hands it straight back. gameslot.spawn also claims the
    # game folder and waits until this build may run next to what else runs.
    import gameslot
    return gameslot.spawn(exe)


def start(exe):
    exe = os.path.abspath(exe)
    log = os.path.join(os.path.dirname(exe), "log.txt")
    if os.path.exists(log):
        os.remove(log)
    before = H.user32.GetForegroundWindow()
    p = launch(exe)
    t0 = time.time()
    while init_count(log) < 1:
        if time.time() - t0 > 60 or p.poll() is not None:
            raise SystemExit("game did not reach the menu")
        time.sleep(0.5)
    time.sleep(3.0)
    fg = H.user32.GetForegroundWindow()
    mine = [w[0] for w in H.windows(p.pid)]
    print("menu reached, pid", p.pid, "| game took the focus:", fg in mine, "| foreground unchanged:", fg == before)


def read_str(h, a):
    size, cap = struct.unpack("<II", H.read(h, a + 0x14, 8))
    buf = a + 4 if cap < 16 else H.u32(h, a + 4)
    return H.read(h, buf, min(size, 400)).decode("cp1252", "replace")


def info():
    h = H.open_proc(0x0410)
    m = menu_ptr(h)
    state, _, sel, arrow = struct.unpack("<4i", H.read(h, m + 0x140, 16))
    begin, end = struct.unpack("<II", H.read(h, m + 0x134, 8))
    n = (end - begin) // 0x54 if begin else 0
    gp = H.u32(h, 0x5E84EC)
    flag = H.u32(h, gp + 0x4C)
    print(f"menu {m:#x} state {state} selected {sel} arrow {arrow} items {n}  GP+4C = {flag:08X}")
    for i in range(n):
        it = begin + i * 0x54
        typ, al = struct.unpack("<ii", H.read(h, it, 8))
        x, y = struct.unpack("<ff", H.read(h, it + 0x24, 8))
        print(f"  [{i}] type {typ} align {al} y {y:5.0f}  {read_str(h, it + 8)!r}")


def shot(path):
    """Copy the game window's own surface (works while it is covered; PrintWindow stalls the game)."""
    hwnd = H.main_window()
    rc = wt.RECT()
    H.user32.GetClientRect(hwnd, ctypes.byref(rc))
    w, hgt = rc.right, rc.bottom
    wdc = H.user32.GetDC(hwnd)
    mdc = H.gdi32.CreateCompatibleDC(wdc)
    bmp = H.gdi32.CreateCompatibleBitmap(wdc, w, hgt)
    old = H.gdi32.SelectObject(mdc, bmp)
    H.gdi32.BitBlt(mdc, 0, 0, w, hgt, wdc, 0, 0, 0x00CC0020)
    H.gdi32.SelectObject(mdc, old)

    class BIH(ctypes.Structure):
        _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                    ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                    ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                    ("biClrImportant", wt.DWORD)]
    bi = BIH(ctypes.sizeof(BIH), w, -hgt, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * hgt * 4)
    H.gdi32.GetDIBits(mdc, bmp, 0, hgt, buf, ctypes.byref(bi), 0)
    H.gdi32.DeleteObject(bmp)
    H.gdi32.DeleteDC(mdc)
    H.user32.ReleaseDC(hwnd, wdc)
    raw = buf.raw
    # the game is not DPI aware: its picture only fills the unscaled part of the surface
    try:
        scale = H.user32.GetDpiForSystem() / max(H.user32.GetDpiForWindow(hwnd), 1)
    except Exception:
        scale = 1.0
    cw, ch = int(round(w / scale)), int(round(hgt / scale))
    out = bytearray(cw * ch * 3)
    for y in range(ch):
        row = raw[y * w * 4:(y * w + cw) * 4]
        o = y * cw * 3
        out[o:o + cw * 3:3] = row[2::4]
        out[o + 1:o + cw * 3:3] = row[1::4]
        out[o + 2:o + cw * 3:3] = row[0::4]
    H.write_png(path, cw, ch, bytes(out))
    nonblack = sum(1 for i in range(0, len(out), 997) if out[i])
    print(f"saved {path} {cw}x{ch} nonblack-samples={nonblack}")


def main():
    cmd = sys.argv[1]
    if cmd == "start":
        start(sys.argv[2])
        return
    if cmd == "shot":
        shot(sys.argv[2])
        return
    if cmd == "info":
        info()
        return
    h = H.open_proc(0x0438)
    if cmd == "page":
        wr(h, CMD_VA, struct.pack("<i", int(sys.argv[2]) + 1))
        time.sleep(0.5)
    elif cmd == "sel":
        wr(h, menu_ptr(h) + 0x148, struct.pack("<i", int(sys.argv[2])))
        time.sleep(0.2)
    elif cmd == "press":
        for _ in range(int(sys.argv[3]) if len(sys.argv) > 3 else 1):
            wr(h, MENU_INJ + 4 * KEYS[sys.argv[2]], struct.pack("<f", 1.0))
            time.sleep(0.3)
    info()


if __name__ == "__main__":
    main()
