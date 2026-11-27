"""Unattended tests of the added engine classes: 200 cc, 250 cc and the tuning class
(sandbox only; no keyboard, no focus, no mouse).

usage: classtest.py <scenario> [...]
    menu      engine class menu: rows, locked / unlocked entries, selecting a class
    tt250     250 cc time trial: records, phantom-5-NN.mhk2, ghost, highscore browser
    tt200     200 cc time trial still lands in its own slots
    tttune    tuning class time trial: records, phantom-6-NN.mhk2, ghost
    champ     unlock chain and its messages, championship highscores of 250 cc and the tuning class
    oldsave   a settings.dat as patch 1.2 left it (200 cc unlocked) with the new exe
    unlockall the switch 'Alles freigeschaltet' (options page): class menu, track lock, championship page, save
    browser   left / right through the six classes in both highscore browsers
    tuning    the tuning page and the pages "Kart", "Welt" and "Gegner": rows, steps, limits, the "Vorlage" row
              (presets), reset, the ways out, the gravity in a race
    save16    a settings.dat of patch 1.6 (seven values) is converted once
    pause     the pause page: class, 60 FPS switch, tuning preset and values
    save18    a settings.dat of patch 1.8: the own slots' numbers in the "Vorlage" row move once
    tunelimit the green 'Am Limit' line: as the patcher computes it, on every page, while stepping
    tunekart  the values of the tuning pages arrive in the kart and the physics world
    tunemouse the tuning pages with a simulated mouse (needs game/ghost_mouse.exe, built with --mouse)
    tuneown   own presets: page 1Eh (save, load, delete, rename on the name page), the slots in the
              "Vorlage" row, settings.dat
    ownmouse  the page of own presets with a simulated mouse

Needs the sandbox next to this folder (.claude/sandbox, built by setup_sandbox.py), like
ghosttest.py: test builds made by prep_class5.py in game/ (ghost_new.exe from the patched exe)
and the pristine phantom folder and settings.dat in fixtures/.
"""
import os
import re
import shutil
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H
import optest as O
import ghostlib as G
import ghosttest as T

check, note, restore, data, phantom = T.check, T.note, T.restore, T.data, T.phantom
GAME, PH, SHOTS, NEW_EXE, NEWP = T.GAME, T.PH, T.SHOTS, T.NEW_EXE, T.NEWP
UNLOCKED, MASK = 0xFD08, 0xFD0C
CHAMP_TABLE, CHAMP_SIZE = 0x8934, 0x8C
HS_TABLE, HS_SIZE = 0x234, 0xB4
ROW = {0: 0, 1: 64, 2: 128, 3: 160, 4: 96, 5: 32}           # first table slot of each class
CHAMP_ROW = {0: 0, 1: 20, 2: 40, 3: 50, 4: 30, 5: 10}       # first championship slot of each class
TUNE_VALUES, TUNE_MARK, TUNE_MAGIC = 0x2E4C, 0x2E7C, 0x454E5554
TUNE_DEFAULT = (155, 200, 100, 100, 100, 100, 100, 100)
TUNE_LIMITS = ((50, 400, 5), (25, 1000, 25), (25, 400, 25), (25, 400, 25), (25, 400, 25), (25, 200, 25), (0, 800, 25),
               (25, 300, 25))
PAGE_TUNING, PAGE_KART, PAGE_WORLD, PAGE_OPP = 0x1D, 0x1F, 0x20, 0x21
OPP_STD = -125                                            # "Tempo" at "Standard": its lowest step and its default (patch 1.10)
OPP_LIMITS, OPP_DEFAULT = (OPP_STD, 200, 25), OPP_STD     # "Gegner": "Tempo", the ninth value; for every class since 1.10
TUNE_DEFAULT9 = TUNE_DEFAULT + (OPP_DEFAULT,)
OPP_INFO = ("Wie schnell fahren die Computer-Karts?"
            "<br>Standard: bis 150 cc 0 %, 200 cc 50 %, ab 250 cc 100 %"
            "<br>0 %: gebremst wie im Spiel, 100 %: Vollgas wie Du"
            "<br>über 100 %: mehr Motorkraft als Du, -100 %: Schritttempo")
TUNING_UNLOCKED = "Du hast die Tuning-Klasse freigeschaltet!"
INFO = ("Länge der Übersetzung, wie der Faktor einer Klasse:<br>länger: höhere Höchstgeschwindigkeit."
        "<br>150 cc: 1.30, 200 cc: 1.47, 250 cc: 1.55",
        "Schub des Motors, und wie viel davon die Reifen<br>auf die Straße bringen."
        "<br>150 cc: 100 %, 200 cc: 150 %, 250 cc: 200 %",
        "Griff der Reifen, seitlich und in Fahrtrichtung.<br>Wenig Haftung: die Räder drehen durch,"
        "<br>das Kart rutscht. 100 %: der Wert der Figur",
        "Masse des Karts. Leicht: schneller Antritt, aber<br>weniger Höchstgeschwindigkeit."
        "<br>100 %: der Wert der Figur",
        "Bremskraft.<br>100 %: der Wert der Figur",
        "Größter Lenkeinschlag.<br>100 %: der Wert der Figur",
        "Drückt das Kart mit der Geschwindigkeit auf die Straße:<br>mehr Griff in Kurven,"
        " weniger Höchstgeschwindigkeit.<br>100 %: der Wert der Figur",
        "Schwerkraft des ganzen Rennens: alle Karts<br>und losen Gegenstände."
        "<br>100 %: wie im Spiel. Wenig: weite Sprünge",
        OPP_INFO)                              # the explanation of rows 1..9 on the detail pages
# the "Vorlage" row: the presets in their order, eight values (copied from the README, not from the
# patcher; 1.9 changed six, dropped Dragster and added four)
TUNE_PRESETS = (
    ("50 cc", (90, 100, 100, 100, 100, 100, 100, 100)), ("100 cc", (110, 100, 100, 100, 100, 100, 100, 100)),
    ("150 cc", (130, 100, 100, 100, 100, 100, 100, 100)), ("200 cc", (147, 150, 100, 100, 100, 100, 100, 100)),
    ("250 cc", (155, 200, 100, 100, 100, 100, 100, 100)), ("Rakete", (345, 325, 250, 100, 400, 200, 250, 100)),
    ("Formel 1", (360, 300, 200, 100, 400, 200, 350, 100)), ("Rallye", (180, 325, 50, 75, 100, 125, 100, 100)),
    ("Glatteis", (155, 200, 50, 100, 75, 125, 75, 100)), ("Bremsversagen", (265, 250, 100, 100, 25, 100, 325, 100)),
    ("Schwergewicht", (155, 250, 100, 250, 250, 100, 200, 100)), ("Federgewicht", (155, 100, 100, 50, 100, 100, 100, 100)),
    ("Federleicht", (290, 325, 175, 25, 100, 100, 175, 150)), ("Hetzjagd", (175, 275, 150, 100, 100, 100, 100, 100)),
    ("Schnecke", (50, 100, 100, 100, 100, 100, 100, 100)), ("Wahnsinn", (315, 350, 50, 25, 25, 100, 275, 300)),
    ("Mondfahrt", (155, 200, 100, 100, 100, 100, 100, 25)), ("Mondrakete", (360, 325, 175, 100, 100, 200, 350, 50)),
    ("Jupiter", (155, 200, 100, 100, 100, 100, 100, 250)))
OWN_BASE, OWN_MARK, OWN_MAGIC = 0x2C64, 0x2D64, 0x504E574F     # own presets: eight slots of 20h bytes
OWN_CUR, OWN_FLAG = OWN_MARK + 4, OWN_MARK + 8
VALUES8_MARK, VALUES8_MAGIC = OWN_MARK + 0xC, 0x544C4557         # "WELT": the save has eight values (patch 1.7)
TUNE_LAST = VALUES8_MARK + 4            # number of the preset copied last (up to 1.6 behind the seven values)
OPP_MARK, OPP_MAGIC = TUNE_LAST + 4, 0x4E474547                 # "GEGN": the save has "Gegner" (patch 1.9)
OWN_OPP, OWN_OPP_MARK, OWN_OPP_MAGIC = OPP_MARK + 8, OPP_MARK + 0x18, 0x5350504F   # the own slots' "Tempo" words
NEW_VALUE, NEW_MARK, NEW_MAGIC = TUNE_VALUES + 36, OWN_OPP_MARK + 4, 0x4757454E     # "Verbesserte Gegner" (patch 1.10), "NEWG"
NEW_LIMITS, NEW_DEFAULT = (0, 6, 1), 0
STD_MARK, STD_MAGIC = NEW_MARK + 4, 0x47445453                  # "STDG": the two values of "Gegner" count (patch 1.10)
PAGE_CHAMP = 0x0C                       # the championship page; item 9 is the button "Gegner" (patch 1.10)
CHAMP_ITEM_OPP = 9
NAV_INJ = 0x00884FC0                    # the test build's one-shot floats "menu up", "menu down" (prep_class5.py)
NEW_INFO = ("Wie viele der sechs Computer-Karts fahren die<br>gelernte Linie? Sie bremsen vor Kurven und"
            "<br>kommen seltener von der Strecke ab. 0: wie im Spiel")
PHYS_MANAGER = 0x005E84FC               # [[[it]+4]+4]+50h = the physics world's gravity, y
PAGE_OWN = 0x1E
ROW_NAMES = ("Motorkraft", "Haftung", "Gewicht", "Bremsen", "Lenkung", "Anpressdruck")
CLEAN = ("<color 200 200 200 255>", "<font 30px_redoutline>", "</font>", "<scale 0.5>", "<scale 0.6>", "</scale>", "<color 255 210 64 255>", "<color 255 170 0 255>", "</color>")


def plain(text):
    for tag in CLEAN:
        text = text.replace(tag, "")
    return text


def items(g):
    """(type, y, text) of every menu item."""
    m = g.menu
    begin, end = struct.unpack("<II", g.read(m + 0x134, 8))
    n = (end - begin) // 0x54 if begin else 0
    out = []
    for i in range(n):
        it = begin + i * 0x54
        typ = struct.unpack("<i", g.read(it, 4))[0]
        y = struct.unpack("<f", g.read(it + 0x28, 4))[0]
        out.append((typ, int(round(y)), plain(O.read_str(g.h, it + 8))))
    return out


def item_x(g, n):
    """An item's x, from the middle of the page (a float at +24h)."""
    begin = struct.unpack("<I", g.read(g.menu + 0x134, 4))[0]
    return round(struct.unpack("<f", g.read(begin + n * 0x54 + 0x24, 4))[0], 1)


def gp_i32(g, off):
    return struct.unpack("<i", g.read(g.gp + off, 4))[0]


def set_i32(g, off, value):
    g.write(g.gp + off, struct.pack("<i", value))


def menu_select(g, item, tries=6):
    """Press "menu select" on an item of a main menu page; returns the page state afterwards."""
    before = g.menu_state()
    for _ in range(tries):
        g.write(g.menu + 0x148, struct.pack("<i", item))
        g.write(G.NAME_INJ, struct.pack("<f", 1.0))
        time.sleep(0.7)
        if g.menu_state() != before:
            break
    time.sleep(0.5)
    return g.menu_state()


def set_menu_name(g, name):
    raw = name.encode("cp1252")
    m = g.menu
    s = bytearray(0x1C)
    s[0:4] = g.read(m + 0x17C, 4)
    s[4:4 + len(raw)] = raw
    struct.pack_into("<II", s, 0x14, len(raw), 15)
    g.write(m + 0x17C, bytes(s))
    g.write(m + 0x174, struct.pack("<i", len(raw)))      # the cursor behind it, as after typing


def hs_entry(g, cls, track0):
    e = g.read(g.gp + HS_TABLE + (ROW[cls] + track0) * HS_SIZE, HS_SIZE)
    times = [round(x, 2) for x in struct.unpack_from("<5f", e, 0)]
    names = [e[0x50 + 16 * i:0x60 + 16 * i].split(b"\0")[0].decode("cp1252") for i in range(5)]
    return times, names


def hs_raw(g, cls):
    """All eight used time trial entries of a class."""
    return g.read(g.gp + HS_TABLE + ROW[cls] * HS_SIZE, 9 * HS_SIZE)


def table(g, cls, track):                 # phantom header, track 1-based
    return g.read(g.gp + G.PH_TABLE + (ROW[cls] + track - 1) * G.PH_SIZE, G.PH_SIZE)


def champ_entry(g, cls, champ):
    e = g.read(g.gp + CHAMP_TABLE + (CHAMP_ROW[cls] + champ) * CHAMP_SIZE, CHAMP_SIZE)
    times = [round(x, 2) for x in struct.unpack_from("<5f", e, 0)]
    points = list(struct.unpack_from("<5i", e, 0x14))
    names = [e[0x28 + 16 * i:0x38 + 16 * i].split(b"\0")[0].decode("cp1252") for i in range(5)]
    return points, times, names


def champ_raw(g, cls):
    return g.read(g.gp + CHAMP_TABLE + CHAMP_ROW[cls] * CHAMP_SIZE, 4 * CHAMP_SIZE)


# ---------------------------------------------------------------------------------------------
def scenario_menu():
    note("== menu: engine class menu (page 8)")
    restore()
    g = G.Game(NEW_EXE)
    try:
        for level, want in ((2, ("label", "label")), (3, ("button", "label")), (4, ("button", "button")),
                            (5, ("button", "button"))):
            set_i32(g, UNLOCKED, level)
            g.page(8)
            time.sleep(0.6)
            its = items(g)
            note("   highest unlocked class %d: %r" % (level, its))
            texts = [t for _, _, t in its]
            check("level %d: six class rows in order" % level,
                  [t.replace("<color 128 128 128 255>", "").replace("</color>", "") for t in texts[1:7]],
                  ["50 cc", "100 cc", "150 cc", "200 cc", "250 cc", "Tuning" if level >= 5 else ""])
            check("level %d: rows at" % level, [y for _, y, _ in its[1:7]], [218, 254, 290, 326, 362, 398])
            check("level %d: 'Tuning' is %s" % (level, "a button" if level >= 5 else "an empty label"),
                  its[6][0], 1 if level >= 5 else 0)
            kinds = tuple("label" if "<color" in t else "button" for t in texts[4:6])
            check("level %d: 200 cc / 250 cc are" % level, kinds, want)
            check("level %d: item 7 is 'Zurück'" % level, texts[7], "Zurück")
            check("level %d: the hint text is still there" % level, any("Leistungsklasse wählen kannst" in t for t in texts))
            g.shot(os.path.join(SHOTS, "c5_menu_level%d.png" % level))
            g.page(0)
            time.sleep(0.3)

        note("-- selecting (all unlocked)")
        for item, cls in ((5, 4), (4, 3), (1, 0)):
            set_i32(g, 0x10, 1)
            g.page(8)
            time.sleep(0.5)
            st = menu_select(g, item)
            check("item %d selects class %d and opens the next page" % (item, cls), (gp_i32(g, 0x10), st), (cls, 6))
            g.page(0)
            time.sleep(0.3)
        set_i32(g, 0x10, 1)
        g.page(8)
        time.sleep(0.5)
        st = menu_select(g, 6)
        check("item 6 ('Tuning') selects class 5 and opens the tuning page", (gp_i32(g, 0x10), st), (5, PAGE_TUNING))
        g.page(0)
        time.sleep(0.3)
        set_i32(g, 0x10, 1)
        g.page(8)
        time.sleep(0.5)
        st = menu_select(g, 7)
        check("item 7 ('Zurück') leaves the page without changing the class", (gp_i32(g, 0x10), st != 8), (1, True))
        note("   page after 'Zurück': %d" % st)

        note("-- a locked class cannot be chosen")
        set_i32(g, UNLOCKED, 3)
        set_i32(g, 0x10, 1)
        g.page(0)
        time.sleep(0.3)
        g.page(8)
        time.sleep(0.5)
        st = menu_select(g, 5, tries=3)
        note("   select on the greyed-out 250 cc row: class %d, page %d" % (gp_i32(g, 0x10), st))
    finally:
        g.kill()


def scenario_tt250():
    note("== tt250: 250 cc, Winter (track 2): no phantom-5-02.mhk2 yet")
    restore()
    p502 = phantom(4, 2)
    check("no phantom file before", os.path.exists(p502), False)
    g = G.Game(NEW_EXE)
    try:
        before = {c: hs_raw(g, c) for c in (0, 1, 2, 3, 5)}
        ph_before = {c: g.read(g.gp + G.PH_TABLE + ROW[c] * G.PH_SIZE, 8 * G.PH_SIZE) for c in (0, 1, 2, 3, 5)}
        check("100 cc row, upper half: placeholders before the first 250 cc run",
              round(struct.unpack_from("<f", table(g, 4, 2), 0x58)[0], 2), 639.99)
        g.start_time_trial(4, 1)
        check("race started", T.wait_racing(g))
        check("class in the game", gp_i32(g, 0x10), 4)
        check("no ghost (gp+54h)", T.ghost_flag(g), 0)
        up, written = T.finish(g, (50.0, 50.0, 50.0))
        check("new-phantom.mhk2 written", up and written)
        d = data(NEWP)
        check("new phantom: track/class", struct.unpack_from("<2i", d, 0x4C), (2, 4))
        check("first run creates phantom-5-02.mhk2", os.path.exists(p502) and data(p502) == d)
        check("table entry (slot 97) is the new header", table(g, 4, 2) == g.header())
        st = g.select(0)
        note("   after 'Weiter': page %s, 250 cc highscores %r" % (hex(st) if st else st, hs_entry(g, 4, 1)))
        check("'Weiter' -> name entry (first 250 cc time is a highscore)", st, 0x13)
        g.set_name("Zweifuenfzig")
        st = g.select(0)
        check("name confirmed -> result list", st, 0x0F)
        times, names = hs_entry(g, 4, 1)
        check("250 cc highscore entry", (150.0 in times, "Zweifuenfzig" in names), (True, True))
        check("phantom-5-02.mhk2 got the name", data(p502)[8:20], T.name12("Zweifuenfzig"))
        note("   result list: %r" % ([plain(t) for _, t in g.overlay_items()],))
        g.shot(os.path.join(SHOTS, "c5_result_250cc.png"))
        for c in (0, 1, 2, 3, 5):
            check("time trial records of class %d untouched" % c, hs_raw(g, c) == before[c])
            check("phantom headers of class %d untouched" % c,
                  g.read(g.gp + G.PH_TABLE + ROW[c] * G.PH_SIZE, 8 * G.PH_SIZE) == ph_before[c])

        note("-- 'Rennen wiederholen': the new ghost, then a slower run")
        g.select(0)
        check("race restarted", T.wait_racing(g))
        check("the new 250 cc ghost is loaded (gp+54h)", T.ghost_flag(g), 1)
        up, written = T.finish(g, (60.0, 60.0, 60.0))
        check("slower 250 cc run leaves the phantom alone", data(p502)[0x58:0x5C], struct.pack("<f", 150.0))
        st = g.select(0)
        if st == 0x13:
            g.set_name("Zweiter")
            st = g.select(0)
        n0 = g.init_count()
        g.select(2)
        check("back in the main menu", g.wait_menu(n0, 60))
        check("after the menu re-read the files: 250 cc header", round(struct.unpack_from("<f", table(g, 4, 2), 0x58)[0], 2), 150.0)
        check("... and its name", table(g, 4, 2)[8:20], T.name12("Zweifuenfzig"))

        note("-- highscore browser, 250 cc")
        g.page(0x17)
        time.sleep(0.5)
        g.write(g.menu + 0x1AC, struct.pack("<i", 4))
        g.page(0)
        time.sleep(0.3)
        g.page(0x17)
        time.sleep(0.8)
        rows = [plain(t) for _, t in g.menu_items()]
        note("   browser items: %r" % (rows,))
        check("browser shows the class name", any(t == "250 cc" or "250 cc" in t for t in rows))
        g.shot(os.path.join(SHOTS, "c5_browser_250cc.png"))
        g.page(0)
    finally:
        g.kill()
    s = data(os.path.join(GAME, "settings.dat"))
    e = s[HS_TABLE - 4 + 97 * HS_SIZE:HS_TABLE - 4 + 98 * HS_SIZE]
    check("settings.dat on disk: 250 cc record in slot 97 (100 cc row, track 34)",
          sorted(round(x, 2) for x in struct.unpack_from("<5f", e, 0))[:2], [150.0, 180.0])


def scenario_tt200():
    note("== tt200: 200 cc, Winter (track 2) still uses slot 161")
    restore()
    p402 = phantom(3, 2)
    g = G.Game(NEW_EXE)
    try:
        before = {c: hs_raw(g, c) for c in (0, 1, 2, 4, 5)}
        g.start_time_trial(3, 1)
        check("race started", T.wait_racing(g))
        up, written = T.finish(g, (50.0, 50.0, 50.0))
        check("new-phantom.mhk2 written", up and written)
        d = data(NEWP)
        check("new phantom: track/class", struct.unpack_from("<2i", d, 0x4C), (2, 3))
        check("first run creates phantom-4-02.mhk2", os.path.exists(p402) and data(p402) == d)
        check("table entry (slot 161) is the new header", table(g, 3, 2) == g.header())
        st = g.select(0)
        if st == 0x13:
            g.set_name("Zweihundert")
            st = g.select(0)
        times, names = hs_entry(g, 3, 1)
        check("200 cc highscore entry", (150.0 in times, "Zweihundert" in names), (True, True))
        for c in (0, 1, 2, 4, 5):
            check("time trial records of class %d untouched" % c, hs_raw(g, c) == before[c])
    finally:
        g.kill()


NAME_OFFSET, NAME_MARK_OFFSET, NAME_MARK = 0x2F10, 0x2F30, 0x454D414E   # the name typed last (patch 1.2)


def stored_name(g):
    if g.u32(g.gp + NAME_MARK_OFFSET) != NAME_MARK:
        return None
    return g.read(g.gp + NAME_OFFSET, 16).split(b"\0")[0].decode("cp1252")


def scenario_namefill():
    note("== namefill: the name page shows the name typed last; an empty name takes it")
    restore()
    g = G.Game(NEW_EXE)
    try:
        g.write(g.gp + NAME_OFFSET, b"Tester".ljust(16, b"\0"))
        g.write(g.gp + NAME_MARK_OFFSET, struct.pack("<I", NAME_MARK))
        g.start_time_trial(3, 1)
        check("race started", T.wait_racing(g))
        T.finish(g, (50.0, 50.0, 50.0))
        st = g.select(0)
        check("'Weiter' -> name page", st, 0x13)
        ov = g.overlay()                               # the result pages are the race's overlay menu
        check("the field holds the stored name, the cursor behind it",
              (O.read_str(g.h, ov + 0x17C), g.u32(ov + 0x174)), ("Tester", 6))
        g.set_name("")
        g.write(ov + 0x174, struct.pack("<i", 0))
        st = g.select(0)
        check("an empty name is confirmed -> result list", st, 0x0F)
        times, names = hs_entry(g, 3, 1)
        check("the highscore gets the stored name", ("Tester" in names, stored_name(g)), (True, "Tester"))
        n0 = g.init_count()
        g.select(2)
        check("back in the main menu", g.wait_menu(n0, 60))
        texts = [t for _, _, t in items(g)]
        check("after a race the main menu shows the patch version", any(t.startswith("Patch 1.") for t in texts), True)
        note("-- championship name entry")
        trophy_page(g, 4, 2, 4, 0x1F)
        g.write(g.gp + 0x1C4, struct.pack("<f", 500.5))
        set_i32(g, 0x1E0, 38)
        st = menu_select(g, 0)
        check("'Weiter' on the trophy page -> name page", st, 0x13)
        check("the field holds the stored name", typed_name(g), "Tester")
        set_menu_name(g, "Meisterin")
        # a real key is seen by the game's name page and by the patch's hook; the test build feeds
        # them from two slots, so both get the key
        g.write(O.MENU_INJ + 4 * O.KEYS["select"], struct.pack("<f", 1.0))
        menu_select(g, 0, tries=1)
        points, times, names = champ_entry(g, 4, 2)
        check("the championship entry has the typed name, and it is stored for next time",
              ("Meisterin" in names, stored_name(g)), (True, "Meisterin"))
        g.page(0)
        time.sleep(0.6)
        texts = [t for _, _, t in items(g)]
        check("the main menu shows the patch version", any(t.startswith("Patch 1.") for t in texts), True)
        note("   main menu: %r" % (texts,))
        g.shot(os.path.join(SHOTS, "main_menu_version.png"))
    finally:
        g.kill()


def trophy_page(g, cls, champ, level, mask, rank=0):
    """Open the championship trophy page as if the player had just finished a championship."""
    g.page(0)
    time.sleep(0.3)
    set_i32(g, 0x1C, 1)                    # championship, one player
    set_i32(g, 0x10, cls)
    set_i32(g, 0x24, champ)
    set_i32(g, UNLOCKED, level)
    set_i32(g, MASK, mask)
    order = [k for k in range(7)]
    order.remove(0)
    order.insert(rank, 0)                  # kart 0 (the player) at this rank
    g.write(g.gp + 0x1FC, struct.pack("<7i", *order))
    g.page(0x1B)
    time.sleep(0.8)
    return [t for _, _, t in items(g)]


def scenario_champ():
    note("== champ: unlock chain, messages, championship highscores")
    restore()
    g = G.Game(NEW_EXE)
    try:
        note("   championship id table at gp+FCB8h: %r" % (struct.unpack("<8i", g.read(g.gp + 0xFCB8, 32)),))
        msg1 = "Du hast die erste Meisterschaft<br>in der %scc-Klasse freigeschaltet!"
        msg2 = "Du hast die zweite Meisterschaft<br>in der %scc-Klasse freigeschaltet!"
        cases = (
            # class, championship, level, mask -> message, level after, mask after
            (0, 3, 0, 0x00, msg1 % "100", 1, 0x00),
            (1, 3, 1, 0x00, msg1 % "150", 2, 0x00),
            (2, 3, 2, 0x00, msg1 % "200", 3, 0x00),
            (3, 3, 3, 0x00, msg1 % "250", 4, 0x00),
            (4, 3, 4, 0x00, TUNING_UNLOCKED, 5, 0x00),
            (4, 3, 5, 0x00, None, 5, 0x00),          # the tuning class is open already
            (5, 3, 5, 0x00, None, 5, 0x00),          # nothing behind the tuning class
            (3, 3, 4, 0x00, None, 4, 0x00),          # 250 cc is open already
            (0, 2, 0, 0x00, msg2 % "50", 0, 0x01),
            (1, 2, 4, 0x01, msg2 % "100", 4, 0x03),
            (2, 2, 4, 0x03, msg2 % "150", 4, 0x07),
            (3, 2, 4, 0x07, msg2 % "200", 4, 0x0F),
            (4, 2, 4, 0x0F, msg2 % "250", 4, 0x1F),
            (4, 2, 4, 0x1F, None, 4, 0x1F),          # second win: nothing new
        )
        for cls, champ, level, mask, want, level2, mask2 in cases:
            texts = trophy_page(g, cls, champ, level, mask)
            got = [t for t in texts if "freigeschaltet" in t]
            label = "class %d, championship %d, level %d, mask %02X" % (cls, champ, level, mask)
            check(label + ": message", got, [want] if want else [])
            check(label + ": level/mask afterwards", (gp_i32(g, UNLOCKED), gp_i32(g, MASK)), (level2, mask2))
            if cls in (3, 4) and want:
                time.sleep(0.5)                    # c5_unlock_c4_m3.png: the tuning class
                g.shot(os.path.join(SHOTS, "c5_unlock_c%d_m%d.png" % (cls, champ)))
        texts = trophy_page(g, 3, 3, 3, 0x0F, rank=1)
        check("second place unlocks nothing", ([t for t in texts if "freigeschaltet" in t], gp_i32(g, UNLOCKED)), ([], 3))

        note("-- track locks follow the mask bit of the class (track menu, track 6)")
        set_i32(g, UNLOCKED, 4)
        for cls, mask, want in ((4, 0x0F, "locked"), (4, 0x1F, "open"), (3, 0x17, "locked"), (3, 0x1F, "open"), (1, 0x1D, "locked")):
            set_i32(g, MASK, mask)
            set_i32(g, 0x10, cls)
            set_i32(g, 0x1C, 0)
            set_i32(g, 0x20, 5)
            g.page(0)
            time.sleep(0.3)
            g.page(7)                      # track menu
            time.sleep(0.6)
            rows = items(g)
            grey = [t for _, _, t in rows if "<color 128 128 128 255>" in t]
            note("   class %d, mask %02X: %r" % (cls, mask, [t for _, _, t in rows]))
            check("class %d, mask %02X: track 6 is %s" % (cls, mask, want), len(grey) > 0, want == "locked")
        g.page(0)

        note("-- championship highscore of 250 cc")
        before = {c: champ_raw(g, c) for c in (0, 1, 2, 3)}
        texts = trophy_page(g, 4, 2, 4, 0x1F)
        g.write(g.gp + 0x1C4, struct.pack("<f", 512.25))     # total time of kart 0
        set_i32(g, 0x1E0, 37)                                # its points
        st = menu_select(g, 0)
        check("'Weiter' on the trophy page -> name entry (new championship highscore)", st, 0x13)
        set_menu_name(g, "Meister250")
        st = menu_select(g, 0, tries=1)
        note("   page after confirming the name: %#x, menu result code %d" % (st, struct.unpack("<i", g.read(g.menu + 0x160, 4))[0]))
        points, times, names = champ_entry(g, 4, 2)
        note("   250 cc championship 2 entry (slot 32): %r %r %r" % (points, times, names))
        check("250 cc championship entry holds the result once",
              (points.count(37), times.count(512.25), names.count("Meister250")), (1, 1, 1))
        for c in (0, 1, 2, 3):
            check("championship records of class %d untouched" % c, champ_raw(g, c) == before[c])
        g.page(0)
        time.sleep(0.3)
        g.page(0x19)
        time.sleep(0.5)
        g.write(g.menu + 0x1AC, struct.pack("<i", 4))
        g.page(0)
        time.sleep(0.3)
        g.page(0x19)
        time.sleep(0.8)
        rows = [plain(t) for _, t in g.menu_items()]
        note("   championship browser items: %r" % (rows,))
        check("championship browser shows class and name", (any("250 cc" in t for t in rows), any("Meister250" in t for t in rows)), (True, True))
        g.shot(os.path.join(SHOTS, "c5_champ_browser_250cc.png"))
        g.page(0)

        note("-- championship highscore of the tuning class")
        before = {c: champ_raw(g, c) for c in (0, 1, 2, 3, 4)}
        texts = trophy_page(g, 5, 3, 4, 0x3F)
        check("tuning class, championship 3: no unlock message, level unchanged",
              ([t for t in texts if "freigeschaltet" in t], gp_i32(g, UNLOCKED)), ([], 4))
        g.write(g.gp + 0x1C4, struct.pack("<f", 433.5))
        set_i32(g, 0x1E0, 40)
        st = menu_select(g, 0)
        check("'Weiter' on the trophy page -> name entry", st, 0x13)
        set_menu_name(g, "Tuner")
        menu_select(g, 0, tries=1)
        points, times, names = champ_entry(g, 5, 3)
        note("   tuning class championship 3 entry (slot 13): %r %r %r" % (points, times, names))
        check("tuning class championship entry holds the result once",
              (points.count(40), times.count(433.5), names.count("Tuner")), (1, 1, 1))
        for c in (0, 1, 2, 3, 4):
            check("championship records of class %d untouched" % c, champ_raw(g, c) == before[c])
        g.page(0)
    finally:
        g.kill()


def scenario_oldsave():
    note("== oldsave: settings.dat with 200 cc unlocked (as patch 1.2 left it)")
    restore()
    s = bytearray(data(os.path.join(GAME, "settings.dat")))
    note("   highest unlocked class in the pristine file: %d" % struct.unpack_from("<i", s, UNLOCKED - 4)[0])
    g = G.Game(NEW_EXE)
    try:
        check("level read from the file", gp_i32(g, UNLOCKED), 3)
        g.page(8)
        time.sleep(0.6)
        texts = [t for _, _, t in items(g)]
        check("200 cc selectable, 250 cc greyed out, tuning hidden", ["<color" in t for t in texts[4:6]] + [texts[6]],
              [False, True, ""])
        g.shot(os.path.join(SHOTS, "c5_menu_oldsave.png"))
        g.page(0)
    finally:
        g.kill()
    import subprocess
    out = subprocess.run([sys.executable, T.PATCHER, "--unlock", os.path.join(GAME, "settings.dat")], capture_output=True, text=True)
    note("   " + (out.stdout + out.stderr).strip())
    s = data(os.path.join(GAME, "settings.dat"))
    check("--unlock sets the level to 4 and opens championship 2 of 50 cc to 250 cc",
          struct.unpack_from("<iI", s, UNLOCKED - 4), (4, struct.unpack_from("<I", s, MASK - 4)[0] | 0x1F))
    check("... mask bits 0..4 set", struct.unpack_from("<I", s, MASK - 4)[0] & 0x1F, 0x1F)
    out = subprocess.run([sys.executable, T.PATCHER, "--unlock-tuning", os.path.join(GAME, "settings.dat")], capture_output=True, text=True)
    note("   " + (out.stdout + out.stderr).strip())
    s = data(os.path.join(GAME, "settings.dat"))
    check("--unlock-tuning sets the level to 5", struct.unpack_from("<i", s, UNLOCKED - 4)[0], 5)



UNLOCK_MARK, UNLOCK_MAGIC = STD_MARK + 4, 0x49455246            # "FREI": the switch "Alles freigeschaltet" (patch 1.10)


def unlock_on(g):
    return g.u32(g.gp + UNLOCK_MARK) == UNLOCK_MAGIC


def options_key(g, item, key):
    g.write(g.menu + 0x148, struct.pack("<i", item))
    time.sleep(0.2)
    g.write(O.MENU_INJ + 4 * O.KEYS[key], struct.pack("<f", 1.0))
    time.sleep(0.5)


def class_rows(g):
    """The class menu's six rows: 'button', 'grey' or 'hidden' each."""
    g.page(0)
    time.sleep(0.3)
    g.page(8)
    time.sleep(0.6)
    its = items(g)
    return [("hidden" if not t else "grey" if "<color 128" in t else "button") if typ in (0, 1) else "?"
            for typ, _, t in its[1:7]]


def track6_open(g, cls):
    set_i32(g, 0x10, cls)
    set_i32(g, 0x1C, 0)
    set_i32(g, 0x20, 5)
    g.page(0)
    time.sleep(0.3)
    g.page(7)                              # track menu, track 6
    time.sleep(0.6)
    return not any("<color 128 128 128 255>" in t for _, _, t in items(g))


def scenario_unlockall():
    note("== unlockall: the switch 'Alles freigeschaltet' on the options page")
    restore()
    g = G.Game(NEW_EXE)
    try:
        set_i32(g, UNLOCKED, 0)            # a new player: only 50 cc, championship 1
        set_i32(g, MASK, 0)
        check("the switch is off in the fixture's save", unlock_on(g), False)
        g.page(1)
        time.sleep(0.5)
        its = items(g)
        note("   %r" % (its,))
        check("options page: the new row above the physics switch, 'Zurück' last",
              [(typ, t) for typ, _, t in its[7:12]],
              [(0, "Alles freigeschaltet"), (3, "Aus"), (0, "60-FPS-Fahrphysik"), (3, "Aus" if g.u32(g.gp + 0x4C) >> 8 != 0x463036 else "An"),
               (1, "Zurück")])
        check("rows from top to bottom", [y for _, y, _ in its[:12]], sorted(y for _, y, _ in its[:12]))
        check("row positions", [y for _, y, _ in its[:12]], [118, 152, 194, 228, 272, 316, 350, 392, 426, 468, 502, 548])
        g.shot(os.path.join(SHOTS, "unlock_options_off.png"))

        phys0 = g.u32(g.gp + 0x4C)
        options_key(g, 8, "select")
        check("select switches it on", (unlock_on(g), items(g)[8][2]), (True, "An"))
        check("... and leaves the physics switch alone", g.u32(g.gp + 0x4C), phys0)
        options_key(g, 8, "left")
        check("left switches it off", (unlock_on(g), items(g)[8][2]), (False, "Aus"))
        options_key(g, 8, "right")
        check("right switches it on", (unlock_on(g), items(g)[8][2]), (True, "An"))
        g.shot(os.path.join(SHOTS, "unlock_options_on.png"))
        options_key(g, 10, "select")
        check("the physics switch still flips on its own", (g.u32(g.gp + 0x4C) != phys0, unlock_on(g)), (True, True))
        options_key(g, 10, "select")
        check("... and back", g.u32(g.gp + 0x4C), phys0)

        check("on: every class is a button", class_rows(g), ["button"] * 6)
        g.shot(os.path.join(SHOTS, "unlock_classes_on.png"))
        st = menu_select(g, 6)
        check("on: 'Tuning' opens the tuning page", (gp_i32(g, 0x10), st), (5, PAGE_TUNING))
        check("on: track 6 is open in 50 cc and 250 cc", (track6_open(g, 0), track6_open(g, 4)), (True, True))
        set_i32(g, 0x10, 2)
        g.page(0)
        time.sleep(0.3)
        g.page(PAGE_CHAMP)
        time.sleep(0.8)
        check("on: the championship page has the button 'Gegner'", [t for _, _, t in items(g)[9:10]], ["Gegner"])
        g.page(0)
        time.sleep(0.3)
        check("on: the progress itself is untouched", (gp_i32(g, UNLOCKED), gp_i32(g, MASK) & 0x1F), (0, 0))

        g.write(g.gp + UNLOCK_MARK, struct.pack("<I", 0))
        check("off: only 50 cc, 100 cc / 150 cc / 200 cc / 250 cc grey, tuning hidden", class_rows(g),
              ["button", "grey", "grey", "grey", "grey", "hidden"])
        check("off: track 6 is locked in 50 cc", track6_open(g, 0), False)
        set_i32(g, UNLOCKED, 3)
        set_i32(g, MASK, 0x05)
        check("off: the real progress shows again (level 3)", class_rows(g), ["button"] * 4 + ["grey", "hidden"])
        check("off: track 6 follows the mask (50 cc open, 100 cc locked)", (track6_open(g, 0), track6_open(g, 1)), (True, False))
        g.page(0)
        time.sleep(0.3)

        note("-- the switch is saved with settings.dat and loaded again")
        g.write(g.gp + UNLOCK_MARK, struct.pack("<I", UNLOCK_MAGIC))
        g.start_time_trial(0, 0)           # leaving the menu writes settings.dat
        time.sleep(1.0)
    finally:
        g.kill()
    s = data(os.path.join(GAME, "settings.dat"))
    check("settings.dat holds the switch and the real progress",
          (s[UNLOCK_MARK - 4:UNLOCK_MARK], struct.unpack_from("<i", s, UNLOCKED - 4)[0]), (b"FREI", 3))
    g = G.Game(NEW_EXE)
    try:
        check("after a restart the switch is on", unlock_on(g))
        g.page(1)
        time.sleep(0.5)
        check("... and the options page says so", items(g)[8][2], "An")
        check("... and every class is a button", class_rows(g), ["button"] * 6)
        g.page(0)
    finally:
        g.kill()


def scenario_browser():
    note("== browser: left / right on the class row of the highscore browsers")
    restore()
    names = ["50 cc", "100 cc", "150 cc", "200 cc", "250 cc", "Tuning"]
    g = G.Game(NEW_EXE)
    try:
        for state, what in ((0x17, "time trial lists"), (0x19, "championship lists")):
            g.page(state)
            time.sleep(0.5)
            g.write(g.menu + 0x1AC, struct.pack("<i", 0))
            g.page(0)
            time.sleep(0.3)
            g.page(state)
            time.sleep(0.6)
            for key, want in (("right", [1, 2, 3, 4, 5, 0]), ("left", [5, 4, 3, 2, 1, 0])):
                seen, shown = [], []
                for _ in range(6):
                    g.write(g.menu + 0x148, struct.pack("<i", 1))            # the class row
                    g.write(O.MENU_INJ + 4 * O.KEYS[key], struct.pack("<f", 1.0))
                    time.sleep(0.7)
                    seen.append(struct.unpack("<i", g.read(g.menu + 0x1AC, 4))[0])
                    shown.append(plain(g.menu_items()[1][1]))
                check("%s, six times %s: class" % (what, key), seen, want)
                check("%s, six times %s: class name shown" % (what, key), shown, [names[c] for c in want])
            g.page(0)
            time.sleep(0.3)
    finally:
        g.kill()


def tune_values(g):
    return struct.unpack("<8i", g.read(g.gp + TUNE_VALUES, 32))


def opp(g):
    """The ninth tuning value, "Gegner"."""
    return struct.unpack("<i", g.read(g.gp + TUNE_VALUES + 32, 4))[0]


def tune_all(g):
    return tune_values(g) + (opp(g),)


def improved(g):
    """The second row of "Gegner": how many computer karts drive the learned way (patch 1.10)."""
    return struct.unpack("<i", g.read(g.gp + NEW_VALUE, 4))[0]


def set_opp(g, tempo):
    """Writes "Tempo" of "Gegner" (OPP_STD = "Standard") with the marker that makes it count."""
    g.write(g.gp + TUNE_VALUES + 32, struct.pack("<i", tempo))
    g.write(g.gp + STD_MARK, struct.pack("<I", STD_MAGIC))
    if g.u32(g.gp + NEW_MARK) != NEW_MAGIC:
        g.write(g.gp + NEW_VALUE, struct.pack("<i", 0))
        g.write(g.gp + NEW_MARK, struct.pack("<I", NEW_MAGIC))


def set_improved(g, n):
    if g.u32(g.gp + STD_MARK) != STD_MAGIC:
        set_opp(g, OPP_STD)
    g.write(g.gp + NEW_VALUE, struct.pack("<i", n))
    g.write(g.gp + NEW_MARK, struct.pack("<I", NEW_MAGIC))


def set_tune(g, values):
    """Writes the tuning values; seven values (a set from before 1.7) get gravity 100 %. A ninth
    value is "Tempo" of "Gegner"; without one it stays as it is."""
    values = tuple(values) + (100,) * (8 - len(values))
    g.write(g.gp + TUNE_VALUES, struct.pack("<8i", *values[:8]))
    if len(values) > 8:
        set_opp(g, values[8])
    g.write(g.gp + TUNE_MARK, struct.pack("<I", TUNE_MAGIC))
    g.write(g.gp + VALUES8_MARK, struct.pack("<I", VALUES8_MAGIC))     # else the game converts them as a 1.6 save
    g.write(g.gp + OPP_MARK, struct.pack("<I", OPP_MAGIC))             # ... or as a 1.8 save


# the line at the defaults (as plain() leaves it), with the top speed of the fixture's character (Moorhuhn)
LIMIT_DEFAULT = "<color 190 190 190 255>Anspruch 0 (Am Limit ab 24), Risiko 0<br>Top speed: ca. 220 km/h"


def p9(k):
    """The eight values of preset k (up to 1.9 a preset had "Tempo" as a ninth)."""
    return TUNE_PRESETS[k][1]


def preset_name(values):
    return next((n for n, v in TUNE_PRESETS if v == tuple(values)), "Ungespeichert")


def kart_texts(values):
    """What the seven rows of the page "Kart" should read for these values."""
    return ["Übersetzung: %d.%02d" % divmod(values[0], 100)] + ["%s: %d %%" % (n, v) for n, v in zip(ROW_NAMES, values[1:7])]


def world_texts(values):
    return ["Schwerkraft: %d %%" % values[7]]


def opp_texts(values):
    return ["Tempo: Standard" if values[8] == OPP_STD else "Tempo: %d %%" % values[8]]


def opp_line(tempo=OPP_STD, new=0):
    """The two values of "Gegner" in one line, as the championship page's button and the pause page show them."""
    return ("Tempo Standard, verbessert %d" % new) if tempo == OPP_STD else "Tempo %d %%, verbessert %d" % (tempo, new)


def nav(g, key, item=None):
    """"menu up" / "menu down" (the test build serves them to Menu::Navigate), from an item if given."""
    if item is not None:
        g.write(g.menu + 0x148, struct.pack("<i", item))
        time.sleep(0.1)
    g.write(NAV_INJ + 4 * ("up", "down").index(key), struct.pack("<f", 1.0))
    time.sleep(0.4)
    return sel(g)


def sel(g):
    return struct.unpack("<i", g.read(g.menu + 0x148, 4))[0]


def press(g, key, item=None, arrow=None):
    """One of the tuning pages' actions (back, select, left, right), on an item if given."""
    if item is not None:
        g.write(g.menu + 0x148, struct.pack("<i", item))
    if arrow is not None:
        g.write(g.menu + 0x14C, struct.pack("<i", arrow))
    g.write(O.MENU_INJ + 4 * O.KEYS[key], struct.pack("<f", 1.0))
    time.sleep(0.6)


def row_place(row):
    """(page, item) where a row sits: 0 "Vorlage", 1..7 "Kart", 8 "Welt"; 9 "Tempo" on the page "Gegner"."""
    if row == 0:
        return PAGE_TUNING, 0
    if row <= 7:
        return PAGE_KART, row - 1
    if row == 8:
        return PAGE_WORLD, 0
    return PAGE_OPP, 0


def goto(g, page):
    if g.menu_state() != page:
        g.page(page)
        time.sleep(0.6)


def step_row(g, row, key):
    """left / right on a row, on its page (opened straight if it is not shown)."""
    page, item = row_place(row)
    goto(g, page)
    press(g, key, item)


def world_gravity(g):
    world = g.u32(g.u32(g.u32(PHYS_MANAGER) + 4) + 4)
    return round(struct.unpack("<f", g.read(world + 0x50, 4))[0], 3)


def scenario_tuning():
    note("== tuning: the tuning page (1Dh) and the pages 'Kart' (1Fh) and 'Welt' (20h)")
    restore()
    g = G.Game(NEW_EXE)
    try:
        check("an older save has no tuning values yet (marker)", g.u32(g.gp + TUNE_MARK) == TUNE_MAGIC, False)
        mask0 = gp_i32(g, MASK)
        g.page(8)
        time.sleep(0.5)
        st = menu_select(g, 6)
        check("'Tuning' sets class 5 and opens the tuning page", (gp_i32(g, 0x10), st), (5, PAGE_TUNING))
        its = items(g)
        note("   %r" % (its,))
        check("items", [t for _, _, t in its],
              ["Vorlage: 250 cc", "Kart", "Welt", "Zurücksetzen", "Eigene Vorlagen", "Weiter", "Zurück", LIMIT_DEFAULT]
              + list(tune_line(TUNE_DEFAULT)) + ["Tuning"])
        check("item types: 'Vorlage' with arrows, buttons, the (empty) 'Am Limit' line, the values, title",
              [t for t, _, _ in its], [3] + [1] * 6 + [0] * 4)
        check("items from top to bottom", [y for _, y, _ in its[:7]] == sorted(y for _, y, _ in its[:7]), True)
        check("each group's values under its button: Kart, line, Welt, line, 'Am Limit', Zurücksetzen",
              [y for _, y, _ in (its[1], its[8], its[2], its[9], its[7], its[3])]
              == sorted(y for _, y, _ in (its[1], its[8], its[2], its[9], its[7], its[3])), True)
        check("defaults stored, with the markers ('Gegner': 'Standard' and 0)",
              (tune_all(g), improved(g), g.u32(g.gp + TUNE_MARK), g.u32(g.gp + VALUES8_MARK), g.u32(g.gp + TUNE_LAST),
               g.u32(g.gp + OPP_MARK), g.u32(g.gp + NEW_MARK), g.u32(g.gp + STD_MARK)),
              (TUNE_DEFAULT9, 0, TUNE_MAGIC, VALUES8_MAGIC, 4, OPP_MAGIC, NEW_MAGIC, STD_MAGIC))
        check("tracks 5-8 are open in the tuning class (mask bit 5)", gp_i32(g, MASK), mask0 | 0x20)
        check("'Weiter' is selected", sel(g), 5)
        g.shot(os.path.join(SHOTS, "tune_page.png"))

        note("-- the page 'Kart'")
        press(g, "select", 1)
        its = items(g)
        note("   %r" % (its,))
        check("'Kart' opens page 1Fh, first row selected", (g.menu_state(), sel(g)), (PAGE_KART, 0))
        check("its items: rows, 'Zurück', 'Am Limit', the explanation of the first row, title",
              [t for _, _, t in its], kart_texts(TUNE_DEFAULT) + ["Zurück", LIMIT_DEFAULT, INFO[0], "Kart"])
        check("its item types", [t for t, _, _ in its], [3] * 7 + [1, 0, 0, 0])
        bad = []
        for item in list(range(7)) + [7, 2]:
            g.write(g.menu + 0x148, struct.pack("<i", item))
            time.sleep(0.4)
            want = INFO[item] if item < 7 else ""
            if items(g)[9][2] != want:
                bad.append((item, items(g)[9][2]))
        check("the explanation follows the selected row, empty on 'Zurück'", bad, [])
        check("rows from top to bottom", [y for _, y, _ in its[:8]] == sorted(y for _, y, _ in its[:8]), True)
        g.shot(os.path.join(SHOTS, "tune_kart.png"))
        press(g, "select", 7)
        check("its 'Zurück' -> tuning page at 'Kart'", (g.menu_state(), sel(g)), (PAGE_TUNING, 1))
        press(g, "select", 1)
        press(g, "back")
        check("'menu back' there -> tuning page at 'Kart'", (g.menu_state(), sel(g)), (PAGE_TUNING, 1))

        note("-- the page 'Welt'")
        press(g, "select", 2)
        its = items(g)
        note("   %r" % (its,))
        check("'Welt' opens page 20h, its row selected", (g.menu_state(), sel(g)), (PAGE_WORLD, 0))
        check("its items and types", its and [(t, s) for t, _, s in its],
              [(3, "Schwerkraft: 100 %"), (1, "Zurück"), (0, LIMIT_DEFAULT), (0, INFO[7]), (0, "Welt")])
        g.shot(os.path.join(SHOTS, "tune_world.png"))
        press(g, "select", 1)
        check("its 'Zurück' -> tuning page at 'Welt'", (g.menu_state(), sel(g)), (PAGE_TUNING, 2))
        press(g, "select", 2)
        press(g, "back")
        check("'menu back' there -> tuning page at 'Welt'", (g.menu_state(), sel(g)), (PAGE_TUNING, 2))

        note("-- 'Gegner' is no part of the tuning class (patch 1.10): presets and 'Zurücksetzen' leave its values alone")
        set_opp(g, 150)
        set_improved(g, 6)
        goto(g, PAGE_KART)
        goto(g, PAGE_TUNING)
        check("the 'Vorlage' row still reads '250 cc'", items(g)[0][2], "Vorlage: 250 cc")
        press(g, "right", 0)
        check("copying a preset leaves them alone", (tune_values(g), opp(g), improved(g)), (TUNE_PRESETS[5][1], 150, 6))
        press(g, "select", 3)
        check("'Zurücksetzen' too", (tune_values(g), opp(g), improved(g)), (TUNE_DEFAULT, 150, 6))
        set_opp(g, OPP_STD)
        set_improved(g, 0)

        note("-- every value: a step right, a step left, and its limits")
        for row, (lo, hi, step) in enumerate(TUNE_LIMITS + (OPP_LIMITS,), 1):
            v = row - 1
            d = TUNE_DEFAULT9[v]
            page, item = row_place(row)
            goto(g, page)
            first, second = ("left", "right") if d == hi else ("right", "left")
            press(g, first, item)
            check("row %d: %s" % (row, first), tune_all(g)[v], d + (step if first == "right" else -step))
            texts = [t for _, _, t in items(g)]
            want = {PAGE_KART: kart_texts, PAGE_WORLD: world_texts, PAGE_OPP: opp_texts}[page](tune_all(g))
            check("row %d: its page shows the value" % row, texts[:len(want)], want)
            press(g, second, item)
            check("row %d: %s" % (row, second), tune_all(g)[v], d)
            vals = list(tune_all(g))
            vals[v] = hi
            set_tune(g, vals)
            press(g, "right", item)
            check("row %d: stops at its maximum" % row, tune_all(g)[v], hi)
            vals[v] = lo
            set_tune(g, vals)
            press(g, "left", item)
            check("row %d: stops at its minimum" % row, tune_all(g)[v], lo)
            if lo < 0:
                check("row %d: its lowest step reads 'Standard'" % row, items(g)[0][2], "Tempo: Standard")
                vals[v] = -100
                set_tune(g, vals)
                press(g, "left", item)
                press(g, "right", item)
                check("row %d: a negative value reads right" % row, (tune_all(g)[v], items(g)[0][2]), (-100, "Tempo: -100 %"))
            vals[v] = d
            set_tune(g, vals)
        check("the other rows kept their values", tune_all(g), TUNE_DEFAULT9)

        note("-- 'select' on a row does nothing, left / right on the buttons neither; 'Vorlage' follows")
        goto(g, PAGE_KART)
        press(g, "right", 0)
        press(g, "right", 1)
        press(g, "select", 2)
        check("'select' on a row itself changes nothing", tune_values(g)[:3], (160, 225, 100))
        press(g, "left", 7)
        check("left on 'Zurück' changes nothing", (tune_values(g)[:3], g.menu_state()), ((160, 225, 100), PAGE_KART))
        press(g, "select", 7)
        check("back on the tuning page: 'Vorlage' reads 'Ungespeichert'", items(g)[0][2], "Vorlage: Ungespeichert")
        press(g, "select", 0)
        press(g, "left", 4)
        press(g, "right", 5)
        check("'select' on 'Vorlage' and left / right on the buttons change nothing", tune_values(g)[:3], (160, 225, 100))
        g.write(g.menu + 0x148, struct.pack("<i", 0))
        time.sleep(0.3)
        g.shot(os.path.join(SHOTS, "tune_page_changed.png"))

        note("-- the 'Vorlage' row: every preset to the right, then to the left")
        press(g, "select", 3)                          # back to the defaults = "250 cc"
        n = len(TUNE_PRESETS)
        order = [(4 + k) % n for k in range(1, n + 1)]     # from 250 cc on, once round
        bad = []
        for k in order:
            press(g, "right", 0)
            if (tune_all(g) != p9(k) + (OPP_STD,) or items(g)[0][2] != "Vorlage: " + TUNE_PRESETS[k][0]
                    or lines(g) != tune_line(TUNE_PRESETS[k][1])):
                bad.append((TUNE_PRESETS[k][0], tune_all(g), items(g)[0][2], lines(g)))
            if TUNE_PRESETS[k][0] == "Rakete":
                g.shot(os.path.join(SHOTS, "tune_page_preset.png"))
        check("right: each preset's values are copied, named and listed, in order, wrapping after the last; 'Tempo' stays", bad, [])
        bad = []
        for k in reversed(order[:-1]):
            press(g, "left", 0)
            if tune_values(g) != TUNE_PRESETS[k][1] or items(g)[0][2] != "Vorlage: " + TUNE_PRESETS[k][0]:
                bad.append((TUNE_PRESETS[k][0], tune_values(g), items(g)[0][2]))
        press(g, "left", 0)
        check("left: the same presets backwards, wrapping before the first", (bad, tune_values(g)), ([], TUNE_PRESETS[4][1]))
        check("the selection stays on 'Vorlage'", sel(g), 0)
        k = [n for n, _ in TUNE_PRESETS].index("Jupiter")
        set_tune(g, p9(k - 1))
        press(g, "right", 0)
        press(g, "select", 2)
        check("'Jupiter' sets the gravity to 250 %", (tune_values(g)[7], items(g)[0][2]), (250, "Schwerkraft: 250 %"))
        press(g, "select", 1)
        press(g, "select", 1)
        check("... and its kart rows are those of 250 cc", [t for _, _, t in items(g)[:7]], kart_texts(TUNE_PRESETS[k][1]))
        press(g, "back")

        note("-- 'Ungespeichert', and where left / right go from there")
        set_tune(g, p9(4))
        press(g, "right", 0)                           # Rakete
        step_row(g, 6, "left")                         # Lenkung 200 -> 175
        changed = TUNE_PRESETS[5][1][:5] + (175,) + TUNE_PRESETS[5][1][6:]
        goto(g, PAGE_TUNING)
        check("a changed value: 'Ungespeichert', the other values kept",
              (items(g)[0][2], tune_values(g)), ("Vorlage: Ungespeichert", changed))
        check("... and the values line shows the change", lines(g), tune_line(changed))
        press(g, "right", 0)
        check("right from 'Ungespeichert' after 'Rakete': 'Formel 1'", (items(g)[0][2], tune_values(g)),
              ("Vorlage: Formel 1", TUNE_PRESETS[6][1]))
        step_row(g, 8, "left")                         # Schwerkraft 100 -> 75
        goto(g, PAGE_TUNING)
        check("a changed gravity is 'Ungespeichert' too, the line has it",
              (items(g)[0][2], lines(g)), ("Vorlage: Ungespeichert", tune_line(TUNE_PRESETS[6][1][:7] + (75,))))
        press(g, "left", 0)
        check("left from 'Ungespeichert' after 'Formel 1': 'Rakete'", (items(g)[0][2], tune_values(g)),
              ("Vorlage: Rakete", TUNE_PRESETS[5][1]))
        set_tune(g, (160, 225, 100, 100, 100, 100, 100, 100))
        g.write(g.gp + TUNE_LAST, struct.pack("<i", 99))   # what an odd save could hold
        press(g, "right", 0)
        check("with no valid last preset, right counts from '250 cc'", tune_values(g), TUNE_PRESETS[5][1])
        set_tune(g, p9(3))
        step_row(g, 2, "right")
        step_row(g, 2, "left")
        goto(g, PAGE_TUNING)
        check("stepping a value back onto a preset shows its name", items(g)[0][2], "Vorlage: 200 cc")
        step_row(g, 1, "right")
        check("200 cc's 1.47 steps to 1.52 (the row's own 0.05 steps)", tune_values(g)[0], 152)

        note("-- the buttons and the ways out")
        goto(g, PAGE_TUNING)
        press(g, "select", 3)
        check("'Zurücksetzen': defaults, same page, same item", (tune_all(g), g.menu_state(), sel(g)),
              (TUNE_DEFAULT9, PAGE_TUNING, 3))
        check("'Vorlage' shows '250 cc' again, the preset copied last is '250 cc'",
              (items(g)[0][2], g.u32(g.gp + TUNE_LAST)), ("Vorlage: 250 cc", 4))
        check("... the values line the defaults", lines(g), tune_line(TUNE_DEFAULT))
        press(g, "select", 6)
        check("'Zurück' -> class menu", g.menu_state(), 8)
        goto(g, PAGE_TUNING)
        press(g, "back")
        check("'menu back' -> class menu", g.menu_state(), 8)
        goto(g, PAGE_TUNING)
        press(g, "select", 5)
        check("'Weiter' -> character menu, class still 5", (g.menu_state(), gp_i32(g, 0x10)), (6, 5))

        note("-- the values survive the game's own save and load")
        set_tune(g, (210, 325, 150, 75, 250, 125, 300, 175, 30))
        g.write(g.gp + TUNE_LAST, struct.pack("<i", 11))
        g.page(0)
        time.sleep(0.3)
        g.start_time_trial(5, 0)             # leaving the menu saves settings.dat
        check("race started", T.wait_racing(g))
        check("the race has the gravity: 175 % of 19.62", world_gravity(g), round(-19.62 * 1.75, 3))
    finally:
        g.kill()
    s = data(os.path.join(GAME, "settings.dat"))
    check("settings.dat on disk holds the values, the preset copied last and the markers",
          (struct.unpack_from("<9i", s, TUNE_VALUES - 4), struct.unpack_from("<I", s, TUNE_MARK - 4)[0],
           struct.unpack_from("<3I", s, VALUES8_MARK - 4), struct.unpack_from("<I", s, STD_MARK - 4)[0]),
          ((210, 325, 150, 75, 250, 125, 300, 175, 30), TUNE_MAGIC, (VALUES8_MAGIC, 11, OPP_MAGIC), STD_MAGIC))
    g = G.Game(NEW_EXE)
    try:
        check("after a restart the game has them", tune_all(g), (210, 325, 150, 75, 250, 125, 300, 175, 30))
        goto(g, PAGE_KART)
        check("... the page 'Kart' shows them", [t for _, _, t in items(g)[:7]], kart_texts(tune_values(g)))
        goto(g, PAGE_WORLD)
        check("... the page 'Welt' too", items(g)[0][2], "Schwerkraft: 175 %")
        goto(g, PAGE_OPP)
        check("... and 'Gegner'", items(g)[0][2], "Tempo: 30 %")
        goto(g, PAGE_TUNING)
        check("... 'Vorlage' reads 'Ungespeichert', the values line has them",
              (items(g)[0][2], lines(g)), ("Vorlage: Ungespeichert", tune_line(tune_values(g))))
        press(g, "right", 0)
        check("right after a restart: the preset after the one copied last ('Federgewicht' -> 'Federleicht')",
              tune_values(g), TUNE_PRESETS[12][1])
        g.page(0)
    finally:
        g.kill()


def scenario_save16():
    note("== save16: a settings.dat as patch 1.6 left it (seven values, own slots with 'filled' = 1)")
    restore()
    path = os.path.join(GAME, "settings.dat")
    s = bytearray(data(path))
    old = (250, 500, 200, 100, 200, 125, 100)
    struct.pack_into("<7i", s, TUNE_VALUES - 4, *old)
    struct.pack_into("<i", s, TUNE_VALUES - 4 + 28, 15)        # 1.6: own slot 2 copied last
    struct.pack_into("<I", s, TUNE_MARK - 4, TUNE_MAGIC)
    struct.pack_into("<i", s, TUNE_VALUES - 4 + 32, 3)         # the character of rank 1 is there up to 1.8
    for n in range(8):
        struct.pack_into("<32s", s, OWN_BASE - 4 + 0x20 * n, b"")
    struct.pack_into("<7HH", s, OWN_BASE - 4, *(300, 400, 150, 75, 125, 100, 200), 1)
    struct.pack_into("<7HH", s, OWN_BASE - 4 + 0x20, *old, 1)
    s[OWN_BASE - 4 + 0x30:OWN_BASE - 4 + 0x36] = b"Meins\0"
    struct.pack_into("<3I", s, OWN_MARK - 4, OWN_MAGIC, 1, 0)
    open(path, "wb").write(s)
    g = G.Game(NEW_EXE)
    try:
        check("loaded as it was (no 1.7 marker yet)", g.u32(g.gp + VALUES8_MARK) == VALUES8_MAGIC, False)
        g.page(PAGE_TUNING)
        time.sleep(0.6)
        check("converted: seven values kept, gravity 100 %, 'Tempo' of 'Gegner' at 'Standard' with its markers",
              (tune_all(g), g.u32(g.gp + OPP_MARK), g.u32(g.gp + STD_MARK)), (old + (100, OPP_STD), OPP_MAGIC, STD_MAGIC))
        check("... and 'Verbesserte Gegner' 0 with its marker", (improved(g), g.u32(g.gp + NEW_MARK)), (0, NEW_MAGIC))
        check("the preset copied last moved and counts the new presets (15 -> %d), marker set" % (len(TUNE_PRESETS) + 1),
              (g.u32(g.gp + TUNE_LAST), g.u32(g.gp + VALUES8_MARK)), (len(TUNE_PRESETS) + 1, VALUES8_MAGIC))
        check("filled slots: gravity 100 % in place of the 'filled' word; empty ones stay empty",
              [own_slot(g, n)[0][7] for n in range(3)], [100, 100, 0])
        check("'Vorlage': the slot copied last that still equals the values", items(g)[0][2], "Vorlage: Meins")
        press(g, "left", 0)
        check("left from slot 2: slot 1", tune_values(g), (300, 400, 150, 75, 125, 100, 200, 100))
        g.page(0)
        time.sleep(0.3)
        g.page(PAGE_TUNING)
        time.sleep(0.6)
        check("the conversion happens once", (tune_values(g)[7], g.u32(g.gp + TUNE_LAST)), (100, len(TUNE_PRESETS)))
        g.page(0)
    finally:
        g.kill()


def scenario_save18():
    note("== save18: a settings.dat as patch 1.8 left it (16 built-in presets, own slot 2 copied last)")
    restore()
    path = os.path.join(GAME, "settings.dat")
    s = bytearray(data(path))
    mine = (250, 500, 200, 100, 200, 125, 100, 75)
    struct.pack_into("<8i", s, TUNE_VALUES - 4, *mine)
    struct.pack_into("<i", s, TUNE_VALUES - 4 + 32, 3)         # the character of rank 1 is there up to 1.8
    struct.pack_into("<I", s, TUNE_MARK - 4, TUNE_MAGIC)
    for n in range(8):
        struct.pack_into("<32s", s, OWN_BASE - 4 + 0x20 * n, b"")
    struct.pack_into("<8H", s, OWN_BASE - 4, *(300, 400, 150, 75, 125, 100, 200, 100))
    struct.pack_into("<8H", s, OWN_BASE - 4 + 0x20, *mine)
    s[OWN_BASE - 4 + 0x30:OWN_BASE - 4 + 0x36] = b"Meins\0"
    struct.pack_into("<3I", s, OWN_MARK - 4, OWN_MAGIC, 1, 0)
    struct.pack_into("<I", s, VALUES8_MARK - 4, VALUES8_MAGIC)
    struct.pack_into("<i", s, TUNE_LAST - 4, 17)               # 1.8: own slot 2 (16 built-in presets)
    struct.pack_into("<I", s, OPP_MARK - 4, 0)
    struct.pack_into("<I", s, OWN_OPP_MARK - 4, 0)
    open(path, "wb").write(s)
    g = G.Game(NEW_EXE)
    try:
        g.page(PAGE_TUNING)
        time.sleep(0.6)
        check("converted: eight values kept, 'Tempo' of 'Gegner' at 'Standard' with its markers",
              (tune_all(g), g.u32(g.gp + OPP_MARK), g.u32(g.gp + STD_MARK)), (mine + (OPP_STD,), OPP_MAGIC, STD_MAGIC))
        check("... and 'Verbesserte Gegner' 0 with its marker", (improved(g), g.u32(g.gp + NEW_MARK)), (0, NEW_MAGIC))
        check("the preset copied last counts the three more presets of 1.9 (17 -> %d)" % (len(TUNE_PRESETS) + 1),
              g.u32(g.gp + TUNE_LAST), len(TUNE_PRESETS) + 1)
        check("'Vorlage': the slot copied last", items(g)[0][2], "Vorlage: Meins")
        press(g, "left", 0)
        check("left from slot 2: slot 1", tune_values(g), (300, 400, 150, 75, 125, 100, 200, 100))
        g.page(0)
        time.sleep(0.3)
        g.page(PAGE_TUNING)
        time.sleep(0.6)
        check("the conversion happens once", g.u32(g.gp + TUNE_LAST), len(TUNE_PRESETS))
        g.page(0)
    finally:
        g.kill()


MOUSE_EXE = os.path.join(GAME, "ghost_mouse.exe")
MOUSE_INJ, WARP_LOG = 0x00884F30, 0x00884F40


def mouse_tools(g):
    def mouse(x, y):
        g.write(MOUSE_INJ, struct.pack("<3f", 1.0, x, y))
        time.sleep(0.04)
        return struct.unpack("<ii", g.read(g.menu + 0x148, 8))

    def click():
        g.write(O.MENU_INJ + 4 * O.KEYS["select"], struct.pack("<f", 1.0))
        time.sleep(0.3)

    def scan(count, only=None):
        hits = {}
        for n, (typ, vy, _) in enumerate(items(g)[:count]):
            if only is not None and n not in only:
                continue
            # The menu's mouse coordinates are those of the window's picture (688 x 528 in the
            # test window): 0.88 picture pixels per menu unit; a text's centre is 23 units below its y.
            y = (vy + 23) * 0.88
            mouse(4.0, 4.0)                          # off every item, so a selection cannot linger
            for x in range(60, 640, 4):
                s, arrow = mouse(float(x), y)
                if s == n:
                    hits.setdefault((s, arrow), []).append((x, y))
        for key in sorted(hits):
            xs = [p[0] for p in hits[key]]
            note("   item %d arrow %d: x %d..%d at y %.0f" % (key[0], key[1], min(xs), max(xs), hits[key][0][1]))
        return hits

    def centre(hits, key):
        pts = hits[key]
        return sum(p[0] for p in pts) / len(pts), pts[0][1]

    def warps():
        return struct.unpack("<i", g.read(WARP_LOG, 4))[0]
    return mouse, click, scan, centre, warps


def scenario_tunemouse():
    note("== tunemouse: the tuning pages with a simulated mouse")
    restore()
    g = G.Game(MOUSE_EXE)
    try:
        mouse, click, scan, centre, warps = mouse_tools(g)
        g.page(PAGE_TUNING)
        time.sleep(0.6)
        hits = scan(7)
        check("tuning page: every item can be hovered", sorted({k[0] for k in hits}), list(range(7)))
        check("'Vorlage' has both arrows, the buttons none",
              ((0, 1) in hits and (0, 2) in hits, any(k[1] in (1, 2) for k in hits if k[0] >= 1)), (True, False))
        if (0, 1) in hits and (0, 2) in hits:
            w0 = warps()
            check("'Vorlage': hover the right arrow", mouse(*centre(hits, (0, 2))), (0, 2))
            click()
            check("'Vorlage': a click on the right arrow copies 'Rakete'", (tune_values(g), items(g)[0][2]),
                  (TUNE_PRESETS[5][1], "Vorlage: Rakete"))
            check("'Vorlage': the cursor is asked to stay on the arrow", warps() - w0, 1)
            x, y = centre(hits, (0, 1))
            for _ in range(2):
                mouse(x, y)
                click()
            check("'Vorlage': two clicks on the left arrow give '200 cc'", tune_values(g), TUNE_PRESETS[3][1])
            mouse(*centre(hits, (0, 2)))
            click()
            check("'Vorlage': one more to the right: '250 cc', the defaults", tune_values(g), TUNE_DEFAULT)
        key = next((k for k in hits if k[0] == 1), None)
        if key:
            mouse(*centre(hits, key))
            click()
            time.sleep(0.3)
        check("click on 'Kart' -> page 1Fh", g.menu_state(), PAGE_KART)
        hits = scan(8)
        check("'Kart': every item can be hovered", sorted({k[0] for k in hits}), list(range(8)))
        check("'Kart': every row has both arrows, 'Zurück' none",
              (all((r, 1) in hits and (r, 2) in hits for r in range(7)), any(k[1] in (1, 2) for k in hits if k[0] == 7)),
              (True, False))
        for item in (0, 1, 6):
            v = item
            if (item, 1) not in hits or (item, 2) not in hits:
                continue
            d, step = TUNE_DEFAULT[v], TUNE_LIMITS[v][2]
            w0 = warps()
            mouse(*centre(hits, (item, 2)))
            click()
            check("'Kart' row %d: click on the right arrow steps up" % item, tune_values(g)[v], d + step)
            check("'Kart' row %d: the cursor is asked to stay on the arrow" % item, warps() - w0, 1)
            x, y = centre(hits, (item, 1))
            for _ in range(2):
                mouse(x, y)
                click()
            check("'Kart' row %d: two clicks on the left arrow step down twice" % item, tune_values(g)[v], d - step)
            mouse(*centre(hits, (item, 2)))
            click()
        check("all rows back at the defaults", tune_values(g), TUNE_DEFAULT)
        if (2, 0) in hits:
            mouse(*centre(hits, (2, 0)))
            click()
            check("a click on the text of a row changes nothing", tune_values(g), TUNE_DEFAULT)
        key = next((k for k in hits if k[0] == 7), None)
        if key:
            mouse(*centre(hits, key))
            click()
            time.sleep(0.3)
        check("click on 'Zurück' -> tuning page", g.menu_state(), PAGE_TUNING)
        g.page(PAGE_WORLD)
        time.sleep(0.6)
        hits = scan(2)
        check("'Welt': the row has both arrows, 'Zurück' can be hovered",
              ((0, 1) in hits, (0, 2) in hits, 1 in {k[0] for k in hits}), (True, True, True))
        if (0, 2) in hits:
            mouse(*centre(hits, (0, 2)))
            click()
            check("'Welt': click on the right arrow: 125 %", (tune_values(g)[7], items(g)[0][2]), (125, "Schwerkraft: 125 %"))
            mouse(*centre(hits, (0, 1)))
            click()
            check("'Welt': click on the left arrow: 100 %", tune_values(g)[7], 100)
        g.page(PAGE_OPP)
        time.sleep(0.6)
        hits = scan(3)
        check("'Gegner': both rows have both arrows, 'Zurück' can be hovered",
              ((0, 1) in hits, (0, 2) in hits, (1, 1) in hits, (1, 2) in hits, 2 in {k[0] for k in hits}), (True,) * 5)
        if (1, 2) in hits and (1, 1) in hits:
            mouse(*centre(hits, (1, 2)))
            click()
            check("'Gegner': click on the second row's right arrow: 1", (improved(g), items(g)[1][2]), (1, "Verbesserte Gegner: 1"))
            mouse(*centre(hits, (1, 1)))
            click()
            check("'Gegner': click on its left arrow: 0", improved(g), 0)
        if (0, 2) in hits and (0, 1) in hits:
            mouse(*centre(hits, (0, 2)))
            click()
            check("'Gegner': click on the right arrow of 'Tempo': -100 %", (opp(g), items(g)[0][2]), (-100, "Tempo: -100 %"))
            hits = scan(1)                          # the row is shorter now, its arrows moved
            if (0, 1) in hits:
                mouse(*centre(hits, (0, 1)))
                click()
            check("'Gegner': click on the left arrow: 'Standard'", (opp(g), items(g)[0][2]), (OPP_STD, "Tempo: Standard"))
        mouse(4.0, 4.0)
        click()
        check("a click beside every item does nothing (up to 1.10-pre it went back)", (g.menu_state(), opp(g)), (PAGE_OPP, OPP_STD))
        note("-- the championship page's button")
        g.page(0)
        time.sleep(0.3)
        set_i32(g, UNLOCKED, 5)
        set_i32(g, 0x10, 2)
        g.page(PAGE_CHAMP)
        time.sleep(0.8)
        hits = scan(CHAMP_ITEM_OPP + 2, only=(0, 5, CHAMP_ITEM_OPP, CHAMP_ITEM_OPP + 1))
        check("championship page: the championship row (with its arrows), 'Gegner' and 'Starte Meisterschaft' "
              "can be hovered, the values line not",
              (sorted({k[0] for k in hits}), (0, 1) in hits and (0, 2) in hits), ([0, 5, CHAMP_ITEM_OPP], True))
        key = next((k for k in hits if k[0] == CHAMP_ITEM_OPP), None)
        if key:
            check("hovering the button selects it", mouse(*centre(hits, key))[0], CHAMP_ITEM_OPP)
            click()
            time.sleep(0.3)
        check("a click on it opens the page 'Gegner'", g.menu_state(), PAGE_OPP)
        hits = scan(3, only=(2,))
        key = next((k for k in hits if k[0] == 2), None)
        if key:
            mouse(*centre(hits, key))
            click()
            time.sleep(0.3)
        check("a click on its 'Zurück' -> the championship page", g.menu_state(), PAGE_CHAMP)
        g.write(MOUSE_INJ, struct.pack("<3f", 0.0, 0.0, 0.0))
    finally:
        g.kill()


def own_slot(g, n):
    """(eight values, name) of own preset slot n (0..7); the last value is 0 in an empty slot."""
    raw = g.read(g.gp + OWN_BASE + 0x20 * n, 0x20)
    return struct.unpack_from("<8H", raw, 0), raw[0x10:].split(b"\0")[0].decode("cp1252")


def own_texts(g):
    return [t for _, _, t in items(g)[:2]]


def values_text(v):
    """The values text of the page of own presets (grouped)."""
    return ("Kart: Übersetzung %d.%02d, Motorkraft %d %%, Haftung %d %%,<br>Gewicht %d %%, Bremsen %d %%, "
            "Lenkung %d %%, Anpressdruck %d %%<br>Welt: Schwerkraft %d %%"
            % ((v[0] // 100, v[0] % 100) + tuple(v[1:8])))


def tune_line(v):
    """The two values lines of the tuning page, under "Kart" and "Welt"."""
    return (("Übersetzung %d.%02d, Motorkraft %d %%, Haftung %d %%,<br>Gewicht %d %%, Bremsen %d %%, "
             "Lenkung %d %%, Anpressdruck %d %%" % ((v[0] // 100, v[0] % 100) + tuple(v[1:7]))),
            "Schwerkraft %d %%" % v[7])


def lines(g):
    """The tuning page's two values lines (items 8..9)."""
    return tuple(t for _, _, t in items(g)[8:10])


def typed_name(g):
    return O.read_str(g.h, g.menu + 0x17C)


def scenario_tuneown():
    note("== tuneown: own presets (page 1Eh) and their place in the 'Vorlage' row")
    restore()
    g = G.Game(NEW_EXE)
    mine = (300, 400, 150, 75, 125, 100, 200, 50)
    empty = ((0,) * 8, "")
    n_presets = len(TUNE_PRESETS)
    try:
        g.page(PAGE_TUNING)
        time.sleep(0.6)
        press(g, "select", 4)
        check("'Eigene Vorlagen' opens page 1Eh", g.menu_state(), PAGE_OWN)
        its = items(g)
        note("   %r" % (its,))
        check("items", [t for _, _, t in its],
              ["Platz 1: Eigene 1", "(leer)", "Laden", "Speichern", "Umbenennen", "Löschen", "Zurück", "Eigene Vorlagen"])
        check("item types: slot row with arrows, values a label", [t for t, _, _ in its[:2]], [3, 0])
        check("an older save gets eight empty slots and the marker",
              ([own_slot(g, n) for n in range(8)], g.u32(g.gp + OWN_MARK)), ([empty] * 8, OWN_MAGIC))
        check("the slot row is selected", sel(g), 0)
        g.shot(os.path.join(SHOTS, "own_page_empty.png"))

        note("-- save, the slots, load")
        press(g, "select", 2)
        check("'Laden' on an empty slot does nothing", (g.menu_state(), tune_values(g)), (PAGE_OWN, TUNE_DEFAULT))
        set_tune(g, mine)
        press(g, "select", 3)
        check("'Speichern' stores the eight values in slot 1", own_slot(g, 0), (mine, ""))
        check("... and the page shows them", own_texts(g), ["Platz 1: Eigene 1", values_text(mine)])
        press(g, "right", 0)
        check("right: slot 2, empty", own_texts(g), ["Platz 2: Eigene 2", "(leer)"])
        press(g, "left", 0)
        press(g, "left", 0)
        check("left twice: round to slot 8", (own_texts(g), g.u32(g.gp + OWN_CUR)), (["Platz 8: Eigene 8", "(leer)"], 7))
        set_tune(g, p9(11) + (-50,))
        press(g, "select", 3)
        check("slot 8 holds a copy of 'Federgewicht'; 'Tempo' of 'Gegner' (-50 %) is no part of it",
              (own_slot(g, 7), opp(g)), ((TUNE_PRESETS[11][1], ""), -50))
        check("... and its values text shows the eight values", own_texts(g)[1], values_text(TUNE_PRESETS[11][1]))
        press(g, "right", 0)
        check("right: slot 1 again", own_texts(g)[0], "Platz 1: Eigene 1")
        press(g, "left", 3)
        press(g, "right", 4)
        check("left / right on the buttons change nothing", (own_texts(g)[0], tune_values(g)),
              ("Platz 1: Eigene 1", TUNE_PRESETS[11][1]))
        press(g, "select", 1)
        check("'select' on the values label does nothing", g.menu_state(), PAGE_OWN)

        note("-- renaming on the game's name page")
        press(g, "select", 4)
        check("'Umbenennen' opens the name page", g.menu_state(), 0x13)
        its = items(g)
        check("its title and prompt", [its[3][2], its[2][2]],
              ["Vorlage umbenennen", "Neuer Name für Platz 1:<br>(leer lassen für den Standardnamen)"])
        check("the field holds the slot's name, the cursor at its end",
              (typed_name(g), g.u32(g.menu + 0x174)), ("Eigene 1", 8))
        check("the renaming flag is set", g.u32(g.gp + OWN_FLAG), 1)
        set_menu_name(g, "Mond-Mod")
        g.write(g.menu + 0x174, struct.pack("<i", 8))
        press(g, "select", 0)
        check("'Weiter' stores the name, back on page 1Eh at 'Umbenennen'",
              (g.menu_state(), sel(g), own_slot(g, 0)[1]), (PAGE_OWN, 4, "Mond-Mod"))
        check("the flag is cleared, the slot row shows the name", (g.u32(g.gp + OWN_FLAG), own_texts(g)[0]),
              (0, "Platz 1: Mond-Mod"))
        check("renaming kept the values", own_slot(g, 0)[0], mine)
        press(g, "select", 4)
        set_menu_name(g, "Nix")
        press(g, "back")
        check("'menu back' on the name page keeps the old name", (g.menu_state(), own_slot(g, 0)[1]), (PAGE_OWN, "Mond-Mod"))
        press(g, "select", 4)
        set_menu_name(g, "")
        press(g, "select", 0)
        check("an empty name gives the default name back", (own_slot(g, 0)[1], own_texts(g)[0]), ("", "Platz 1: Eigene 1"))
        press(g, "select", 4)
        set_menu_name(g, "ÄÖÜß-.!xyz12345")
        press(g, "select", 0)
        check("15 characters, umlauts and the game's punctuation", own_slot(g, 0)[1], "ÄÖÜß-.!xyz12345")
        press(g, "select", 4)
        set_menu_name(g, "Mond-Mod")
        press(g, "select", 0)
        press(g, "select", 4)
        g.page(0)
        time.sleep(0.4)
        check("leaving the name page another way ends the renaming", g.u32(g.gp + OWN_FLAG), 0)
        g.page(0x13)
        time.sleep(0.4)
        check("... so the game's own name page is its own again (flag, title)",
              (g.u32(g.gp + OWN_FLAG), items(g)[3][2]), (0, "Neue Highscore"))
        g.page(0)
        time.sleep(0.3)

        note("-- the 'Vorlage' row of the tuning page goes through the filled slots")
        g.page(PAGE_TUNING)
        time.sleep(0.6)
        set_tune(g, p9(len(TUNE_PRESETS) - 1))
        press(g, "right", 0)
        check("right after the last built-in preset: own slot 1", (items(g)[0][2], tune_values(g)),
              ("Vorlage: Mond-Mod", mine))
        press(g, "right", 0)
        set_opp(g, 25)
        check("right: slot 8 (the empty ones are skipped), a copy of 'Federgewicht' showing its own name; 'Tempo' stays",
              (items(g)[0][2], tune_values(g), g.u32(g.gp + TUNE_LAST), opp(g)),
              ("Vorlage: Eigene 8", TUNE_PRESETS[11][1], n_presets + 7, 25))
        press(g, "right", 0)
        check("right: round to '50 cc'", items(g)[0][2], "Vorlage: 50 cc")
        press(g, "left", 0)
        press(g, "left", 0)
        check("left twice: slot 8, then slot 1", (items(g)[0][2], tune_values(g)), ("Vorlage: Mond-Mod", mine))
        step_row(g, 7, "right")
        goto(g, PAGE_TUNING)
        check("a changed value: 'Ungespeichert'", items(g)[0][2], "Vorlage: Ungespeichert")
        press(g, "right", 0)
        check("right from there: after slot 1 comes slot 8", tune_values(g), TUNE_PRESETS[11][1])

        note("-- 'Laden', 'Löschen', the ways back")
        press(g, "select", 3)                          # Zurücksetzen
        press(g, "select", 4)
        check("back on page 1Eh at the slot shown last", own_texts(g)[0], "Platz 1: Mond-Mod")
        press(g, "select", 2)
        check("'Laden': the tuning page with the slot's values, 'Vorlage' selected",
              (g.menu_state(), tune_values(g), items(g)[0][2], sel(g), g.u32(g.gp + TUNE_LAST)),
              (PAGE_TUNING, mine, "Vorlage: Mond-Mod", 0, n_presets))
        press(g, "select", 2)
        check("... with its gravity on 'Welt'", items(g)[0][2], "Schwerkraft: 50 %")
        press(g, "back")
        press(g, "select", 4)
        press(g, "select", 6)
        check("'Zurück' -> the tuning page, at 'Eigene Vorlagen'", (g.menu_state(), sel(g)), (PAGE_TUNING, 4))
        press(g, "select", 4)
        press(g, "back")
        check("'menu back' -> the tuning page", (g.menu_state(), sel(g)), (PAGE_TUNING, 4))
        press(g, "select", 4)
        press(g, "left", 0)
        press(g, "select", 5)
        check("'Löschen' empties slot 8, name and all", (own_slot(g, 7), own_texts(g)), (empty, ["Platz 8: Eigene 8", "(leer)"]))
        press(g, "right", 0)
        g.shot(os.path.join(SHOTS, "own_page.png"))
        check("slot 1 kept its values and name", own_slot(g, 0), (mine, "Mond-Mod"))

        note("-- the slots survive the game's own save and load")
        g.page(0)
        time.sleep(0.3)
        g.start_time_trial(5, 0)             # leaving the menu saves settings.dat
        check("race started", T.wait_racing(g))
    finally:
        g.kill()
    s = data(os.path.join(GAME, "settings.dat"))
    raw = s[OWN_BASE - 4:OWN_BASE - 4 + 0x20]
    check("settings.dat on disk holds slot 1 and the marker",
          (struct.unpack_from("<8H", raw, 0), raw[0x10:0x19], struct.unpack_from("<I", s, OWN_MARK - 4)[0]),
          (mine, b"Mond-Mod\0", OWN_MAGIC))
    g = G.Game(NEW_EXE)
    try:
        g.page(PAGE_OWN)
        time.sleep(0.6)
        check("after a restart the page shows slot 1", own_texts(g), ["Platz 1: Mond-Mod", values_text(mine)])
        g.page(0)
    finally:
        g.kill()


def scenario_ownmouse():
    note("== ownmouse: the page of own presets with a simulated mouse")
    restore()
    g = G.Game(MOUSE_EXE)
    try:
        mouse, click, scan, centre, warps = mouse_tools(g)
        g.page(PAGE_OWN)
        time.sleep(0.6)
        hits = scan(7)
        check("the slot row and the five buttons can be hovered, not the label",
              sorted({k[0] for k in hits}), [0, 2, 3, 4, 5, 6])
        check("the slot row has both arrows", ((0, 1) in hits, (0, 2) in hits), (True, True))
        if (0, 2) in hits and (0, 1) in hits:
            mouse(*centre(hits, (0, 2)))
            click()
            check("click on the right arrow: slot 2", own_texts(g)[0], "Platz 2: Eigene 2")
            mouse(*centre(hits, (0, 1)))
            click()
            check("click on the left arrow: slot 1", own_texts(g)[0], "Platz 1: Eigene 1")
        key = next((k for k in hits if k[0] == 3), None)
        if key:
            mouse(*centre(hits, key))
            click()
        check("click on 'Speichern'", own_slot(g, 0), (TUNE_DEFAULT, ""))
        key = next((k for k in hits if k[0] == 6), None)
        if key:
            mouse(*centre(hits, key))
            click()
        check("click on 'Zurück' -> tuning page", g.menu_state(), PAGE_TUNING)
        time.sleep(0.4)
        check("... where 'Vorlage' shows '250 cc' (a built-in preset wins over an equal slot)",
              items(g)[0][2], "Vorlage: 250 cc")
        g.write(MOUSE_INJ, struct.pack("<3f", 0.0, 0.0, 0.0))
    finally:
        g.kill()


def car_values(g):
    car = g.car()

    def f(off):
        return round(struct.unpack("<f", g.read(car + off, 4))[0], 4)
    return {"mass": f(0x60), "grip": (f(0xB8), f(0xBC)), "roll friction": (f(0xC0), f(0xC4), f(0xC8), f(0xCC)),
            "brakes": (f(0x110), f(0x114), f(0x118), f(0x11C)),
            "steering angle": f(0x18C), "downforce": f(0x180), "diff ratio": f(0x13C),
            "torque": tuple(f(0x154 + 4 * i) for i in range(4)), "gravity": world_gravity(g)}


def scenario_tunekart():
    note("== tunekart: kart values and gravity in a race (Moorhuhn: mass 20, grip 2.2, roll friction 4.4 2.2 1 0.5, brakes 1, angle 40, downforce 0.5, diff 6, torque 1.4 1 0.6 0; gravity 19.62)")
    restore()
    cases = (
        (2, None, {"mass": 20.0, "grip": (2.2, 2.2), "roll friction": (4.4, 2.2, 1.0, 0.5), "brakes": (1.0, 1.0, 1.0, 1.0),
                   "steering angle": 40.0, "downforce": 0.5, "diff ratio": round(6 / 1.3, 4), "torque": (1.82, 1.3, 0.78, 0.0),
                   "gravity": -19.62}),
        (5, (200, 300, 150, 50, 200, 75, 400, 25),
         {"mass": 10.0, "grip": (3.3, 3.3), "roll friction": (6.6, 3.3, 1.5, 0.75), "brakes": (2.0, 2.0, 2.0, 2.0),
          "steering angle": 30.0, "downforce": 2.0, "diff ratio": 3.0, "torque": (2.8, 2.0, 1.2, 0.0), "gravity": -4.905}),
        (5, (155, 200, 100, 100, 100, 100, 100, 300), {"gravity": -58.86}),
        (5, None, {"mass": 20.0, "grip": (2.2, 2.2), "roll friction": (4.4, 2.2, 1.0, 0.5), "brakes": (1.0, 1.0, 1.0, 1.0),
                   "steering angle": 40.0, "downforce": 0.5, "diff ratio": round(6 / 1.55, 4), "torque": (2.17, 1.55, 0.93, 0.0),
                   "gravity": -19.62}),
    )
    for cls, tune, want in cases:
        g = G.Game(NEW_EXE)
        try:
            if tune:
                set_tune(g, tune)
            label = "class %d%s" % (cls, ", values %r" % (tune,) if tune else (", an old save: defaults" if cls == 5 else ""))
            g.start_time_trial(cls, 0)
            check("%s: race started" % label, T.wait_racing(g))
            got = car_values(g)
            for key in want:
                near = all(abs(a - b) < 0.002 for a, b in zip(got[key], want[key])) if isinstance(want[key], tuple) \
                    else abs(got[key] - want[key]) < 0.002
                check("%s: %s %r" % (label, key, got[key]), near)
            if cls == 5 and not tune:
                check("%s: defaults were stored when the race started" % label, tune_values(g), TUNE_DEFAULT)
        finally:
            g.kill()
        restore()


def scenario_tttune():
    note("== tttune: tuning class, Winter (track 2): no phantom-6-02.mhk2 yet")
    restore()
    p602 = phantom(5, 2)
    check("no phantom file before", os.path.exists(p602), False)
    g = G.Game(NEW_EXE)
    try:
        before = {c: hs_raw(g, c) for c in (0, 1, 2, 3, 4)}
        g.start_time_trial(5, 1)
        check("race started", T.wait_racing(g))
        check("no ghost (gp+54h)", T.ghost_flag(g), 0)
        up, written = T.finish(g, (50.0, 50.0, 50.0))
        check("new-phantom.mhk2 written", up and written)
        d = data(NEWP)
        check("new phantom: track/class", struct.unpack_from("<2i", d, 0x4C), (2, 5))
        check("first run creates phantom-6-02.mhk2", os.path.exists(p602) and data(p602) == d)
        check("table entry (slot 33) is the new header", table(g, 5, 2) == g.header())
        st = g.select(0)
        check("'Weiter' -> name entry", st, 0x13)
        g.set_name("Tuner")
        st = g.select(0)
        check("name confirmed -> result list", st, 0x0F)
        times, names = hs_entry(g, 5, 1)
        check("tuning class highscore entry (slot 33)", (150.0 in times, "Tuner" in names), (True, True))
        for c in (0, 1, 2, 3, 4):
            check("time trial records of class %d untouched" % c, hs_raw(g, c) == before[c])
        raw = g.read(g.gp + HS_TABLE + 62 * HS_SIZE, 2 * HS_SIZE)
        g.select(0)
        check("race restarted", T.wait_racing(g))
        check("the new ghost is loaded (gp+54h)", T.ghost_flag(g), 1)
        check("the entries that hold the tuning values and the player name are not touched by records",
              g.read(g.gp + HS_TABLE + 62 * HS_SIZE, 2 * HS_SIZE) == raw)
    finally:
        g.kill()


def scenario_pause():
    note("== pause: the pause page shows the class, the 60 FPS switch, the tuning values and, with opponents, 'Gegner'")
    import pause_look as PL
    orange = "<color 255 170 0 255>%s</color>"
    # the volumes are one line each since the medals (their headings are empty)
    stock = ["", "Lautst\xe4rke Musik: 0 %", "", "Lautst\xe4rke Effekte: 0 %",
             "Rennen fortsetzen", "Neustart", "Rennen beenden", "<font 30px_redoutline>Pause</font>"]

    def head(*pairs):
        return "<scale 0.6>%s</scale>" % ", ".join("%s %s" % (orange % (k + ":"), v) for k, v in pairs)

    def top(values, char, scale, sep):         # the top speed behind the values or below the class line
        return "<scale %s>%s%s ca. %d km/h</scale>" % (scale, sep, orange % "Top speed:", _patcher().top_kmh(values, char))

    def values(v):
        return ("<scale 0.5>\xdcbersetzung %d.%02d, Motorkraft %d %%, Haftung %d %%, Gewicht %d %%,<br>"
                "Bremsen %d %%, Lenkung %d %%, Anpressdruck %d %%, Schwerkraft %d %%</scale>"
                % ((v[0] // 100, v[0] % 100) + tuple(v[1:8])))

    def gegner(scale, tempo, new):             # behind the top speed, in a race with opponents
        return "<scale %s>, %s %s</scale>" % (scale, orange % "Gegner:", opp_line(tempo, new))

    cases = (("250 cc, switch off", 4, None, False, [head(("Klasse", "250 cc"), ("60-FPS-Fahrphysik", "Aus"))
                                                       + top(p9(4), 0, "0.6", "<br>")]),
             ("150 cc, snowman", 2, None, False, [head(("Klasse", "150 cc"), ("60-FPS-Fahrphysik", "Aus"))
                                                    + top(p9(2), 4, "0.6", "<br>")]),
             ("tuning, 'Mondrakete', switch on", 5, p9([n for n, _ in TUNE_PRESETS].index("Mondrakete")), True, None),
             ("tuning, values of own slot 3 'Meins'", 5, (210, 325, 150, 75, 250, 125, 300, 175, -30), True, None),
             ("tuning, values that match nothing", 5, (290, 1000, 25, 400, 25, 50, 0, 25, -100), False, None))
    for what, cls, tune, phys, want in cases:
        note("-- " + what)
        restore()
        g = G.Game(NEW_EXE)
        try:
            if tune:
                set_tune(g, tune)
                if "own slot" in what:
                    g.write(g.gp + OWN_BASE + 2 * 0x20, struct.pack("<8H", *tune[:8]) + b"Meins".ljust(16, b"\0"))
                    g.write(g.gp + OWN_MARK, struct.pack("<I", OWN_MAGIC))
            g.write(g.gp + 0x4D, b"60F" if phys else bytes(3))
            char = 4 if "snowman" in what else 0
            g.write(g.gp + 0x58, struct.pack("<i", char))
            g.start_time_trial(cls, 0)
            check("race started", T.wait_racing(g))
            time.sleep(1.0)
            menu, page = PL.pause(g)
            its = PL.items(g, menu)
            if want is None:
                name = next((n for n, v in TUNE_PRESETS if v == tuple(tune[:8])),
                            "Meins" if "own slot" in what else "Ungespeichert")
                want = [head(("Klasse", "Tuning"), ("Vorlage", name), ("60-FPS-Fahrphysik", "An" if phys else "Aus")),
                        values(tune) + top(tune, char, "0.5", "<br>")]
            check("page 0Bh: the stock items, then the new lines", (page, [t for _, t in its]), (0x0B, stock + want))
            check("the new lines are labels; 'Rennen fortsetzen' is still selected",
                  ([k for k, _ in its[len(stock):]], struct.unpack("<i", g.read(menu + 0x148, 4))[0]), ([0] * len(want), 4))
            if "Mondrakete" in what:
                g.shot(os.path.join(SHOTS, "pause_tuning.png"))
        finally:
            g.kill()
    note("-- races with opponents: 'Gegner' follows the top speed (a time trial, above, has none)")
    for what, cls, tempo, new in (("150 cc, 'Gegner' untouched (a save without its marker)", 2, None, 0),
                                  ("150 cc, Tempo 150 %, 3 improved", 2, 150, 3),
                                  ("tuning class, Tempo -100 %, 6 improved", 5, -100, 6)):
        restore()
        g = G.Game(NEW_EXE)
        try:
            if tempo is not None:
                set_opp(g, tempo)
                set_improved(g, new)
            g.write(g.gp + 0x58, struct.pack("<i", 0))
            g.start_time_trial(cls, 0, mode=1)
            check("%s: race started" % what, T.wait_racing(g))
            time.sleep(1.0)
            menu, page = PL.pause(g)
            texts = [t for _, t in PL.items(g, menu)]
            vals = p9(cls) if cls < 5 else TUNE_DEFAULT
            if cls < 5:
                want = (head(("Klasse", "150 cc"), ("60-FPS-Fahrphysik", "Aus")) + top(vals, 0, "0.6", "<br>")
                        + gegner("0.6", OPP_STD if tempo is None else tempo, new))
            else:
                want = values(vals) + top(vals, 0, "0.5", "<br>") + gegner("0.5", tempo, new)
            check("%s: the last line ends with the two values" % what, texts[-1], want)
            if cls == 5:
                g.shot(os.path.join(SHOTS, "pause_gegner.png"))
        finally:
            g.kill()


def scenario_gegner():
    note("== gegner: the page 'Gegner' (21h) behind the championship page (0Ch), for every class (patch 1.10)")
    restore()
    g = G.Game(NEW_EXE)
    try:
        set_i32(g, 0x10, 2)                            # 150 cc
        g.page(PAGE_CHAMP)
        time.sleep(0.8)
        its = items(g)
        note("   %r" % (its,))
        check("the tuning class is locked: the game's page, nine items, the tracks at 350..455",
              (len(its), [y for _, y, _ in its[1:5]]), (9, [350, 385, 420, 455]))
        check("... and the save is not touched (no markers)",
              (g.u32(g.gp + STD_MARK) == STD_MAGIC, g.u32(g.gp + TUNE_MARK) == TUNE_MAGIC), (False, False))
        mask0 = gp_i32(g, MASK)
        g.page(0)
        time.sleep(0.3)
        set_i32(g, UNLOCKED, 5)
        g.page(PAGE_CHAMP)
        time.sleep(0.8)
        its = items(g)
        note("   %r" % (its,))
        check("unlocked: behind the title a button 'Gegner' and a label with its two values",
              (len(its), its[9:]), (11, [(1, 356, "Gegner"), (0, 388, opp_line())]))
        check("two columns: the championship row on top, the track rows beside the picture; the rest stayed",
              [y for _, y, _ in its[:9]], [126, 177, 215, 253, 291, 510, 550, 505, 20])
        check("the track rows are 140 to the right of the middle, the other items where they were",
              [item_x(g, n) for n in range(11)], [0.0] + [140.0] * 4 + [0.0] * 3 + [30.0, 0.0, 0.0])   # (the title: 30)
        check("the button and its values sit between the last track and the line above 'Starte Meisterschaft'",
              its[4][1] + 40 <= its[9][1] < its[10][1] and its[10][1] + 40 <= its[7][1], True)
        check("the save got the markers: 'Tempo' at 'Standard', 0 improved",
              (opp(g), improved(g), g.u32(g.gp + STD_MARK), g.u32(g.gp + NEW_MARK)), (OPP_STD, 0, STD_MAGIC, NEW_MAGIC))
        check("... and the tuning defaults, as the tuning page would store them (mask bit 5 too)",
              (tune_values(g), gp_i32(g, MASK)), (TUNE_DEFAULT, mask0 | 0x20))
        check("the championship row is selected", sel(g), 0)
        g.shot(os.path.join(SHOTS, "champ_gegner.png"))

        note("-- up / down: the button comes between the tracks and 'Starte Meisterschaft'")
        check("down from the championship (the tracks are labels): the button", nav(g, "down", 0), CHAMP_ITEM_OPP)
        g.shot(os.path.join(SHOTS, "champ_gegner_selected.png"))
        check("down: 'Starte Meisterschaft'", nav(g, "down"), 5)
        check("down: 'Zurück'", nav(g, "down"), 6)
        check("down: round to the championship", nav(g, "down"), 0)
        check("up from the championship: 'Zurück'", nav(g, "up"), 6)
        check("up: 'Starte Meisterschaft'", nav(g, "up"), 5)
        check("up: the button", nav(g, "up"), CHAMP_ITEM_OPP)
        check("up: the championship", nav(g, "up"), 0)
        # (left / right on the button: the game's own handler reads them, from the real keyboard, and
        # acts on items 0..4 only; the test build cannot press them on this page)

        note("-- the page 'Gegner'")
        press(g, "select", CHAMP_ITEM_OPP)
        its = items(g)
        note("   %r" % (its,))
        check("'select' on the button opens page 21h, its first row selected", (g.menu_state(), sel(g)), (PAGE_OPP, 0))
        check("its items and types", its and [(t, s) for t, _, s in its],
              [(3, "Tempo: Standard"), (3, "Verbesserte Gegner: 0"), (1, "Zurück"), (0, ""), (0, OPP_INFO), (0, "Gegner")])
        check("the rows and the explanation in this order above 'Zurück'",
              its and its[0][1] < its[1][1] < its[4][1] < its[2][1], True)
        g.shot(os.path.join(SHOTS, "gegner_page.png"))
        press(g, "left", 0)
        check("left on 'Tempo' at 'Standard': stays", (opp(g), items(g)[0][2]), (OPP_STD, "Tempo: Standard"))
        press(g, "right", 0)
        check("right: -100 %", (opp(g), items(g)[0][2]), (-100, "Tempo: -100 %"))
        for _ in range(12):
            press(g, "right", 0)
        check("12 more to the right: 200 %", (opp(g), items(g)[0][2]), (200, "Tempo: 200 %"))
        press(g, "right", 0)
        check("stops at 200 %", opp(g), 200)
        press(g, "right", 1)
        check("'Verbesserte Gegner' right: 1, the row shows it", (improved(g), items(g)[1][2]), (1, "Verbesserte Gegner: 1"))
        check("the explanation follows the selected row", items(g)[4][2], NEW_INFO)
        press(g, "left", 1)
        press(g, "left", 1)
        check("left twice: stops at 0", improved(g), 0)
        set_improved(g, 6)
        press(g, "right", 1)
        check("stops at 6", (improved(g), items(g)[1][2]), (6, "Verbesserte Gegner: 6"))
        press(g, "select", 0)
        check("'select' on a row changes nothing", (opp(g), improved(g), g.menu_state()), (200, 6, PAGE_OPP))
        press(g, "select", 2)
        check("'Zurück' -> the championship page, on the button, which shows the values",
              (g.menu_state(), sel(g), items(g)[-1][2]), (PAGE_CHAMP, CHAMP_ITEM_OPP, opp_line(200, 6)))
        check("the tuning values are untouched", tune_values(g), TUNE_DEFAULT)
        press(g, "select", CHAMP_ITEM_OPP)
        press(g, "back")
        check("'menu back' on the page -> the championship page, on the button", (g.menu_state(), sel(g)), (PAGE_CHAMP, CHAMP_ITEM_OPP))
        g.shot(os.path.join(SHOTS, "champ_gegner_set.png"))

        note("-- the tuning class shows the same page from its championship page")
        set_i32(g, 0x10, 5)
        g.page(0)
        time.sleep(0.3)
        g.page(PAGE_CHAMP)
        time.sleep(0.8)
        check("class 5: the same button with the same values", [t for _, _, t in items(g)[9:]], ["Gegner", opp_line(200, 6)])

        note("-- the values survive the game's own save and load")
        g.page(0)
        time.sleep(0.3)
        g.start_time_trial(2, 0)             # leaving the menu saves settings.dat
        check("race started", T.wait_racing(g))
    finally:
        g.kill()
    s = data(os.path.join(GAME, "settings.dat"))
    check("settings.dat on disk holds the two values and their markers",
          (struct.unpack_from("<2i", s, TUNE_VALUES - 4 + 32), struct.unpack_from("<2I", s, NEW_MARK - 4)),
          ((200, 6), (NEW_MAGIC, STD_MAGIC)))

    note("-- a settings.dat as patch 1.9 left it: 'Tempo' 200 % was the tuning class's")
    s = bytearray(s)
    struct.pack_into("<I", s, STD_MARK - 4, 0)
    struct.pack_into("<I", s, NEW_MARK - 4, 0)
    struct.pack_into("<i", s, NEW_VALUE - 4, 4)                # a character number was there
    open(os.path.join(GAME, "settings.dat"), "wb").write(s)
    g = G.Game(NEW_EXE)
    try:
        check("loaded as it was", (opp(g), improved(g), g.u32(g.gp + STD_MARK) == STD_MAGIC), (200, 4, False))
        set_i32(g, 0x10, 2)
        g.page(PAGE_CHAMP)
        time.sleep(0.8)
        check("converted once: 'Standard' and 0, the button shows them",
              (opp(g), improved(g), g.u32(g.gp + STD_MARK), items(g)[-1][2]), (OPP_STD, 0, STD_MAGIC, opp_line()))
        set_opp(g, 50)
        g.page(0)
        time.sleep(0.3)
        g.page(PAGE_TUNING)
        time.sleep(0.6)
        check("a value set afterwards stays", opp(g), 50)
        g.page(0)
    finally:
        g.kill()


LIMIT_TEXTS = ("Am Limit: extrem, aber noch fahrbar", "Hart am Limit: gerade noch fahrbar")
LIMIT_ITEM = {PAGE_TUNING: 7, PAGE_KART: 8, PAGE_WORLD: 2, PAGE_OPP: 3}


def limit_line(g):
    """The text of the "Am Limit" line on the current page, without its tags."""
    text = items(g)[LIMIT_ITEM[g.menu_state()]][2]
    return re.sub(r"<[^>]*>", "", text)


def _patcher():
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "tools"))
    import patch_200cc as P
    return P


def limit_want(values):
    """What the line should say (with the points), from the patcher's own copy of the computation."""
    return re.sub(r"<[^>]*>", "", _patcher().limit_line(list(values)))


def limit_level(values):
    return _patcher().tune_limit(list(values))[0]


def scenario_tunelimit():
    note("== tunelimit: the green 'Am Limit' line of the tuning pages")
    import random
    restore()
    g = G.Game(NEW_EXE)
    try:
        shown = {}
        for k, (name, _) in enumerate(TUNE_PRESETS):
            set_tune(g, p9(k))
            g.page(PAGE_TUNING)
            time.sleep(0.5)
            shown[name] = limit_line(g)
            check("preset %s: %r" % (name, limit_want(p9(k))[:13]), shown[name], limit_want(p9(k)))
        check("the defaults show the points only, both 0, and the top speed", shown["250 cc"],
              "Anspruch 0 (Am Limit ab 24), Risiko 0Top speed: ca. 220 km/h")
        note("   presets with the line: %r" % {n: t for n, t in shown.items() if "Limit:" in t})
        # random sets: the game's line must match the patcher's computation on every page
        rnd = random.Random(7)
        rows = ((50, 400, 5), (25, 1000, 25), (25, 400, 25), (25, 400, 25), (25, 400, 25), (25, 200, 25),
                (0, 800, 25), (25, 300, 25))
        sets, levels = [], {0: 0, 1: 0, 2: 0}
        while len(sets) < 24:
            v = [155, 200, 100, 100, 100, 100, 100, 100]
            for k in rnd.sample(range(8), rnd.choice((1, 2, 3, 4))):
                lo, hi, st = rows[k]
                v[k] = rnd.randrange(lo, hi + 1, st)
            lvl = limit_level(v)
            if levels[lvl] < 8:                 # eight of each: nothing, "Am Limit", "Hart am Limit"
                levels[lvl] += 1
                sets.append(v)
        bad = []
        for v in sets:
            set_tune(g, v)
            for page in (PAGE_TUNING, PAGE_KART, PAGE_WORLD):
                g.page(page)
                time.sleep(0.4)
                if limit_line(g) != limit_want(v):
                    bad.append((v, page, limit_line(g)))
        check("24 random sets (eight of each level) on all three pages: the line as computed", bad, [])
        want = limit_want(sets[-1])
        set_opp(g, 200)
        g.page(PAGE_OPP)
        time.sleep(0.4)
        check("the page 'Gegner' has no such line", limit_line(g), "")
        g.page(PAGE_TUNING)
        time.sleep(0.4)
        check("'Tempo' 200 % of 'Gegner' does not count (up to 1.9 it did)", limit_line(g), want)
        set_opp(g, OPP_STD)
        g.shot(os.path.join(SHOTS, "tune_limit_world.png"))

        note("-- the line follows the values while stepping")
        # Übersetzung upwards from the defaults until the line appears, on the page "Kart"
        set_tune(g, (155, 200, 100, 100, 100, 100, 100, 100))
        g.page(PAGE_KART)
        time.sleep(0.5)
        seen = []
        for _ in range(49):
            press(g, "right", 0)
            v = tune_all(g)
            seen.append((v[0], limit_line(g), limit_want(v)))
        check("Übersetzung 1.60 .. 4.00 step by step: the line as computed at every step",
              [s for s in seen if s[1] != s[2]], [])
        first = next((s for s in seen if "Limit:" in s[1]), None)
        note("   first step with the line: %r" % (first,))
        check("the line appears somewhere on the way", first is not None, True)
        check("... below the rows and above 'Zurück'", items(g)[6][1] < items(g)[8][1] < items(g)[7][1], True)
        g.shot(os.path.join(SHOTS, "tune_limit_kart.png"))
        press(g, "select", 7)
        check("back on the tuning page it shows the same", (g.menu_state(), limit_line(g)), (PAGE_TUNING, seen[-1][1]))
        g.shot(os.path.join(SHOTS, "tune_limit_page.png"))
        press(g, "right", 0)
        check("the next preset changes it as computed", limit_line(g), limit_want(tune_all(g)))
        g.page(0)
    finally:
        g.kill()


def read_png(path):
    """(width, height, pixel(x, y) -> rgb bytes) of a picture harness.shot wrote (filter 0 rows)."""
    import zlib
    d = open(path, "rb").read()
    i, idat = 8, b""
    while i < len(d):
        n, = struct.unpack(">I", d[i:i + 4])
        tag, body = d[i + 4:i + 8], d[i + 8:i + 8 + n]
        if tag == b"IHDR":
            w, h = struct.unpack(">II", body[:8])
        elif tag == b"IDAT":
            idat += body
        i += 12 + n
    raw = zlib.decompress(idat)
    stride = 3 * w + 1
    return w, h, lambda x, y: raw[y * stride + 1 + 3 * x:y * stride + 4 + 3 * x]


def hud_lines(path, ys=(32, 58, 84, 110, 296, 322, 348, 374)):
    """Which HUD text lines (left column, 688 x 528 picture) hold white text: y -> True. A line of
    text has about 400 near-white pixels in its band, an empty band (sky, track) 0."""
    w, h, px = read_png(path)
    return {y: sum(1 for yy in range(y - 9, y + 9) for x in range(85, 200) if min(px(x, yy)) > 225) > 150 for y in ys}


def scenario_hud():
    note("== hud: the speed below lap and position while racing (time trial, race, two players)")
    import hud_look as HL
    sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "tools"))
    import patch_200cc as P
    exe = os.path.join(GAME, "c5_new60.exe")
    # mode, class, what the left column should hold (y of each line in the picture)
    cases = (("time trial", 0, 4, {32: True, 58: True, 84: False}),
             ("race with computer karts", 1, 4, {32: True, 58: True, 84: True, 110: False}),
             ("two players", 2, 2, {32: True, 58: True, 84: True, 110: False, 296: True, 322: True, 348: True, 374: False}))
    for what, mode, cls, want in cases:
        note("-- " + what)
        restore()
        g = G.Game(exe)
        try:
            check("the hook is in place (jmp at 0x41920D)", g.read(P.HUD_SPEED_HOOK, 1), b"\xE9")
            path = os.path.join(SHOTS, "hud_mode%d.png" % mode)
            before, after = HL.drive_and_shoot(g, path, cls, 0, mode, 3.0)
            check("the kart drives (%.0f km/h)" % before, before > 40)
            got = hud_lines(path, tuple(want))
            check("lap, position and speed lines where expected", got, want)
            if mode == 2:
                check("the second player's kart drives too (%.0f km/h)" % HL.car_speed(g, 1), HL.car_speed(g, 1) > 40)
        finally:
            g.kill()


SCENARIOS = {"hud": scenario_hud, "browser": scenario_browser, "tuning": scenario_tuning, "gegner": scenario_gegner, "save16": scenario_save16, "save18": scenario_save18, "pause": scenario_pause, "tunelimit": scenario_tunelimit, "tunekart": scenario_tunekart,
             "tunemouse": scenario_tunemouse, "tuneown": scenario_tuneown, "ownmouse": scenario_ownmouse,
             "tttune": scenario_tttune, "menu": scenario_menu, "tt250": scenario_tt250, "namefill": scenario_namefill, "tt200": scenario_tt200, "champ": scenario_champ,
             "oldsave": scenario_oldsave, "unlockall": scenario_unlockall}


def main():
    os.makedirs(SHOTS, exist_ok=True)
    for name in sys.argv[1:]:
        try:
            SCENARIOS[name]()
        except SystemExit as e:
            T.OK[1] += 1
            print("  FAIL scenario %s stopped: %s" % (name, e), flush=True)
        except Exception as e:                       # a broken scenario must not take the others with it
            T.OK[1] += 1
            print("  FAIL scenario %s broke: %r" % (name, e), flush=True)
        finally:
            try:
                if H.alive():
                    G.k32.TerminateProcess(H.open_proc(0x0001), 0)
            except BaseException:
                pass
    print("%d checks ok, %d failed" % tuple(T.OK), flush=True)


if __name__ == "__main__":
    main()
