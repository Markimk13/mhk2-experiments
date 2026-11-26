"""How long does a test build hold the foreground while it starts?

usage: focus_probe.py <test exe> [seconds, default 12]

Starts the build the usual way (optest.launch, with the focus guard as safety net) and samples
the foreground window about every millisecond. Prints for how long, and during which part of
the start-up (bytes of log.txt written so far), a window of the game was the foreground window.
Only observes; the game is ended afterwards.
"""
import ctypes
import ctypes.wintypes as wt
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H
import optest as O
import ghostlib as G


def main():
    exe = os.path.abspath(sys.argv[1])
    seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 12.0
    log = os.path.join(os.path.dirname(exe), "log.txt")
    G.wait_free()
    if os.path.exists(log):
        os.remove(log)
    p = O.launch(exe)
    t0 = time.perf_counter()
    spans, cur = [], None
    pid = wt.DWORD()
    while time.perf_counter() - t0 < seconds and p.poll() is None:
        fg = H.user32.GetForegroundWindow()
        H.user32.GetWindowThreadProcessId(fg, ctypes.byref(pid))
        mine = pid.value == p.pid
        now = time.perf_counter() - t0
        if mine and cur is None:
            try:
                size = os.path.getsize(log)
            except OSError:
                size = 0
            cur = [now, now, size]
            cls = ctypes.create_unicode_buffer(100)
            title = ctypes.create_unicode_buffer(100)
            H.user32.GetClassNameW(fg, cls, 100)
            H.user32.GetWindowTextW(fg, title, 100)
            H.user32.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
            style = H.user32.GetWindowLongW(fg, -16) & 0xFFFFFFFF
            ex = H.user32.GetWindowLongW(fg, -20) & 0xFFFFFFFF
            print("   %.3f s: foreground window %#x class %r title %r style %08X exstyle %08X visible %d"
                  % (now, fg, cls.value, title.value, style, ex, H.user32.IsWindowVisible(fg)), flush=True)
        elif mine:
            cur[1] = now
        elif cur is not None:
            spans.append(cur)
            cur = None
        time.sleep(0.001)
    if cur is not None:
        spans.append(cur)
    reached = O.init_count(log)
    total = sum(b - a for a, b, _ in spans)
    print("menu reached: %s | foreground held %d time(s), %.3f s in total" % (bool(reached), len(spans), total))
    text = open(log, "rb").read() if os.path.exists(log) else b""
    for a, b, size in spans:
        last = text[:size].decode("latin-1").strip().splitlines()[-1:] or ["(log empty)"]
        print("   from %.3f s to %.3f s after the start; last log line before it: %r" % (a, b, last[0][:70]))
    if H.alive():
        H.kernel32.TerminateProcess(H.open_proc(0x0001), 0)


if __name__ == "__main__":
    main()
