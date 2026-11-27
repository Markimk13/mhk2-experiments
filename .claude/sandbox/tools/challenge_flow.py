"""The challenge menu from end to end in a sandbox game (no keyboard, focus or mouse).

usage: challenge_flow.py <build dir> <out dir> [--random] [--tuned]

--tuned: the player has own tuning values (with marker), 200 cc, Insel and character 5 before the test.

<build dir>: a patcher output (MHK2-XXL.exe, data\\MK2\\text-20.csv), e.g. builds\\ch. The tool makes
a test build of it (prep_class5.py) in a free game folder, puts the build's text-20.csv there
for the run, and restores the fixtures (settings.dat, phantoms) before and after.

Steps (pictures in <out dir>):
1. Page 4 ("Rennmodus"): item 3 must be the button "Herausforderung".
2. "Herausforderung" -> page 22h. "Täglich" (--random: "Zufall") -> the draw: compares GameParameters
   and the challenge block with the patcher's challenge_draw() for the seed.
3. "Weiter" -> the race. The stretch is shortened to 0.02 of the path, so full throttle finishes.
   Checks: settings.dat written at the race start holds the player's own settings.
4. After the finish: the result overlay's "Weiter" leads to the result list (no name entry); daily:
   data\\Phantom\\daily-<day>.mhk2 and the best time in GameParameters.
5. "Hauptmenü": the player's settings are back in GameParameters, the challenge is off.
6. Daily only: "Täglich" again shows the best time, and the race loads the phantom of the day.
"""
import os
import shutil
import struct
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))
import ghostlib as G
import ghosttest as T
import classtest as C
import harness as H
import patch_200cc as P

MENU_INJ = 0x00884F10          # one-shot back, select, left, right (test builds)
CH_FIELDS = (("class", 0x10), ("mode", 0x1C), ("track", 0x20), ("phys", 0x4C), ("char", 0x58))
results = []


def check(name, ok, detail=""):
    results.append((name, ok))
    print(("PASS " if ok else "FAIL ") + name + (": " + detail if detail else ""))


def f32(g, a):
    return struct.unpack("<f", g.read(a, 4))[0]


def i32(g, a):
    return struct.unpack("<i", g.read(a, 4))[0]


def settings_of(g):
    vals = {n: g.u32(g.gp + off) for n, off in CH_FIELDS}
    vals["values"] = struct.unpack("<8i", g.read(g.gp + P.TUNE_VALUES, 32))
    return vals


def settings_in_file(path):
    d = open(path, "rb").read()
    vals = {n: struct.unpack_from("<I", d, off - 4)[0] for n, off in CH_FIELDS}
    vals["values"] = struct.unpack_from("<8i", d, P.TUNE_VALUES - 4)
    return vals


def press(g, item, key=1, wait=1.0):
    """Select an item of the current page and press 'select' (key 1) or 'back' (key 0)."""
    g.write(g.menu + 0x148, struct.pack("<i", item))
    g.write(MENU_INJ + 4 * key, struct.pack("<f", 1.0))
    time.sleep(wait)


def show(g, title):
    print("--", title, "page %02X" % g.menu_state())
    for n, (typ, y, text) in enumerate(C.items(g)):
        print("   %2d type %d y %4d  %s" % (n, typ, y, text[:110]))


def main():
    build, out = sys.argv[1], sys.argv[2]
    daily = "--random" not in sys.argv
    os.makedirs(out, exist_ok=True)
    exe = os.path.join(T.GAME, "ch_flow.exe")
    subprocess.run([sys.executable, os.path.join(HERE, "prep_class5.py"), os.path.join(build, "MHK2-XXL.exe"), exe, "60"],
                   check=True, stdout=subprocess.DEVNULL)
    texts = os.path.join(T.GAME, "data", "MK2", "text-20.csv")
    shutil.copyfile(texts, texts + ".bak_flow")
    shutil.copyfile(os.path.join(build, "data", "MK2", "text-20.csv"), texts)
    T.restore()
    for f in os.listdir(T.PH):
        if f.startswith("daily-"):
            os.remove(os.path.join(T.PH, f))
    g = G.Game(exe)
    try:
        run(g, out, daily)
    finally:
        g.kill()
        time.sleep(1.0)
        shutil.copyfile(texts + ".bak_flow", texts)
        os.remove(texts + ".bak_flow")
        T.restore()
        for f in os.listdir(T.PH):
            if f.startswith("daily-"):
                os.remove(os.path.join(T.PH, f))
    bad = [n for n, ok in results if not ok]
    print("%d checks, %d failed%s" % (len(results), len(bad), (": " + ", ".join(bad)) if bad else ""))
    sys.exit(1 if bad else 0)


def run(g, out, daily):
    if "--tuned" in sys.argv:            # a player with own tuning values, marked, and 200 cc on Insel
        g.write(g.gp + P.TUNE_VALUES, struct.pack("<8i", 205, 300, 125, 75, 150, 125, 250, 125))
        for mark, magic in ((P.TUNE_MARK, P.TUNE_MAGIC), (P.VALUES8_MARK, P.VALUES8_MAGIC), (P.OPP_MARK, P.OPP_MAGIC)):
            g.write(g.gp + mark, struct.pack("<I", magic))   # the markers of a save from 1.9 on
        g.r.gp_i32(0x10, 3)
        g.r.gp_i32(0x20, 2)
        g.r.gp_i32(0x58, 5)
    own = settings_of(g)
    if g.u32(g.gp + P.TUNE_MARK) != P.TUNE_MAGIC:
        # a save from before the tuning class: the first draw gives the values their defaults
        # (tune_defaults), as the tuning page does
        own["values"] = tuple(row[3] for row in P.TUNE_ROWS[:P.PRESET_VALUES])
    print("player's settings:", own)
    # 1. page 4
    g.page(P.PAGE_MODE)
    time.sleep(0.5)
    show(g, "race mode")
    its = C.items(g)
    check("page 4 item 3 is the button 'Herausforderung'", len(its) > 3 and its[3][0] == 1 and "Herausforderung" in its[3][2],
          repr(its[3] if len(its) > 3 else None))
    check("page 4 has the label 'Zwei Spieler' again", any(t == 0 and "Zwei Spieler" in s for t, _, s in its))
    g.shot(os.path.join(out, "1_mode.png"))
    # 2. the challenge page and the draw
    press(g, P.MODE_ITEM_CH)
    check("'Herausforderung' opens page 22h", g.menu_state() == P.PAGE_CH, "page %02X" % g.menu_state())
    show(g, "challenge page")
    g.shot(os.path.join(out, "2_page.png"))
    press(g, P.CH_ITEM_DAILY if daily else P.CH_ITEM_RANDOM)
    show(g, "after the draw")
    g.shot(os.path.join(out, "3_draw.png"))
    active, start, length = i32(g, P.CH_ACTIVE), f32(g, P.CH_START), f32(g, P.CH_LEN)
    day = i32(g, P.CH_DAY)
    seed0 = P.challenge_daily_seed(day) if daily else None
    now_day = int((time.time() + 11644473600) // 86400)
    if daily:
        check("the day is today (UTC)", day == now_day, "%d / %d" % (day, now_day))
    drawn = settings_of(g)
    check("a draw arms the challenge", active == 1)
    check("selection is 'Weiter' after the draw", i32(g, g.menu + 0x148) == P.CH_ITEM_NEXT)
    check("class 5, time trial, 60 FPS physics", drawn["class"] == 5 and drawn["mode"] == 0
          and drawn["phys"] >> 8 == P.PHYS_MAGIC, str(drawn))
    if daily:
        track, st, share, char, values = P.challenge_draw(seed0)
        check("the draw matches challenge_draw()", (drawn["track"], drawn["char"], drawn["values"]) == (track, char, values)
              and abs(start - st) < 1e-6 and abs(length - share) < 1e-6,
              "game %s / %.4f / %.4f, python %s / %.4f / %.4f" % ((drawn["track"], drawn["char"], drawn["values"]), start, length,
                                                                (track, char, values), st, share))
    else:
        check("a random draw is a valid set", drawn["values"] in P.challenge_sets() and 0.3 <= length <= 0.7 + 1e-6)
    lines = [s for t, _, s in C.items(g) if t == 0]
    check("the page shows the draw", any("Strecke" in s for s in lines) and any("Fahrer" in s for s in lines))
    if daily:
        check("the page shows 'no time yet today'", any("noch keine Zeit" in s for s in lines))
    # 3. the race
    sfile = os.path.join(T.GAME, "settings.dat")
    n0 = g.init_count()
    press(g, P.CH_ITEM_NEXT, wait=0.2)
    t0 = time.time()
    while g.init_count() == n0 and time.time() - t0 < 90:
        time.sleep(0.5)
    check("'Weiter' starts the race", g.init_count() != n0)
    saved = settings_in_file(sfile)
    check("settings.dat holds the player's settings at the race start", saved == own,
          "file %s" % saved)
    check("GameParameters hold the challenge in the race", settings_of(g) == drawn,
          "race %s, draw %s" % (settings_of(g), drawn))
    g.write(P.CH_LEN, struct.pack("<f", 0.02))
    cm = g.u32(0x5E8520)
    t0 = time.time()
    while f32(g, cm + 0x20) <= 0.0 and time.time() - t0 < 60:
        time.sleep(0.05)
    g.write(G.INJECT, struct.pack("<3f", 0.0, 0.0, 1.0))
    time.sleep(1.0)
    g.shot(os.path.join(out, "4_race.png"))
    ok = g.wait_overlay(0x0E, timeout=40)
    g.write(G.INJECT, struct.pack("<3f", 0.0, 0.0, 0.0))
    check("the stretch is finished", ok)
    if not ok:
        return
    run_time = f32(g, g.gp + P.PHANTOM_RUN + 0x58)
    check("the run has a time", 0.5 < run_time < 60, "%.2f s" % run_time)
    page = g.select(0)
    check("result 'Weiter' leads to the result list (no name entry)", page == 0x0F, "page %s" % page)
    phantom = os.path.join(T.PH, "daily-%d.mhk2" % day)
    if daily:
        check("the phantom of the day is saved", os.path.exists(phantom))
        mark, dday, best = struct.unpack("<IIf", g.read(g.gp + P.DAILY_ENTRY, 12))
        check("the best time of the day is kept", mark == P.DAILY_MAGIC and dday == day and abs(best - run_time) < 1e-4,
              "%08X %d %.2f (run %.2f)" % (mark, dday, best, run_time))
    else:
        check("a random challenge saves no phantom", not any(f.startswith("daily-") for f in os.listdir(T.PH)))
    # 4b. "Rennen wiederholen": the same stretch from its start again
    n_restart = g.init_count()
    g.select(0)
    time.sleep(4.0)
    car = g.car()
    prog = f32(g, car + 0x224)
    check("'Rennen wiederholen' starts at the challenge's start again", abs(prog - start) < 0.003 and f32(g, P.CH_DONE) < 0.003,
          "progress %.4f (start %.4f), done %.4f" % (prog, start, f32(g, P.CH_DONE)))
    t0 = time.time()
    while g.race_time() <= 0.0 and time.time() - t0 < 30:
        time.sleep(0.05)
    g.write(G.INJECT, struct.pack("<3f", 0.0, 0.0, 1.0))
    ok = g.wait_overlay(0x0E, timeout=40)
    g.write(G.INJECT, struct.pack("<3f", 0.0, 0.0, 0.0))
    check("the repeated stretch is finished", ok)
    if not ok:
        return
    check("again the result list", g.select(0) == 0x0F)
    # 5. back to the main menu
    n0 = g.init_count()
    page = g.select(2)                       # "Hauptmenü"
    g.wait_menu(n0)
    time.sleep(1.0)
    check("back in the main menu", g.menu_state() == 0, "page %02X" % g.menu_state())
    check("the challenge is off", i32(g, P.CH_ACTIVE) == 0)
    check("the player's settings are back", settings_of(g) == own, str(settings_of(g)))
    if not daily:
        return
    # 6. the daily challenge again: best time, ghost
    g.page(P.PAGE_MODE)
    time.sleep(0.5)
    press(g, P.MODE_ITEM_CH)
    press(g, P.CH_ITEM_DAILY)
    show(g, "daily again")
    g.shot(os.path.join(out, "5_daily_again.png"))
    lines = [s for t, _, s in C.items(g) if t == 0]
    check("the page shows the best time of the day", any("Bestzeit heute" in s for s in lines))
    check("the same draw again", settings_of(g) == drawn, "now %s, first %s" % (settings_of(g), drawn))
    n0 = g.init_count()
    press(g, P.CH_ITEM_NEXT, wait=0.2)
    t0 = time.time()
    while g.init_count() == n0 and time.time() - t0 < 90:
        time.sleep(0.5)
    time.sleep(3.0)
    check("the race loads the phantom of the day", g.read(g.gp + 0x54, 1)[0] == 1)
    g.shot(os.path.join(out, "6_ghost.png"))


if __name__ == "__main__":
    main()
