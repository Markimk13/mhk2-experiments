"""Test harness for driving the sandboxed game: start / shot / keys / mem / stop.

    harness.py start <exe> [args...]      launch (cwd = exe dir), remember pid
    harness.py wait <seconds>
    harness.py shot <out.png> [maxwidth]  screenshot of the game window's client area
    harness.py keys <k> [k...]            scancode key taps into the game window (e.g. down enter esc; "w:0.3" = wait)
    harness.py hold <key> <seconds>       hold a key
    harness.py mem                        dump interesting GameParameters fields
    harness.py peek <hexaddr> <count>     read dwords
    harness.py poke <hexaddr> <hexvalue>  write a dword
    harness.py alive
    harness.py stop
"""
import ctypes
import ctypes.wintypes as wt
import os
import struct
import subprocess
import sys
import time
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
# The pid of the test game this process started lives in its game folder (gameslot.spawn sets
# it). The command line (harness.py stop, ...) uses MHK2_GAME's folder, default game\.
_g = os.environ.get("MHK2_GAME", "game")
PIDFILE = os.path.join(_g if os.path.isabs(_g) else os.path.join(os.path.dirname(HERE), _g), "game.pid")


def set_pidfile(path):
    global PIDFILE
    PIDFILE = path

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
try:
    ctypes.WinDLL("shcore").SetProcessDpiAwareness(2)
except Exception:
    pass

kernel32.OpenProcess.restype = wt.HANDLE
kernel32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
kernel32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
kernel32.WriteProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
kernel32.GetExitCodeProcess.argtypes = [wt.HANDLE, ctypes.POINTER(wt.DWORD)]
kernel32.TerminateProcess.argtypes = [wt.HANDLE, wt.UINT]
user32.GetDC.restype = wt.HDC
user32.GetDC.argtypes = [wt.HWND]
user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
user32.PrintWindow.argtypes = [wt.HWND, wt.HDC, wt.UINT]
user32.GetClientRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.ClientToScreen.argtypes = [wt.HWND, ctypes.POINTER(wt.POINT)]
user32.GetForegroundWindow.restype = wt.HWND
user32.SetForegroundWindow.argtypes = [wt.HWND]
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.GetWindowTextW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
user32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]
gdi32.CreateCompatibleDC.restype = wt.HDC
gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
gdi32.CreateCompatibleBitmap.restype = wt.HBITMAP
gdi32.CreateCompatibleBitmap.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int]
gdi32.SelectObject.restype = wt.HGDIOBJ
gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
gdi32.BitBlt.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.HDC, ctypes.c_int, ctypes.c_int, wt.DWORD]
gdi32.GetDIBits.argtypes = [wt.HDC, wt.HBITMAP, wt.UINT, wt.UINT, ctypes.c_void_p, ctypes.c_void_p, wt.UINT]
gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wt.HDC]

SCAN = {"up": (0x48, True), "down": (0x50, True), "left": (0x4B, True), "right": (0x4D, True),
        "enter": (0x1C, False), "esc": (0x01, False), "space": (0x39, False), "tab": (0x0F, False),
        "ctrl": (0x1D, False), "shift": (0x2A, False), "alt": (0x38, False), "back": (0x0E, False),
        "f1": (0x3B, False), "f2": (0x3C, False), "f3": (0x3D, False), "f4": (0x3E, False),
        "a": (0x1E, False), "s": (0x1F, False), "d": (0x20, False), "w": (0x11, False),
        "x": (0x2D, False), "y": (0x15, False), "z": (0x2C, False), "m": (0x32, False), "p": (0x19, False)}


def get_pid():
    return int(open(PIDFILE).read().strip())


def open_proc(access=0x100439):
    # default: read and write memory, query, terminate, wait - not the right to start threads
    h = kernel32.OpenProcess(access, False, get_pid())
    if not h:
        raise SystemExit("cannot open process (not running?)")
    return h


def alive():
    try:
        h = kernel32.OpenProcess(0x1000, False, get_pid())  # QUERY_LIMITED_INFORMATION
    except FileNotFoundError:
        return False
    if not h:
        return False
    code = wt.DWORD()
    kernel32.GetExitCodeProcess(h, ctypes.byref(code))
    kernel32.CloseHandle(h)
    return code.value == 259


def windows(pid):
    res = []
    proto = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)

    def cb(hwnd, lparam):
        p = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
        if p.value == pid and user32.IsWindowVisible(hwnd):
            r = wt.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(r))
            t = ctypes.create_unicode_buffer(200)
            user32.GetWindowTextW(hwnd, t, 200)
            c = ctypes.create_unicode_buffer(200)
            user32.GetClassNameW(hwnd, c, 200)
            res.append((hwnd, (r.right - r.left) * (r.bottom - r.top), t.value, c.value, (r.left, r.top, r.right, r.bottom)))
        return True

    user32.EnumWindows(proto(cb), 0)
    res.sort(key=lambda x: -x[1])
    return res


def main_window():
    w = windows(get_pid())
    if not w:
        raise SystemExit("no visible window")
    return w[0][0]


def write_png(path, w, h, rgb):
    def chunk(tag, data):
        c = struct.pack(">I", len(data)) + tag + data
        return c + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    raw = bytearray()
    stride = w * 3
    for y in range(h):
        raw.append(0)
        raw += rgb[y * stride:(y + 1) * stride]
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)) + \
        chunk(b"IDAT", zlib.compress(bytes(raw), 6)) + chunk(b"IEND", b"")
    open(path, "wb").write(png)


def capture(hwnd):
    rc = wt.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(rc))
    w, h = rc.right, rc.bottom
    pt = wt.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    sdc = user32.GetDC(None)
    mdc = gdi32.CreateCompatibleDC(sdc)
    bmp = gdi32.CreateCompatibleBitmap(sdc, w, h)
    old = gdi32.SelectObject(mdc, bmp)
    gdi32.BitBlt(mdc, 0, 0, w, h, sdc, pt.x, pt.y, 0x00CC0020 | 0x40000000)  # SRCCOPY | CAPTUREBLT
    gdi32.SelectObject(mdc, old)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
                    ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
                    ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
                    ("biClrImportant", wt.DWORD)]
    bi = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, 0, 0, 0, 0, 0, 0)
    buf = ctypes.create_string_buffer(w * h * 4)
    gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bi), 0)
    gdi32.DeleteObject(bmp)
    gdi32.DeleteDC(mdc)
    user32.ReleaseDC(None, sdc)
    return w, h, buf.raw


def shot(path, maxw=1000):
    hwnd = main_window()
    w, h, bgra = capture(hwnd)
    step = 1
    while w // step > maxw:
        step += 1
    ow, oh = w // step, h // step
    out = bytearray(ow * oh * 3)
    mv = memoryview(bgra)
    o = 0
    for y in range(oh):
        row = (y * step) * w * 4
        for x in range(ow):
            p = row + x * step * 4
            out[o] = mv[p + 2]
            out[o + 1] = mv[p + 1]
            out[o + 2] = mv[p]
            o += 3
    write_png(path, ow, oh, bytes(out))
    print(f"saved {path} {ow}x{oh} (window client {w}x{h})")


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", wt.WORD), ("wScan", wt.WORD), ("dwFlags", wt.DWORD), ("time", wt.DWORD),
                ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", wt.LONG), ("dy", wt.LONG), ("mouseData", wt.DWORD), ("dwFlags", wt.DWORD),
                ("time", wt.DWORD), ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]


class _U(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wt.DWORD), ("u", _U)]


def send_scan(code, ext, up):
    flags = 0x0008 | (0x0001 if ext else 0) | (0x0002 if up else 0)
    inp = INPUT(1, _U(ki=KEYBDINPUT(0, code, flags, 0, None)))
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


def focus(hwnd):
    if user32.GetForegroundWindow() == hwnd:
        return True
    # a synthetic ALT tap lifts the foreground lock for SetForegroundWindow
    send_scan(0x38, False, False)
    send_scan(0x38, False, True)
    user32.ShowWindow(hwnd, 9)
    user32.SetForegroundWindow(hwnd)
    time.sleep(0.4)
    return user32.GetForegroundWindow() == hwnd


def keys(seq, hold=0.08, gap=0.35):
    hwnd = main_window()
    for k in seq:
        if k.startswith("w:"):
            time.sleep(float(k[2:]))
            continue
        if not focus(hwnd):
            raise SystemExit("game window is not in the foreground - not sending keys")
        code, ext = SCAN[k]
        send_scan(code, ext, False)
        time.sleep(hold)
        send_scan(code, ext, True)
        time.sleep(gap)
    print("sent", " ".join(seq))


def read(h, addr, n):
    buf = ctypes.create_string_buffer(n)
    got = ctypes.c_size_t()
    if not kernel32.ReadProcessMemory(h, ctypes.c_void_p(addr), buf, n, ctypes.byref(got)):
        raise OSError(f"read {addr:#x} failed: {ctypes.get_last_error()}")
    return buf.raw


def u32(h, addr):
    return struct.unpack("<I", read(h, addr, 4))[0]


def mem():
    h = open_proc(0x0410)
    gp = u32(h, 0x5E84EC)
    print(f"GameParameters @ {gp:#x}")
    if not gp:
        return
    raw = read(h, gp, 0x60)
    ints = struct.unpack("<24i", raw)
    names = {2: "musicVol", 3: "sfxVol", 4: "class", 5: "f14", 6: "resolution", 7: "mode", 8: "track", 9: "championship"}
    for i, v in enumerate(ints):
        if i in names:
            print(f"  +{i*4:#04x} {names[i]:<13} {v}")
    print("  numTracks", struct.unpack("<i", read(h, gp + 0xFB70, 4))[0],
          "unlockedClass", struct.unpack("<i", read(h, gp + 0xFD08, 4))[0],
          "unlockMask", bin(u32(h, gp + 0xFD0C)))
    for slot in (128, 160, 161):
        e = read(h, gp + 0x234 + slot * 0xB4, 0xB4)
        t = struct.unpack_from("<5f", e, 0)
        nm = [e[0x50 + 16 * i:0x60 + 16 * i].split(b"\0")[0].decode("latin-1") for i in range(5)]
        print(f"  highscore slot {slot}: {[round(x, 2) for x in t]} {nm}")
    for slot in (40 + 2, 50 + 2, 50 + 3):
        e = read(h, gp + 0x8934 + slot * 0x8C, 0x8C)
        t = struct.unpack_from("<5f", e, 0)
        p = struct.unpack_from("<5i", e, 0x14)
        print(f"  championship slot {slot}: {[round(x, 2) for x in t]} pts={p}")
    for slot in (128, 160, 161):
        e = read(h, gp + 0xAA04 + slot * 0x6C, 0x6C)
        trk, cls, ch = struct.unpack_from("<3i", e, 0x4C)
        tot = struct.unpack_from("<f", e, 0x58)[0]
        print(f"  phantom slot {slot}: track={trk} class={cls} char={ch} total={tot:.2f}")


def main():
    cmd = sys.argv[1]
    if cmd == "start":
        import gameslot
        p = gameslot.spawn(sys.argv[2], sys.argv[3:])
        print("started pid", p.pid)
    elif cmd == "wait":
        time.sleep(float(sys.argv[2]))
    elif cmd == "alive":
        print("alive" if alive() else "dead")
    elif cmd == "wins":
        for w in windows(get_pid()):
            print(w)
        print("foreground:", user32.GetForegroundWindow())
    elif cmd == "shot":
        shot(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 1000)
    elif cmd == "keys":
        keys(sys.argv[2:])
    elif cmd == "hold":
        hwnd = main_window()
        if not focus(hwnd):
            raise SystemExit("game window is not in the foreground")
        ks = sys.argv[2].split("+")
        for k in ks:
            send_scan(*SCAN[k], False)
        time.sleep(float(sys.argv[3]))
        for k in ks:
            send_scan(*SCAN[k], True)
        print("held", sys.argv[2], sys.argv[3])
    elif cmd == "mem":
        mem()
    elif cmd == "peek":
        h = open_proc(0x0410)
        a = int(sys.argv[2], 16)
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 8
        raw = read(h, a, 4 * n)
        for i in range(n):
            v = struct.unpack_from("<I", raw, 4 * i)[0]
            f = struct.unpack_from("<f", raw, 4 * i)[0]
            print(f"  {a + 4*i:08X}: {v:08X} {v:>11} {f:.6g}")
    elif cmd == "poke":
        h = open_proc(0x0438)
        a, v = int(sys.argv[2], 16), int(sys.argv[3], 16)
        got = ctypes.c_size_t()
        ok = kernel32.WriteProcessMemory(h, ctypes.c_void_p(a), struct.pack("<I", v), 4, ctypes.byref(got))
        print("poke", "ok" if ok else "FAILED")
    elif cmd == "stop":
        if alive():
            h = open_proc(0x0001)
            kernel32.TerminateProcess(h, 0)
            print("terminated")
        else:
            print("not running")


if __name__ == "__main__":
    main()
