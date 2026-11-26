r"""Starting test games so that several can run at once and nothing gets in each other's way.

Every test game is started through `spawn()` here. It keeps these rules:

1. One game per game folder. A test game writes settings.dat, log.txt and data\Phantom in its
   own folder, and the scenarios put the fixtures back into that folder before each start, so
   a folder belongs to one test process at a time: `claim_dir()` holds a lock file in it
   (`.claim.lock`, released by Windows when the process ends, even if it crashes) and also
   waits while any game process still runs from that folder (an orphaned game).
2. Never next to the user's real game. A test start pops a window up for a moment and
   costs CPU; while the user plays, nothing starts. "Real" means a game process that holds
   the single-instance lock and runs from outside the sandboxes.
3. Test builds without the single-instance lock (every build made by prep_fps.build since
   2026-11-22, or pu_noinst.py) may run next to other test games, up to MAX_GAMES on the whole
   PC (all sandboxes and worktrees together; MHK2_MAX_GAMES overrides it).
   A build that still has the lock runs alone, as before: it waits until no game at all has
   run for 40 s, because as a second instance it would raise the first one's window and exit.
4. One start at a time on the whole PC. A start holds the named mutex
   Local\mhk2-sandbox-launch until the game has reached its menu, so two windows never take
   and hand back the foreground at the same moment (focusguard sees one start at a time).

Games are recognised by their code, not by their name: every process whose memory at
0x46F3AC holds either the original call of the instance lock or the test builds' replacement
is a Moorhuhn Kart 2.

    py gameslot.py               lists the running games (real / test with lock / test without)
    py gameslot.py make game2    makes or fills the game folder game2 from game\
"""
import ctypes
import ctypes.wintypes as wt
import msvcrt
import os
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H

HERE = os.path.dirname(os.path.abspath(__file__))
SANDBOX = os.path.dirname(HERE)
MAX_GAMES = int(os.environ.get("MHK2_MAX_GAMES", "3"))
QUIET = 40                                  # seconds of no game before a build with the lock starts

LOCK_VA = 0x0046F3AC                        # call InstanceLock (file offset == rva - 0x400000 here)
LOCK_ORIG = bytes.fromhex("E8 9F 55 03 00")
LOCK_SKIP = bytes.fromhex("83 C4 04 90 90")
TEST_MARKS = ("\\.claude\\sandbox\\", "\\.claude\\worktrees\\",
              os.path.join(os.environ.get("LOCALAPPDATA", ""), "Temp", "claude").lower() + "\\")

k32 = H.kernel32
psapi = ctypes.WinDLL("psapi")
k32.QueryFullProcessImageNameW.argtypes = [wt.HANDLE, wt.DWORD, wt.LPWSTR, ctypes.POINTER(wt.DWORD)]
k32.CreateMutexW.restype = wt.HANDLE
k32.CreateMutexW.argtypes = [ctypes.c_void_p, wt.BOOL, wt.LPCWSTR]
k32.WaitForSingleObject.argtypes = [wt.HANDLE, wt.DWORD]
k32.ReleaseMutex.argtypes = [wt.HANDLE]

_held = {}                                  # folder -> open lock file (kept for the process lifetime)


def say(text):
    print("[gameslot] " + text, flush=True)


# -- what runs ---------------------------------------------------------------------------

def exe_has_lock(exe):
    """True if the exe still takes the single-instance lock, False for a test build without it."""
    with open(exe, "rb") as f:
        f.seek(LOCK_VA - 0x400000)
        b = f.read(5)
    if b == LOCK_SKIP:
        return False
    if b == LOCK_ORIG:
        return True
    raise SystemExit("%s does not look like MHK2-XXL.exe (bytes at %08X: %s)" % (exe, LOCK_VA, b.hex(" ")))


def is_test_path(path):
    p = path.lower()
    return any(m in p for m in TEST_MARKS if m != "\\")


def games():
    """Every running Moorhuhn Kart 2: list of dicts pid, path, lock (holds the instance lock), real."""
    arr = (wt.DWORD * 8192)()
    got = wt.DWORD()
    psapi.EnumProcesses(arr, ctypes.sizeof(arr), ctypes.byref(got))
    me = os.getpid()
    res = []
    for pid in arr[:got.value // 4]:
        if pid in (0, 4, me):
            continue
        h = k32.OpenProcess(0x1010, False, pid)          # QUERY_LIMITED_INFORMATION | VM_READ
        if not h:
            continue
        try:
            buf = ctypes.create_unicode_buffer(600)
            n = wt.DWORD(600)
            if not k32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)) or not buf.value.lower().endswith(".exe"):
                continue
            b = ctypes.create_string_buffer(5)
            rd = ctypes.c_size_t()
            if not k32.ReadProcessMemory(h, ctypes.c_void_p(LOCK_VA), b, 5, ctypes.byref(rd)) or rd.value != 5:
                continue
            if b.raw not in (LOCK_ORIG, LOCK_SKIP):
                continue
            lock = b.raw == LOCK_ORIG
            res.append({"pid": pid, "path": buf.value, "lock": lock, "real": lock and not is_test_path(buf.value)})
        finally:
            k32.CloseHandle(h)
    return res


# -- folders -----------------------------------------------------------------------------

def try_claim(folder):
    """Claim a game folder without waiting; True if this process has it now."""
    folder = os.path.normcase(os.path.abspath(folder))
    if folder in _held:
        return True
    os.makedirs(folder, exist_ok=True)
    f = open(os.path.join(folder, ".claim.lock"), "a+b")
    try:
        f.seek(0)
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
    except OSError:
        f.close()
        return False
    if any(os.path.normcase(os.path.dirname(g["path"])) == folder for g in games()):
        msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)   # an orphaned game still runs there
        f.close()
        return False
    f.seek(0)
    f.truncate()
    f.write(("pid %d %s\n" % (os.getpid(), " ".join(sys.argv))).encode("utf-8", "replace"))
    f.flush()
    _held[folder] = f
    return True


def claim_dir(folder, timeout=3600):
    """Claim a game folder for this process, waiting while another test uses it."""
    t0 = time.time()
    told = False
    while not try_claim(folder):
        if not told:
            say("waiting: %s is in use by another test" % folder)
            told = True
        if time.time() - t0 > timeout:
            raise SystemExit("game folder %s stayed in use" % folder)
        time.sleep(2)
    if told:
        say("got %s after %.0f s" % (folder, time.time() - t0))


class setup_lock:
    """Held while setup_sandbox.py rewrites game\\ (and by sync_from_game while it copies)."""

    def __enter__(self):
        self.f = open(os.path.join(SANDBOX, ".setup.lock"), "a+b")
        while True:
            try:
                self.f.seek(0)
                msvcrt.locking(self.f.fileno(), msvcrt.LK_NBLCK, 1)
                return self
            except OSError:
                time.sleep(2)

    def __exit__(self, *exc):
        self.f.seek(0)
        msvcrt.locking(self.f.fileno(), msvcrt.LK_UNLCK, 1)
        self.f.close()


SKIP_SYNC = {"settings.dat", "log.txt", "game.pid", ".claim.lock"}


def sync_from_game(dst, force=(), locked=False):
    """Fill game folder dst from the sandbox's game\\: files dst lacks are copied (test builds,
    game data, phantom folder, settings.dat); files it has stay, so a build a test made there
    under a name game\\ also has is never overwritten. `force` lists relative paths to copy
    anyway (setup_sandbox.py passes what it rebuilt). The folder must be claimed by the caller."""
    src = os.path.join(SANDBOX, "game")
    if os.path.normcase(os.path.abspath(dst)) == os.path.normcase(os.path.abspath(src)):
        return
    if not os.path.exists(os.path.join(src, "data", "mhk2-00.dat")):
        raise SystemExit("%s has no game data: run setup_sandbox.py first" % src)
    force = {os.path.normcase(f) for f in force}
    n = 0
    with (_nolock() if locked else setup_lock()):
        for dirpath, dirs, files in os.walk(src):
            rel = os.path.relpath(dirpath, src)
            if os.path.normcase(rel).startswith(os.path.normcase(os.path.join("data", "Phantom"))):
                continue                                  # in use by game\'s test: from the fixtures below
            os.makedirs(os.path.join(dst, rel), exist_ok=True)
            for name in files:
                relname = os.path.normpath(os.path.join(rel, name))
                if rel == "." and name.lower() in SKIP_SYNC:
                    continue
                b = os.path.join(dst, relname)
                if os.path.exists(b) and os.path.normcase(relname) not in force:
                    continue
                shutil.copy2(os.path.join(dirpath, name), b)
                n += 1
        fixtures = os.path.join(SANDBOX, "fixtures")
        if not os.path.isdir(os.path.join(dst, "data", "Phantom")):
            shutil.copytree(os.path.join(fixtures, "Phantom"), os.path.join(dst, "data", "Phantom"))
            n += 1
        if not os.path.exists(os.path.join(dst, "settings.dat")):
            shutil.copy2(os.path.join(fixtures, "settings.dat"), os.path.join(dst, "settings.dat"))
            n += 1
    if n:
        say("%s: %d files copied from game\\" % (dst, n))


class _nolock:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        pass


def slot_dirs():
    """The extra game folders of this sandbox that exist (game2, game3, ...)."""
    return sorted(os.path.join(SANDBOX, n) for n in os.listdir(SANDBOX)
                  if n.startswith("game") and n[4:].isdigit() and os.path.isdir(os.path.join(SANDBOX, n)))


def is_slot_dir(folder):
    d = os.path.normcase(os.path.abspath(folder))
    return os.path.normcase(os.path.dirname(d)) == os.path.normcase(SANDBOX) and \
        os.path.basename(d).startswith("game") and os.path.basename(d)[4:].isdigit()


def pick_game_dir():
    """The game folder for this test process: MHK2_GAME if set, else the first free one of
    game, game2, ... game<MAX_GAMES> (made from game\\ when needed). It stays claimed."""
    want = os.environ.get("MHK2_GAME")
    if want:
        d = want if os.path.isabs(want) else os.path.join(SANDBOX, want)
        claim_dir(d)
        sync_from_game(d)
        return os.path.abspath(d)
    names = ["game"] + ["game%d" % i for i in range(2, MAX_GAMES + 1)]
    t0 = time.time()
    told = False
    while True:
        for name in names:
            d = os.path.join(SANDBOX, name)
            if try_claim(d):
                sync_from_game(d)
                if told or name != "game":
                    say("using %s" % d)
                return d
        if not told:
            say("waiting: all %d game folders are in use" % len(names))
            told = True
        if time.time() - t0 > 3600:
            raise SystemExit("no free game folder")
        time.sleep(3)


# -- starting ----------------------------------------------------------------------------

class launch_mutex:
    def __enter__(self):
        self.h = k32.CreateMutexW(None, False, "Local\\mhk2-sandbox-launch")
        r = k32.WaitForSingleObject(self.h, 0)
        if r not in (0, 0x80):                            # WAIT_OBJECT_0, WAIT_ABANDONED
            say("waiting: another test game is starting")
            r = k32.WaitForSingleObject(self.h, 0xFFFFFFFF)
        return self

    def __exit__(self, *exc):
        k32.ReleaseMutex(self.h)
        k32.CloseHandle(self.h)


def wait_turn(exe, timeout=3600):
    """Wait until rules 2 and 3 let this exe start."""
    lock = exe_has_lock(exe)
    t0 = time.time()
    last_seen = None
    told = None
    while True:
        gs = games()
        now = time.time()
        if gs:
            last_seen = now
        if any(g["real"] for g in gs):
            why = "your own game is running"
        elif lock and gs:
            why = "this build has the single-instance lock and another game runs"
        elif lock and last_seen is not None and now - last_seen < QUIET:
            why = "this build has the single-instance lock; waiting for %d s without any game" % QUIET
        elif not lock and any(g["lock"] for g in gs):
            why = "a test build with the single-instance lock runs (it must run alone)"
        elif not lock and len(gs) >= MAX_GAMES:
            why = "%d test games are running (MHK2_MAX_GAMES=%d)" % (len(gs), MAX_GAMES)
        else:
            if told:
                say("free after %.0f s" % (now - t0))
            return
        if why != told:
            say("waiting: " + why)
            told = why
        if now - t0 > timeout:
            raise SystemExit("could not start %s: %s" % (exe, why))
        time.sleep(2)


def _menu_reached(log, since):
    try:
        if os.path.getmtime(log) < since - 1:
            return False
        return "GameMK2::Init done" in open(log, "r", encoding="latin-1").read()
    except OSError:
        return False


def spawn(exe, args=(), quiet_start=True, guard=True):
    """Start a test game the safe way (see the module text) and return its Popen.

    quiet_start: show the window without activating it; guard: run focusguard.py next to it.
    Returns once the game has reached its menu (or died, or 60 s passed). The pid goes into
    <game folder>\\game.pid, and harness.PIDFILE points there for this process.
    """
    exe = os.path.abspath(exe)
    folder = os.path.dirname(exe)
    claim_dir(folder)
    if is_slot_dir(folder):
        sync_from_game(folder)                            # game2\c5_new60.exe works without a setup step
    log = os.path.join(folder, "log.txt")
    with launch_mutex():
        wait_turn(exe)
        here = [g for g in games() if os.path.normcase(os.path.dirname(g["path"])) == os.path.normcase(folder)]
        if here:
            raise SystemExit("a game still runs from %s (pid %d): stop it first" % (folder, here[0]["pid"]))
        si = None
        if quiet_start:
            si = subprocess.STARTUPINFO()
            si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            si.wShowWindow = 4                            # SW_SHOWNOACTIVATE
        before = H.user32.GetForegroundWindow() or 0
        t0 = time.time()
        p = subprocess.Popen([exe] + list(args), cwd=folder, startupinfo=si)
        H.set_pidfile(os.path.join(folder, "game.pid"))
        open(H.PIDFILE, "w").write(str(p.pid))
        if guard:
            subprocess.Popen([sys.executable.replace("python.exe", "pythonw.exe"), os.path.join(HERE, "focusguard.py"),
                              str(p.pid), str(before)], creationflags=0x08000008, close_fds=True)
        while not _menu_reached(log, t0) and p.poll() is None and time.time() - t0 < 60:
            time.sleep(0.5)
    return p


def status():
    for g in games():
        kind = "REAL (user)" if g["real"] else ("test, with lock" if g["lock"] else "test, no lock")
        print("%6d  %-16s %s" % (g["pid"], kind, g["path"]))
    print("max test games at once:", MAX_GAMES)


def main():
    """gameslot.py               running games and the limit
       gameslot.py make <name>   make or update the game folder <name> (game2, ...) from game\\"""
    if len(sys.argv) > 2 and sys.argv[1] == "make":
        d = sys.argv[2] if os.path.isabs(sys.argv[2]) else os.path.join(SANDBOX, sys.argv[2])
        claim_dir(d)
        sync_from_game(d)
        print("ready:", d)
    else:
        status()


if __name__ == "__main__":
    main()
