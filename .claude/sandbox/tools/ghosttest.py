"""Unattended tests of the phantom kart changes (sandbox only; no keyboard, no focus, no mouse).

usage: ghosttest.py <scenario> [...]
    main      own ghost, promotion, header clean-up, name entry, restart path   (ghost_new.exe)
    stock     the unpatched game refuses the ghost the patched one left behind    (ghost_orig.exe)
    cc200     200 cc: first run creates phantom-4-NN.mhk2                         (ghost_new.exe)
    version   "V1.1" with mhk2-01.dat, "V1.0" without                             (ghost_new.exe)
    cliname   --player-name of the patcher                                        (ghost_new.exe)
    import    MHK2-XXL.exe <own file>.mhk2                                        (both)
    options   the options page still has its switch                               (ghost_new.exe)
    shot      a result list with plausible times for the README picture           (ghost_new.exe)

Needs the sandbox next to this folder (.claude/sandbox, built by setup_sandbox.py): test builds in
game/ and the pristine phantom folder and settings.dat in fixtures/, which every scenario
restores first.

The fixtures: the game's 24 original phantoms (no player name, the developers' ids; none for
200 cc and up) and the user's settings.dat as of 2026-11-18 (highscores, muted, 640x480). The
expected highscore ranks are those of that settings.dat. "main" stamps its phantom-3-01 in game/
first (name "Test-200", 21.55 s), so it has a fast, named, foreign ghost to race.
MHK2_REPO overrides the repository path (default: the repository this folder is in).
"""
import hashlib
import os
import shutil
import struct
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H
import optest as O
import ghostlib as G
import gameslot

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# This process's own game folder: game, or game2, game3, ... when another test holds game
# (MHK2_GAME picks one). It stays claimed until the process ends.
GAME = gameslot.pick_game_dir()
KEEP = os.path.join(ROOT, "fixtures")
PH = os.path.join(GAME, "data", "Phantom")
SHOTS = os.path.join(ROOT, "shots")
NEW_EXE = os.path.join(GAME, "ghost_new.exe")
ORIG_EXE = os.path.join(GAME, "ghost_orig.exe")
NEWP = os.path.join(PH, "new-phantom.mhk2")
REPO = os.environ.get("MHK2_REPO", os.path.dirname(os.path.dirname(ROOT)))
PATCHER = os.path.join(REPO, "tools", "patch_200cc.py")
OK = [0, 0]


def check(label, got, want=True):
    good = got == want
    OK[0 if good else 1] += 1
    print("  %s %s: %r%s" % ("ok  " if good else "FAIL", label, got, "" if good else "   (expected %r)" % (want,)), flush=True)
    return good


def note(text):
    print(text, flush=True)


def restore():
    """Put the sandbox's phantom folder and settings.dat back to their pristine copies."""
    gameslot.claim_dir(GAME)                      # (already ours: GAME was claimed at import)
    if os.path.isdir(PH):
        shutil.rmtree(PH)
    shutil.copytree(os.path.join(KEEP, "Phantom"), PH)
    shutil.copyfile(os.path.join(KEEP, "settings.dat"), os.path.join(GAME, "settings.dat"))
    p = os.path.join(GAME, "data", "mhk2-01.dat")
    if os.path.exists(p):
        os.remove(p)


def data(path):
    return open(path, "rb").read()


def sha(path):
    return hashlib.sha256(data(path)).hexdigest()[:12]


def phantom(cls, track):
    return os.path.join(PH, "phantom-%d-%02d.mhk2" % (cls + 1, track))


def wait_racing(g, timeout=60):
    t0 = time.time()
    since = None
    while time.time() - t0 < timeout:
        try:
            if g.u32(g.car() + 0x2D0) == 2 and g.race_phase() == 2:
                since = since or time.time()
                if time.time() - since > 1.5:
                    return True
            else:
                since = None
        except OSError:
            since = None
        time.sleep(0.1)
    return False


def finish(g, laps):
    """Force the player's finish; returns when the result overlay is up."""
    before = os.path.getmtime(NEWP) if os.path.exists(NEWP) else None
    g.force_finish(laps)
    up = g.wait_overlay(0x0E, 30)
    written = os.path.exists(NEWP) and os.path.getmtime(NEWP) != before
    return up, written


def ghost_flag(g):
    return g.read(g.gp + 0x54, 1)[0]


def hs_slot(g, cls, track0):
    slot = (160 if cls == 3 else cls * 64) + track0
    e = g.read(g.gp + 0x234 + slot * 0xB4, 0xB4)
    times = [round(x, 2) for x in struct.unpack_from("<5f", e, 0)]
    names = [e[0x50 + 16 * i:0x60 + 16 * i].split(b"\0")[0].decode("cp1252") for i in range(5)]
    return times, names


def name12(text):
    return text.encode("cp1252")[:12].ljust(12, b"\0")


def stamp(path, name, total):
    """Write a player name (bytes 8..19) and a total time (0x58) into a phantom file's header,
    as mhk2_manager does; the recording itself stays."""
    d = bytearray(data(path))
    d[8:20] = name12(name)
    struct.pack_into("<f", d, 0x58, total)
    with open(path, "wb") as f:
        f.write(d)


# ---------------------------------------------------------------------------------------------
def scenario_main():
    note("== main: 150 cc, Moorhuhn X (track 1). Original phantom, stamped 'Test-200' / 21.55 s, foreign id")
    restore()
    p301 = phantom(2, 1)
    stamp(p301, "Test-200", 21.55)
    keep_sha = sha(p301)
    g = G.Game(NEW_EXE)
    try:
        check("version string at start", g.version(), b"V1.0\0")
        check("no player name stored yet", g.stored_name()[0], False)
        own_id = None

        note("-- run 1: slower than the phantom (30+30+30 s)")
        g.start_time_trial(2, 0)
        check("race started", wait_racing(g))
        check("ghost loaded (gp+54h)", ghost_flag(g), 1)
        check("header slot holds the loaded ghost's name", g.header()[8:20], name12("Test-200"))
        up, written = finish(g, (30.0, 30.0, 30.0))
        check("result overlay shown", up)
        check("new-phantom.mhk2 written", written)
        d = data(NEWP)
        own_id = d[0x28:0x48]
        shutil.copyfile(NEWP, os.path.join(GAME, "ghost_1_own.mhk2"))     # for the import scenario
        check("new phantom: version", d[:5], b"V1.0\0")
        check("new phantom: bytes 5..31 are clean (no name/checksum of the other ghost)", d[5:32], bytes(27))
        check("new phantom: id is not the dashes", own_id != b"-" * 32 and len(own_id.rstrip(b"\0")) == 32)
        check("new phantom: track/class/character", struct.unpack_from("<3i", d, 0x4C), (1, 2, 0))
        check("new phantom: times", struct.unpack_from("<4f", d, 0x58), (90.0, 30.0, 30.0, 30.0))
        check("slower run: phantom file untouched", sha(p301), keep_sha)
        check("slower run: table entry untouched", round(struct.unpack_from("<f", g.table(2, 1), 0x58)[0], 2), 21.55)
        note("   overlay items: %r" % (g.overlay_items(),))
        st = g.select(0)
        check("'Weiter' -> result list (no highscore)", st, 0x0F)
        note("   list page items: %r" % (g.overlay_items(),))
        g.shot(os.path.join(SHOTS, "ghost_1_list_foreign.png"))

        note("-- run 2 via 'Rennen wiederholen': faster than the phantom (7+7+7 s)")
        g.select(0)
        check("race restarted", wait_racing(g))
        check("ghost loaded again through the restart path", ghost_flag(g), 1)
        up, written = finish(g, (7.0, 7.0, 7.0))
        check("result overlay shown", up)
        check("new-phantom.mhk2 written", written)
        d = data(NEWP)
        check("faster run: phantom file replaced by the new run", data(p301) == d)
        check("faster run: table entry is the new header", g.table(2, 1) == g.header())
        check("new phantom: bytes 5..31 clean", d[5:32], bytes(27))
        st = g.select(0)
        check("'Weiter' -> name entry (new highscore)", st, 0x13)
        g.set_name("Tester")
        st = g.select(0)
        check("name confirmed -> result list", st, 0x0F)
        named, raw = g.stored_name()
        check("name stored with marker", (named, raw), (True, b"Tester".ljust(16, b"\0")))
        check("new-phantom.mhk2 got the name", data(NEWP)[8:20], name12("Tester"))
        check("phantom file got the name", data(p301)[8:20], name12("Tester"))
        check("phantom file: checksum bytes still zero", data(p301)[20:32], bytes(12))
        check("phantom file: nothing else changed", data(p301)[:8] + data(p301)[20:] == d[:8] + d[20:])
        check("table entry got the name", g.table(2, 1)[8:20], name12("Tester"))
        times, names = hs_slot(g, 2, 0)
        check("highscore entry", (times[1], names[1]), (21.0, "Tester"))
        note("   list page items: %r" % (g.overlay_items(),))
        g.shot(os.path.join(SHOTS, "ghost_2_list_own.png"))

        note("-- run 3 via 'Rennen wiederholen': own ghost, faster again (6.9 * 3); table entry made to look manager-stamped")
        g.select(0)
        check("race restarted", wait_racing(g))
        check("OWN ghost loaded through the restart path", ghost_flag(g), 1)
        up, written = finish(g, (6.9, 6.9, 6.9))
        check("new-phantom.mhk2 written", up and written)
        d = data(NEWP)
        check("new phantom carries the stored name from the start", d[8:20], name12("Tester"))
        check("new phantom: checksum bytes zero", d[20:32], bytes(12))
        check("faster run: phantom file replaced", data(p301) == d)
        slot = 2 * 64 + 0
        g.write(g.gp + G.PH_TABLE + slot * G.PH_SIZE + 0x14, struct.pack("<I", 0xDEADBEEF))   # as if a checksum were there
        st = g.select(0)
        check("'Weiter' -> name entry", st, 0x13)
        g.set_name("Zweiter Name!")
        st = g.select(0)
        check("name confirmed -> result list", st, 0x0F)
        check("stored name is cut to 12 characters", g.stored_name(), (True, b"Zweiter Name".ljust(16, b"\0")))
        check("new-phantom.mhk2 got the new name", data(NEWP)[8:20], b"Zweiter Name")
        check("phantom file with (pretended) checksum was left alone", data(p301)[8:20], name12("Tester"))
        times, names = hs_slot(g, 2, 0)
        check("highscore entry keeps the full name", (times[1], names[1]), (20.7, "Zweiter Name!"))

        note("-- back to the main menu, then a new race from the menu")
        n0 = g.init_count()
        g.select(2)
        check("back in the main menu", g.wait_menu(n0, 60))
        check("table entry after the menu re-read the files: name", g.table(2, 1)[8:20], name12("Tester"))
        check("table entry after the menu re-read the files: time", round(struct.unpack_from("<f", g.table(2, 1), 0x58)[0], 2), 20.7)
        g.page(0)
        g.start_time_trial(2, 0)
        check("race started", wait_racing(g))
        check("OWN ghost loaded at race start", ghost_flag(g), 1)
        hdr = g.header()
        check("the loaded ghost is the run with this PC's id", hdr[0x28:0x48], own_id)
    finally:
        g.kill()
    s = data(os.path.join(GAME, "settings.dat"))
    check("settings.dat on disk: name and marker", (s[G.NAME_OFF - 4:G.NAME_OFF + 12], struct.unpack_from("<I", s, G.MARK_OFF - 4)[0]),
          (b"Zweiter Name".ljust(16, b"\0"), G.MARK))


def scenario_stock():
    note("== stock: the unpatched game with the phantom the patched game left (own id)")
    d = data(phantom(2, 1))
    note("   phantom-3-01.mhk2: %r" % (G.phantom_info(phantom(2, 1)),))
    g = G.Game(ORIG_EXE)
    try:
        g.start_time_trial(2, 0)
        check("race started", wait_racing(g))
        check("stock game: ghost with this PC's id is NOT loaded (gp+54h)", ghost_flag(g), 0)
        check("the file it skipped carries the id the stock game writes itself", g.header()[0x28:0x48], d[0x28:0x48])
    finally:
        g.kill()


def scenario_cc200():
    note("== cc200: 200 cc, Winter (track 2): no phantom-4-02.mhk2 yet")
    restore()
    p402 = phantom(3, 2)
    check("no phantom file before", os.path.exists(p402), False)
    g = G.Game(NEW_EXE)
    try:
        g.start_time_trial(3, 1)
        check("race started", wait_racing(g))
        check("no ghost (gp+54h)", ghost_flag(g), 0)
        check("table entry is the placeholder", round(struct.unpack_from("<f", g.table(3, 2), 0x58)[0], 2), 639.99)
        up, written = finish(g, (50.0, 50.0, 50.0))
        check("new-phantom.mhk2 written", up and written)
        d = data(NEWP)
        check("new phantom: track/class", struct.unpack_from("<2i", d, 0x4C), (2, 3))
        check("first run creates phantom-4-02.mhk2", os.path.exists(p402) and data(p402) == d)
        check("table entry (slot 161) is the new header", g.table(3, 2) == g.header())
        st = g.select(0)
        note("   after 'Weiter': page %s, highscores %r" % (hex(st) if st else st, hs_slot(g, 3, 1)))
        if st == 0x13:
            g.set_name("Zweihundert")
            st = g.select(0)
            check("name confirmed -> result list", st, 0x0F)
            check("phantom-4-02.mhk2 got the name", data(p402)[8:20], name12("Zweihundert"))
        g.shot(os.path.join(SHOTS, "ghost_3_list_200cc.png"))
        g.select(0)
        check("race restarted", wait_racing(g))
        check("the new 200 cc ghost is loaded (gp+54h)", ghost_flag(g), 1)
        up, written = finish(g, (60.0, 60.0, 60.0))
        check("slower 200 cc run leaves the phantom alone", data(p402)[0x58:0x5C], struct.pack("<f", 150.0))
    finally:
        g.kill()


def scenario_version():
    note("== version: with data\\mhk2-01.dat")
    restore()
    import paths
    v11 = paths.v11_data()
    if not v11:
        raise SystemExit("needs v11_data (mhk2-01.dat) in .claude/sandbox/local.json")
    shutil.copyfile(v11, os.path.join(GAME, "data", "mhk2-01.dat"))
    g = G.Game(NEW_EXE)
    try:
        check("version string with V1.1 data", g.version(), b"V1.1\0")
        g.start_time_trial(2, 4)
        check("race started", wait_racing(g))
        up, written = finish(g, (40.0, 40.0, 40.0))
        check("new-phantom.mhk2 written", up and written)
        check("new phantom says V1.1", data(NEWP)[:8], b"V1.1\0\0\0\0")
    finally:
        g.kill()
        os.remove(os.path.join(GAME, "data", "mhk2-01.dat"))
    g = G.Game(ORIG_EXE)
    try:
        check("stock game with V1.1 data still says", g.version(), b"V1.0\0")
    finally:
        g.kill()


def scenario_cliname():
    note("== cliname: patch_200cc.py --player-name")
    restore()
    out = subprocess.run([sys.executable, PATCHER, "--player-name", "Kommandozeil", os.path.join(GAME, "settings.dat")],
                         capture_output=True, text=True)
    note("   " + (out.stdout + out.stderr).strip())
    too_long = subprocess.run([sys.executable, PATCHER, "--player-name", "dreizehn Zeic", os.path.join(GAME, "settings.dat")],
                              capture_output=True, text=True)
    check("13 characters are refused", too_long.returncode != 0 and "at most 12" in (too_long.stdout + too_long.stderr))
    g = G.Game(NEW_EXE)
    try:
        check("game sees the name", g.stored_name(), (True, b"Kommandozeil".ljust(16, b"\0")))
        g.start_time_trial(2, 4)
        check("race started", wait_racing(g))
        up, written = finish(g, (40.0, 40.0, 40.0))
        check("new-phantom.mhk2 written", up and written)
        check("new phantom carries the name", data(NEWP)[8:20], b"Kommandozeil")
        check("... and nothing behind it", data(NEWP)[20:32], bytes(12))
    finally:
        g.kill()


def launch_with_file(exe, arg):
    """Start <exe> <file> without focus and wait for the menu."""
    log = os.path.join(GAME, "log.txt")
    if os.path.exists(log):
        os.remove(log)
    p = gameslot.spawn(exe, [arg])
    t0 = time.time()
    while O.init_count(log) < 1:
        if time.time() - t0 > 60 or p.poll() is not None:
            return False
        time.sleep(0.5)
    time.sleep(2.0)
    return True


def scenario_import():
    note("== import: MHK2-XXL.exe <file>.mhk2 with a file that carries this PC's id")
    restore()
    src = os.path.join(GAME, "ghost_1_own.mhk2")
    if not os.path.exists(src):
        raise SystemExit("run the main scenario first (it leaves a phantom with this PC's id)")
    d = bytearray(data(src))
    struct.pack_into("<2i", d, 0x4C, 5, 3)            # pretend: track 5, 200 cc
    own = os.path.join(GAME, "own-test.mhk2")
    open(own, "wb").write(d)
    target = phantom(3, 5)
    for exe, want in ((ORIG_EXE, False), (NEW_EXE, True)):
        if os.path.exists(target):
            os.remove(target)
        okay = launch_with_file(exe, own)
        check("%s started with the file" % os.path.basename(exe), okay)
        check("%s: phantom-4-05.mhk2 %s" % (os.path.basename(exe), "created" if want else "not created (stock refuses own files)"),
              os.path.exists(target), want)
        if want and os.path.exists(target):
            check("the copy is identical", data(target) == bytes(d))
        if H.alive():
            G.k32.TerminateProcess(H.open_proc(0x0001), 0)
        time.sleep(1.5)
    os.remove(own)


def scenario_options():
    note("== options: the 60 FPS switch page is unchanged")
    restore()
    g = G.Game(NEW_EXE)
    try:
        g.page(1)
        items = g.menu_items()
        note("   %r" % (items,))
        # items 0..6 as in the stock game, 7 / 8 "Alles freigeschaltet" (patch 1.10), 9 heading,
        # 10 switch, 11 "Zurück", 12 the page title
        check("thirteen items, switch at 10, 'Zurück' at 11", (len(items), items[10][0], items[11][1]), (13, 3, "Zurück"))
        before = g.u32(g.gp + 0x4C) >> 8
        g.write(g.menu + 0x148, struct.pack("<i", 10))
        time.sleep(0.2)
        g.write(O.MENU_INJ + 4 * O.KEYS["select"], struct.pack("<f", 1.0))
        time.sleep(0.5)
        after = g.u32(g.gp + 0x4C) >> 8
        check("select flips the switch", {before, after}, {0, 0x463036})
        check("text follows", g.menu_items()[10][1], "An" if after else "Aus")
    finally:
        g.kill()


def scenario_shot():
    note("== shot: 50 cc, Fabrik (track 5); original phantom 159.40 s, highscores 108.21 / 113.64")
    restore()
    g = G.Game(NEW_EXE)
    try:
        g.start_time_trial(0, 4)
        check("race started", wait_racing(g))
        check("ghost loaded", ghost_flag(g), 1)
        up, written = finish(g, (35.84, 35.61, 35.92))
        check("new-phantom.mhk2 written", up and written)
        check("faster run: phantom replaced", data(phantom(0, 5)) == data(NEWP))
        st = g.select(0)
        check("'Weiter' -> name entry", st, 0x13)
        g.set_name("Marki13")
        g.shot(os.path.join(SHOTS, "ghost_name_entry.png"))
        st = g.select(0)
        check("name confirmed -> result list", st, 0x0F)
        check("phantom file got the name", data(phantom(0, 5))[8:20], name12("Marki13"))
        time.sleep(0.5)
        g.shot(os.path.join(SHOTS, "ghost_readme_list.png"))
    finally:
        g.kill()


SCENARIOS = {"main": scenario_main, "stock": scenario_stock, "cc200": scenario_cc200, "version": scenario_version,
             "cliname": scenario_cliname, "import": scenario_import, "options": scenario_options, "shot": scenario_shot}


def main():
    for name in sys.argv[1:]:
        try:
            SCENARIOS[name]()
        except SystemExit as e:
            OK[1] += 1
            print("  FAIL scenario %s stopped: %s" % (name, e), flush=True)
        finally:
            try:
                if H.alive():
                    G.k32.TerminateProcess(H.open_proc(0x0001), 0)
            except BaseException:
                pass
    print("%d checks ok, %d failed" % tuple(OK), flush=True)


if __name__ == "__main__":
    main()
