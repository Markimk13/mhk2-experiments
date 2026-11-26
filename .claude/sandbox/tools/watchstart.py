import sys, time, os, subprocess, ctypes
import ctypes.wintypes as wt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H
exe = os.path.abspath(sys.argv[1])
p = subprocess.Popen([exe] + sys.argv[2:], cwd=os.path.dirname(exe))
open(H.PIDFILE, "w").write(str(p.pid))
seen = set()
t0 = time.time()
user32 = H.user32
def all_windows(pid):
    res = []
    proto = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, lparam):
        pp = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pp))
        if pp.value == pid:
            res.append(hwnd)
            def cb2(h2, l2):
                res.append(h2); return True
            user32.EnumChildWindows(hwnd, proto(cb2), 0)
        return True
    user32.EnumWindows(proto(cb), 0)
    return res
while time.time() - t0 < float(os.environ.get("WATCH", "6")) and p.poll() is None:
    for hwnd in all_windows(p.pid):
        r = wt.RECT(); c = wt.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(r)); user32.GetClientRect(hwnd, ctypes.byref(c))
        t = ctypes.create_unicode_buffer(100); user32.GetWindowTextW(hwnd, t, 100)
        k = ctypes.create_unicode_buffer(100); user32.GetClassNameW(hwnd, k, 100)
        key = (hwnd, r.left, r.top, r.right, r.bottom, c.right, c.bottom, bool(user32.IsWindowVisible(hwnd)))
        if key not in seen:
            seen.add(key)
            print(f"{time.time()-t0:5.2f}s hwnd={hwnd:#x} class={k.value!r} title={t.value!r} win=({r.left},{r.top},{r.right},{r.bottom}) client={c.right}x{c.bottom} visible={bool(user32.IsWindowVisible(hwnd))} iconic={bool(user32.IsIconic(hwnd))}")
    time.sleep(0.03)
print("exit code", p.poll())
