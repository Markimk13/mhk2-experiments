r"""Check that test games run side by side without touching each other (gameslot.py).

usage: py parallel_check.py [n=2] [seconds=20] [exe name=c5_new60.exe]

Starts n test games, each in its own game folder (game, game2, ...), from this one process
through gameslot.spawn, then for `seconds`: are all alive, does each have its own window,
did none take the foreground, how much CPU does each use, does each answer a remote call
(through its own pid). Also checks the start rules with made-up process lists. Stops only
the games it started.
"""
import ctypes
import ctypes.wintypes as wt
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H
import gameslot as S
import remote_test as R

k32 = H.kernel32
k32.GetProcessTimes.argtypes = [wt.HANDLE] + [ctypes.POINTER(wt.FILETIME)] * 4
OK = [0, 0]


def check(label, good):
    OK[0 if good else 1] += 1
    print("  %s %s" % ("ok  " if good else "FAIL", label), flush=True)


def cpu_seconds(pid):
    h = k32.OpenProcess(0x1000, False, pid)
    t = [wt.FILETIME() for _ in range(4)]
    k32.GetProcessTimes(h, *[ctypes.byref(x) for x in t])
    k32.CloseHandle(h)
    return sum((x.dwHighDateTime << 32 | x.dwLowDateTime) for x in t[2:]) / 1e7


def rules():
    print("== start rules (made-up process lists)")
    real = {"pid": 1, "path": r"C:\Games\MHK2\MHK2-XXL.exe", "lock": True, "real": True}
    old = {"pid": 2, "path": r"C:\x\.claude\sandbox\game\old.exe", "lock": True, "real": False}
    new = {"pid": 3, "path": r"C:\x\.claude\sandbox\game2\c5.exe", "lock": False, "real": False}
    exe = os.path.join(S.SANDBOX, "game", "c5_new60.exe")
    saved = S.games, S.exe_has_lock, S.QUIET, time.sleep

    def verdict(gs, has_lock):
        S.games = lambda: gs
        S.exe_has_lock = lambda e: has_lock
        S.QUIET = 0
        time.sleep = lambda s: None
        try:
            S.wait_turn(exe, timeout=-1)
            return "start"
        except SystemExit:
            return "wait"
    try:
        check("no lock, nothing runs -> start", verdict([], False) == "start")
        check("no lock, user's game runs -> wait", verdict([real], False) == "wait")
        check("no lock, a build with lock runs -> wait", verdict([old], False) == "wait")
        check("no lock, %d other test games -> start" % (S.MAX_GAMES - 1), verdict([new] * (S.MAX_GAMES - 1), False) == "start")
        check("no lock, %d other test games -> wait" % S.MAX_GAMES, verdict([new] * S.MAX_GAMES, False) == "wait")
        check("with lock, a test game runs -> wait", verdict([new], True) == "wait")
        check("with lock, nothing runs -> start", verdict([], True) == "start")
    finally:
        S.games, S.exe_has_lock, S.QUIET, time.sleep = saved
    check("real-game test: path outside the sandboxes counts as the user's",
          not S.is_test_path(r"D:\Games\Moorhuhn Kart 2\MHK2-XXL.exe"))
    check("... a worktree's sandbox counts as a test", S.is_test_path(r"C:\r\.claude\worktrees\a\.claude\sandbox\game\x.exe"))
    check("test builds have no lock", not S.exe_has_lock(exe))
    check("the original exe has it", S.exe_has_lock(os.path.join(S.SANDBOX, "work", "MHK2-XXL.orig.exe")))


def live(n, seconds, name):
    print("== %d test games side by side for %d s" % (n, seconds))
    folders = [os.path.join(S.SANDBOX, "game" if i == 0 else "game%d" % (i + 1)) for i in range(n)]
    fg0 = H.user32.GetForegroundWindow()
    started = []
    try:
        for d in folders:
            S.claim_dir(d)
            S.sync_from_game(d)
            log = os.path.join(d, "log.txt")
            if os.path.exists(log):
                os.remove(log)
            t = time.time()
            p = S.spawn(os.path.join(d, name))
            started.append((d, p, H.PIDFILE))
            check("%s: menu reached in %.1f s (pid %d)" % (os.path.basename(d), time.time() - t, p.pid),
                  p.poll() is None and S._menu_reached(log, t))
        seen = {g["pid"] for g in S.games()}
        check("all %d are seen by gameslot.games()" % n, all(p.pid in seen for _, p, _ in started))
        c0 = {p.pid: cpu_seconds(p.pid) for _, p, _ in started}
        fg_game = False
        t0 = time.time()
        while time.time() - t0 < seconds:
            fg = H.user32.GetForegroundWindow()
            for _, p, _ in started:
                fg_game |= fg in [w[0] for w in H.windows(p.pid)]
            time.sleep(0.25)
        el = time.time() - t0
        check("none took the foreground", not fg_game)
        check("foreground as before the starts", H.user32.GetForegroundWindow() == fg0)
        for d, p, pidfile in started:
            check("%s alive after %d s" % (os.path.basename(d), seconds), p.poll() is None)
            check("%s has its own window" % os.path.basename(d), len(H.windows(p.pid)) >= 1)
            print("    CPU %.0f %% of one core" % (100 * (cpu_seconds(p.pid) - c0[p.pid]) / el))
            H.set_pidfile(pidfile)
            r = R.Remote()
            frames = H.u32(r.h, 0x5E84EC)                 # GameParameters pointer: set once the game runs
            check("%s: memory of its own process readable (pid file %s)" % (os.path.basename(d), os.path.relpath(pidfile, S.SANDBOX)),
                  frames != 0 and int(open(pidfile).read()) == p.pid)
            check("%s: answers a remote call" % os.path.basename(d), r.call(0x0057C0F7) != 0)
    finally:
        for d, p, _ in started:
            if p.poll() is None:
                p.kill()
        time.sleep(1.5)
    check("all stopped", all(p.poll() is not None for _, p, _ in started))


def main():
    a = sys.argv[1:]
    n = int(a[0]) if a else 2
    seconds = int(a[1]) if len(a) > 1 else 20
    name = a[2] if len(a) > 2 else "c5_new60.exe"
    rules()
    live(n, seconds, name)
    print("passed %d, failed %d" % tuple(OK))
    sys.exit(1 if OK[1] else 0)


if __name__ == "__main__":
    main()
