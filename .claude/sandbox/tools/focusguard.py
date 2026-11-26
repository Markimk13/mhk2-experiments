"""Watch that the sandboxed test game does not keep the keyboard focus.

usage: focusguard.py <pid> [hwnd that had the focus before the launch]
       (started by optest.launch; ends with the game or after 20 minutes)

The test builds do not activate their window (prep_fps.py, no_activation). Should a window of
the game become the foreground window anyway, this script writes the handle of the window that
was in the foreground before into the game's hand-back slot; the game then passes the foreground
on itself, at its next frame (only the process that owns the foreground may do that).
No code is put into the game's process.
"""
import ctypes
import ctypes.wintypes as wt
import os
import struct
import sys
import time

LOG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "focusguard.log")
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
u32 = ctypes.WinDLL("user32", use_last_error=True)
k32.OpenProcess.restype = wt.HANDLE
k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
k32.WriteProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
k32.GetExitCodeProcess.argtypes = [wt.HANDLE, ctypes.POINTER(wt.DWORD)]
u32.GetForegroundWindow.restype = wt.HWND
u32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
u32.IsWindow.argtypes = [wt.HWND]
u32.GetWindow.restype = wt.HWND
u32.GetWindow.argtypes = [wt.HWND, wt.UINT]
u32.GetTopWindow.restype = wt.HWND
u32.GetTopWindow.argtypes = [wt.HWND]
u32.IsIconic.argtypes = [wt.HWND]
u32.IsWindowVisible.argtypes = [wt.HWND]
u32.GetWindowLongW.argtypes = [wt.HWND, ctypes.c_int]
u32.GetWindowRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
u32.GetClassNameW.argtypes = [wt.HWND, wt.LPWSTR, ctypes.c_int]

HANDBACK_VA = 0x00884F90            # the test build's hand-back slot (prep_fps.py)
SHELL_CLASSES = ("Progman", "WorkerW", "Shell_TrayWnd")
ACCESS = 0x0008 | 0x0020 | 0x1000   # write memory (two rights), query limited information


def owner(hwnd):
    p = wt.DWORD()
    u32.GetWindowThreadProcessId(hwnd, ctypes.byref(p))
    return p.value


def below(pid):
    """First ordinary visible window under the game's windows in the z-order."""
    w = u32.GetTopWindow(None)
    seen_game = False
    for _ in range(500):
        if not w:
            break
        if owner(w) == pid:
            seen_game = True
        elif seen_game and u32.IsWindowVisible(w) and not u32.IsIconic(w):
            r = wt.RECT()
            u32.GetWindowRect(w, ctypes.byref(r))
            c = ctypes.create_unicode_buffer(100)
            u32.GetClassNameW(w, c, 100)
            tool = u32.GetWindowLongW(w, -20) & 0x80
            if not tool and r.right - r.left > 200 and r.bottom - r.top > 100 and c.value not in SHELL_CLASSES:
                return w
        w = u32.GetWindow(w, 2)
    return None


def main():
    pid = int(sys.argv[1])
    h = k32.OpenProcess(ACCESS, False, pid)
    if not h:
        return
    last_other = int(sys.argv[2]) if len(sys.argv) > 2 else None
    t_end = time.time() + 20 * 60
    while time.time() < t_end:
        code = wt.DWORD()
        if not k32.GetExitCodeProcess(h, ctypes.byref(code)) or code.value != 259:
            break
        fg = u32.GetForegroundWindow()
        if fg and owner(fg) == pid:
            ok = last_other and u32.IsWindow(last_other) and owner(last_other) != pid
            target = last_other if ok else below(pid)
            if target:
                n = ctypes.c_size_t()
                k32.WriteProcessMemory(h, ctypes.c_void_p(HANDBACK_VA), struct.pack("<I", target), 4, ctypes.byref(n))
                try:                    # so a test run can tell whether the game ever held the foreground
                    with open(LOG, "a") as f:
                        f.write("%s pid %d was in the foreground, handed back to %#x\n" % (time.strftime("%H:%M:%S"), pid, target))
                except OSError:
                    pass
                time.sleep(0.05)
        elif fg:
            last_other = fg
        time.sleep(0.01)


if __name__ == "__main__":
    main()
