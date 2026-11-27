#!/usr/bin/env python3
"""Moorhuhn Kart 2 XXL (V1.0, build Mar 23 2004) - 200 cc, 250 cc and tuning class mod.

Adds two engine classes ("200 cc", "250 cc") next to 50 / 100 / 150 cc:

  * engine class menu gets a fourth and a fifth entry; each is locked until
    championship 2 is won in the class below (the same chain that unlocks
    100 and 150 cc)
  * kart physics: the stock classes differ in one factor (0.9 / 1.1 / 1.3) that
    lengthens the gearing. The new classes have 1.468 and 1.545 and, unlike the
    stock ones, pull harder: 1.5 and 2 times the thrust. Together that gives
    the top speed a 150 cc kart has with the siren and with the power can
  * computer karts use the 150 cc AI / target ranking settings of each level, but the game
    holds them back less: in 200 cc by half as much, in 250 cc not at all (full throttle)
  * time trial + championship highscores, phantom karts and the highscore
    browser work for the new classes
  * settings.dat keeps its format: the new records live in table slots the game
    never uses (tracks 33-64 / championships 11-20 of the 150 cc rows for
    200 cc, of the 100 cc rows for 250 cc, of the 50 cc rows for the tuning class)

And a sixth class, "Tuning", unlocked by winning championship 2 in 250 cc (hidden until then):
choosing it shows a page where gearing, pull, grip, weight, brakes, steering and downforce of
the kart, the gravity and the pace of the computer karts are set. The values are kept in
settings.dat and apply to every kart in the race. The page's top row, "Vorlage", copies built-in
presets (the five classes and eleven more) into them.

It also adds a switch "60-FPS-Fahrphysik" to the options menu (off by default).
The stock game derives the wheel springs from the length of the physics step,
so above ~100 FPS the kart sags onto its chassis: it gets slower, slippery and
hops. Switched on, the springs are always the ones the game has at 60 FPS.
Above it a second switch, "Alles freigeschaltet" (off by default): while it is on, every class,
championship and track is open; the progress won stays in settings.dat as it is.

Phantom karts (ghosts) work without a helper program:

  * the game races against ghosts recorded on the same PC (the stock game
    skips every phantom file that carries its own machine id)
  * a time trial run that beats the phantom of its track and class replaces it
  * new phantom files say "V1.1" when the V1.1 data (mhk2-01.dat) is loaded
  * they carry the name typed for the highscore, in the place where
    mhk2_manager keeps it, and the highscore lists show that name

usage:
    patch_200cc.py <original MHK2-XXL.exe> <output dir> [--factor F] [--pull P] [--factor-250 F] [--pull-250 P]
                                                         [--lang de|en] [--listing FILE]
    patch_200cc.py --unlock <settings.dat>      (open 50 cc to 250 cc with both championships)
    patch_200cc.py --unlock-tuning <settings.dat>   (the same and the tuning class)
    patch_200cc.py --lock <settings.dat>        (lock 200 cc and up again)
    patch_200cc.py --physics60 on|off <settings.dat>   (same as the menu switch)
    patch_200cc.py --player-name NAME <settings.dat>   (name for new phantoms, max 12 characters)

The output dir receives the patched MHK2-XXL.exe and data/MK2/text-20.csv
(text overrides; the game merges text-NN.csv on top of its text.csv), in German or,
with --lang en, in English (only the patch's own texts; the rest stays German).
Copy both into the game folder. Nothing is written next to the original exe.
"""
import argparse
import hashlib
import math
import os
import struct
import sys

# Version: the last release is PATCH_RELEASE (tagged v<release> in the repositories). Builds in
# between carry the next release's number with "-preN" (1.10-pre5 = the fifth commit after
# release 1.9); a release has two digits, raises the second one and drops the suffix
# (make_release.py builds with release=True). After a release: set PATCH_RELEASE to it and tag
# that commit v<release>.
PATCH_RELEASE = "1.10"


def patch_version(release=False):
    """1.10-preN while working (the next release, N = commits since tag v1.9 plus the one this
    build goes into), the plain release number (1.10) with release=True. Only a checkout of the
    repository (the one with the sandbox in .claude) counts commits; a copy of this script
    anywhere else, such as the one in the release zips, builds the release number."""
    major, minor = PATCH_RELEASE.split(".")
    next_release = "%s.%d" % (major, int(minor) + 1)
    here = os.path.dirname(os.path.abspath(__file__))
    if release or not os.path.isdir(os.path.join(here, "..", ".claude", "sandbox")):
        return next_release
    import subprocess
    try:
        out = subprocess.run(["git", "rev-list", "--count", "v%s..HEAD" % PATCH_RELEASE],
                             cwd=here, capture_output=True, text=True)
        if out.returncode == 0:
            return "%s-pre%d" % (next_release, int(out.stdout.strip()) + 1)
    except OSError:
        pass
    return next_release + "-pre"


PATCH_VERSION = patch_version(release=True)   # the next release: README / CHANGELOG and the release zips' names
ORIGINAL_SHA256 = "272bfad50336ec4c"  # first 16 hex digits are enough to pin the build
ORIGINAL_SIZE = 0x224000
IMAGE_BASE = 0x400000
SECTION_NAME = b".mod200\0"
SECTION_RVA = 0x4C0000          # == SizeOfImage of the original
SECTION_RAW = ORIGINAL_SIZE     # appended at the end of the file
SECTION_SIZE = 0x7000            # 28 KB since the challenges (24 KB since the learned driver tables, 16 KB since the geometric driver)
SIGNATURE_PREFIX = b"MHK2 200cc mod"
TXT_VERSION = 305           # the main menu's version line
# The two new classes pull harder than the stock ones (PULL: thrust and traction limit, the way
# the game's power-ups do it: siren 2.5, power can 5). The class factors (gearing) are chosen
# so that the top speed is the one a 150 cc kart has with the siren and with the power can.
PULL_200 = 1.5
PULL_250 = 2.0
FACTOR_200 = 1.468              # with PULL_200: top speed of a 150 cc kart with the siren ("blue light")
FACTOR_250 = 1.545              # with PULL_250: ... with the power can ("turbo can")

# --- tuning class (class 5) ----------------------------------------------------
# A sixth class whose values are set on menu pages of its own: seven kart values and the
# gravity. The eight values are integers in GameParameters, in a highscore entry the game
# never reaches (50 cc, track 63: the names of rank 4 and 5), with a marker in that entry's
# last "character".
TUNE_VALUES = 0x2E4C
TUNE_MARK = 0x2E7C
TUNE_MAGIC = 0x454E5554         # "TUNE"
# (minimum, maximum, step, default); the first value is the class factor in hundredths,
# the next six are percent of the chosen character's own value, the last is percent of the
# world's gravity (19.62 units/s^2)
TUNE_ROWS = (
    (50, 400, 5, 155),          # Übersetzung: gearing, like the class factor (150 cc = 1.30)
    (25, 1000, 25, 200),        # Motorkraft: pull (thrust and traction limit)
    (25, 400, 25, 100),         # Haftung: grip of the tyres, sideways and in the driving direction
    (25, 400, 25, 100),         # Gewicht: mass
    (25, 400, 25, 100),         # Bremsen: brake force
    (25, 200, 25, 100),         # Lenkung: largest steering angle
    (0, 800, 25, 100),          # Anpressdruck: downforce
    (25, 300, 25, 100),         # Schwerkraft: gravity of the physics world, for every kart and object
    (-125, 200, 25, -125),      # Gegner "Tempo": the computer karts' throttle, above 100 their pull (see AI_CATCHUP);
)                               # the lowest step is "Standard" (OPP_STANDARD), the class's own pace
KART_ROWS = 7                   # the first seven values are on the page "Kart"
PRESET_VALUES = 8               # the values of the tuning class, which a preset (built-in or own slot) holds: "Kart" and "Welt"
ROW_GRAVITY, ROW_OPP = 8, 9     # rows of the pages "Welt" and "Gegner"
# "Gegner" (patch 1.10: a page of its own behind the championship page, for every class; in 1.9 a
# page of the tuning class, and "Tempo" a value of its presets) has two rows. "Tempo" is the ninth
# value. The second row (patch 1.10): how many of the six computer karts drive the learned
# way (the geometric driver's tables, see GEO_DRIVER and .claude/memory/mhk2-computer-kart-ai.md);
# kart numbers 1..N do. Its dword follows the nine values, its line follows the nine in the rows
# table. Neither is a value of a preset, and "Am Limit" counts neither.
ROW_NEW = 10
NEW_ROW = (0, 6, 1, 0)          # (minimum, maximum, step, default)
OPP_STANDARD = TUNE_ROWS[ROW_OPP - 1][0]
assert OPP_STANDARD == TUNE_ROWS[ROW_OPP - 1][3] == -125 and -128 <= OPP_STANDARD   # geo_driver.asm (TEMPOSTD), imm8
# Computer karts: the game holds them back (throttle cap per class, rubber band, random strength
# per kart; see .claude/memory/mhk2-computer-kart-ai.md); 200 cc, 250 cc and the tuning class use
# the 150 cc row. Their throttle t becomes t + (1 - t) * g: g = 0 is the game's handicap, 1 is
# full throttle all the time, as the player has. g is "Tempo" of the page "Gegner" (percent), in
# every class (patch 1.10; in 1.9 only the tuning class had it). "Standard" there is the class's
# own g, OPP_CLASS_TEMPO: 0 from 50 to 150 cc (the game), AI_CATCHUP in 200 cc and 250 cc, and
# 100 % in the tuning class. It goes further down: below 0 the throttle is t * (1 + g)
# (-100 %: none above speed 10; below it the game gives full throttle, so they creep at 10).
# More than full throttle does nothing (tried with 1.5 and 2.0 on 2026-11-22: the game caps it),
# so above 100 % the computer karts get full throttle and Tempo / 100 times the pull instead
# (thrust and traction limit, on top of the class's pull and power-ups); the player's kart does not.
AI_CATCHUP = (0.5, 1.0)
OPP_CLASS_TEMPO = (0, 0, 0) + tuple(int(round(100 * g)) for g in AI_CATCHUP) + (100,)
# A computer kart that holds a power-up fires it when rand(800) is 0, checked at every update of
# its controller, i.e. every frame: on average after 13 s at 60 FPS, but after 4 s at 200 FPS.
# The patch scales the 800 by the frame time, so it is 800 at 60 FPS and the chance per second is
# the same at any frame rate (measured at 200 FPS before: 21 to 23 uses per minute against 12, and
# far more karts standing frozen after a hit).
AI_ITEM_UPDATES = 800           # the game's number, meant for 60 updates per second
# value number -> offsets in the Car object that it scales (see .claude/memory/mhk2-kart-parameters.md)
TUNE_APPLY = ((2, 0xB8), (2, 0xBC),                              # lateral friction front / rear
              (2, 0xC0), (2, 0xC4), (2, 0xC8), (2, 0xCC),        # roll friction (driving direction), rolling and locked
              (3, 0x60),                                         # mass
              (4, 0x110), (4, 0x114), (4, 0x118), (4, 0x11C),    # brake coefficient and maximum, front / rear
              (5, 0x18C),                                        # largest steering angle
              (6, 0x180))                                        # downforce coefficient
# The game presses a kart down with a force that grows with the square of its forward speed.
# Far beyond what the stock classes reach (much "Anpressdruck", little "Gewicht", high speed)
# one physics step no longer catches that force: the suspension starts to hammer, the kart is
# thrown into the air and, tumbling, accelerates itself without end. So in the tuning class the
# downforce stops growing at what a kart with stock weight and stock downforce has at this
# forward speed (a 250 cc kart tops out at 61). The speed that goes into the downforce is
# limited to DOWNFORCE_SPEED * sqrt(Gewicht / Anpressdruck).
# The force acts along the kart's own "down", in the air as well. While no wheel touches the
# ground the limit is DOWNFORCE_SPEED_AIR (the gearing of a 250 cc kart ends at 65, with the
# power can at 74). And a kart that is tilted by more than 60 degrees gets no downforce at
# all: on its back it would be pushed into the sky, and standing on its tail in a wheelie
# (ten times the thrust does that) it would be shoved forward faster than its engine can.
DOWNFORCE_SPEED = 120.0
DOWNFORCE_SPEED_AIR = 75.0
DOWNFORCE_UPRIGHT = 0.5         # the up axis' vertical part: cos(60 degrees)
# Gravity: RwPhysics::Init (0x468E30, at every race start) builds the physics world with
# gravity (0, -19.62, 0) and stores it at world+4Ch (world = [[[5E84FCh]+4]+4]). In the tuning
# class it is scaled right after that call.
PHYS_MANAGER = 0x005E84FC
PHYS_INIT = 0x00468E30
WORLD_GRAVITY_Y = 0x50
STOCK_GRAVITY_Y = -19.62
PAGE_TUNING = 0x1D              # menu page number (the game's own pages end at 1Ch)
PAGE_KART, PAGE_WORLD = 0x1F, 0x20
PAGE_CLASS, PAGE_CHARACTER = 8, 6
PAGE_OPP = 0x21
# Items of the tuning page: 0 "Vorlage", 1 "Kart", 2 "Welt", 3 "Zurücksetzen",
# 4 "Eigene Vorlagen", 5 "Weiter", 6 "Zurück", 7 the "Am Limit" line, 8..9 the values of the two
# groups, each under its button (the title is the last item).
# Page "Kart": items 0..6 the kart values, 7 "Zurück"; page "Welt": item 0 "Schwerkraft",
# 1 "Zurück"; page "Gegner": items 0 "Tempo", 1 "Verbesserte Gegner", 2 "Zurück". Behind "Zurück"
# each of them has the "Am Limit" line (empty on "Gegner") and then the explanation of the
# selected row. A "row" counts 0 "Vorlage", 1..10 the values.
(TUNE_ITEM_KART, TUNE_ITEM_WORLD, TUNE_ITEM_RESET, TUNE_ITEM_OWN, TUNE_ITEM_NEXT,
 TUNE_ITEM_BACK) = range(1, 7)
TUNE_Y_PRESET = 132
TUNE_ITEM_GROUPS = 8            # items 8..9: the values of "Kart", "Welt"
TUNE_Y_BUTTONS = (180, 268, 420, 454, 490, 526)        # Kart, Welt, Zurücksetzen, Eigene Vorlagen, Weiter, Zurück
TUNE_Y_GROUPS = (212, 300)                             # the values under "Kart", "Welt"
TUNE_Y0, TUNE_Y_STEP = 152, 33  # the value rows of the pages "Kart", "Welt" and "Gegner"
TUNE_Y_BACK = 526
TUNE_Y_INFO = {"kart": 444, "world": 290, "opp": 240}     # the explanation of the selected row
# The championship page (0Ch; the game builds it anew in every frame): once the tuning class is
# unlocked it gets a button "Gegner" behind its nine items that opens that page, and a small
# line with the two values under it, as the tuning page has them under "Kart" and "Welt". For
# the room the page gets two columns (user, 2026-11-24: "image on the left, the 4 track names on
# the right ... as there will be added more Gegner settings later"): the championship row moves
# to the top, the picture to the left, the track rows to its right. Stock: the picture at
# (288, 130), 225 x 170 (the page is 800 x 600), the championship row at y 300, the tracks at
# 350, 385, 420, 455 in the middle, the line at 505, "Starte Meisterschaft" at 510.
PAGE_CHAMP = 0x0C
CHAMP_ITEMS = 9                 # 0 championship, 1..4 tracks, 5 start, 6 back, 7 the line, 8 the title
CHAMP_ITEM_START, CHAMP_ITEM_BACK, CHAMP_ITEM_OPP = 5, 6, 9      # item 10: the values under the button
CHAMP_Y_CHAMP = 126
CHAMP_PICTURE_STOCK = (288.0, 130.0, 225.0, 170.0)               # x, y, width, height
CHAMP_PICTURE = (148.0, 170.0, 225.0, 170.0)
CHAMP_X_TRACKS = 140.0          # the track rows' middle, from the middle of the page (the picture's is at -140)
CHAMP_Y_TRACKS = (177, 215, 253, 291)
CHAMP_Y_OPP, CHAMP_Y_OPP_VALUES = 356, 388
# Menu::Draw pushes the picture's rectangle (height, width, y, x) at CHAMP_RECT_HOOK; esi = menu.
CHAMP_RECT_HOOK, CHAMP_RECT_BACK = 0x004158E7, 0x004158FB
CHAMP_RECT_ORIG = "68 00 00 2A 43 68 00 00 61 43 68 00 00 02 43 68 00 00 90 43"
assert bytes.fromhex(CHAMP_RECT_ORIG) == b"".join(b"\x68" + struct.pack("<f", v) for v in reversed(CHAMP_PICTURE_STOCK))
SUB_PAGES = ((PAGE_KART, 1, KART_ROWS + 1), (PAGE_WORLD, ROW_GRAVITY, ROW_GRAVITY + 1),
             (PAGE_OPP, ROW_OPP, ROW_NEW + 1))   # page, first row, row behind the last
# "Am Limit": a green line on the tuning page and its two detail pages for value sets that
# are far from the defaults in a way that makes the race harder, and that the game still handles
# (patch 1.9; from 1.7 to 1.8 there were yellow warnings for three bad combinations instead).
# Near the defaults, and past what works, the line stays empty. Found in races with computer
# karts over many value sets (.claude/memory/mhk2-tuning-class.md, "Am Limit").
# Each value v of row k is turned into x = log2 of its distance from the default (Anpressdruck
# shifted by 25, so 0 % has a logarithm). Up to 1.9 "Tempo" of "Gegner" counted too (a ninth row
# and a channel "opp" times "power"); since 1.10 it is no value of the tuning class. A row gives every channel the points
# SCALE * sum(slope * max(0, side * x - knot)) over its terms (side +1: above the default,
# -1: below), rounded; the game reads these points from a table per row and grid step.
# Channel "risk" gets the products of the pairs on top (each >> shift, only where the first
# factor is positive; the second may be negative). The line shows text 1 when "push" >= PUSH_MIN and
# "risk" < RISK_HARD, text 2 when RISK_HARD <= "risk" < RISK_MAX, else nothing.
LIMIT_CHANNELS = ("risk", "push", "power", "gear", "mstab", "ustab")
LIMIT_SCALE = 32            # points per unit
UP, DOWN = 1, -1
# "risk": what the computer karts' races showed (2026-11-22/23, about 1250 races of 45 s with six computer
# karts on all eight tracks, 60 FPS; tune_sweep.py / tune_sweep_fit.py): a badness of 0 is a race
# like with the defaults, 1 one where the karts were clearly stuck, reset or in the air (airtime
# share - 0.12 over 0.25, still seconds - 5 over 25, resets - 3 over 15, added up; extra over the
# defaults on the same track). The weights are a ridge fit of that badness (tune_sweep_fit.py
# emit() writes this table), none negative except in the products: Motorkraft times "mstab" (much weight
# makes them stand up on their tails and lose the ground, downforce holds them down) and
# Übersetzung times "ustab" (downforce helps at speed).
# "push": how much harder the race gets, set by hand: faster, less grip, less steering and brakes,
# an unusual gravity or weight count; slower karts count against it.
LIMIT_POINTS = (     # per row: channel -> terms (side, knot, slope)
    {"risk": ((UP, 0, 0.41), (UP, 0.75, 0.59)),
     "push": ((UP, 0, 1.0), (DOWN, 0, -1.0)),
     "gear": ((UP, 0, 1),)},   # Übersetzung
    {"risk": ((UP, 0, 0.06), (UP, 0.75, 0.82), (DOWN, 1.5, 0.24)),
     "push": ((UP, 0, 0.5), (DOWN, 0, -0.5)),
     "power": ((UP, 0, 1),)},   # Motorkraft
    {"risk": ((UP, 0.75, 0.22), (DOWN, 0, 0.07), (DOWN, 0.75, 0.22), (DOWN, 1.5, 0.21)),
     "push": ((DOWN, 0, 1.0), (UP, 0, -0.25)),
     "mstab": ((UP, 0, -0.07),),
     "ustab": ((UP, 0, 0.01),)},   # Haftung
    {"risk": ((UP, 0, 0.37), (UP, 0.75, 0.35)),
     "push": ((UP, 0, 0.25), (DOWN, 0, 0.25)),
     "mstab": ((UP, 0, 0.1),)},   # Gewicht
    {"push": ((DOWN, 0, 0.5),)},   # Bremsen
    {"risk": ((DOWN, 0, 0.47), (DOWN, 0.75, 0.08), (DOWN, 1.5, 0.16)),
     "push": ((DOWN, 0, 0.75), (UP, 0, -0.25))},   # Lenkung
    {"risk": ((UP, 0.75, 0.05), (DOWN, 0, 0.56), (DOWN, 1.5, 0.07)),
     "push": ((DOWN, 0, 0.5), (UP, 0, -0.15)),
     "mstab": ((UP, 0, -0.02),),
     "ustab": ((UP, 0, -0.18),)},   # Anpressdruck
    {"risk": ((UP, 0.75, 0.19), (DOWN, 0.75, 0.16), (DOWN, 1.5, 0.51)),
     "push": ((UP, 0, 0.5), (DOWN, 0, 0.5))},   # Schwerkraft
)
assert len(LIMIT_POINTS) == PRESET_VALUES
LIMIT_PAIRS = (("power", "mstab", 5), ("gear", "ustab", 5))   # >> 5: / SCALE
LIMIT_PUSH_MIN = 24         # 0.75: e.g. Übersetzung 2.65, Motorkraft 575 %, Haftung 50 %
LIMIT_RISK_HARD, LIMIT_RISK_MAX = 12, 24     # races there: badness 0.26 (7 % bad) / 0.42 (15 %) / 1.5 (62 %) beyond
TXT_LIMIT = (224, 225)      # "Am Limit", "Hart am Limit", each with the points
TXT_LIMIT_LOW, TXT_LIMIT_OVER = 306, 307     # the points alone: too little challenge / too much risk
LIMIT_GREY, LIMIT_OVER_COLOR = "190 190 190 255", "255 140 90 255"
LIMIT_COLORS = ("96 224 96 255", "40 255 40 255")
TUNE_LIMIT_ITEM = {"tuning": 7, "kart": 8, "world": 2, "opp": 3}      # the label's item on each page
TUNE_Y_LIMIT = {"tuning": 352, "kart": 384, "world": 220, "opp": 236}


def limit_x(k, v):
    """log2 distance of value v of row k from its default (see LIMIT_POINTS)."""
    d = TUNE_ROWS[k][3]
    shift = 25 if k == 6 else 0
    return math.log2((v + shift) / (d + shift))


def limit_table():
    """Points of every channel for every grid step of every row: [row][step] -> tuple."""
    tab = []
    for k, (lo, hi, step, _) in enumerate(TUNE_ROWS[:PRESET_VALUES]):
        rows = []
        for v in range(lo, hi + 1, step):
            x = limit_x(k, v)
            pts = []
            for ch in LIMIT_CHANNELS:
                terms = LIMIT_POINTS[k].get(ch, ())
                p = int(round(LIMIT_SCALE * sum(slope * max(0.0, side * x - knot) for side, knot, slope in terms)))
                pts.append(max(-128, min(127, p)))
            rows.append(tuple(pts))
        tab.append(rows)
    return tab


def tune_limit(values):
    """What the game computes: (level 0 / 1 / 2, risk, push) for the eight values (more are
    ignored); mirrors tune_limit."""
    tab = limit_table()
    ch = [0] * len(LIMIT_CHANNELS)
    for k, (lo, hi, step, _) in enumerate(TUNE_ROWS[:PRESET_VALUES]):
        idx = min(max(0, values[k] - lo) // step, (hi - lo) // step)
        for c, p in enumerate(tab[k][idx]):
            ch[c] += p
    for a, b, shift in LIMIT_PAIRS:
        pa, pb = ch[LIMIT_CHANNELS.index(a)], ch[LIMIT_CHANNELS.index(b)]
        if pa > 0:
            ch[0] += (pa * pb) >> shift
    risk, push = ch[0], ch[1]
    level = 0 if push < LIMIT_PUSH_MIN or risk >= LIMIT_RISK_MAX else 2 if risk >= LIMIT_RISK_HARD else 1
    return level, risk, push


def challenge_sets():
    """The CH_SET_COUNT sets of tuning values a challenge picks from: random values on each row's
    grid (gravity in CH_GRAVITY), kept when the tuning page would call them "Am Limit" or "Hart
    am Limit" (a challenge, but drivable). Fixed by the seed of the generator."""
    import random
    rnd = random.Random(35)
    sets = []
    while len(sets) < CH_SET_COUNT:
        vals = []
        for k, (lo, hi, step, _) in enumerate(TUNE_ROWS[:PRESET_VALUES]):
            if k == PRESET_VALUES - 1:
                lo, hi = CH_GRAVITY
            vals.append(rnd.randrange(lo, hi + 1, step))
        if tune_limit(vals)[0] >= 1 and tuple(vals) not in sets:
            sets.append(tuple(vals))
    return sets


def challenge_draw(seed):
    """What the game draws for a seed (mirrors ch_draw): track, start, length (share of the
    path), character, the eight tuning values."""
    state = seed & 0xFFFFFFFF or 1

    def nxt():
        nonlocal state
        state ^= (state << 13) & 0xFFFFFFFF
        state ^= state >> 17
        state ^= (state << 5) & 0xFFFFFFFF
        return state
    track = nxt() % 8
    start = struct.unpack("<f", struct.pack("<f", (nxt() % 1000) * 0.001))[0]
    share = (CH_METRES_MIN + nxt() % CH_METRES_SPAN) / CH_PATHS[track]
    share = min(max(share, CH_LEN_MIN), CH_LEN_MAX)
    char = nxt() % 7
    values = challenge_sets()[nxt() % CH_SET_COUNT]
    return track, start, share, char, values


def challenge_daily_seed(day):
    return ((day * CH_DAILY_MUL) & 0xFFFFFFFF) ^ CH_DAILY_XOR


def limit_line(values, lang="de", char=0):
    """The line the tuning pages show for the eight values (with its tags, and the top speed for the
    character), as the game prints it."""
    level, risk, push = tune_limit(values)
    texts = dict(text_overrides(lang, "x", lines_only=True))
    tid = (TXT_LIMIT_OVER if risk >= LIMIT_RISK_MAX else TXT_LIMIT_LOW if push < LIMIT_PUSH_MIN
           else TXT_LIMIT[level - 1])
    return texts[tid] % (max(0, push), max(0, risk)) + texts[TXT_TOP] % top_kmh(values, char)


# Top speed (1.9, the user asked on 2026-11-23): the tuning pages and the pause page show the
# top speed the values give, in km/h (1 unit/s = 3.6 km/h). Measured on an endless straight
# (.claude/sandbox/tools/topspeed.py: about 420 runs of 60 FPS physics, all seven characters)
# and fitted by a force balance (fit error: median 1.8 %, 90 % of the sets within 6.6 %, every
# built-in preset within 2.5 %):
# - drive: the engine's torque curve (1.4 at 0 rpm, 1.0 at 2000, 0.6 at 4000, 0 at 6000) times
#   TOP_DRIVE * k * Motorkraft, at most TOP_TRACTION * Motorkraft and TOP_DRIVE_MAX, in top gear:
#   engine speed = k * speed / Übersetzung, k = 47.75 * top gear * diff ratio of the character.
# - air: TOP_AIR * speed^2.
# - the chassis on the road: once the downforce (0.5 * Anpressdruck * speed^2, the speed limited
#   as in the tuning class) and the weight (mass * 19.62 * TOP_LOAD_G * Schwerkraft) exceed
#   TOP_CAP times the weight at stock gravity, the chassis carries the rest and rubs on the
#   road: TOP_RUB + TOP_RUB_LIGHT / Gewicht + TOP_RUB_G * mass * Schwerkraft + TOP_RUB_LOAD *
#   the load above that limit. This makes the "wall" at about 61 units/s that most sets hit.
# Grip, brakes and steering made no difference. The characters differ in mass and k:
TOP_CHARS = ((20, 0.5 * 6.0), (20, 0.5 * 6.0), (17, 0.55 * 6.0), (18, 0.45 * 7.0),
             (23, 0.55 * 5.5), (17, 0.52 * 6.7), (21, 0.5 * 6.2))    # moorhuhn .. hank: mass, top gear * diff ratio
TOP_K = 47.75
TOP_DRIVE, TOP_TRACTION, TOP_DRIVE_MAX = 2.2548, 444.0, 1048.0
TOP_AIR = 0.01862
TOP_CAP, TOP_LOAD_G = 6.039, 1.0249
TOP_RUB, TOP_RUB_LIGHT, TOP_RUB_G, TOP_RUB_LOAD = 413.2, 63.8, -0.1994, 0.01078
TOP_STEPS = 20                  # bisection steps between 0 and the speed of 6000 rpm
TOP_KMH = 3.6
TXT_TOP = 206                   # the line on the tuning pages (behind the "Am Limit" line)
# Speed in the race (1.9, the user asked on 2026-11-23): Hud::Draw (0x418EF0, ecx = the Hud,
# [Hud+4] = the player whose view it draws) prints "Runde %d/3" (text 100) at x 100, y 20 and,
# in races with opponents ([GameMode+1Ch] != 0), "Position %d" (101) at y 50, both scaled by the
# screen ([esp+20h] holds the x, [esp+10h] the y scale). Both paths meet at 0x41920D; there the
# patch adds the speed of that player's car (the CarManager's car list, |velocity| * 3.6) below.
HUD_SPEED_HOOK, HUD_SPEED_BACK = 0x0041920D, 0x00419212
HUD_GAME_MODE = 0x00403790      # returns the game mode object; +1Ch: 0 time trial, else with opponents
HUD_FONT = 0x004014E0           # the text renderer (Instance)
HUD_DRAW_TEXT = 0x00490820      # renderer->DrawText(const char*, float x, float y), thiscall
CAR_MANAGER = 0x005E8520        # CarManager*; +10h / +14h: begin and end of its car list
CAR_VELOCITY = 0x2B4
HUD_SPEED_Y = (50.0, 80.0)      # without / with the position line
TXT_SPEED = 209
# Challenges (work in progress, 2026-11-27): a time trial over a stretch of a track. A runtime
# block in the free rest of the _rwdseg page (0x885008..0x885FFF is mapped, writable and unused)
# holds the challenge; for now a test tool writes it before the race. When "active" is set:
# the grid stands at "start" (path progress, instead of the track's "start spline offset" read at
# 0x406481), the race ends when player 1 has covered "length" of progress (the lap test at
# 0x406B5A), "Runde %d/3" becomes the metres left, and the minimap shows the stretch.
CH_DATA = 0x00885100
CH_ACTIVE, CH_START, CH_LEN, CH_DONE, CH_LAST, CH_LO, CH_HI, CH_DAY, CH_METRES, CH_SEED, CH_UNUSED, CH_TMP, CH_FROM = (
    CH_DATA + 4 * k for k in range(13))
# CH_ACTIVE: a challenge is drawn; GameParameters then hold its settings (CH_SWAP) and CH_SAVE the
# player's own. CH_DAY: the day of a daily challenge (days since 1601, UTC), 0 for a random one.
# CH_METRES: the metres the HUD shows last (for the tests). CH_SEED: the generator's state.
# CH_FROM: the challenge page was left with "Zurück" (the race mode page then selects its button).
CH_SAVE = CH_DATA + 0x40
CH_SWAP = (0x10, 0x1C, 0x20, 0x4C, 0x58) + tuple(0x2E4C + 4 * k for k in range(8))   # class, mode, track,
# the 60 FPS switch, player 1's character, the eight tuning values (TUNE_VALUES)
# The menu: page 4 ("Rennmodus") gets the button "Herausforderung" as its item 3 (the game's
# label "Zwei Spieler" there becomes it, and the label comes again behind the game's items), which
# opens the challenge page 22h: "Zufall", "Täglich", "Weiter", "Zurück", and after a draw the
# lines with the challenge. "Weiter" starts the race with the game's own start (0x4122E0).
PAGE_MODE, PAGE_CH = 4, 0x22
MODE_ITEM_CH, MODE_Y_CH, MODE_Y_TWO = 3, 300, 350
TXT_TWO_PLAYERS = 284
CH_ITEM_RANDOM, CH_ITEM_DAILY, CH_ITEM_NEXT, CH_ITEM_BACK = range(4)
CH_Y_BUTTONS = (140, 180, 480, 526)
CH_Y_LINES = (250, 310, 400)    # track and driver, the values, the best time of the day
(TXT_CH_MODE, TXT_CH_TITLE, TXT_CH_RANDOM, TXT_CH_DAILY, TXT_CH_DRAW, TXT_CH_BEST,
 TXT_CH_BEST_NONE) = range(150, 157)
TXT_CH_CHAR0 = 160              # 160..166: the names of the seven characters (karts.txt order)
TXT_TRACK0 = 400                # the game's track names
START_RACE = 0x004122E0         # Menu::StartRace (this = menu), what the game's track page calls
TIME_TEXT = 0x00411FA0          # std::string* __stdcall (std::string* out, float seconds): "mm:ss:hh"
IMP_TICKS = 0x0059514C          # GetTickCount
IMP_SYSTIME = 0x0059511C        # GetSystemTimeAsFileTime
DAY_100NS = 864000000000.0      # one day in FILETIME units
# The draw: xorshift32 from the seed (random: GetTickCount; daily: the day * 9E3779B1h xor
# 5EED35h), five numbers in this order: track (% 8), start (% 1000, per mille of the path),
# metres (1000 + % 601, then as a share of the path, kept in 0.3..0.7), character (% 7), set of
# tuning values (% CH_SET_COUNT). Path lengths per track measured in the game (fn 0x4437F0).
CH_PATHS = (2222.0, 1799.0, 2860.0, 3401.0, 1260.0, 2641.0, 2906.0, 2435.0)
CH_METRES_MIN, CH_METRES_SPAN = 1000, 601
CH_LEN_MIN, CH_LEN_MAX = 0.3, 0.7
CH_DAILY_MUL, CH_DAILY_XOR = 0x9E3779B1, 0x5EED35
CH_SET_COUNT = 64
CH_GRAVITY = (50, 200)          # the gravity of a set stays in this range (percent)
# The best time of the day: in a highscore entry the game never reaches (50 cc, track 60).
DAILY_ENTRY = 0x234 + 59 * 0xB4     # 2BB0h: marker, day, best time (float)
DAILY_MAGIC = 0x43594144            # "DAYC"
STR_DAILY_FMT = "data\\Phantom\\daily-%d.mhk2"
CH_BAND = 0.008                 # progress around the finish drawn in its colour
# ARGB. Not red or green: the kart dots on the minimap are red (player 1), blue and green.
CH_COLORS = {"rest": 0x60C0C0C0, "stretch": 0xFFFFD040, "finish": 0xFFFFFFFF}
CH_GRID_HOOK, CH_GRID_BACK = 0x00406481, 0x00406488
CH_FINISH_HOOK, CH_FINISH_GO, CH_FINISH_NOT = 0x00406B5A, 0x00406B67, 0x00406DD8
CH_LAPID_HOOK, CH_LAPID_BACK = 0x00419078, 0x0041907E
CH_LAPNUM_HOOK, CH_LAPNUM_BACK = 0x00419094, 0x00419099
CH_MAP_HOOK, CH_MAP_BACK = 0x00418C28, 0x00418C30
PATH_LENGTH = 0x004437F0        # TrackPath::Length (thiscall, ecx = [CarManager+1Ch]), st0 = mean of the edge splines
# A challenge is no time trial for the records: no highscore (the result pages ask 0x412A90,
# thiscall, 3 stack arguments, al = "top five"), no promotion to the track's phantom, and no
# phantom of the track at the start (both ghost loads format the file name with 0x494EB0 into a
# std::string; the challenge formats it again: an empty name, so the load finds no file).
TOP_FIVE = 0x00412A90
TOP_FIVE_CALLS = (0x00421A2F, 0x00422398)
STR_FORMAT = 0x00494EB0         # cdecl (std::string* out, const char* format, ...)
CH_GHOST_HOOKS = ((0x00409B44, "83 C4 10 C7 84 24 EC 02 00 00 2A 00 00 00", 0x294),   # race start
                  (0x00407304, "83 C4 10 C7 84 24 CC 00 00 00 06 00 00 00", 0x38))    # restart
# hook, displaced bytes, the string's offset from esp after the displaced "add esp,10h"
# The two writes of settings.dat (menu end fn 0x412100, GameMK2::Exit fn 0x4038D0): "mov ecx,esi /
# call [eax+14h]" (File::Write of the 0FD0Ch bytes); a drawn challenge is swapped out around it.
CH_SAVE_HOOKS = (0x004122BB, 0x00403B72)
CH_SAVE_ORIG = "8B CE FF 50 14"
TXT_CH_LEFT = 105               # "Noch %d m" in place of "Runde %d/3" (text 100)
TXT_TOP_PAUSE = (207, 208)      # on the pause page: behind the values (tuning class), below the class line (others)


def top_speed(values, char=0):
    """Top speed in units/s for the values (gearing in hundredths, the rest in percent) and a
    character; mirrors tune_top (which computes in single precision)."""
    mass, gd = TOP_CHARS[char if 0 <= char < len(TOP_CHARS) else 0]
    k = TOP_K * gd
    s, pull, w, d, g = (values[n] * 0.01 for n in (0, 1, 3, 6, 7))
    m = mass * w
    kv = k / s
    drive = TOP_DRIVE * k * pull
    drive_cap = min(TOP_TRACTION * pull, TOP_DRIVE_MAX)
    vcl = DOWNFORCE_SPEED * math.sqrt(values[3] / values[6]) if values[6] > 0 else 1e9
    base = m * -STOCK_GRAVITY_Y * (TOP_LOAD_G * g - TOP_CAP)
    rub = TOP_RUB + TOP_RUB_LIGHT / w + TOP_RUB_G * m * g
    lo, hi = 0.0, 6000.0 / kv
    for _ in range(TOP_STEPS):
        v = (lo + hi) * 0.5
        rpm = kv * v
        t = 1.4 - 0.0002 * rpm if rpm < 4000 else 1.8 - 0.0003 * rpm
        th = min(drive * t, drive_cap)
        vd = min(v, vcl)
        over = 0.005 * values[6] * vd * vd + base
        res = TOP_AIR * v * v + (TOP_RUB_LOAD * over + rub if over > 0 else 0.0)
        if res < th:
            lo = v
        else:
            hi = v
    return lo


TOP_CONSTS = ("hundredth", "rpm_max", "drive", "traction", "drive_max", "no_limit", "downforce_speed",
              "load_g", "cap", "gravity", "rub_g", "rub_light", "rub", "downforce", "half", "rpm_mid",
              "torque_slope1", "torque_at0", "torque_slope2", "torque_at0_2", "rub_load", "air", "kmh")


def top_const(name):
    return {"hundredth": 0.01, "rpm_max": 6000.0, "drive": TOP_DRIVE, "traction": TOP_TRACTION,
            "drive_max": TOP_DRIVE_MAX, "no_limit": 1e9, "downforce_speed": DOWNFORCE_SPEED,
            "load_g": TOP_LOAD_G, "cap": TOP_CAP, "gravity": -STOCK_GRAVITY_Y, "rub_g": TOP_RUB_G,
            "rub_light": TOP_RUB_LIGHT, "rub": TOP_RUB, "downforce": 0.005, "half": 0.5,
            "rpm_mid": 4000.0, "torque_slope1": 0.0002, "torque_at0": 1.4, "torque_slope2": 0.0003,
            "torque_at0_2": 1.8, "rub_load": TOP_RUB_LOAD, "air": TOP_AIR, "kmh": TOP_KMH}[name]


def top_kmh(values, char=0):
    return int(round(top_speed(values, char) * TOP_KMH))


# Built-in presets of the "Vorlage" row: name and the eight values in the order of TUNE_ROWS.
# (Up to 1.9 a ninth value, "Tempo" of "Gegner": 50 cc -25, 100 cc and 150 cc 0, 200 cc 50,
# Hetzjagd 200, the others 100. Since 1.10 "Tempo" is set on the page "Gegner" for every class.)
# Left / right on the row copies the previous / next one into the values. The row shows the
# first preset that equals the values, or "Ungespeichert". The classes' gearing (1.468, 1.545)
# does not fit two decimals, so their copies read 1.47 and 1.55.
# Rakete, Formel 1, Rallye, Glatteis, Schwergewicht and Wahnsinn were changed in 1.9: searched
# with the "Am Limit" model and raced on all eight tracks (tune_sweep.py, preset_search.py); their
# values up to 1.8 left the computer karts stuck or reset (badness 0.4 to 1.4, see the note).
# 1.9 also dropped "Dragster" (no variant of it raced well) and added Bremsversagen, Federleicht,
# Hetzjagd and Mondrakete, found the same way.
TUNE_PRESETS = (
    ("50 cc",         (90, 100, 100, 100, 100, 100, 100, 100)),
    ("100 cc",        (110, 100, 100, 100, 100, 100, 100, 100)),
    ("150 cc",        (130, 100, 100, 100, 100, 100, 100, 100)),
    ("200 cc",        (147, 150, 100, 100, 100, 100, 100, 100)),
    ("250 cc",        (155, 200, 100, 100, 100, 100, 100, 100)),   # = the defaults
    ("Rakete",        (345, 325, 250, 100, 400, 200, 250, 100)),
    ("Formel 1",      (360, 300, 200, 100, 400, 200, 350, 100)),
    ("Rallye",        (180, 325, 50, 75, 100, 125, 100, 100)),
    ("Glatteis",      (155, 200, 50, 100, 75, 125, 75, 100)),
    ("Bremsversagen", (265, 250, 100, 100, 25, 100, 325, 100)),
    ("Schwergewicht", (155, 250, 100, 250, 250, 100, 200, 100)),
    ("Federgewicht",  (155, 100, 100, 50, 100, 100, 100, 100)),
    ("Federleicht",   (290, 325, 175, 25, 100, 100, 175, 150)),
    ("Hetzjagd",      (175, 275, 150, 100, 100, 100, 100, 100)),
    ("Schnecke",      (50, 100, 100, 100, 100, 100, 100, 100)),
    ("Wahnsinn",      (315, 350, 50, 25, 25, 100, 275, 300)),
    ("Mondfahrt",     (155, 200, 100, 100, 100, 100, 100, 25)),
    ("Mondrakete",    (360, 325, 175, 100, 100, 200, 350, 50)),
    ("Jupiter",       (155, 200, 100, 100, 100, 100, 100, 250)),
)
TUNE_PRESET_DEFAULT = 4         # "250 cc"
# The first eight values fill the names of rank 4 and 5; "Tempo" of "Gegner" (patch 1.9) is the
# character of rank 1 (+0A0h), the marker that of rank 5 (+0B0h).
assert TUNE_VALUES + 4 * PRESET_VALUES == TUNE_MARK - 0x10 and TUNE_VALUES + 4 * len(TUNE_ROWS) <= TUNE_MARK
assert len(TUNE_ROWS) == ROW_OPP and PRESET_VALUES == ROW_GRAVITY
assert TUNE_PRESETS[TUNE_PRESET_DEFAULT][1] == tuple(row[3] for row in TUNE_ROWS[:PRESET_VALUES])
assert all(len(vals) == PRESET_VALUES for _, vals in TUNE_PRESETS)
assert all(lo <= v <= hi for _, vals in TUNE_PRESETS for v, (lo, hi, _, _) in zip(vals, TUNE_ROWS))
assert len({vals for _, vals in TUNE_PRESETS}) == len(TUNE_PRESETS)   # the row could not tell two apart
# Own presets ("Eigene Vorlagen", menu page 1Eh): eight slots in two more highscore entries the
# game never reaches (50 cc, tracks 61 and 62). A slot is the seven values as words, a word
# "filled", and a name of up to 15 characters (empty: "Eigene N"). Behind the slots: a marker,
# the slot shown on the page and the flag "the name page renames a slot".
OWN_BASE = 0x234 + 60 * 0xB4    # 2C64h
OWN_SLOT = 0x20
OWN_SLOTS = 8
OWN_FILLED, OWN_NAME = 0x0E, 0x10   # "filled" is the last value's word (up to 1.6 a word 1)
assert OWN_FILLED == 2 * (PRESET_VALUES - 1) and OWN_NAME >= 2 * PRESET_VALUES
assert TUNE_ROWS[PRESET_VALUES - 1][0] > 0      # so a filled slot never has a zero there
OWN_MARK = OWN_BASE + OWN_SLOT * OWN_SLOTS
OWN_MAGIC = 0x504E574F          # "OWNP"
OWN_CUR = OWN_MARK + 4
OWN_FLAG = OWN_MARK + 8
# Patch 1.7 added the gravity as the eighth value, where up to 1.6 the number of the preset
# copied last was kept. That number moved behind the own presets, with a marker: a save
# without it is converted once (see tune_defaults).
VALUES8_MARK = OWN_FLAG + 4
VALUES8_MAGIC = 0x544C4557      # "WELT"
TUNE_LAST = VALUES8_MARK + 4    # number of the preset copied last: where left / right count from
OLD_TUNE_LAST = TUNE_VALUES + 4 * 7
OLD_PRESETS = 14                # built-in presets up to 1.6: the own slots were numbered from there
PRESETS_18 = 16                 # ... and in 1.7 / 1.8 (a save without OPP_MARK is renumbered once)
# Patch 1.9 added "Gegner" as the ninth value; a save without this marker gets its default once
# (up to 1.8 a character number was there).
OPP_MARK = TUNE_LAST + 4
OPP_MAGIC = 0x4E474547          # "GEGN"
INFO_SHOWN = OPP_MARK + 4       # the item whose explanation a detail page shows (-1: none yet)
# "Tempo" of the own slots in 1.9 (a slot's 20h bytes are full): eight words, then a marker.
# Unused since 1.10 ("Tempo" is no value of a preset any more); the 14h bytes stay where they are.
OWN_OPP = INFO_SHOWN + 4
OWN_OPP_MARK = OWN_OPP + 2 * OWN_SLOTS
OWN_OPP_MAGIC = 0x5350504F      # "OPPS"
# Patch 1.10 added the second row of "Gegner" behind the nine values (the character of rank 2,
# +0A4h); a save without this marker gets its default once.
NEW_VALUE = TUNE_VALUES + 4 * (ROW_NEW - 1)
NEW_MARK = OWN_OPP_MARK + 4
NEW_MAGIC = 0x4757454E          # "NEWG"
OPP_VALUE = TUNE_VALUES + 4 * (ROW_OPP - 1)
assert NEW_VALUE == 0x2E70 and OPP_VALUE == 0x2E6C      # geo_driver.asm reads them (NEWV, TEMPOV)
assert NEW_VALUE + 4 <= TUNE_MARK and ROW_NEW == len(TUNE_ROWS) + 1
# Patch 1.10 moved "Gegner" out of the tuning class: its two values apply in every class, and
# "Tempo" got the step "Standard". A save without this marker gets "Standard" once (its "Tempo"
# was the tuning class's). Whoever reads the two values checks the marker first: without it
# they are "Standard" and 0 (a save the tuning pages never saw holds character numbers there).
STD_MARK = NEW_MARK + 4
STD_MAGIC = 0x47445453          # "STDG"
assert STD_MARK == 0x2D98       # geo_driver.asm reads it (STDM, STDMAGIC)
assert STD_MARK + 4 <= TUNE_VALUES - 0x80      # entry 62 (the tuning values' entry) starts at 2DCCh
# The switch "Alles freigeschaltet" of the options menu (patch 1.10): on while this dword holds
# the magic. It only changes what the menus and the track lock read (unlock_level, unlock_test);
# the progress itself (gp+0FD08h, gp+0FD0Ch) stays as won, and a championship won while the
# switch is on still counts.
UNLOCK_MARK = STD_MARK + 4
UNLOCK_MAGIC = 0x49455246       # "FREI"
assert UNLOCK_MARK + 4 <= TUNE_VALUES - 0x80
PRESETS_ALL = len(TUNE_PRESETS) + OWN_SLOTS    # numbers of the "Vorlage" row: built-in, then own slots
PAGE_OWN = 0x1E
PAGE_NAME = 0x13                # the game's name entry page; renames a slot while OWN_FLAG is set
OWN_Y_SLOT, OWN_Y_VALUES = 130, 184
OWN_Y_BUTTONS = (290, 330, 370, 410)            # Laden, Speichern, Umbenennen, Löschen
OWN_Y_BACK = 526
# The pause page (0Ah, 0Bh: without / with "Neustart") shows the class, the 60 FPS switch and, in
# the tuning class, the preset and the values (patch 1.9). Its stock items move down for them.
PAUSE_Y_STOCK = (180, 220, 270, 310, 390, 430, 470)   # music, value, effects, value, continue, 430, 470
PAUSE_Y_SHIFT = 40
PAUSE_Y_HEAD, PAUSE_Y_VALUES = 111, 144               # the line with class and switch, the values
assert PAUSE_Y_STOCK[-1] + PAUSE_Y_SHIFT <= 550

# --- addresses inside the original executable -------------------------------
GP_GET = 0x00403790        # GameParameters* GameParameters::Instance()   (clobbers eax, ecx)
GP_POINTER = 0x005E84EC    # where Instance() keeps the object once it exists
MAIN_PROGRAM = 0x005E851C  # the main program; +4 = the current game state (the main menu while in the menus)
RACE_POINTER = 0x005E8520  # the race object (getter 0x4017F0); +10h: the human players' cars,
                           # [0] player 1, [4] player 2 (taking part while its byte +308h is set);
                           # a car's vehicle is [car+44h]
LS_GET = 0x00401940        # LevelSettings*  LevelSettings::Instance()
RAND_MOD = 0x004922D0      # int rand_mod(int n) = rand() % n  (cdecl)
TEXTMGR_GET = 0x00401710   # TextManager*    TextManager::Instance()
GET_TEXT = 0x00490C70      # std::string* TextManager::GetText(std::string* out, int id, int line)
STR_CSTR = 0x004946D0      # const char* std::string::c_str()
STR_DTOR = 0x0048CA70      # std::string::~string()  (leaves a valid empty string behind)
STR_ASSIGN = 0x004954D0    # std::string::assign(const std::string&)
ADD_LABEL = 0x00413A30     # MenuItem* Menu::AddLabel(const char* text, int y)   (not selectable)
ADD_BUTTON = 0x00413C00    # MenuItem* Menu::AddButton(const char* text, int y)
SOUNDMGR_GET = 0x00401390  # SoundManager* SoundManager::Instance()
FIND_SOUND = 0x00488CA0    # Sound* SoundManager::Find(const char* name, int)
STR_MENU_TOGGLE = 0x00595620   # "MENU_toggle"
STR_CTOR = 0x00494E70      # std::string::string(const char*)
FILEMGR_GET = 0x00401550   # FileManager* FileManager::Instance()
FILE_CLOSE = 0x00450F20    # void FileManager::Close(File*)
ARCHIVE_COUNT = 0x00410F70     # number of mounted mhk2-NN.dat files (ecx = FileManager + 4)
ARCHIVE_FIND = 0x00451360      # Entry* FileManager::Find(Archive*, const char* name); size at Entry+6Ch
SETTINGS_LOAD = 0x004136F0     # GameParameters::Load(const char* file)
HIGHSCORE_INSERT = 0x00412AE0  # Menu::InsertTimeTrialHighscore(int kart): the name is the std::string at Menu+17Ch
PAGE_SET = 0x00413DD0          # void Menu::SetPage(int page): builds the page's items
PAUSE_PAGE_DONE = 0x004146D6  # SetPage's common end (the pause pages jump there when built)
PAGE_BUILD_LAST = 0x00422420   # the last of the three page builders SetPage calls (result pages)
PAGE_UPDATE_MAIN = 0x0041D400  # int Menu::UpdateMainPages(float dt): input of the main menu pages
RESULT_UPDATE = 0x00421970     # int Menu::UpdateResultPages(float dt): result pages 0Eh..15h, the name entry among them
MENU_NAVIGATE = 0x004117D0     # void Menu::Navigate(float dt): mouse and up / down, sets the selected item
ITEMS_CLEAR = 0x004077E0       # clears the menu's item list (this = menu + 130h)
SET_TITLE = 0x00413CE0         # MenuItem* Menu::SetTitle(const char* text)
INPUT_GET = 0x004016A0         # InputController* InputController::Instance()
INPUT_READ = 0x0045C890        # float InputController::Read(const char* action): not zero = pressed
CAR_REBUILD = 0x0042BFF0       # Car: drops the physics objects before they are built again from the values
STR_MENU_BACK = 0x00597570     # "menu back"
STR_MENU_SELECT = 0x00595F1C   # "menu select"
STR_MENU_LEFT = 0x00596D4C     # "menu left"
STR_MENU_RIGHT = 0x00596D40    # "menu right"
STR_MENU_UP = 0x00596B44       # "menu up"
STR_MENU_DOWN = 0x00596B38     # "menu down"
STR_PHANTOM_FMT = 0x00595EF8   # "data\Phantom\phantom-%d-%02d.mhk2"
STR_NEW_PHANTOM = 0x00595F3C   # "data\Phantom\new-phantom.mhk2"
VERSION_STRING = 0x005C38B8    # "V1.0": the first bytes of every phantom header (writable)
# import table slots
IMP_COPYFILE = 0x005951CC
IMP_LSTRCPYN = 0x00595278
IMP_SETFILEPOINTER = 0x00595280
IMP_WRITEFILE = 0x00595284
IMP_CREATEFILE = 0x00595290
IMP_CLOSEHANDLE = 0x005952E4
IMP_WSPRINTF = 0x00595374

# --- phantom karts -------------------------------------------------------------
# A phantom file is a 6Ch byte header followed by the recording:
#   +00 char[20h] version ("V1.0")       +4C track (1..8)    +58 total time
#   +28 char[20h] id of the PC it is from   +50 class (0..4)    +5C three lap times
#                                           +54 character
# mhk2_manager keeps the player's name in bytes 8..19 and its checksum in 20..31.
PHANTOM_SIZE = 0x6C
PHANTOM_NAME = 8
PHANTOM_NAME_LEN = 12
PHANTOM_RUN = 0xFB04           # GameParameters: header of the run just driven
PHANTOM_TABLE = 0xAA04         # GameParameters: headers of all phantom files, [class * 64 + track - 1]
# The typed name has to survive until the next run is saved. It lives in a
# highscore entry the game never reaches (50 cc, track 64, rank 5), together with
# a marker, because the stock game leaves "-" and a character number there.
NAME_OFFSET = 0x2F10
NAME_MARK_OFFSET = 0x2F30
NAME_MARK = 0x454D414E         # "NAME"
V11_FILE = b"data\\mk2\\level01\\objects\\collision_border.dff\0"
V11_FILE_SIZE = 29772          # 42004 in V1.0 (the manager's TODO.txt names the same file)

# --- "60 FPS physics" switch ---------------------------------------------------
# Stored in the three padding bytes behind the bool at GameParameters+4Ch, which
# the game writes to / reads from settings.dat with the rest of the object but
# never looks at. Only this exact value means "on", so stray bytes in an old
# settings.dat cannot switch it on by accident.
PHYS_FLAG_OFFSET = 0x4C
PHYS_MAGIC = 0x463036           # bytes "60F" at +4Dh..+4Fh
REFERENCE_STEP = 0x3C888889     # float 1/60 s: the step the suspension was tuned for

# --- text ids ----------------------------------------------------------------
TXT_200CC = 0x14F          # 335: was the engine menu's "Zurück"; class names are looked up as 332 + class
TXT_250CC = 0x150          # 336: was the engine menu's hint
TXT_TUNING = 0x151         # 337: name of the tuning class (332 + 5)
TXT_HINT = 0x156           # 342: the hint's new place
TXT_TUNE_TITLE = 0xF0      # 240: title of the tuning page (233..269 are unused in text.csv)
TXT_TUNE_ROW0 = 0xF1       # 241..247: the seven kart rows (rows 1..7: 240 + row), as wsprintf formats
TXT_TUNE_ROW8 = 0xE9       # 233: "Schwerkraft" (row 8)
TXT_CHAMP_OPP, TXT_OPP_TITLE, TXT_OPP_ROW, TXT_OPP_INFO = 343, 344, 345, 346   # the championship page's button, the page "Gegner" (row 9)
TXT_CHAMP_OPP_VALUES = 319  # ... and the small line under the button
TXT_OPP_ROW_STD = 355       # row 9 at its lowest step: "Tempo: Standard"
TXT_OPP_VALUES, TXT_OPP_VALUES_STD = 308, 309     # the two values of "Gegner" in one line, the second with "Standard"
TXT_PAUSE_OPP = (317, 318)  # ... on the pause page: behind the top speed, in the tuning class / in the others
TXT_GROUP_TEXTS = (347, 349)           # the tuning page's values of "Kart", "Welt"
TXT_NEW_ROW, TXT_NEW_INFO = 356, 357   # the second row of "Gegner" (row 10); 350..354 and 358.. are the game's
TXT_INFO = (293, 294, 295, 296, 297, 298, 299, 289, TXT_OPP_INFO, TXT_NEW_INFO)   # explanation of rows 1..10
TXT_TUNING_HIDDEN = 348    # empty: the class menu's tuning row before the class is unlocked
TXT_TUNING_UNLOCKED = 589  # "tuning class unlocked" (584 + 4 would be 588, taken by 250 cc)
MAIN_Y_VERSION = 540       # the version line under the main menu's buttons (the last one, "Beenden", is at 470)
TXT_KART_BUTTON, TXT_WORLD_BUTTON = 234, 235    # the tuning page's buttons to the two pages
TXT_KART_TITLE, TXT_WORLD_TITLE = 236, 237
TXT_TUNE_RESET = 0xF8      # 248: "Zurücksetzen"
TXT_TUNE_PRESET = 0xF9     # 249: the "Vorlage" row, a wsprintf format for the name
TXT_TUNE_PRESET0 = 0xFA    # 250..265: names of the first 16 presets
TXT_TUNE_PRESET16 = 226    # 226..228: names of presets 16.. (patch 1.9; 266.. is taken)
TXT_TUNE_OWN = 278         # "Ungespeichert"
TXT_OWN_DEFAULT = 279      # default name of a slot, "Eigene %d"
TXT_OWN_TITLE = 266        # 266..277 without 270: the page of own presets (the game takes every
                           # text with an id from 400 to 499 as a track name, so 4xx is out)
TXT_OWN_BUTTON = 267       # the tuning page's button
TXT_OWN_SLOT = 268         # "Platz %d: %s"
TXT_OWN_VALUES = 269       # the values of an own slot, 10 numbers (OWN_VALUES_BUF)
OWN_VALUES_BUF = 0x180     # buffer for that text
TXT_OWN_EMPTY = 271
assert TXT_TUNE_PRESET0 + 16 == TXT_OWN_TITLE and TXT_LIMIT[-1] < TXT_TUNE_PRESET16
assert TXT_TUNE_PRESET16 + len(TUNE_PRESETS) - 16 <= TXT_TUNE_ROW8 - 4    # 229 is still free


def preset_text_id(n):
    """Text id of the name of built-in preset n."""
    return TXT_TUNE_PRESET0 + n if n < 16 else TXT_TUNE_PRESET16 + n - 16
assert len(TUNE_ROWS) == 9          # rows 10.. would need text ids of their own (row 10: TXT_NEW_ROW)
TXT_PAUSE_PLAIN, TXT_PAUSE_TUNING = 238, 239     # the pause page's line: class, (preset,) switch
TXT_PAUSE_VALUES = 229     # ... and the tuning values below it
TXT_CLASS0 = 332           # class names: 332 + class (335..337 are the patch's)
TXT_OWN_LOAD = 272         # 272..275: Laden, Speichern, Umbenennen, Löschen
TXT_OWN_RENAME_TITLE = 276
TXT_OWN_RENAME = 277       # the name page's prompt, "... Platz %d ..."
TXT_NEXT = 0x188           # 392: the stock "Weiter"
TXT_BACK = 0x143           # 323: the track menu's "Zurück", reused for the engine menu
TXT_200CC_LOCKED = 0x152   # 338: greyed-out "200 cc"
TXT_250CC_LOCKED = 0x153   # 339: greyed-out "250 cc"
TXT_CHAMP2_UNLOCKED = 0x244        # 580 + class: "championship 2 unlocked in this class" (stock: 580..582)
TXT_CHAMP2_UNLOCKED_250 = 0x24C    # 588, because 580 + 4 is the stock text "championship 1 unlocked in 100 cc"
# engine class menu rows; the stock page: heading 200, line 240, classes 260/300/340, line 400, hint 430, back 520
MENU_Y_HEADING = 160
MENU_Y_TOP_LINE = 200
MENU_Y_CLASSES = (218, 254, 290, 326, 362, 398)
MENU_Y_LINE = 442          # separator below the class list
MENU_Y_HINT = 464          # "win both championships first" hint
MENU_Y_BACK = 526
TXT_PHYS_LABEL = 0xDD      # 221: heading of the new options entry (221..229 are unused in text.csv)
TXT_PHYS_OFF = 0xDE        # 222: its value while off; "on" is the next id
TXT_UNLOCK_LABEL = 288    # heading of the switch "Alles freigeschaltet" (its values are 222 / 223)
TXT_BACK_OPTIONS = 0xD9    # 217: the options menu's own "Zurück"
# options menu rows; the stock page uses 160/200, 250/290, 350, 410/450, 520
OPTIONS_Y = (118, 152, 194, 228, 272, 316, 350)   # music, effects, resolution, quality
OPTIONS_Y_STOCK = (160, 200, 250, 290, 350, 410, 450)
OPTIONS_Y_UNLOCK_LABEL = 392
OPTIONS_Y_UNLOCK_VALUE = 426
OPTIONS_Y_PHYS_LABEL = 468
OPTIONS_Y_PHYS_VALUE = 502
OPTIONS_Y_BACK = 548
# items 0..6 as before, 7 / 8 "Alles freigeschaltet" (heading, value), 9 / 10 the physics switch,
# 11 "Zurück"
OPTIONS_ITEM_UNLOCK = 8
OPTIONS_ITEM_PHYS = 10
OPTIONS_ITEM_BACK = 11
MENU_ITEM_SIZE = 0x54

TXT_GROUP = "<color 255 170 0 255>%s</color>"     # "Kart:" / "Welt:" / "Gegner:" in the values text

# The patch's texts in German (the game's language) and English. Only these texts change; the
# rest of the menus comes from the game's own text.csv. Both go into text-20.csv, the file the
# German game reads; --lang picks one. Each language has the same keys.
TEXTS = {
    "de": {
        "phys": "60-FPS-Fahrphysik", "off": "Aus", "on": "An", "tuning": "Tuning",
        "unlock_all": "Alles freigeschaltet",
        "rows": ("Übersetzung", "Motorkraft", "Haftung", "Gewicht", "Bremsen", "Lenkung",
                 "Anpressdruck", "Schwerkraft"),
        "limit": ("Am Limit: extrem, aber noch fahrbar", "Hart am Limit: gerade noch fahrbar"),
        "points": "Anspruch %d, Risiko %d", "points_low": "Anspruch %%d (Am Limit ab %d), Risiko %%d",
        "points_over": "Anspruch %%d, Risiko %%d: zu riskant (fahrbar bis %d)",
        "kart": "Kart", "world": "Welt", "reset": "Zurücksetzen", "preset": "Vorlage",
        "presets": tuple(name for name, _ in TUNE_PRESETS),
        "unsaved": "Ungespeichert", "own_default": "Eigene", "own": "Eigene Vorlagen",
        "slot": "Platz", "empty": "(leer)", "load": "Laden", "save": "Speichern",
        "rename": "Umbenennen", "delete": "Löschen", "rename_title": "Vorlage umbenennen",
        "rename_prompt": "Neuer Name für Platz %d:<br>(leer lassen für den Standardnamen)",
        "hint": "Bevor Du eine höhere Leistungsklasse wählen kannst,"
                "<br>musst Du zuerst beide Meisterschaften gewinnen!",
        "unlock": "Du hast die %s Meisterschaft<br>in der %scc-Klasse freigeschaltet!",
        "first": "erste", "second": "zweite",
        "tuning_unlocked": "Du hast die Tuning-Klasse freigeschaltet!",
        "opp": "Gegner", "opp_row": "Tempo", "std": "Standard", "class": "Klasse", "top": "Top speed:", "top_about": "ca. %d km/h",
        "ch_left": "Noch %d m",
        "ch_mode": "Herausforderung", "ch_random": "Zufall", "ch_daily": "Täglich",
        "ch_draw": "Strecke: %s, %d m ab %d %%<br>Fahrer: %s",
        "ch_best": "Deine Bestzeit heute: %s", "ch_best_none": "Heute noch keine Zeit",
        "chars": ("Moorhuhn", "Lesshuhn", "Moorfrosch", "Kürbis", "Schneemann", "Schildkröte", "Hank"),
        "new_row": "Verbesserte Gegner", "new_short": "verbessert",
        "new_info": "Wie viele der sechs Computer-Karts fahren die<br>gelernte Linie? Sie bremsen vor Kurven und"
                    "<br>kommen seltener von der Strecke ab. 0: wie im Spiel",
        "opp_info": "Wie schnell fahren die Computer-Karts?"
                    "<br>Standard: bis 150 cc 0 %, 200 cc 50 %, ab 250 cc 100 %"
                    "<br>0 %: gebremst wie im Spiel, 100 %: Vollgas wie Du"
                    "<br>über 100 %: mehr Motorkraft als Du, -100 %: Schritttempo",
        "info": ("Länge der Übersetzung, wie der Faktor einer Klasse:<br>länger: höhere Höchstgeschwindigkeit."
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
                 "<br>100 %: wie im Spiel. Wenig: weite Sprünge"),
    },
    "en": {
        "phys": "60 FPS driving physics", "off": "Off", "on": "On", "tuning": "Tuning",
        "unlock_all": "Everything unlocked",
        "rows": ("Gearing", "Engine power", "Grip", "Weight", "Brakes", "Steering",
                 "Downforce", "Gravity"),
        "limit": ("Pushing the limits: still raceable", "Right at the limit: only just raceable"),
        "points": "challenge %d, risk %d", "points_low": "Challenge %%d (pushing the limits from %d), risk %%d",
        "points_over": "Challenge %%d, risk %%d: too risky (raceable up to %d)",
        "kart": "Kart", "world": "World", "reset": "Reset", "preset": "Preset",
        "presets": ("50 cc", "100 cc", "150 cc", "200 cc", "250 cc", "Rocket", "Formula 1",
                    "Rally", "Black Ice", "Brake Failure", "Heavyweight", "Featherweight",
                    "Feather Light", "Hot Pursuit", "Snail", "Madness", "Moon Ride", "Moon Rocket",
                    "Jupiter"),
        "unsaved": "Unsaved", "own_default": "Custom", "own": "Own presets",
        "slot": "Slot", "empty": "(empty)", "load": "Load", "save": "Save",
        "rename": "Rename", "delete": "Delete", "rename_title": "Rename preset",
        "rename_prompt": "New name for slot %d:<br>(leave empty for the default name)",
        "hint": "Before you can choose a higher engine class,"
                "<br>you have to win both championships first!",
        "unlock": "You have unlocked the %s championship<br>in the %scc class!",
        "first": "first", "second": "second",
        "tuning_unlocked": "You have unlocked the tuning class!",
        "opp": "Opponents", "opp_row": "Pace", "std": "default", "class": "Class", "top": "Top speed:", "top_about": "about %d km/h",
        "ch_left": "%d m to go",
        "ch_mode": "Challenge", "ch_random": "Random", "ch_daily": "Daily",
        "ch_draw": "Track: %s, %d m from %d %%<br>Driver: %s",
        "ch_best": "Your best time today: %s", "ch_best_none": "No time yet today",
        "chars": ("Moorhuhn", "Lesshuhn", "Moorfrosch", "Pumpkin", "Snowman", "Turtle", "Hank"),
        "new_row": "Improved opponents", "new_short": "improved",
        "new_info": "How many of the six computer karts drive the<br>learned line? They brake before corners and"
                    "<br>leave the track less often. 0: as in the game",
        "opp_info": "How fast do the computer karts drive?"
                    "<br>Default: up to 150 cc 0 %, 200 cc 50 %, from 250 cc 100 %"
                    "<br>0 %: held back as in the game, 100 %: full throttle like you"
                    "<br>above 100 %: more engine power than you, -100 %: walking pace",
        "info": ("Length of the gearing, like the factor of a class:<br>longer: higher top speed."
                 "<br>150 cc: 1.30, 200 cc: 1.47, 250 cc: 1.55",
                 "Thrust of the engine, and how much of it the tyres<br>put on the road."
                 "<br>150 cc: 100 %, 200 cc: 150 %, 250 cc: 200 %",
                 "Grip of the tyres, sideways and in the driving direction.<br>Little grip: the wheels spin,"
                 "<br>the kart slides. 100 %: the character's value",
                 "Mass of the kart. Light: quick off the line, but<br>a lower top speed."
                 "<br>100 %: the character's value",
                 "Brake force.<br>100 %: the character's value",
                 "Largest steering angle.<br>100 %: the character's value",
                 "Presses the kart onto the road with its speed:<br>more grip in corners,"
                 " less top speed.<br>100 %: the character's value",
                 "Gravity of the whole race: every kart<br>and loose object."
                 "<br>100 %: as in the game. Little: long jumps"),
    },
}
assert all(TEXTS[lang].keys() == TEXTS["de"].keys() for lang in TEXTS)
assert all(len(TEXTS[lang]["info"]) == PRESET_VALUES for lang in TEXTS)
assert all(len(TEXTS[lang]["presets"]) == len(TUNE_PRESETS) and len(TEXTS[lang]["limit"]) == len(TXT_LIMIT)
           and len(TEXTS[lang]["rows"]) == PRESET_VALUES for lang in TEXTS)


def text_overrides(lang="de", version=None, lines_only=False):
    """The contents of text-20.csv in one language; version = the patch version on the main menu.
    lines_only: the (id, text) pairs instead."""
    t = TEXTS[lang]
    title = "<font 30px_redoutline>%s</font>"
    row = dict(zip(range(TXT_TUNE_ROW0, TXT_TUNE_ROW0 + 7), t["rows"][:7]))
    r = t["rows"]
    values = ("<scale 0.6>" + TXT_GROUP % (t["kart"] + ":")
              + " %s %%d.%%02d, %s %%d %%%%, %s %%d %%%%,<br>" % r[0:3]
              + "%s %%d %%%%, %s %%d %%%%, %s %%d %%%%, %s %%d %%%%<br>" % r[3:7]
              + TXT_GROUP % (t["world"] + ":") + " %s %%d %%%%" % r[7])
    lines = [
        (221, title % t["phys"]), (222, t["off"]), (223, t["on"]),
        (TXT_UNLOCK_LABEL, title % t["unlock_all"]),
        (240, title % t["tuning"]),
        (TXT_TUNE_ROW0, r[0] + ": %d.%02d"),
    ] + [(n, row[n] + ": %d %%") for n in range(TXT_TUNE_ROW0 + 1, TXT_TUNE_ROW0 + 7)] + [
        (TXT_TUNE_ROW8, r[7] + ": %d %%"),
    ] + [(TXT_LIMIT[n], "<scale 0.6><color %s>%s</color> <color %s>(%s)</color></scale>"
          % (color, text, LIMIT_GREY, t["points"])) for n, (color, text) in enumerate(zip(LIMIT_COLORS, t["limit"]))] + [
        (TXT_LIMIT_LOW, "<scale 0.6><color %s>%s</color></scale>" % (LIMIT_GREY, t["points_low"] % LIMIT_PUSH_MIN)),
        (TXT_LIMIT_OVER, "<scale 0.6><color %s>%s</color></scale>"
         % (LIMIT_OVER_COLOR, t["points_over"] % (LIMIT_RISK_MAX - 1))),
        (234, t["kart"]), (235, t["world"]),
        (236, title % t["kart"]), (237, title % t["world"]),
        (248, t["reset"]), (249, t["preset"] + ": %s"),
    ] + [(preset_text_id(n), name) for n, name in enumerate(t["presets"])] + [
        (TXT_TUNE_OWN, t["unsaved"]),
        (TXT_OWN_DEFAULT, t["own_default"] + " %d"),
        (266, title % t["own"]), (267, t["own"]),
        (268, t["slot"] + " %d: %s"),
        (269, values + "</scale>"),
        (TXT_GROUP_TEXTS[0], "<scale 0.6>%s %%d.%%02d, %s %%d %%%%, %s %%d %%%%,<br>" % r[0:3]
         + "%s %%d %%%%, %s %%d %%%%, %s %%d %%%%, %s %%d %%%%</scale>" % r[3:7]),
        (TXT_GROUP_TEXTS[1], "<scale 0.6>%s %%d %%%%</scale>" % r[7]),
        (TXT_OPP_VALUES, "%s %%d %%%%, %s %%d" % (t["opp_row"], t["new_short"])),
        (TXT_OPP_VALUES_STD, "%s %s, %s %%d" % (t["opp_row"], t["std"], t["new_short"])),
        (TXT_CHAMP_OPP, t["opp"]),
        (TXT_CHAMP_OPP_VALUES, "<scale 0.6>%s</scale>"),
        (TXT_PAUSE_OPP[0], "<scale 0.5>, %s %%s</scale>" % (TXT_GROUP % (t["opp"] + ":"))),
        (TXT_PAUSE_OPP[1], "<scale 0.6>, %s %%s</scale>" % (TXT_GROUP % (t["opp"] + ":"))),
        (271, "<scale 0.6>%s</scale>" % t["empty"]),
        (TXT_PAUSE_PLAIN, "<scale 0.6>%s %%s, %s %%s</scale>" % (TXT_GROUP % (t["class"] + ":"),
                                                                    TXT_GROUP % (t["phys"] + ":"))),
        (TXT_PAUSE_TUNING, "<scale 0.6>%s %%s, %s %%s, %s %%s</scale>" % (
            TXT_GROUP % (t["class"] + ":"), TXT_GROUP % (t["preset"] + ":"), TXT_GROUP % (t["phys"] + ":"))),
        (TXT_PAUSE_VALUES, "<scale 0.5>%s %%d.%%02d, %s %%d %%%%, %s %%d %%%%, %s %%d %%%%,<br>" % r[0:4]
         + "%s %%d %%%%, %s %%d %%%%, %s %%d %%%%, %s %%d %%%%</scale>" % r[4:8]),
        (TXT_TOP, "<scale 0.6><br>%s %s</scale>" % (TXT_GROUP % t["top"], t["top_about"])),
        (TXT_TOP_PAUSE[0], "<scale 0.5><br>%s %s</scale>" % (TXT_GROUP % t["top"], t["top_about"])),
        (TXT_SPEED, "<scale 0.75>%d km/h</scale>"),
        (TXT_CH_LEFT, "<scale 0.75>%s</scale>" % t["ch_left"]),
        (TXT_CH_MODE, t["ch_mode"]), (TXT_CH_TITLE, title % t["ch_mode"]),
        (TXT_CH_RANDOM, t["ch_random"]), (TXT_CH_DAILY, t["ch_daily"]),
        (TXT_CH_DRAW, "<scale 0.7>%s</scale>" % t["ch_draw"]),
        (TXT_CH_BEST, "<scale 0.7>%s</scale>" % t["ch_best"]),
        (TXT_CH_BEST_NONE, "<scale 0.7>%s</scale>" % t["ch_best_none"]),
    ] + [(TXT_CH_CHAR0 + k, name) for k, name in enumerate(t["chars"])] + [
        (TXT_TOP_PAUSE[1], "<scale 0.6><br>%s %s</scale>" % (TXT_GROUP % t["top"], t["top_about"])),
        (272, t["load"]), (273, t["save"]), (274, t["rename"]), (275, t["delete"]),
        (276, title % t["rename_title"]),
        (277, t["rename_prompt"]),
        (335, "200 cc"), (336, "250 cc"), (337, t["tuning"]),
        (338, "<color 128 128 128 255>200 cc</color>"),
        (339, "<color 128 128 128 255>250 cc</color>"),
        (342, "<font 30px_redoutline><scale 0.5>%s</scale></font>" % t["hint"]),
        (TXT_OPP_TITLE, title % t["opp"]),
        (TXT_OPP_ROW, t["opp_row"] + ": %d %%"),
        (TXT_OPP_ROW_STD, t["opp_row"] + ": " + t["std"]),
        (TXT_OPP_INFO, "<scale 0.6>%s</scale>" % t["opp_info"]),
        (TXT_NEW_ROW, t["new_row"] + ": %d"),
        (TXT_NEW_INFO, "<scale 0.6>%s</scale>" % t["new_info"]),
    ] + [(TXT_INFO[n], "<scale 0.6>%s</scale>" % text) for n, text in enumerate(t["info"])] + [
        (TXT_TUNING_HIDDEN, ""),
        (583, t["unlock"] % (t["second"], "200")),
        (586, t["unlock"] % (t["first"], "200")),
        (587, t["unlock"] % (t["first"], "250")),
        (588, t["unlock"] % (t["second"], "250")),
        (TXT_TUNING_UNLOCKED, t["tuning_unlocked"]),
        (TXT_VERSION, "<scale 0.5><color 200 200 200 255>Patch %s</color></scale>" % (version or PATCH_VERSION)),
    ]
    # the game lists every text with an id from 400 to 499 as a track ("Available tracks" in log.txt)
    assert not any(400 <= n < 500 for n, _ in lines)
    assert len({n for n, _ in lines}) == len(lines)
    # the longest values lines must fit their buffers
    longest = dict(lines)
    widest = (400, 1000, 400, 400, 400, 200, 800, 300)
    opp_widest = max((longest[TXT_OPP_VALUES] % (-100, 6), longest[TXT_OPP_VALUES_STD] % 6), key=len)
    assert len(opp_widest) < 0x40 and len(longest[TXT_CHAMP_OPP_VALUES] % opp_widest) < 0x80
    assert len(longest[269].replace("%d.%02d", "4.00") % widest[1:]) < OWN_VALUES_BUF
    assert len(longest[TXT_GROUP_TEXTS[0]].replace("%d.%02d", "4.00") % widest[1:7]) < 0x100
    assert all(len(longest[n] % (999, 999)) + len(longest[TXT_TOP] % 999) < 0x100
               for n in TXT_LIMIT + (TXT_LIMIT_LOW, TXT_LIMIT_OVER))
    assert (len(longest[TXT_PAUSE_VALUES].replace("%d.%02d", "4.00") % widest[1:]) + len(longest[TXT_TOP_PAUSE[0]] % 999)
            + len(longest[TXT_PAUSE_OPP[0]] % opp_widest) < OWN_VALUES_BUF)
    assert (len(longest[TXT_PAUSE_PLAIN] % ("x" * 0x1F, "x" * 0x1F)) + len(longest[TXT_TOP_PAUSE[1]] % 999)
            + len(longest[TXT_PAUSE_OPP[1]] % opp_widest) < OWN_VALUES_BUF)
    if lines_only:
        return lines
    return ("# Moorhuhn Kart 2 - 200 cc / 250 cc / tuning mod. The game merges this file over text.csv.\r\n"
            + "".join("%d;%s\r\n" % line for line in lines))


TEXT_OVERRIDES = text_overrides("de")


class Asm:
    """Tiny two-pass emitter: raw instruction bytes plus label-relative branches."""

    def __init__(self, base):
        self.base = base
        self.buf = bytearray()
        self.labels = {}
        self.fixups = []    # (offset, size, target)
        self.listing = []   # (va, text) - text uses dumpbin's syntax so it can be diffed

    @property
    def here(self):
        return self.base + len(self.buf)

    def label(self, name):
        assert name not in self.labels, name
        self.labels[name] = self.here
        return self.here

    def raw(self, hexbytes, text):
        self.listing.append((self.here, text))
        self.buf += bytes.fromhex(hexbytes)

    def data(self, blob, text):
        self.listing.append((self.here, "; " + text))
        self.buf += blob

    def _branch(self, opcode, size, target, text):
        self.listing.append((self.here, (text, target)))
        self.buf += opcode
        self.fixups.append((len(self.buf), size, target))
        self.buf += b"\0" * size

    def call(self, target):
        self._branch(b"\xE8", 4, target, "call")

    def jmp(self, target):
        self._branch(b"\xE9", 4, target, "jmp")

    def jmp_short(self, target):
        self._branch(b"\xEB", 1, target, "jmp")

    _CC = {"jb": 2, "jae": 3, "je": 4, "jne": 5, "jbe": 6, "ja": 7, "js": 8, "jns": 9, "jl": 0xC, "jge": 0xD, "jle": 0xE, "jg": 0xF}

    def jcc_short(self, cc, target):
        self._branch(bytes([0x70 + self._CC[cc]]), 1, target, cc)

    def jcc_near(self, cc, target):
        self._branch(bytes([0x0F, 0x80 + self._CC[cc]]), 4, target, cc)

    def resolve(self, target):
        return self.labels[target] if isinstance(target, str) else target

    def finish(self):
        for off, size, target in self.fixups:
            rel = self.resolve(target) - (self.base + off + size)
            if size == 1:
                assert -128 <= rel <= 127, (target, rel)
                struct.pack_into("<b", self.buf, off, rel)
            else:
                struct.pack_into("<i", self.buf, off, rel)
        lines = []
        for va, text in self.listing:
            if isinstance(text, tuple):
                text = "%-11s %08X" % (text[0], self.resolve(text[1]))
            lines.append((va, text))
        return bytes(self.buf), lines


def _le(value):
    """Little-endian dword as spaced hex."""
    return struct.pack("<I", value & 0xFFFFFFFF).hex(" ")


def _imm(value):
    """An immediate the way dumpbin prints it (the listing is diffed against dumpbin)."""
    value &= 0xFFFFFFFF
    if value < 10:
        return "%d" % value
    text = "%X" % value
    return ("0" if text[0] in "ABCDEF" else "") + text + "h"


# The computer karts' geometric driver: written in MASM (.claude/sandbox/tools/geo_driver.asm,
# where its working is explained) and turned into this table by asm2py.py. Hooked at GEO_HOOK.
GEO_HOOK, GEO_HOOK_ORIG = 0x0043A9EA, "8B 4E 10 C7 44 24 14 00 00 00 00"
GEO_LINE_HOOK, GEO_LINE_ORIG = 0x00439596, "89 7C 24 18 8D 9B 00 00 00 00"
# >>> GEO_DRIVER
# generated by .claude/sandbox/tools/asm2py.py from geo_driver.asm; do not edit by hand
GEO_DRIVER = (
    (0x0000, '60', 'pushad', None),
    (0x0001, '81 EC 14 01 00 00', 'sub         esp,114h', None),
    (0x0007, 'E8 00 00 00 00', 'call        %08X', ('local', 12)),
    (0x000C, '5B', 'pop         ebx', None),
    (0x000D, 'E8 00 00 00 00', 'call', ('ext', 4208528)),
    (0x0012, '8B D0', 'mov         edx,eax', None),
    (0x0014, '89 84 24 0C 01 00 00', 'mov         dword ptr [esp+0000010Ch],eax', None),
    (0x001B, '8B 40 10', 'mov         eax,dword ptr [eax+10h]', None),
    (0x001E, '83 F8 05', 'cmp         eax,5', None),
    (0x0021, '0F 87 E8 04 00 00', 'ja          %08X', ('local', 1295)),
    (0x0027, '0F B6 8C 03 A6 0A 00 00', 'movzx       ecx,byte ptr [ebx+eax+00000AA6h]', None),
    (0x002F, '85 C9', 'test        ecx,ecx', None),
    (0x0031, '0F 84 D8 04 00 00', 'je          %08X', ('local', 1295)),
    (0x0037, '8B 7E 10', 'mov         edi,dword ptr [esi+10h]', None),
    (0x003A, '89 7C 24 3C', 'mov         dword ptr [esp+3Ch],edi', None),
    (0x003E, '8B 87 04 03 00 00', 'mov         eax,dword ptr [edi+00000304h]', None),
    (0x0044, '83 F8 06', 'cmp         eax,6', None),
    (0x0047, '76 02', 'jbe         %08X', ('local', 75)),
    (0x0049, '33 C0', 'xor         eax,eax', None),
    (0x004B, '83 F9 02', 'cmp         ecx,2', None),
    (0x004E, '75 23', 'jne         %08X', ('local', 115)),
    (0x0050, '8B C8', 'mov         ecx,eax', None),
    (0x0052, '85 C9', 'test        ecx,ecx', None),
    (0x0054, '75 01', 'jne         %08X', ('local', 87)),
    (0x0056, '41', 'inc         ecx', None),
    (0x0057, '81 BA 98 2D 00 00 53 54 44 47', 'cmp         dword ptr [edx+00002D98h],47445453h', None),
    (0x0061, '0F 85 A8 04 00 00', 'jne         %08X', ('local', 1295)),
    (0x0067, '3B 8A 70 2E 00 00', 'cmp         ecx,dword ptr [edx+00002E70h]', None),
    (0x006D, '0F 8F 9C 04 00 00', 'jg          %08X', ('local', 1295)),
    (0x0073, '6B C0 7C', 'imul        eax,eax,7Ch', None),
    (0x0076, '8D AC 03 AE 0A 00 00', 'lea         ebp,[ebx+eax+00000AAEh]', None),
    (0x007D, '83 7D 2C 00', 'cmp         dword ptr [ebp+2Ch],0', None),
    (0x0081, '0F 84 88 04 00 00', 'je          %08X', ('local', 1295)),
    (0x0087, '8B 87 04 03 00 00', 'mov         eax,dword ptr [edi+00000304h]', None),
    (0x008D, 'E8 ED 05 00 00', 'call        %08X', ('local', 1663)),
    (0x0092, '89 84 24 08 01 00 00', 'mov         dword ptr [esp+00000108h],eax', None),
    (0x0099, '8B CF', 'mov         ecx,edi', None),
    (0x009B, 'E8 00 00 00 00', 'call', ('ext', 4378192)),
    (0x00A0, 'D9 94 24 50 01 00 00', 'fst         dword ptr [esp+00000150h]', None),
    (0x00A7, 'D9 5C 24 10', 'fstp        dword ptr [esp+10h]', None),
    (0x00AB, 'E8 00 00 00 00', 'call', ('ext', 4200432)),
    (0x00B0, '8B 48 1C', 'mov         ecx,dword ptr [eax+1Ch]', None),
    (0x00B3, '89 4C 24 28', 'mov         dword ptr [esp+28h],ecx', None),
    (0x00B7, 'E8 00 00 00 00', 'call', ('ext', 4470768)),
    (0x00BC, 'D9 5C 24 14', 'fstp        dword ptr [esp+14h]', None),
    (0x00C0, 'D9 44 24 10', 'fld         dword ptr [esp+10h]', None),
    (0x00C4, 'D8 4D 04', 'fmul        dword ptr [ebp+4]', None),
    (0x00C7, 'D9 45 00', 'fld         dword ptr [ebp]', None),
    (0x00CA, 'D8 D1', 'fcom        st(1)', None),
    (0x00CC, 'DF E0', 'fnstsw      ax', None),
    (0x00CE, 'F6 C4 01', 'test        ah,1', None),
    (0x00D1, '75 04', 'jne         %08X', ('local', 215)),
    (0x00D3, 'DD D9', 'fstp        st(1)', None),
    (0x00D5, 'EB 02', 'jmp         %08X', ('local', 217)),
    (0x00D7, 'DD D8', 'fstp        st(0)', None),
    (0x00D9, 'D8 74 24 14', 'fdiv        dword ptr [esp+14h]', None),
    (0x00DD, 'D9 5C 24 18', 'fstp        dword ptr [esp+18h]', None),
    (0x00E1, 'D9 87 24 02 00 00', 'fld         dword ptr [edi+00000224h]', None),
    (0x00E7, 'D9 5C 24 1C', 'fstp        dword ptr [esp+1Ch]', None),
    (0x00EB, 'D9 45 28', 'fld         dword ptr [ebp+28h]', None),
    (0x00EE, 'D9 EE', 'fldz', None),
    (0x00F0, 'D8 D9', 'fcomp       st(1)', None),
    (0x00F2, 'DF E0', 'fnstsw      ax', None),
    (0x00F4, 'F6 C4 41', 'test        ah,41h', None),
    (0x00F7, '74 06', 'je          %08X', ('local', 255)),
    (0x00F9, 'D9 5C 24 38', 'fstp        dword ptr [esp+38h]', None),
    (0x00FD, 'EB 2E', 'jmp         %08X', ('local', 301)),
    (0x00FF, 'D9 E0', 'fchs', None),
    (0x0101, 'D9 87 2C 02 00 00', 'fld         dword ptr [edi+0000022Ch]', None),
    (0x0107, 'D8 D1', 'fcom        st(1)', None),
    (0x0109, 'DF E0', 'fnstsw      ax', None),
    (0x010B, 'F6 C4 01', 'test        ah,1', None),
    (0x010E, '74 04', 'je          %08X', ('local', 276)),
    (0x0110, 'DD D8', 'fstp        st(0)', None),
    (0x0112, 'D9 C0', 'fld         st(0)', None),
    (0x0114, 'D9 E8', 'fld1', None),
    (0x0116, 'D8 E2', 'fsub        st,st(2)', None),
    (0x0118, 'D8 D1', 'fcom        st(1)', None),
    (0x011A, 'DF E0', 'fnstsw      ax', None),
    (0x011C, 'F6 C4 01', 'test        ah,1', None),
    (0x011F, '75 04', 'jne         %08X', ('local', 293)),
    (0x0121, 'DD D8', 'fstp        st(0)', None),
    (0x0123, 'EB 02', 'jmp         %08X', ('local', 295)),
    (0x0125, 'DD D9', 'fstp        st(1)', None),
    (0x0127, 'D9 5C 24 38', 'fstp        dword ptr [esp+38h]', None),
    (0x012B, 'DD D8', 'fstp        st(0)', None),
    (0x012D, '8B 4D 08', 'mov         ecx,dword ptr [ebp+8]', None),
    (0x0130, '41', 'inc         ecx', None),
    (0x0131, '89 4C 24 2C', 'mov         dword ptr [esp+2Ch],ecx', None),
    (0x0135, '8D 7C 24 40', 'lea         edi,[esp+40h]', None),
    (0x0139, '6A 00', 'push        0', None),
    (0x013B, 'FF 74 24 3C', 'push        dword ptr [esp+3Ch]', None),
    (0x013F, 'FF 74 24 24', 'push        dword ptr [esp+24h]', None),
    (0x0143, '8D 44 24 0C', 'lea         eax,[esp+0Ch]', None),
    (0x0147, '50', 'push        eax', None),
    (0x0148, '8B 4C 24 38', 'mov         ecx,dword ptr [esp+38h]', None),
    (0x014C, 'E8 00 00 00 00', 'call', ('ext', 4470992)),
    (0x0151, '8B 04 24', 'mov         eax,dword ptr [esp]', None),
    (0x0154, '89 07', 'mov         dword ptr [edi],eax', None),
    (0x0156, '8B 44 24 08', 'mov         eax,dword ptr [esp+8]', None),
    (0x015A, '89 47 04', 'mov         dword ptr [edi+4],eax', None),
    (0x015D, '83 C7 08', 'add         edi,8', None),
    (0x0160, 'D9 44 24 1C', 'fld         dword ptr [esp+1Ch]', None),
    (0x0164, 'D8 44 24 18', 'fadd        dword ptr [esp+18h]', None),
    (0x0168, 'D9 5C 24 1C', 'fstp        dword ptr [esp+1Ch]', None),
    (0x016C, 'FF 4C 24 2C', 'dec         dword ptr [esp+2Ch]', None),
    (0x0170, '75 C7', 'jne         %08X', ('local', 313)),
    (0x0172, 'D9 45 20', 'fld         dword ptr [ebp+20h]', None),
    (0x0175, 'D9 5C 24 24', 'fstp        dword ptr [esp+24h]', None),
    (0x0179, 'D9 EE', 'fldz', None),
    (0x017B, 'D9 5C 24 20', 'fstp        dword ptr [esp+20h]', None),
    (0x017F, '8D 7C 24 40', 'lea         edi,[esp+40h]', None),
    (0x0183, '8B 4D 08', 'mov         ecx,dword ptr [ebp+8]', None),
    (0x0186, '49', 'dec         ecx', None),
    (0x0187, '89 4C 24 2C', 'mov         dword ptr [esp+2Ch],ecx', None),
    (0x018B, 'D9 47 08', 'fld         dword ptr [edi+8]', None),
    (0x018E, 'D8 27', 'fsub        dword ptr [edi]', None),
    (0x0190, 'D9 47 0C', 'fld         dword ptr [edi+0Ch]', None),
    (0x0193, 'D8 67 04', 'fsub        dword ptr [edi+4]', None),
    (0x0196, 'D9 C1', 'fld         st(1)', None),
    (0x0198, 'D8 C8', 'fmul        st,st(0)', None),
    (0x019A, 'D9 C1', 'fld         st(1)', None),
    (0x019C, 'D8 C8', 'fmul        st,st(0)', None),
    (0x019E, 'DE C1', 'faddp       st(1),st', None),
    (0x01A0, 'D9 FA', 'fsqrt', None),
    (0x01A2, 'D9 54 24 34', 'fst         dword ptr [esp+34h]', None),
    (0x01A6, 'D8 44 24 20', 'fadd        dword ptr [esp+20h]', None),
    (0x01AA, 'D9 5C 24 20', 'fstp        dword ptr [esp+20h]', None),
    (0x01AE, 'D9 47 10', 'fld         dword ptr [edi+10h]', None),
    (0x01B1, 'D8 67 08', 'fsub        dword ptr [edi+8]', None),
    (0x01B4, 'D9 47 14', 'fld         dword ptr [edi+14h]', None),
    (0x01B7, 'D8 67 0C', 'fsub        dword ptr [edi+0Ch]', None),
    (0x01BA, 'D9 C3', 'fld         st(3)', None),
    (0x01BC, 'D8 C9', 'fmul        st,st(1)', None),
    (0x01BE, 'D9 C3', 'fld         st(3)', None),
    (0x01C0, 'D8 CB', 'fmul        st,st(3)', None),
    (0x01C2, 'D9 5C 24 30', 'fstp        dword ptr [esp+30h]', None),
    (0x01C6, 'D8 64 24 30', 'fsub        dword ptr [esp+30h]', None),
    (0x01CA, 'D9 E1', 'fabs', None),
    (0x01CC, 'D9 5C 24 30', 'fstp        dword ptr [esp+30h]', None),
    (0x01D0, 'D8 C8', 'fmul        st,st(0)', None),
    (0x01D2, 'D9 C9', 'fxch        st(1)', None),
    (0x01D4, 'D8 C8', 'fmul        st,st(0)', None),
    (0x01D6, 'DE C1', 'faddp       st(1),st', None),
    (0x01D8, 'D9 FA', 'fsqrt', None),
    (0x01DA, 'D8 4C 24 34', 'fmul        dword ptr [esp+34h]', None),
    (0x01DE, 'D9 5C 24 34', 'fstp        dword ptr [esp+34h]', None),
    (0x01E2, 'DD D8', 'fstp        st(0)', None),
    (0x01E4, 'DD D8', 'fstp        st(0)', None),
    (0x01E6, 'D9 47 10', 'fld         dword ptr [edi+10h]', None),
    (0x01E9, 'D8 27', 'fsub        dword ptr [edi]', None),
    (0x01EB, 'D8 C8', 'fmul        st,st(0)', None),
    (0x01ED, 'D9 47 14', 'fld         dword ptr [edi+14h]', None),
    (0x01F0, 'D8 67 04', 'fsub        dword ptr [edi+4]', None),
    (0x01F3, 'D8 C8', 'fmul        st,st(0)', None),
    (0x01F5, 'DE C1', 'faddp       st(1),st', None),
    (0x01F7, 'D9 FA', 'fsqrt', None),
    (0x01F9, 'D8 4C 24 34', 'fmul        dword ptr [esp+34h]', None),
    (0x01FD, 'D9 5C 24 34', 'fstp        dword ptr [esp+34h]', None),
    (0x0201, 'D9 44 24 30', 'fld         dword ptr [esp+30h]', None),
    (0x0205, 'D8 C0', 'fadd        st,st(0)', None),
    (0x0207, 'D8 45 24', 'fadd        dword ptr [ebp+24h]', None),
    (0x020A, 'D9 5C 24 30', 'fstp        dword ptr [esp+30h]', None),
    (0x020E, 'D9 44 24 34', 'fld         dword ptr [esp+34h]', None),
    (0x0212, 'D8 74 24 30', 'fdiv        dword ptr [esp+30h]', None),
    (0x0216, 'D8 45 10', 'fadd        dword ptr [ebp+10h]', None),
    (0x0219, 'D8 4D 0C', 'fmul        dword ptr [ebp+0Ch]', None),
    (0x021C, 'D8 C8', 'fmul        st,st(0)', None),
    (0x021E, 'D9 44 24 20', 'fld         dword ptr [esp+20h]', None),
    (0x0222, 'D8 4D 14', 'fmul        dword ptr [ebp+14h]', None),
    (0x0225, 'DE C1', 'faddp       st(1),st', None),
    (0x0227, 'D9 FA', 'fsqrt', None),
    (0x0229, 'D8 54 24 24', 'fcom        dword ptr [esp+24h]', None),
    (0x022D, 'DF E0', 'fnstsw      ax', None),
    (0x022F, 'F6 C4 01', 'test        ah,1', None),
    (0x0232, '74 04', 'je          %08X', ('local', 568)),
    (0x0234, 'D9 54 24 24', 'fst         dword ptr [esp+24h]', None),
    (0x0238, 'DD D8', 'fstp        st(0)', None),
    (0x023A, '83 C7 08', 'add         edi,8', None),
    (0x023D, 'FF 4C 24 2C', 'dec         dword ptr [esp+2Ch]', None),
    (0x0241, '0F 85 44 FF FF FF', 'jne         %08X', ('local', 395)),
    (0x0247, '8B 7C 24 3C', 'mov         edi,dword ptr [esp+3Ch]', None),
    (0x024B, 'C7 84 24 10 01 00 00 00 00 00 00', 'mov         dword ptr [esp+00000110h],0', None),
    (0x0256, '83 7D 44 00', 'cmp         dword ptr [ebp+44h],0', None),
    (0x025A, '0F 84 BC 00 00 00', 'je          %08X', ('local', 796)),
    (0x0260, '8B 84 24 08 01 00 00', 'mov         eax,dword ptr [esp+00000108h]', None),
    (0x0267, '85 C0', 'test        eax,eax', None),
    (0x0269, '0F 84 AD 00 00 00', 'je          %08X', ('local', 796)),
    (0x026F, 'D9 87 24 02 00 00', 'fld         dword ptr [edi+00000224h]', None),
    (0x0275, 'E8 67 04 00 00', 'call        %08X', ('local', 1761)),
    (0x027A, '85 C9', 'test        ecx,ecx', None),
    (0x027C, '0F 84 98 00 00 00', 'je          %08X', ('local', 794)),
    (0x0282, 'D9 44 24 10', 'fld         dword ptr [esp+10h]', None),
    (0x0286, 'D8 4D 48', 'fmul        dword ptr [ebp+48h]', None),
    (0x0289, 'D8 74 24 14', 'fdiv        dword ptr [esp+14h]', None),
    (0x028D, 'D8 87 24 02 00 00', 'fadd        dword ptr [edi+00000224h]', None),
    (0x0293, 'E8 49 04 00 00', 'call        %08X', ('local', 1761)),
    (0x0298, '85 C9', 'test        ecx,ecx', None),
    (0x029A, '74 09', 'je          %08X', ('local', 677)),
    (0x029C, 'D8 D1', 'fcom        st(1)', None),
    (0x029E, 'DF E0', 'fnstsw      ax', None),
    (0x02A0, 'F6 C4 01', 'test        ah,1', None),
    (0x02A3, '75 04', 'jne         %08X', ('local', 681)),
    (0x02A5, 'DD D8', 'fstp        st(0)', None),
    (0x02A7, 'EB 02', 'jmp         %08X', ('local', 683)),
    (0x02A9, 'DD D9', 'fstp        st(1)', None),
    (0x02AB, 'D8 8B 12 0E 00 00', 'fmul        dword ptr [ebx+00000E12h]', None),
    (0x02B1, 'D8 4D 44', 'fmul        dword ptr [ebp+44h]', None),
    (0x02B4, '8B 84 24 0C 01 00 00', 'mov         eax,dword ptr [esp+0000010Ch]', None),
    (0x02BB, '83 78 10 05', 'cmp         dword ptr [eax+10h],5', None),
    (0x02BF, '75 0C', 'jne         %08X', ('local', 717)),
    (0x02C1, 'DA 88 4C 2E 00 00', 'fimul       dword ptr [eax+00002E4Ch]', None),
    (0x02C7, 'D8 8B 26 0E 00 00', 'fmul        dword ptr [ebx+00000E26h]', None),
    (0x02CD, 'D9 54 24 24', 'fst         dword ptr [esp+24h]', None),
    (0x02D1, 'D8 4D 60', 'fmul        dword ptr [ebp+60h]', None),
    (0x02D4, 'D9 9C 24 10 01 00 00', 'fstp        dword ptr [esp+00000110h]', None),
    (0x02DB, 'D9 87 24 02 00 00', 'fld         dword ptr [edi+00000224h]', None),
    (0x02E1, 'C7 44 24 30 00 01 00 00', 'mov         dword ptr [esp+30h],100h', None),
    (0x02E9, 'DA 4C 24 30', 'fimul       dword ptr [esp+30h]', None),
    (0x02ED, 'D8 A3 12 0E 00 00', 'fsub        dword ptr [ebx+00000E12h]', None),
    (0x02F3, 'DB 5C 24 30', 'fistp       dword ptr [esp+30h]', None),
    (0x02F7, '8B 44 24 30', 'mov         eax,dword ptr [esp+30h]', None),
    (0x02FB, '25 FF 00 00 00', 'and         eax,0FFh', None),
    (0x0300, '8B 8C 24 08 01 00 00', 'mov         ecx,dword ptr [esp+00000108h]', None),
    (0x0307, 'F6 04 41 01', 'test        byte ptr [ecx+eax*2],1', None),
    (0x030B, '74 0F', 'je          %08X', ('local', 796)),
    (0x030D, '8B 44 24 24', 'mov         eax,dword ptr [esp+24h]', None),
    (0x0311, '89 84 24 10 01 00 00', 'mov         dword ptr [esp+00000110h],eax', None),
    (0x0318, 'EB 02', 'jmp         %08X', ('local', 796)),
    (0x031A, 'DD D8', 'fstp        st(0)', None),
    (0x031C, 'D9 44 24 24', 'fld         dword ptr [esp+24h]', None),
    (0x0320, 'D9 87 3C 03 00 00', 'fld         dword ptr [edi+0000033Ch]', None),
    (0x0326, 'D8 94 24 10 01 00 00', 'fcom        dword ptr [esp+00000110h]', None),
    (0x032D, 'DF E0', 'fnstsw      ax', None),
    (0x032F, 'F6 C4 01', 'test        ah,1', None),
    (0x0332, '74 09', 'je          %08X', ('local', 829)),
    (0x0334, 'DD D8', 'fstp        st(0)', None),
    (0x0336, 'D9 84 24 10 01 00 00', 'fld         dword ptr [esp+00000110h]', None),
    (0x033D, 'D8 D1', 'fcom        st(1)', None),
    (0x033F, 'DF E0', 'fnstsw      ax', None),
    (0x0341, 'F6 C4 01', 'test        ah,1', None),
    (0x0344, '74 04', 'je          %08X', ('local', 842)),
    (0x0346, 'DD D9', 'fstp        st(1)', None),
    (0x0348, 'EB 02', 'jmp         %08X', ('local', 844)),
    (0x034A, 'DD D8', 'fstp        st(0)', None),
    (0x034C, 'C7 87 3C 03 00 00 00 C0 79 44', 'mov         dword ptr [edi+0000033Ch],4479C000h', None),
    (0x0356, '83 7D 74 00', 'cmp         dword ptr [ebp+74h],0', None),
    (0x035A, '0F 84 D7 00 00 00', 'je          %08X', ('local', 1079)),
    (0x0360, 'E8 00 00 00 00', 'call', ('ext', 4200432)),
    (0x0365, '8B 48 10', 'mov         ecx,dword ptr [eax+10h]', None),
    (0x0368, '8B 40 14', 'mov         eax,dword ptr [eax+14h]', None),
    (0x036B, '2B C1', 'sub         eax,ecx', None),
    (0x036D, 'C1 F8 02', 'sar         eax,2', None),
    (0x0370, '89 44 24 2C', 'mov         dword ptr [esp+2Ch],eax', None),
    (0x0374, '89 4C 24 30', 'mov         dword ptr [esp+30h],ecx', None),
    (0x0378, 'FF 4C 24 2C', 'dec         dword ptr [esp+2Ch]', None),
    (0x037C, '0F 88 B5 00 00 00', 'js          %08X', ('local', 1079)),
    (0x0382, '8B 44 24 2C', 'mov         eax,dword ptr [esp+2Ch]', None),
    (0x0386, '8B 4C 24 30', 'mov         ecx,dword ptr [esp+30h]', None),
    (0x038A, '8B 0C 81', 'mov         ecx,dword ptr [ecx+eax*4]', None),
    (0x038D, '85 C9', 'test        ecx,ecx', None),
    (0x038F, '74 E7', 'je          %08X', ('local', 888)),
    (0x0391, '3B CF', 'cmp         ecx,edi', None),
    (0x0393, '74 E3', 'je          %08X', ('local', 888)),
    (0x0395, '83 79 44 00', 'cmp         dword ptr [ecx+44h],0', None),
    (0x0399, '74 DD', 'je          %08X', ('local', 888)),
    (0x039B, 'D9 81 24 02 00 00', 'fld         dword ptr [ecx+00000224h]', None),
    (0x03A1, 'D8 A7 24 02 00 00', 'fsub        dword ptr [edi+00000224h]', None),
    (0x03A7, 'D8 93 16 0E 00 00', 'fcom        dword ptr [ebx+00000E16h]', None),
    (0x03AD, 'DF E0', 'fnstsw      ax', None),
    (0x03AF, 'F6 C4 01', 'test        ah,1', None),
    (0x03B2, '74 04', 'je          %08X', ('local', 952)),
    (0x03B4, 'D9 E8', 'fld1', None),
    (0x03B6, 'DE C1', 'faddp       st(1),st', None),
    (0x03B8, 'D8 4C 24 14', 'fmul        dword ptr [esp+14h]', None),
    (0x03BC, 'D9 54 24 34', 'fst         dword ptr [esp+34h]', None),
    (0x03C0, 'D9 EE', 'fldz', None),
    (0x03C2, 'D8 D9', 'fcomp       st(1)', None),
    (0x03C4, 'DF E0', 'fnstsw      ax', None),
    (0x03C6, 'F6 C4 01', 'test        ah,1', None),
    (0x03C9, '74 65', 'je          %08X', ('local', 1072)),
    (0x03CB, 'D8 5D 78', 'fcomp       dword ptr [ebp+78h]', None),
    (0x03CE, 'DF E0', 'fnstsw      ax', None),
    (0x03D0, 'F6 C4 01', 'test        ah,1', None),
    (0x03D3, '74 A3', 'je          %08X', ('local', 888)),
    (0x03D5, 'D9 81 2C 02 00 00', 'fld         dword ptr [ecx+0000022Ch]', None),
    (0x03DB, 'D8 A7 2C 02 00 00', 'fsub        dword ptr [edi+0000022Ch]', None),
    (0x03E1, 'D9 E1', 'fabs', None),
    (0x03E3, 'D8 5D 6C', 'fcomp       dword ptr [ebp+6Ch]', None),
    (0x03E6, 'DF E0', 'fnstsw      ax', None),
    (0x03E8, 'F6 C4 01', 'test        ah,1', None),
    (0x03EB, '74 8B', 'je          %08X', ('local', 888)),
    (0x03ED, 'E8 00 00 00 00', 'call', ('ext', 4378192)),
    (0x03F2, 'D9 44 24 10', 'fld         dword ptr [esp+10h]', None),
    (0x03F6, 'D8 4D 68', 'fmul        dword ptr [ebp+68h]', None),
    (0x03F9, 'D8 D9', 'fcomp       st(1)', None),
    (0x03FB, 'DF E0', 'fnstsw      ax', None),
    (0x03FD, 'F6 C4 01', 'test        ah,1', None),
    (0x0400, '75 27', 'jne         %08X', ('local', 1065)),
    (0x0402, 'D8 45 74', 'fadd        dword ptr [ebp+74h]', None),
    (0x0405, 'D8 C8', 'fmul        st,st(0)', None),
    (0x0407, 'D9 44 24 34', 'fld         dword ptr [esp+34h]', None),
    (0x040B, 'D8 4D 14', 'fmul        dword ptr [ebp+14h]', None),
    (0x040E, 'DE C1', 'faddp       st(1),st', None),
    (0x0410, 'D9 FA', 'fsqrt', None),
    (0x0412, 'D8 D1', 'fcom        st(1)', None),
    (0x0414, 'DF E0', 'fnstsw      ax', None),
    (0x0416, 'F6 C4 01', 'test        ah,1', None),
    (0x0419, '75 07', 'jne         %08X', ('local', 1058)),
    (0x041B, 'DD D8', 'fstp        st(0)', None),
    (0x041D, 'E9 56 FF FF FF', 'jmp         %08X', ('local', 888)),
    (0x0422, 'DD D9', 'fstp        st(1)', None),
    (0x0424, 'E9 4F FF FF FF', 'jmp         %08X', ('local', 888)),
    (0x0429, 'DD D8', 'fstp        st(0)', None),
    (0x042B, 'E9 48 FF FF FF', 'jmp         %08X', ('local', 888)),
    (0x0430, 'DD D8', 'fstp        st(0)', None),
    (0x0432, 'E9 41 FF FF FF', 'jmp         %08X', ('local', 888)),
    (0x0437, 'D9 45 1C', 'fld         dword ptr [ebp+1Ch]', None),
    (0x043A, 'D8 D1', 'fcom        st(1)', None),
    (0x043C, 'DF E0', 'fnstsw      ax', None),
    (0x043E, 'F6 C4 01', 'test        ah,1', None),
    (0x0441, '75 04', 'jne         %08X', ('local', 1095)),
    (0x0443, 'DD D9', 'fstp        st(1)', None),
    (0x0445, 'EB 02', 'jmp         %08X', ('local', 1097)),
    (0x0447, 'DD D8', 'fstp        st(0)', None),
    (0x0449, 'D9 96 88 00 00 00', 'fst         dword ptr [esi+00000088h]', None),
    (0x044F, 'D8 6C 24 10', 'fsubr       dword ptr [esp+10h]', None),
    (0x0453, 'D8 4D 18', 'fmul        dword ptr [ebp+18h]', None),
    (0x0456, 'D9 EE', 'fldz', None),
    (0x0458, 'D8 D9', 'fcomp       st(1)', None),
    (0x045A, 'DF E0', 'fnstsw      ax', None),
    (0x045C, 'F6 C4 01', 'test        ah,1', None),
    (0x045F, '74 18', 'je          %08X', ('local', 1145)),
    (0x0461, 'D9 E8', 'fld1', None),
    (0x0463, 'D8 D1', 'fcom        st(1)', None),
    (0x0465, 'DF E0', 'fnstsw      ax', None),
    (0x0467, 'F6 C4 01', 'test        ah,1', None),
    (0x046A, '74 02', 'je          %08X', ('local', 1134)),
    (0x046C, 'D9 C9', 'fxch        st(1)', None),
    (0x046E, 'DD D8', 'fstp        st(0)', None),
    (0x0470, 'D9 9C 24 48 01 00 00', 'fstp        dword ptr [esp+00000148h]', None),
    (0x0477, 'EB 0D', 'jmp         %08X', ('local', 1158)),
    (0x0479, 'DD D8', 'fstp        st(0)', None),
    (0x047B, 'C7 84 24 48 01 00 00 00 00 00 00', 'mov         dword ptr [esp+00000148h],0', None),
    (0x0486, '8B 45 54', 'mov         eax,dword ptr [ebp+54h]', None),
    (0x0489, '0B 45 58', 'or          eax,dword ptr [ebp+58h]', None),
    (0x048C, '74 75', 'je          %08X', ('local', 1283)),
    (0x048E, 'D9 44 24 10', 'fld         dword ptr [esp+10h]', None),
    (0x0492, 'D8 5D 5C', 'fcomp       dword ptr [ebp+5Ch]', None),
    (0x0495, 'DF E0', 'fnstsw      ax', None),
    (0x0497, 'F6 C4 01', 'test        ah,1', None),
    (0x049A, '75 67', 'jne         %08X', ('local', 1283)),
    (0x049C, 'D9 84 24 54 01 00 00', 'fld         dword ptr [esp+00000154h]', None),
    (0x04A3, 'D8 B6 BC 00 00 00', 'fdiv        dword ptr [esi+000000BCh]', None),
    (0x04A9, 'D9 E1', 'fabs', None),
    (0x04AB, 'D8 5D 54', 'fcomp       dword ptr [ebp+54h]', None),
    (0x04AE, 'DF E0', 'fnstsw      ax', None),
    (0x04B0, 'F6 C4 01', 'test        ah,1', None),
    (0x04B3, '75 4E', 'jne         %08X', ('local', 1283)),
    (0x04B5, '83 7D 58 00', 'cmp         dword ptr [ebp+58h],0', None),
    (0x04B9, '74 39', 'je          %08X', ('local', 1268)),
    (0x04BB, '8B 84 24 08 01 00 00', 'mov         eax,dword ptr [esp+00000108h]', None),
    (0x04C2, '85 C0', 'test        eax,eax', None),
    (0x04C4, '74 3D', 'je          %08X', ('local', 1283)),
    (0x04C6, '40', 'inc         eax', None),
    (0x04C7, 'D9 87 24 02 00 00', 'fld         dword ptr [edi+00000224h]', None),
    (0x04CD, 'E8 0F 02 00 00', 'call        %08X', ('local', 1761)),
    (0x04D2, '85 C9', 'test        ecx,ecx', None),
    (0x04D4, '74 2B', 'je          %08X', ('local', 1281)),
    (0x04D6, 'D8 8B 2A 0E 00 00', 'fmul        dword ptr [ebx+00000E2Ah]', None),
    (0x04DC, 'D8 A3 2E 0E 00 00', 'fsub        dword ptr [ebx+00000E2Eh]', None),
    (0x04E2, 'D8 A7 2C 02 00 00', 'fsub        dword ptr [edi+0000022Ch]', None),
    (0x04E8, 'D9 E1', 'fabs', None),
    (0x04EA, 'D8 5D 58', 'fcomp       dword ptr [ebp+58h]', None),
    (0x04ED, 'DF E0', 'fnstsw      ax', None),
    (0x04EF, 'F6 C4 01', 'test        ah,1', None),
    (0x04F2, '75 0F', 'jne         %08X', ('local', 1283)),
    (0x04F4, 'C7 84 24 44 01 00 00 00 00 00 00', 'mov         dword ptr [esp+00000144h],0', None),
    (0x04FF, 'EB 02', 'jmp         %08X', ('local', 1283)),
    (0x0501, 'DD D8', 'fstp        st(0)', None),
    (0x0503, '81 C4 14 01 00 00', 'add         esp,114h', None),
    (0x0509, '61', 'popad', None),
    (0x050A, 'E9 00 00 00 00', 'jmp', ('ext', 4434677)),
    (0x050F, '81 C4 14 01 00 00', 'add         esp,114h', None),
    (0x0515, '61', 'popad', None),
    (0x0516, '8B 4E 10', 'mov         ecx,dword ptr [esi+10h]', None),
    (0x0519, 'C7 44 24 14 00 00 00 00', 'mov         dword ptr [esp+14h],0', None),
    (0x0521, 'E9 00 00 00 00', 'jmp', ('ext', 4434421)),
    (0x0526, '53', 'push        ebx', None),
    (0x0527, '51', 'push        ecx', None),
    (0x0528, '52', 'push        edx', None),
    (0x0529, '56', 'push        esi', None),
    (0x052A, '8B F0', 'mov         esi,eax', None),
    (0x052C, 'E8 00 00 00 00', 'call        %08X', ('local', 1329)),
    (0x0531, '5B', 'pop         ebx', None),
    (0x0532, 'E8 00 00 00 00', 'call', ('ext', 4208528)),
    (0x0537, '8B D0', 'mov         edx,eax', None),
    (0x0539, '8B 42 10', 'mov         eax,dword ptr [edx+10h]', None),
    (0x053C, '83 F8 05', 'cmp         eax,5', None),
    (0x053F, '77 49', 'ja          %08X', ('local', 1418)),
    (0x0541, '0F B6 8C 03 81 05 00 00', 'movzx       ecx,byte ptr [ebx+eax+00000581h]', None),
    (0x0549, '85 C9', 'test        ecx,ecx', None),
    (0x054B, '74 3D', 'je          %08X', ('local', 1418)),
    (0x054D, '8B 86 04 03 00 00', 'mov         eax,dword ptr [esi+00000304h]', None),
    (0x0553, '83 F8 06', 'cmp         eax,6', None),
    (0x0556, '76 02', 'jbe         %08X', ('local', 1370)),
    (0x0558, '33 C0', 'xor         eax,eax', None),
    (0x055A, '83 F9 02', 'cmp         ecx,2', None),
    (0x055D, '75 1B', 'jne         %08X', ('local', 1402)),
    (0x055F, '8B C8', 'mov         ecx,eax', None),
    (0x0561, '85 C9', 'test        ecx,ecx', None),
    (0x0563, '75 01', 'jne         %08X', ('local', 1382)),
    (0x0565, '41', 'inc         ecx', None),
    (0x0566, '81 BA 98 2D 00 00 53 54 44 47', 'cmp         dword ptr [edx+00002D98h],47445453h', None),
    (0x0570, '75 18', 'jne         %08X', ('local', 1418)),
    (0x0572, '3B 8A 70 2E 00 00', 'cmp         ecx,dword ptr [edx+00002E70h]', None),
    (0x0578, '7F 10', 'jg          %08X', ('local', 1418)),
    (0x057A, '6B C0 7C', 'imul        eax,eax,7Ch', None),
    (0x057D, '8D 84 03 89 05 00 00', 'lea         eax,[ebx+eax+00000589h]', None),
    (0x0584, '83 78 2C 00', 'cmp         dword ptr [eax+2Ch],0', None),
    (0x0588, '75 02', 'jne         %08X', ('local', 1420)),
    (0x058A, '33 C0', 'xor         eax,eax', None),
    (0x058C, '5E', 'pop         esi', None),
    (0x058D, '5A', 'pop         edx', None),
    (0x058E, '59', 'pop         ecx', None),
    (0x058F, '5B', 'pop         ebx', None),
    (0x0590, 'C3', 'ret', None),
    (0x0591, '', ':geo_obst', None),
    (0x0591, 'D9 5C 24 54', 'fstp        dword ptr [esp+54h]', None),
    (0x0595, '60', 'pushad', None),
    (0x0596, 'E8 00 00 00 00', 'call        %08X', ('local', 1435)),
    (0x059B, '5B', 'pop         ebx', None),
    (0x059C, '8B 47 10', 'mov         eax,dword ptr [edi+10h]', None),
    (0x059F, 'E8 82 FF FF FF', 'call        %08X', ('local', 1318)),
    (0x05A4, '85 C0', 'test        eax,eax', None),
    (0x05A6, '0F 84 C9 00 00 00', 'je          %08X', ('local', 1653)),
    (0x05AC, '8B E8', 'mov         ebp,eax', None),
    (0x05AE, '83 7D 6C 00', 'cmp         dword ptr [ebp+6Ch],0', None),
    (0x05B2, '0F 84 BD 00 00 00', 'je          %08X', ('local', 1653)),
    (0x05B8, '8B 4F 10', 'mov         ecx,dword ptr [edi+10h]', None),
    (0x05BB, '83 79 44 00', 'cmp         dword ptr [ecx+44h],0', None),
    (0x05BF, '0F 84 B0 00 00 00', 'je          %08X', ('local', 1653)),
    (0x05C5, '83 7E 44 00', 'cmp         dword ptr [esi+44h],0', None),
    (0x05C9, '0F 84 A6 00 00 00', 'je          %08X', ('local', 1653)),
    (0x05CF, 'E8 00 00 00 00', 'call', ('ext', 4378192)),
    (0x05D4, 'D8 4D 68', 'fmul        dword ptr [ebp+68h]', None),
    (0x05D7, '8B CE', 'mov         ecx,esi', None),
    (0x05D9, 'E8 00 00 00 00', 'call', ('ext', 4378192)),
    (0x05DE, 'DE D9', 'fcompp', None),
    (0x05E0, 'DF E0', 'fnstsw      ax', None),
    (0x05E2, 'F6 C4 01', 'test        ah,1', None),
    (0x05E5, '0F 84 8A 00 00 00', 'je          %08X', ('local', 1653)),
    (0x05EB, 'D9 44 24 38', 'fld         dword ptr [esp+38h]', None),
    (0x05EF, 'D8 8B 8B 08 00 00', 'fmul        dword ptr [ebx+0000088Bh]', None),
    (0x05F5, 'D9 C0', 'fld         st(0)', None),
    (0x05F7, 'D8 4D 70', 'fmul        dword ptr [ebp+70h]', None),
    (0x05FA, 'D9 86 24 02 00 00', 'fld         dword ptr [esi+00000224h]', None),
    (0x0600, 'D8 E1', 'fsub        st,st(1)', None),
    (0x0602, 'D9 5C 24 70', 'fstp        dword ptr [esp+70h]', None),
    (0x0606, 'D9 44 24 38', 'fld         dword ptr [esp+38h]', None),
    (0x060A, 'D8 8B 83 08 00 00', 'fmul        dword ptr [ebx+00000883h]', None),
    (0x0610, 'DE C1', 'faddp       st(1),st', None),
    (0x0612, 'D9 54 24 78', 'fst         dword ptr [esp+78h]', None),
    (0x0616, 'D9 5C 24 38', 'fstp        dword ptr [esp+38h]', None),
    (0x061A, 'DD D8', 'fstp        st(0)', None),
    (0x061C, 'D9 86 2C 02 00 00', 'fld         dword ptr [esi+0000022Ch]', None),
    (0x0622, 'D8 65 6C', 'fsub        dword ptr [ebp+6Ch]', None),
    (0x0625, 'D9 45 6C', 'fld         dword ptr [ebp+6Ch]', None),
    (0x0628, 'D8 C0', 'fadd        st,st(0)', None),
    (0x062A, 'D9 83 8F 08 00 00', 'fld         dword ptr [ebx+0000088Fh]', None),
    (0x0630, 'D8 DA', 'fcomp       st(2)', None),
    (0x0632, 'DF E0', 'fnstsw      ax', None),
    (0x0634, 'F6 C4 01', 'test        ah,1', None),
    (0x0637, '75 17', 'jne         %08X', ('local', 1616)),
    (0x0639, 'DD D8', 'fstp        st(0)', None),
    (0x063B, 'DD D8', 'fstp        st(0)', None),
    (0x063D, 'D9 E8', 'fld1', None),
    (0x063F, 'D9 E0', 'fchs', None),
    (0x0641, 'D9 86 2C 02 00 00', 'fld         dword ptr [esi+0000022Ch]', None),
    (0x0647, 'D8 45 6C', 'fadd        dword ptr [ebp+6Ch]', None),
    (0x064A, 'D9 E8', 'fld1', None),
    (0x064C, 'DE C1', 'faddp       st(1),st', None),
    (0x064E, 'EB 1D', 'jmp         %08X', ('local', 1645)),
    (0x0650, 'D9 C1', 'fld         st(1)', None),
    (0x0652, 'D8 C1', 'fadd        st,st(1)', None),
    (0x0654, 'D9 E8', 'fld1', None),
    (0x0656, 'D8 A3 8F 08 00 00', 'fsub        dword ptr [ebx+0000088Fh]', None),
    (0x065C, 'DE D9', 'fcompp', None),
    (0x065E, 'DF E0', 'fnstsw      ax', None),
    (0x0660, 'F6 C4 01', 'test        ah,1', None),
    (0x0663, '74 08', 'je          %08X', ('local', 1645)),
    (0x0665, 'DD D8', 'fstp        st(0)', None),
    (0x0667, 'D9 83 93 08 00 00', 'fld         dword ptr [ebx+00000893h]', None),
    (0x066D, 'D9 5C 24 7C', 'fstp        dword ptr [esp+7Ch]', None),
    (0x0671, 'D9 5C 24 74', 'fstp        dword ptr [esp+74h]', None),
    (0x0675, '61', 'popad', None),
    (0x0676, 'D9 44 24 50', 'fld         dword ptr [esp+50h]', None),
    (0x067A, 'E9 00 00 00 00', 'jmp', ('ext', 4430194)),
    (0x067F, '51', 'push        ecx', None),
    (0x0680, '52', 'push        edx', None),
    (0x0681, '50', 'push        eax', None),
    (0x0682, 'E8 00 00 00 00', 'call', ('ext', 4208528)),
    (0x0687, '8B 48 1C', 'mov         ecx,dword ptr [eax+1Ch]', None),
    (0x068A, '83 F9 01', 'cmp         ecx,1', None),
    (0x068D, '74 0A', 'je          %08X', ('local', 1689)),
    (0x068F, '83 F9 03', 'cmp         ecx,3', None),
    (0x0692, '74 05', 'je          %08X', ('local', 1689)),
    (0x0694, '8B 40 20', 'mov         eax,dword ptr [eax+20h]', None),
    (0x0697, 'EB 0A', 'jmp         %08X', ('local', 1699)),
    (0x0699, '8B 48 48', 'mov         ecx,dword ptr [eax+48h]', None),
    (0x069C, '83 E1 03', 'and         ecx,3', None),
    (0x069F, '8B 44 88 28', 'mov         eax,dword ptr [eax+ecx*4+28h]', None),
    (0x06A3, 'E8 00 00 00 00', 'call        %08X', ('local', 1704)),
    (0x06A8, '5A', 'pop         edx', None),
    (0x06A9, '59', 'pop         ecx', None),
    (0x06AA, '80 BA 9E 17 00 00 00', 'cmp         byte ptr [edx+0000179Eh],0', None),
    (0x06B1, '74 14', 'je          %08X', ('local', 1735)),
    (0x06B3, '83 F9 06', 'cmp         ecx,6', None),
    (0x06B6, '76 02', 'jbe         %08X', ('local', 1722)),
    (0x06B8, '33 C9', 'xor         ecx,ecx', None),
    (0x06BA, 'C1 E1 09', 'shl         ecx,9', None),
    (0x06BD, '8D 84 0A A2 17 00 00', 'lea         eax,[edx+ecx+000017A2h]', None),
    (0x06C4, '5A', 'pop         edx', None),
    (0x06C5, '59', 'pop         ecx', None),
    (0x06C6, 'C3', 'ret', None),
    (0x06C7, '3B 82 96 07 00 00', 'cmp         eax,dword ptr [edx+00000796h]', None),
    (0x06CD, '73 0D', 'jae         %08X', ('local', 1756)),
    (0x06CF, 'C1 E0 09', 'shl         eax,9', None),
    (0x06D2, '8D 84 02 9A 07 00 00', 'lea         eax,[edx+eax+0000079Ah]', None),
    (0x06D9, '5A', 'pop         edx', None),
    (0x06DA, '59', 'pop         ecx', None),
    (0x06DB, 'C3', 'ret', None),
    (0x06DC, '33 C0', 'xor         eax,eax', None),
    (0x06DE, '5A', 'pop         edx', None),
    (0x06DF, '59', 'pop         ecx', None),
    (0x06E0, 'C3', 'ret', None),
    (0x06E1, '83 EC 08', 'sub         esp,8', None),
    (0x06E4, 'C7 04 24 00 01 00 00', 'mov         dword ptr [esp],100h', None),
    (0x06EB, 'DA 0C 24', 'fimul       dword ptr [esp]', None),
    (0x06EE, 'C7 04 24 00 00 80 3F', 'mov         dword ptr [esp],3F800000h', None),
    (0x06F5, 'D8 24 24', 'fsub        dword ptr [esp]', None),
    (0x06F8, 'DB 54 24 04', 'fist        dword ptr [esp+4]', None),
    (0x06FC, 'DA 64 24 04', 'fisub       dword ptr [esp+4]', None),
    (0x0700, 'C7 04 24 00 00 00 3F', 'mov         dword ptr [esp],3F000000h', None),
    (0x0707, 'D8 04 24', 'fadd        dword ptr [esp]', None),
    (0x070A, '8B 4C 24 04', 'mov         ecx,dword ptr [esp+4]', None),
    (0x070E, '8D 51 01', 'lea         edx,[ecx+1]', None),
    (0x0711, '81 E1 FF 00 00 00', 'and         ecx,0FFh', None),
    (0x0717, '81 E2 FF 00 00 00', 'and         edx,0FFh', None),
    (0x071D, '0F B6 0C 48', 'movzx       ecx,byte ptr [eax+ecx*2]', None),
    (0x0721, '0F B6 14 50', 'movzx       edx,byte ptr [eax+edx*2]', None),
    (0x0725, '85 C9', 'test        ecx,ecx', None),
    (0x0727, '74 1B', 'je          %08X', ('local', 1860)),
    (0x0729, '85 D2', 'test        edx,edx', None),
    (0x072B, '74 17', 'je          %08X', ('local', 1860)),
    (0x072D, '89 0C 24', 'mov         dword ptr [esp],ecx', None),
    (0x0730, '89 54 24 04', 'mov         dword ptr [esp+4],edx', None),
    (0x0734, 'DB 44 24 04', 'fild        dword ptr [esp+4]', None),
    (0x0738, 'DA 24 24', 'fisub       dword ptr [esp]', None),
    (0x073B, 'DE C9', 'fmulp       st(1),st', None),
    (0x073D, 'DA 04 24', 'fiadd       dword ptr [esp]', None),
    (0x0740, '83 C4 08', 'add         esp,8', None),
    (0x0743, 'C3', 'ret', None),
    (0x0744, 'DD D8', 'fstp        st(0)', None),
    (0x0746, 'D9 EE', 'fldz', None),
    (0x0748, '33 C9', 'xor         ecx,ecx', None),
    (0x074A, '83 C4 08', 'add         esp,8', None),
    (0x074D, 'C3', 'ret', None),
    (0x074E, '', ':geo_line', None),
    (0x074E, '60', 'pushad', None),
    (0x074F, '83 EC 40', 'sub         esp,40h', None),
    (0x0752, 'E8 00 00 00 00', 'call        %08X', ('local', 1879)),
    (0x0757, '5B', 'pop         ebx', None),
    (0x0758, 'E8 00 00 00 00', 'call', ('ext', 4208528)),
    (0x075D, '8B D0', 'mov         edx,eax', None),
    (0x075F, '8B 40 10', 'mov         eax,dword ptr [eax+10h]', None),
    (0x0762, '83 F8 05', 'cmp         eax,5', None),
    (0x0765, '0F 87 24 02 00 00', 'ja          %08X', ('local', 2447)),
    (0x076B, '0F B6 BC 03 5B 03 00 00', 'movzx       edi,byte ptr [ebx+eax+0000035Bh]', None),
    (0x0773, '85 FF', 'test        edi,edi', None),
    (0x0775, '0F 84 14 02 00 00', 'je          %08X', ('local', 2447)),
    (0x077B, '8B 4E 10', 'mov         ecx,dword ptr [esi+10h]', None),
    (0x077E, '8B 81 04 03 00 00', 'mov         eax,dword ptr [ecx+00000304h]', None),
    (0x0784, '83 F8 06', 'cmp         eax,6', None),
    (0x0787, '76 02', 'jbe         %08X', ('local', 1931)),
    (0x0789, '33 C0', 'xor         eax,eax', None),
    (0x078B, '83 FF 02', 'cmp         edi,2', None),
    (0x078E, '75 23', 'jne         %08X', ('local', 1971)),
    (0x0790, '8B C8', 'mov         ecx,eax', None),
    (0x0792, '85 C9', 'test        ecx,ecx', None),
    (0x0794, '75 01', 'jne         %08X', ('local', 1943)),
    (0x0796, '41', 'inc         ecx', None),
    (0x0797, '81 BA 98 2D 00 00 53 54 44 47', 'cmp         dword ptr [edx+00002D98h],47445453h', None),
    (0x07A1, '0F 85 E8 01 00 00', 'jne         %08X', ('local', 2447)),
    (0x07A7, '3B 8A 70 2E 00 00', 'cmp         ecx,dword ptr [edx+00002E70h]', None),
    (0x07AD, '0F 8F DC 01 00 00', 'jg          %08X', ('local', 2447)),
    (0x07B3, '6B C0 7C', 'imul        eax,eax,7Ch', None),
    (0x07B6, '8D BC 03 63 03 00 00', 'lea         edi,[ebx+eax+00000363h]', None),
    (0x07BD, '83 7F 2C 00', 'cmp         dword ptr [edi+2Ch],0', None),
    (0x07C1, '0F 84 C8 01 00 00', 'je          %08X', ('local', 2447)),
    (0x07C7, '83 7F 4C 00', 'cmp         dword ptr [edi+4Ch],0', None),
    (0x07CB, '74 77', 'je          %08X', ('local', 2116)),
    (0x07CD, '8B 46 10', 'mov         eax,dword ptr [esi+10h]', None),
    (0x07D0, '8B 80 04 03 00 00', 'mov         eax,dword ptr [eax+00000304h]', None),
    (0x07D6, 'E8 A4 FE FF FF', 'call        %08X', ('local', 1663)),
    (0x07DB, '85 C0', 'test        eax,eax', None),
    (0x07DD, '74 65', 'je          %08X', ('local', 2116)),
    (0x07DF, '40', 'inc         eax', None),
    (0x07E0, 'D9 44 24 7C', 'fld         dword ptr [esp+7Ch]', None),
    (0x07E4, 'E8 F8 FE FF FF', 'call        %08X', ('local', 1761)),
    (0x07E9, '85 C9', 'test        ecx,ecx', None),
    (0x07EB, '74 55', 'je          %08X', ('local', 2114)),
    (0x07ED, 'D8 8B DF 06 00 00', 'fmul        dword ptr [ebx+000006DFh]', None),
    (0x07F3, 'D8 A3 E3 06 00 00', 'fsub        dword ptr [ebx+000006E3h]', None),
    (0x07F9, 'D8 A3 C7 06 00 00', 'fsub        dword ptr [ebx+000006C7h]', None),
    (0x07FF, 'D8 4F 64', 'fmul        dword ptr [edi+64h]', None),
    (0x0802, 'D8 83 C7 06 00 00', 'fadd        dword ptr [ebx+000006C7h]', None),
    (0x0808, 'D9 47 50', 'fld         dword ptr [edi+50h]', None),
    (0x080B, 'D9 E0', 'fchs', None),
    (0x080D, 'D8 D1', 'fcom        st(1)', None),
    (0x080F, 'DF E0', 'fnstsw      ax', None),
    (0x0811, 'F6 C4 41', 'test        ah,41h', None),
    (0x0814, '75 02', 'jne         %08X', ('local', 2072)),
    (0x0816, 'D9 C9', 'fxch        st(1)', None),
    (0x0818, 'DD D8', 'fstp        st(0)', None),
    (0x081A, 'D9 E8', 'fld1', None),
    (0x081C, 'D8 47 50', 'fadd        dword ptr [edi+50h]', None),
    (0x081F, 'D8 D1', 'fcom        st(1)', None),
    (0x0821, 'DF E0', 'fnstsw      ax', None),
    (0x0823, 'F6 C4 01', 'test        ah,1', None),
    (0x0826, '75 04', 'jne         %08X', ('local', 2092)),
    (0x0828, 'DD D8', 'fstp        st(0)', None),
    (0x082A, 'EB 02', 'jmp         %08X', ('local', 2094)),
    (0x082C, 'DD D9', 'fstp        st(1)', None),
    (0x082E, 'D8 64 24 70', 'fsub        dword ptr [esp+70h]', None),
    (0x0832, 'D8 4F 4C', 'fmul        dword ptr [edi+4Ch]', None),
    (0x0835, 'D8 44 24 70', 'fadd        dword ptr [esp+70h]', None),
    (0x0839, 'D9 5C 24 70', 'fstp        dword ptr [esp+70h]', None),
    (0x083D, 'E9 4D 01 00 00', 'jmp         %08X', ('local', 2447)),
    (0x0842, 'DD D8', 'fstp        st(0)', None),
    (0x0844, '83 7F 30 00', 'cmp         dword ptr [edi+30h],0', None),
    (0x0848, '0F 84 41 01 00 00', 'je          %08X', ('local', 2447)),
    (0x084E, '8B CD', 'mov         ecx,ebp', None),
    (0x0850, 'E8 00 00 00 00', 'call', ('ext', 4470768)),
    (0x0855, 'D9 5C 24 28', 'fstp        dword ptr [esp+28h]', None),
    (0x0859, 'D9 47 38', 'fld         dword ptr [edi+38h]', None),
    (0x085C, 'D8 67 3C', 'fsub        dword ptr [edi+3Ch]', None),
    (0x085F, 'D8 74 24 28', 'fdiv        dword ptr [esp+28h]', None),
    (0x0863, 'D8 44 24 7C', 'fadd        dword ptr [esp+7Ch]', None),
    (0x0867, 'D9 5C 24 2C', 'fstp        dword ptr [esp+2Ch]', None),
    (0x086B, 'D9 47 3C', 'fld         dword ptr [edi+3Ch]', None),
    (0x086E, 'D8 74 24 28', 'fdiv        dword ptr [esp+28h]', None),
    (0x0872, 'D9 5C 24 30', 'fstp        dword ptr [esp+30h]', None),
    (0x0876, 'C7 44 24 34 03 00 00 00', 'mov         dword ptr [esp+34h],3', None),
    (0x087E, '8D 74 24 10', 'lea         esi,[esp+10h]', None),
    (0x0882, '6A 00', 'push        0', None),
    (0x0884, '68 00 00 00 3F', 'push        3F000000h', None),
    (0x0889, 'FF 74 24 34', 'push        dword ptr [esp+34h]', None),
    (0x088D, '8D 44 24 0C', 'lea         eax,[esp+0Ch]', None),
    (0x0891, '50', 'push        eax', None),
    (0x0892, '8B CD', 'mov         ecx,ebp', None),
    (0x0894, 'E8 00 00 00 00', 'call', ('ext', 4470992)),
    (0x0899, '8B 04 24', 'mov         eax,dword ptr [esp]', None),
    (0x089C, '89 06', 'mov         dword ptr [esi],eax', None),
    (0x089E, '8B 44 24 08', 'mov         eax,dword ptr [esp+8]', None),
    (0x08A2, '89 46 04', 'mov         dword ptr [esi+4],eax', None),
    (0x08A5, '83 C6 08', 'add         esi,8', None),
    (0x08A8, 'D9 44 24 2C', 'fld         dword ptr [esp+2Ch]', None),
    (0x08AC, 'D8 44 24 30', 'fadd        dword ptr [esp+30h]', None),
    (0x08B0, 'D9 5C 24 2C', 'fstp        dword ptr [esp+2Ch]', None),
    (0x08B4, 'FF 4C 24 34', 'dec         dword ptr [esp+34h]', None),
    (0x08B8, '75 C8', 'jne         %08X', ('local', 2178)),
    (0x08BA, 'D9 44 24 18', 'fld         dword ptr [esp+18h]', None),
    (0x08BE, 'D8 64 24 10', 'fsub        dword ptr [esp+10h]', None),
    (0x08C2, 'D9 44 24 24', 'fld         dword ptr [esp+24h]', None),
    (0x08C6, 'D8 64 24 1C', 'fsub        dword ptr [esp+1Ch]', None),
    (0x08CA, 'DE C9', 'fmulp       st(1),st', None),
    (0x08CC, 'D9 44 24 1C', 'fld         dword ptr [esp+1Ch]', None),
    (0x08D0, 'D8 64 24 14', 'fsub        dword ptr [esp+14h]', None),
    (0x08D4, 'D9 44 24 20', 'fld         dword ptr [esp+20h]', None),
    (0x08D8, 'D8 64 24 18', 'fsub        dword ptr [esp+18h]', None),
    (0x08DC, 'DE C9', 'fmulp       st(1),st', None),
    (0x08DE, 'D9 5C 24 38', 'fstp        dword ptr [esp+38h]', None),
    (0x08E2, 'D8 64 24 38', 'fsub        dword ptr [esp+38h]', None),
    (0x08E6, 'D8 C0', 'fadd        st,st(0)', None),
    (0x08E8, 'D9 5C 24 38', 'fstp        dword ptr [esp+38h]', None),
    (0x08EC, 'D9 44 24 18', 'fld         dword ptr [esp+18h]', None),
    (0x08F0, 'D8 64 24 10', 'fsub        dword ptr [esp+10h]', None),
    (0x08F4, 'D8 C8', 'fmul        st,st(0)', None),
    (0x08F6, 'D9 44 24 1C', 'fld         dword ptr [esp+1Ch]', None),
    (0x08FA, 'D8 64 24 14', 'fsub        dword ptr [esp+14h]', None),
    (0x08FE, 'D8 C8', 'fmul        st,st(0)', None),
    (0x0900, 'DE C1', 'faddp       st(1),st', None),
    (0x0902, 'D9 FA', 'fsqrt', None),
    (0x0904, 'D9 44 24 20', 'fld         dword ptr [esp+20h]', None),
    (0x0908, 'D8 64 24 18', 'fsub        dword ptr [esp+18h]', None),
    (0x090C, 'D8 C8', 'fmul        st,st(0)', None),
    (0x090E, 'D9 44 24 24', 'fld         dword ptr [esp+24h]', None),
    (0x0912, 'D8 64 24 1C', 'fsub        dword ptr [esp+1Ch]', None),
    (0x0916, 'D8 C8', 'fmul        st,st(0)', None),
    (0x0918, 'DE C1', 'faddp       st(1),st', None),
    (0x091A, 'D9 FA', 'fsqrt', None),
    (0x091C, 'DE C9', 'fmulp       st(1),st', None),
    (0x091E, 'D9 44 24 20', 'fld         dword ptr [esp+20h]', None),
    (0x0922, 'D8 64 24 10', 'fsub        dword ptr [esp+10h]', None),
    (0x0926, 'D8 C8', 'fmul        st,st(0)', None),
    (0x0928, 'D9 44 24 24', 'fld         dword ptr [esp+24h]', None),
    (0x092C, 'D8 64 24 14', 'fsub        dword ptr [esp+14h]', None),
    (0x0930, 'D8 C8', 'fmul        st,st(0)', None),
    (0x0932, 'DE C1', 'faddp       st(1),st', None),
    (0x0934, 'D9 FA', 'fsqrt', None),
    (0x0936, 'DE C9', 'fmulp       st(1),st', None),
    (0x0938, 'D8 47 24', 'fadd        dword ptr [edi+24h]', None),
    (0x093B, 'D9 5C 24 3C', 'fstp        dword ptr [esp+3Ch]', None),
    (0x093F, 'D9 44 24 38', 'fld         dword ptr [esp+38h]', None),
    (0x0943, 'D8 74 24 3C', 'fdiv        dword ptr [esp+3Ch]', None),
    (0x0947, 'D8 4F 34', 'fmul        dword ptr [edi+34h]', None),
    (0x094A, 'D9 E8', 'fld1', None),
    (0x094C, 'D8 D1', 'fcom        st(1)', None),
    (0x094E, 'DF E0', 'fnstsw      ax', None),
    (0x0950, 'F6 C4 01', 'test        ah,1', None),
    (0x0953, '74 02', 'je          %08X', ('local', 2391)),
    (0x0955, 'D9 C9', 'fxch        st(1)', None),
    (0x0957, 'DD D8', 'fstp        st(0)', None),
    (0x0959, 'D9 E8', 'fld1', None),
    (0x095B, 'D9 E0', 'fchs', None),
    (0x095D, 'D8 D1', 'fcom        st(1)', None),
    (0x095F, 'DF E0', 'fnstsw      ax', None),
    (0x0961, 'F6 C4 41', 'test        ah,41h', None),
    (0x0964, '75 02', 'jne         %08X', ('local', 2408)),
    (0x0966, 'D9 C9', 'fxch        st(1)', None),
    (0x0968, 'DD D8', 'fstp        st(0)', None),
    (0x096A, 'D8 4F 30', 'fmul        dword ptr [edi+30h]', None),
    (0x096D, 'D8 83 C7 06 00 00', 'fadd        dword ptr [ebx+000006C7h]', None),
    (0x0973, 'D8 64 24 70', 'fsub        dword ptr [esp+70h]', None),
    (0x0977, 'D8 4F 40', 'fmul        dword ptr [edi+40h]', None),
    (0x097A, 'D8 44 24 70', 'fadd        dword ptr [esp+70h]', None),
    (0x097E, 'D9 5C 24 70', 'fstp        dword ptr [esp+70h]', None),
    (0x0982, '83 C4 40', 'add         esp,40h', None),
    (0x0985, '61', 'popad', None),
    (0x0986, '89 7C 24 18', 'mov         dword ptr [esp+18h],edi', None),
    (0x098A, 'E9 00 00 00 00', 'jmp', ('ext', 4429216)),
    (0x098F, '83 C4 40', 'add         esp,40h', None),
    (0x0992, '61', 'popad', None),
    (0x0993, '89 7C 24 18', 'mov         dword ptr [esp+18h],edi', None),
    (0x0997, 'E9 00 00 00 00', 'jmp', ('ext', 4429216)),
    (0x099C, '', ':geo_watch', None),
    (0x099C, '8B 4E 10', 'mov         ecx,dword ptr [esi+10h]', None),
    (0x099F, '53', 'push        ebx', None),
    (0x09A0, '57', 'push        edi', None),
    (0x09A1, 'E8 00 00 00 00', 'call        %08X', ('local', 2470)),
    (0x09A6, '5B', 'pop         ebx', None),
    (0x09A7, '8D BE C0 00 00 00', 'lea         edi,[esi+000000C0h]', None),
    (0x09AD, '80 B9 08 03 00 00 00', 'cmp         byte ptr [ecx+00000308h],0', None),
    (0x09B4, '0F 85 E7 00 00 00', 'jne         %08X', ('local', 2721)),
    (0x09BA, '83 B9 D0 02 00 00 02', 'cmp         dword ptr [ecx+000002D0h],2', None),
    (0x09C1, '0F 85 CB 00 00 00', 'jne         %08X', ('local', 2706)),
    (0x09C7, '51', 'push        ecx', None),
    (0x09C8, 'E8 00 00 00 00', 'call', ('ext', 4208528)),
    (0x09CD, '59', 'pop         ecx', None),
    (0x09CE, '8B D0', 'mov         edx,eax', None),
    (0x09D0, '8B 42 10', 'mov         eax,dword ptr [edx+10h]', None),
    (0x09D3, '83 F8 05', 'cmp         eax,5', None),
    (0x09D6, '0F 87 C5 00 00 00', 'ja          %08X', ('local', 2721)),
    (0x09DC, '80 BC 03 A8 22 00 00 00', 'cmp         byte ptr [ebx+eax+000022A8h],0', None),
    (0x09E4, '75 26', 'jne         %08X', ('local', 2572)),
    (0x09E6, '81 BA 98 2D 00 00 53 54 44 47', 'cmp         dword ptr [edx+00002D98h],47445453h', None),
    (0x09F0, '0F 85 AB 00 00 00', 'jne         %08X', ('local', 2721)),
    (0x09F6, '83 BA 70 2E 00 00 00', 'cmp         dword ptr [edx+00002E70h],0', None),
    (0x09FD, '75 0D', 'jne         %08X', ('local', 2572)),
    (0x09FF, '83 BA 6C 2E 00 00 83', 'cmp         dword ptr [edx+00002E6Ch],0FFFFFF83h', None),
    (0x0A06, '0F 84 95 00 00 00', 'je          %08X', ('local', 2721)),
    (0x0A0C, 'C6 81 4C 02 00 00 01', 'mov         byte ptr [ecx+0000024Ch],1', None),
    (0x0A13, '83 B9 9C 02 00 00 14', 'cmp         dword ptr [ecx+0000029Ch],14h', None),
    (0x0A1A, '74 67', 'je          %08X', ('local', 2691)),
    (0x0A1C, 'D9 81 20 02 00 00', 'fld         dword ptr [ecx+00000220h]', None),
    (0x0A22, 'D9 07', 'fld         dword ptr [edi]', None),
    (0x0A24, 'D9 C1', 'fld         st(1)', None),
    (0x0A26, 'D8 83 B8 22 00 00', 'fadd        dword ptr [ebx+000022B8h]', None),
    (0x0A2C, 'D8 D9', 'fcomp       st(1)', None),
    (0x0A2E, 'DF E0', 'fnstsw      ax', None),
    (0x0A30, 'F6 C4 01', 'test        ah,1', None),
    (0x0A33, '75 59', 'jne         %08X', ('local', 2702)),
    (0x0A35, 'D8 83 BC 22 00 00', 'fadd        dword ptr [ebx+000022BCh]', None),
    (0x0A3B, 'DE D9', 'fcompp', None),
    (0x0A3D, 'DF E0', 'fnstsw      ax', None),
    (0x0A3F, 'F6 C4 01', 'test        ah,1', None),
    (0x0A42, '75 4E', 'jne         %08X', ('local', 2706)),
    (0x0A44, 'D9 47 04', 'fld         dword ptr [edi+4]', None),
    (0x0A47, 'D8 84 24 94 00 00 00', 'fadd        dword ptr [esp+00000094h]', None),
    (0x0A4E, 'D9 57 04', 'fst         dword ptr [edi+4]', None),
    (0x0A51, 'D8 9B B0 22 00 00', 'fcomp       dword ptr [ebx+000022B0h]', None),
    (0x0A57, 'DF E0', 'fnstsw      ax', None),
    (0x0A59, 'F6 C4 41', 'test        ah,41h', None),
    (0x0A5C, '75 43', 'jne         %08X', ('local', 2721)),
    (0x0A5E, '8B 81 9C 02 00 00', 'mov         eax,dword ptr [ecx+0000029Ch]', None),
    (0x0A64, '83 F8 0A', 'cmp         eax,0Ah', None),
    (0x0A67, '74 38', 'je          %08X', ('local', 2721)),
    (0x0A69, '83 F8 0F', 'cmp         eax,0Fh', None),
    (0x0A6C, '74 33', 'je          %08X', ('local', 2721)),
    (0x0A6E, '83 F8 14', 'cmp         eax,14h', None),
    (0x0A71, '74 2E', 'je          %08X', ('local', 2721)),
    (0x0A73, '83 F8 18', 'cmp         eax,18h', None),
    (0x0A76, '74 29', 'je          %08X', ('local', 2721)),
    (0x0A78, '8B 41 5C', 'mov         eax,dword ptr [ecx+5Ch]', None),
    (0x0A7B, '85 C0', 'test        eax,eax', None),
    (0x0A7D, '74 22', 'je          %08X', ('local', 2721)),
    (0x0A7F, 'C6 40 08 01', 'mov         byte ptr [eax+8],1', None),
    (0x0A83, '8B 83 B4 22 00 00', 'mov         eax,dword ptr [ebx+000022B4h]', None),
    (0x0A89, '89 47 04', 'mov         dword ptr [edi+4],eax', None),
    (0x0A8C, 'EB 13', 'jmp         %08X', ('local', 2721)),
    (0x0A8E, 'DD D8', 'fstp        st(0)', None),
    (0x0A90, 'DD D8', 'fstp        st(0)', None),
    (0x0A92, '8B 81 20 02 00 00', 'mov         eax,dword ptr [ecx+00000220h]', None),
    (0x0A98, '89 07', 'mov         dword ptr [edi],eax', None),
    (0x0A9A, 'C7 47 04 00 00 00 00', 'mov         dword ptr [edi+4],0', None),
    (0x0AA1, '5F', 'pop         edi', None),
    (0x0AA2, '5B', 'pop         ebx', None),
    (0x0AA3, '8B 81 D0 02 00 00', 'mov         eax,dword ptr [ecx+000002D0h]', None),
    (0x0AA9, 'E9 00 00 00 00', 'jmp', ('ext', 4433681)),
    (0x0AAE, '47 45 4F 31 02 02 02 02 02 02 00 1F 00 00 80 40 8F C2 F5 3D 0E 00 00 00 CD CC 0C 40 00 00 80 40 00 00 48 42 00 00 00 3F 00 00 40 41 00 C0 79 44', '; GEO_DRIVER data +0', None),
    (0x0ADE, '6F 12 83 3A 00 00 00 3F 01 00 00 00 00 00 80 BE 00 00 F0 41 00 00 20 41 00 00 C0 40 CD CC CC 3E CD CC 8C 3F CD CC 4C 3E 00 00 00 3F 00 00 40 3F', '; GEO_DRIVER data +48', None),
    (0x0B0E, '00 00 00 00 00 00 00 00 00 00 C8 41 00 00 00 00 00 00 80 3F 00 00 00 3F CD CC CC 3E 00 00 A0 41 00 00 70 41 00 00 20 42 00 00 80 40 8F C2 F5 3D', '; GEO_DRIVER data +96', None),
    (0x0B3E, '0E 00 00 00 CD CC 0C 40 00 00 80 40 00 00 48 42 00 00 00 3F 00 00 40 41 00 C0 79 44 6F 12 83 3A 00 00 00 3F 01 00 00 00 00 00 80 BE 00 00 F0 41', '; GEO_DRIVER data +144', None),
    (0x0B6E, '00 00 20 41 00 00 C0 40 CD CC CC 3E CD CC 8C 3F CD CC 4C 3E 00 00 00 3F 00 00 40 3F 00 00 00 00 00 00 00 00 00 00 C8 41 00 00 00 00 00 00 80 3F', '; GEO_DRIVER data +192', None),
    (0x0B9E, '00 00 00 3F CD CC CC 3E 00 00 A0 41 00 00 70 41 00 00 20 42 00 00 80 40 8F C2 F5 3D 0E 00 00 00 CD CC 0C 40 00 00 80 40 00 00 48 42 00 00 00 3F', '; GEO_DRIVER data +240', None),
    (0x0BCE, '00 00 40 41 00 C0 79 44 6F 12 83 3A 00 00 00 3F 01 00 00 00 00 00 80 BE 00 00 F0 41 00 00 20 41 00 00 C0 40 CD CC CC 3E CD CC 8C 3F CD CC 4C 3E', '; GEO_DRIVER data +288', None),
    (0x0BFE, '00 00 00 3F 00 00 40 3F 00 00 00 00 00 00 00 00 00 00 C8 41 00 00 00 00 00 00 80 3F 00 00 00 3F CD CC CC 3E 00 00 A0 41 00 00 70 41 00 00 20 42', '; GEO_DRIVER data +336', None),
    (0x0C2E, '00 00 80 40 8F C2 F5 3D 0E 00 00 00 CD CC 0C 40 00 00 80 40 00 00 48 42 00 00 00 3F 00 00 40 41 00 C0 79 44 6F 12 83 3A 00 00 00 3F 01 00 00 00', '; GEO_DRIVER data +384', None),
    (0x0C5E, '00 00 80 BE 00 00 F0 41 00 00 20 41 00 00 C0 40 CD CC CC 3E CD CC 8C 3F CD CC 4C 3E 00 00 00 3F 00 00 40 3F 00 00 00 00 00 00 00 00 00 00 C8 41', '; GEO_DRIVER data +432', None),
    (0x0C8E, '00 00 00 00 00 00 80 3F 00 00 00 3F CD CC CC 3E 00 00 A0 41 00 00 70 41 00 00 20 42 00 00 80 40 8F C2 F5 3D 0E 00 00 00 CD CC 0C 40 00 00 80 40', '; GEO_DRIVER data +480', None),
    (0x0CBE, '00 00 48 42 00 00 00 3F 00 00 40 41 00 C0 79 44 6F 12 83 3A 00 00 00 3F 01 00 00 00 00 00 80 BE 00 00 F0 41 00 00 20 41 00 00 C0 40 CD CC CC 3E', '; GEO_DRIVER data +528', None),
    (0x0CEE, 'CD CC 8C 3F CD CC 4C 3E 00 00 00 3F 00 00 40 3F 00 00 00 00 00 00 00 00 00 00 C8 41 00 00 00 00 00 00 80 3F 00 00 00 3F CD CC CC 3E 00 00 A0 41', '; GEO_DRIVER data +576', None),
    (0x0D1E, '00 00 70 41 00 00 20 42 00 00 80 40 8F C2 F5 3D 0E 00 00 00 CD CC 0C 40 00 00 80 40 00 00 48 42 00 00 00 3F 00 00 40 41 00 C0 79 44 6F 12 83 3A', '; GEO_DRIVER data +624', None),
    (0x0D4E, '00 00 00 3F 01 00 00 00 00 00 80 BE 00 00 F0 41 00 00 20 41 00 00 C0 40 CD CC CC 3E CD CC 8C 3F CD CC 4C 3E 00 00 00 3F 00 00 40 3F 00 00 00 00', '; GEO_DRIVER data +672', None),
    (0x0D7E, '00 00 00 00 00 00 C8 41 00 00 00 00 00 00 80 3F 00 00 00 3F CD CC CC 3E 00 00 A0 41 00 00 70 41 00 00 20 42 00 00 80 40 8F C2 F5 3D 0E 00 00 00', '; GEO_DRIVER data +720', None),
    (0x0DAE, 'CD CC 0C 40 00 00 80 40 00 00 48 42 00 00 00 3F 00 00 40 41 00 C0 79 44 6F 12 83 3A 00 00 00 3F 01 00 00 00 00 00 80 BE 00 00 F0 41 00 00 20 41', '; GEO_DRIVER data +768', None),
    (0x0DDE, '00 00 C0 40 CD CC CC 3E CD CC 8C 3F CD CC 4C 3E 00 00 00 3F 00 00 40 3F 00 00 00 00 00 00 00 00 00 00 C8 41 00 00 00 00 00 00 80 3F 00 00 00 3F', '; GEO_DRIVER data +816', None),
    (0x0E0E, 'CD CC CC 3E 00 00 A0 41 00 00 70 41 00 00 20 42 00 00 00 3F 00 00 00 BF AB AA AA 3E CD CC CC 3D 00 00 40 40 0D 68 D3 3B 04 02 81 3C 08 04 C2 3F', '; GEO_DRIVER data +864', None),
    (0x0E3E, '08 00 00 00 7A 7E 7A 82 78 84 76 80 76 77 76 6E 78 6E 78 7A 78 89 78 93 76 95 74 95 72 94 72 94 72 95 72 91 72 86 72 7A 72 75 72 76 74 78 74 77', '; GEO_DRIVER data +912', None),
    (0x0E6E, '74 7A 74 82 74 7F 72 7A 72 7C 72 84 72 8A 72 8B 72 8B 70 84 70 74 70 6C 6E 71 6C 79 6C 7E 6C 7C 6C 79 6E 7A 70 79 72 7B 72 80 74 7E 74 7A 74 7A', '; GEO_DRIVER data +960', None),
    (0x0E9E, '74 79 74 77 74 75 76 73 76 70 76 6F 76 73 76 79 76 7B 76 77 78 76 78 7A 76 7A 74 75 74 73 72 72 74 72 74 71 74 70 74 6F 76 70 76 76 78 7E 78 84', '; GEO_DRIVER data +1008', None),
    (0x0ECE, '78 87 78 8B 78 8B 78 84 78 82 78 86 78 88 76 8B 76 8E 76 8E 76 8D 76 88 76 82 74 85 74 8C 74 90 74 91 74 91 74 8D 72 87 72 80 72 7F 72 7F 72 79', '; GEO_DRIVER data +1056', None),
    (0x0EFE, '74 76 74 77 76 78 76 7B 76 7E 76 81 76 83 76 86 76 88 74 88 74 88 76 8B 76 8E 78 90 78 90 78 8F 76 8E 76 8E 76 8E 76 88 76 7E 76 7B 74 7C 72 78', '; GEO_DRIVER data +1104', None),
    (0x0F2E, '72 73 72 77 72 81 72 86 72 83 72 7C 72 73 72 71 72 7A 72 88 74 91 74 92 76 8B 76 7E 76 71 74 6D 72 70 72 77 74 82 74 8C 74 92 74 94 72 92 74 8E', '; GEO_DRIVER data +1152', None),
    (0x0F5E, '74 8B 76 87 74 83 72 7F 70 7C 6E 7A 6E 74 6E 70 6E 72 6E 77 6E 7A 6E 77 70 72 72 76 72 7C 72 84 72 8D 74 92 74 92 74 8F 74 8F 74 8E 76 8C 76 8E', '; GEO_DRIVER data +1200', None),
    (0x0F8E, '76 91 76 95 76 97 76 96 76 93 78 8C 76 83 76 79 74 71 72 6B 70 68 6E 6A 6A 70 68 76 6A 7B 6C 81 6E 88 70 8D 70 8F 70 90 70 90 70 90 70 91 70 90', '; GEO_DRIVER data +1248', None),
    (0x0FBE, '70 8D 72 8A 72 8A 74 8C 74 89 74 7F 74 76 72 75 70 77 6E 77 70 76 70 77 72 7B 72 80 72 82 72 7E 74 76 74 72 74 79 74 84 74 8B 72 8D 72 8B 70 88', '; GEO_DRIVER data +1296', None),
    (0x0FEE, '70 88 6E 8C 6E 8F 6C 8A 6A 7F 66 77 5E 74 58 74 56 7E 56 8B 54 8C 56 85 5A 7F 60 7C 66 79 6C 73 6E 6D 6E 6C 70 6F 72 73 72 77 74 7B 76 7F 76 83', '; GEO_DRIVER data +1344', None),
    (0x101E, '76 87 78 8A 78 91 7A 96 78 96 78 92 76 8A 76 7D 76 73 74 6D 74 6B 76 6D 76 70 78 72 78 73 78 75 78 77 78 7A 62 86 66 86 6A 85 6C 85 6E 85 70 81', '; GEO_DRIVER data +1392', None),
    (0x104E, '72 7D 72 7D 72 7D 72 80 72 85 72 88 70 89 6A 89 64 88 64 87 62 87 62 89 64 8D 66 93 66 9E 62 9C 58 8B 4E 87 44 8E 44 89 46 7E 46 70 44 65 48 60', '; GEO_DRIVER data +1440', None),
    (0x107E, '4C 5F 4C 60 4C 5F 4A 5D 46 5A 48 5A 4C 5B 52 5D 56 60 5A 65 5E 6D 5E 78 5C 7C 54 82 50 9A 52 A5 56 A2 58 9E 5A 97 58 8D 54 86 50 83 50 7F 4E 77', '; GEO_DRIVER data +1488', None),
    (0x10AE, '4A 6E 40 68 34 65 36 67 3E 72 48 7A 4E 7F 54 87 58 89 5A 89 5A 8D 5C 8F 5C 91 5A 93 5A 95 5C 97 5E 94 5E 8D 60 88 62 89 62 8A 62 82 64 76 62 71', '; GEO_DRIVER data +1536', None),
    (0x10DE, '60 6F 60 6B 60 6B 60 6E 5C 79 5C 8F 5A 9B 58 98 5A 92 5C 8E 5C 8C 5E 8A 60 88 64 87 68 87 6C 86 6E 87 70 87 72 88 72 86 72 81 70 7D 70 7C 70 7C', '; GEO_DRIVER data +1584', None),
    (0x110E, '70 7D 70 7C 70 79 72 76 72 73 72 74 72 77 72 7A 72 7A 74 75 74 77 74 7D 74 81 74 82 74 82 76 86 74 89 74 86 74 83 74 85 74 87 72 84 72 83 70 83', '; GEO_DRIVER data +1632', None),
    (0x113E, '70 82 70 82 70 80 6E 7F 6E 7D 6E 77 6E 74 6E 78 6C 78 6C 74 6E 6E 70 6D 72 6F 74 73 74 75 76 76 78 75 76 74 76 72 74 6F 74 70 72 78 70 82 70 86', '; GEO_DRIVER data +1680', None),
    (0x116E, '70 84 70 85 6E 87 6E 84 6C 83 6A 80 6A 76 6A 6C 6A 6C 6C 72 6E 77 6E 7B 70 7D 70 7E 72 7F 74 81 74 83 76 86 74 88 74 8B 74 8E 74 90 72 91 72 91', '; GEO_DRIVER data +1728', None),
    (0x119E, '70 8F 70 8A 70 82 70 7D 70 7E 70 7C 6E 75 6E 77 6C 81 6A 85 6A 7F 68 74 66 6C 64 76 5E 92 54 A3 4C 9F 4E 97 52 90 52 89 52 7E 50 71 4C 66 4A 5F', '; GEO_DRIVER data +1776', None),
    (0x11CE, '48 5D 4A 5D 4C 5C 50 5B 54 5E 58 63 5A 66 5E 6B 60 72 5E 77 58 85 4E 98 44 9F 48 97 50 91 56 88 5A 75 5E 6A 60 6A 64 6B 66 6E 66 75 66 7D 66 83', '; GEO_DRIVER data +1824', None),
    (0x11FE, '66 87 66 8D 64 92 64 93 62 91 62 8D 60 7E 5C 66 56 5B 52 5A 4A 56 46 52 48 58 4E 65 52 72 58 7D 5C 84 5E 8B 62 8F 64 8F 64 8B 64 86 64 7E 60 73', '; GEO_DRIVER data +1872', None),
    (0x122E, '5E 79 54 92 44 A2 40 A0 44 99 4C 93 52 8E 58 88 5C 85 60 85 76 94 76 94 76 90 76 8B 74 89 74 89 74 88 74 8F 76 96 76 98 76 99 76 97 76 92 76 8C', '; GEO_DRIVER data +1920', None),
    (0x125E, '74 83 70 77 6E 70 6E 71 6E 74 6E 75 70 72 70 6D 70 6B 70 68 70 68 70 6B 70 6D 70 6F 70 72 70 72 72 72 72 73 72 74 74 79 74 7B 76 79 76 7B 76 81', '; GEO_DRIVER data +1968', None),
    (0x128E, '76 87 76 8D 76 92 76 92 76 8E 76 8A 76 8A 74 8A 72 89 70 88 6E 86 70 81 70 7C 72 76 70 6E 6C 6B 6C 6E 6C 73 6E 74 6E 72 6E 70 6E 6F 6E 6D 6C 6C', '; GEO_DRIVER data +2016', None),
    (0x12BE, '6C 6D 6C 6E 6E 71 70 73 72 6F 72 6C 72 6A 72 69 70 6C 70 74 70 80 70 8B 70 93 70 96 70 94 70 8C 6E 88 6E 89 6E 89 70 89 70 89 70 88 72 85 72 83', '; GEO_DRIVER data +2064', None),
    (0x12EE, '72 83 72 83 72 84 72 84 74 83 74 84 72 85 72 83 70 83 72 7E 72 77 72 7A 72 81 74 7C 74 71 72 70 72 76 70 7C 6E 84 6E 8B 70 8F 70 92 70 93 6E 8F', '; GEO_DRIVER data +2112', None),
    (0x131E, '62 8E 50 8D 3C 84 2E 7E 38 82 48 8A 54 90 5C 93 62 8F 66 85 68 82 6A 84 6A 88 6A 8E 6A 8F 6A 8D 6A 8C 6C 8D 6E 8E 6E 8C 6C 8B 6C 89 6C 88 6A 89', '; GEO_DRIVER data +2160', None),
    (0x134E, '6A 8B 6A 90 6C 92 6E 8F 6E 8F 6C 8D 6C 85 6E 84 6E 88 6E 8A 6E 8A 6E 89 6E 8B 6E 8F 6E 91 6E 91 66 93 58 8C 48 78 38 6B 32 6C 38 74 42 7E 4E 7F', '; GEO_DRIVER data +2208', None),
    (0x137E, '58 78 5E 75 64 74 66 74 6A 75 6C 77 6E 7B 70 7F 72 83 74 86 74 87 74 86 76 87 76 88 78 8A 76 8B 76 89 74 86 76 84 76 83 78 83 78 85 78 89 78 8B', '; GEO_DRIVER data +2256', None),
    (0x13AE, '78 8A 78 8C 76 8E 76 8F 78 8E 76 8D 74 8C 74 8A 74 88 76 87 78 88 78 87 78 86 78 87 78 84 78 81 76 83 74 87 74 87 72 80 6C 78 66 77 66 7C 6A 86', '; GEO_DRIVER data +2304', None),
    (0x13DE, '6C 90 6E 93 70 90 72 89 72 83 74 83 74 84 72 86 70 8D 70 8E 70 88 70 81 70 7C 6E 79 6E 78 6E 75 6E 71 6C 6F 6A 74 6A 7A 6A 7A 6E 77 70 74 6E 70', '; GEO_DRIVER data +2352', None),
    (0x140E, '6E 6F 6E 70 70 6C 72 6B 72 73 72 83 70 91 6E 98 6C 96 68 8F 66 85 66 79 60 87 52 A2 52 9E 5C 94 62 96 68 96 6C 94 6E 91 70 8E 72 8C 74 8B 74 89', '; GEO_DRIVER data +2400', None),
    (0x143E, '74 89 74 8F 78 87 78 89 7A 8C 7A 8E 7A 91 7A 94 7A 97 78 95 74 84 6E 63 6A 51 68 61 66 7B 68 8A 6A 8D 6C 88 6E 80 6C 75 6C 6C 6A 67 6C 65 6E 63', '; GEO_DRIVER data +2448', None),
    (0x146E, '6E 6F 6E 83 6A 83 68 7A 66 7E 66 83 66 7F 66 77 64 7C 64 91 66 9F 6A A6 6E A6 70 98 72 80 74 70 74 72 74 82 72 96 6C AC 60 C5 54 D7 4E DA 4C D4', '; GEO_DRIVER data +2496', None),
    (0x149E, '48 CE 48 BA 4C 93 54 7B 58 7B 5C 7B 62 75 66 77 66 83 6A 89 6C 86 6E 7E 6E 71 6C 62 6E 5C 70 5C 72 5F 72 66 72 6D 72 73 74 71 74 6A 74 68 74 69', '; GEO_DRIVER data +2544', None),
    (0x14CE, '76 6D 76 70 76 6F 74 6D 74 6B 74 70 74 7E 74 89 74 89 72 84 72 76 72 6C 72 74 72 85 72 92 72 99 72 92 72 80 72 7C 70 84 6E 8F 6C 9A 6A 99 6C 94', '; GEO_DRIVER data +2592', None),
    (0x14FE, '6C A2 66 C3 5E E1 58 E6 52 D3 56 C1 5E B3 62 A9 64 A5 66 A2 68 99 68 8D 68 88 68 87 68 88 6A 8F 6A 96 6E 9C 70 99 70 8F 72 8A 74 89 76 88 78 89', '; GEO_DRIVER data +2640', None),
    (0x152E, '78 89 78 89 78 8D 78 91 78 97 76 9B 74 93 72 7E 6E 72 6C 7E 6A 91 6A 9F 6C A7 6E A0 70 8C 72 77 72 72 74 7B 74 84 72 89 72 8B 70 84 70 75 70 6D', '; GEO_DRIVER data +2688', None),
    (0x155E, '70 76 70 84 72 8A 72 81 72 70 72 65 70 62 70 68 6E 78 6C 8C 6C 95 68 93 64 91 64 8C 66 81 66 7B 66 79 68 7A 6C 7C 6C 80 68 87 66 85 68 81 6A 88', '; GEO_DRIVER data +2736', None),
    (0x158E, '68 9B 62 AA 60 A9 62 A0 64 8F 64 7D 62 79 5E 7F 5C 81 5A 88 5C 90 5E 8C 62 7D 64 70 68 6C 6C 6F 70 75 72 7A 74 7F 76 80 76 83 74 84 70 84 6C 85', '; GEO_DRIVER data +2784', None),
    (0x15BE, '6A 87 6A 88 66 8B 66 8D 6A 8F 6E 8F 72 8C 72 8A 70 8B 70 91 6E 98 6E 9B 6E 9B 70 9C 72 A0 74 AB 76 AD 74 A8 74 AB 74 AC 72 A9 72 A5 70 A1 6E A1', '; GEO_DRIVER data +2832', None),
    (0x15EE, '6E A5 6E AA 6C B1 6E B8 70 AF 70 A1 72 A1 72 9C 72 8F 70 92 70 9A 70 97 70 8A 6E 79 6C 6E 6A 72 68 73 68 68 68 68 68 72 68 75 6C 74 70 76 72 79', '; GEO_DRIVER data +2880', None),
    (0x161E, '74 7A 76 76 78 75 78 76 76 79 76 80 74 89 74 8F 74 8E 74 8E 72 8F 72 88 72 7D 72 79 72 7B 74 83 76 88 76 87 74 78 74 76 74 77 74 79 74 79 74 79', '; GEO_DRIVER data +2928', None),
    (0x164E, '74 7B 74 7A 74 77 74 71 74 6B 74 6A 74 68 74 5D 74 54 74 51 74 4E 76 53 76 5F 76 72 74 8B 74 95 74 93 76 93 76 90 76 81 76 79 76 87 76 8F 74 8D', '; GEO_DRIVER data +2976', None),
    (0x167E, '74 8C 74 8C 74 8B 74 89 75 8A 73 88 6D 78 69 5C 65 45 63 4B 61 5F 5D 61 59 69 57 85 54 9F 52 A9 4E A4 4A 9A 46 94 44 99 40 9A 3C 84 3A 6B 36 73', '; GEO_DRIVER data +3024', None),
    (0x16AE, '30 93 2C 8D 2E 78 34 7B 3A 83 40 85 46 77 4C 69 52 68 56 64 58 60 5A 63 5C 62 5E 5C 62 5D 64 5E 66 5D 68 60 68 64 66 6C 62 78 5E 81 5C 7D 5A 68', '; GEO_DRIVER data +3072', None),
    (0x16DE, '58 40 54 24 54 28 54 34 54 3F 54 55 56 6D 5A 66 5C 55 5E 5E 60 71 62 84 64 92 66 8E 68 7D 6A 70 6A 6D 6C 6E 6C 6F 6E 71 6E 6C 6E 62 6E 5F 6E 62', '; GEO_DRIVER data +3120', None),
    (0x170E, '6C 64 6C 62 6A 5C 6A 59 6C 59 6C 5A 6C 5A 6C 6D 6E 89 6E 96 6E A0 6E A3 70 9D 70 94 72 85 72 7A 74 74 74 6E 74 68 76 63 76 62 76 66 74 68 76 71', '; GEO_DRIVER data +3168', None),
    (0x173E, '76 77 76 78 76 7D 78 7E 78 7A 78 79 78 7F 78 85 78 8F 78 9A 7A 9E 7A 9D 7A 98 7A 93 7A 8C 7A 8A 7C 8E 7C 8E 7C 8B 7C 8D 7A 90 7A 8D 76 8A 72 85', '; GEO_DRIVER data +3216', None),
    (0x176E, '70 80 6A 90 66 A6 62 99 5E 74 5C 5C 5A 51 58 41 56 42 52 60 50 74 4E 6C 4E 68 4E 6F 4E 76 4C 7D 4C 81 4A 84 48 85 48 84 46 82 44 7A 42 67 40 54', '; GEO_DRIVER data +3264', None),
    (0x179E, '40 4A 3E 54 3E 71 3E 87 42 8D 42 8D 42 89 48 89 4C 8A 50 84 56 76 5A 54 5C 2C 5E 24 60 38 60 5E 5E 8C 5C A3 5C 9F 60 91 62 95 64 A6 64 9F 66 82', '; GEO_DRIVER data +3312', None),
    (0x17CE, '68 77 6A 7B 6A 78 68 78 64 7D 5A 87 50 97 42 A0 30 A6 28 A5 34 95 3C 78 38 6A 30 72 26 68 26 58 30 54 38 53 3C 57 42 5E 48 64 4C 67 50 66 54 64', '; GEO_DRIVER data +3360', None),
    (0x17FE, '56 64 58 65 5A 66 5C 68 5C 71 5C 7F 5C 8E 5E 9A 60 98 62 91 64 8F 66 8D 66 8B 68 88 6A 86 6A 81 6C 7A 6E 78 6E 7C 6E 7F 6E 78 6E 60 6E 62 6E 83', '; GEO_DRIVER data +3408', None),
    (0x182E, '70 88 70 7A 72 72 72 71 72 76 74 76 74 72 74 72 74 76 74 78 74 7F 74 7D 74 7D 74 7D 74 7D 76 7C 76 7E 74 7F 74 78 72 70 72 6E 70 70 6C 6F 6A 6C', '; GEO_DRIVER data +3456', None),
    (0x185E, '6A 6C 6C 6F 6E 76 6C 7C 6C 82 6E 89 6E 8B 6C 88 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 60 7E 5A 61 4E 4E 44 65', '; GEO_DRIVER data +3504', None),
    (0x188E, '40 7B 38 7D 32 80 38 83 44 8C 4C 95 52 94 58 8F 5C 8F 5E 91 62 93 62 96 66 95 68 7F 6A 59 6C 4C 6C 64 6C 72 6C 6A 6C 6E 6E 88 70 A0 72 A5 72 96', '; GEO_DRIVER data +3552', None),
    (0x18BE, '74 7E 74 6E 76 6B 76 71 76 76 76 7C 76 82 76 82 76 7E 74 7A 74 79 72 75 72 6C 72 69 72 6B 72 6C 72 72 74 77 74 7A 74 7D 74 7C 72 77 72 78 72 79', '; GEO_DRIVER data +3600', None),
    (0x18EE, '70 76 6E 75 6E 75 70 75 72 77 72 7D 72 80 74 80 74 81 74 84 76 84 76 80 76 84 76 8D 78 91 76 94 76 97 76 93 78 88 78 85 78 88 78 88 78 82 78 7B', '; GEO_DRIVER data +3648', None),
    (0x191E, '78 79 78 7C 78 84 78 8F 78 95 78 98 78 9B 76 9A 76 95 76 94 76 90 76 8B 78 90 78 94 78 90 78 8C 78 8B 78 8A 76 89 74 89 72 89 70 8A 70 86 72 81', '; GEO_DRIVER data +3696', None),
    (0x194E, '72 84 74 89 74 85 74 80 76 81 76 82 76 85 76 88 76 8A 76 8C 74 92 72 94 72 95 72 93 72 90 70 90 72 8F 72 8D 74 8A 74 89 72 88 70 82 6E 79 6C 76', '; GEO_DRIVER data +3744', None),
    (0x197E, '6C 7E 6C 8C 6E 93 6E 90 6E 8D 6E 8F 6E 8D 6E 88 6C 83 6A 75 66 6C 62 7C 60 88 62 83 64 7F 68 80 6C 7F 6E 7E 70 7C 72 7C 74 7F 76 7D 76 79 76 76', '; GEO_DRIVER data +3792', None),
    (0x19AE, '76 75 76 79 74 7E 74 7D 74 7B 74 7D 74 83 74 86 74 85 74 83 74 82 72 83 72 7F 72 7C 72 7D 70 82 70 8A 70 8C 72 85 72 7E 72 7B 72 7B 72 76 72 6F', '; GEO_DRIVER data +3840', None),
    (0x19DE, '70 68 70 6C 72 7E 72 8D 72 90 72 91 74 94 74 8F 74 82 74 6E 72 5A 72 4D 72 4E 72 52 70 53 6E 5F 6E 6E 6E 68 6E 56 70 4E 70 4B 70 42 70 37 70 3E', '; GEO_DRIVER data +3888', None),
    (0x1A0E, '6E 5C 6E 77 6E 7A 70 7B 72 89 74 92 74 91 74 91 74 9A 74 A0 72 A1 72 96 72 89 72 8E 74 92 74 8C 76 82 76 78 78 76 78 71 78 6D 7A 72 7A 77 78 78', '; GEO_DRIVER data +3936', None),
    (0x1A3E, '76 7A 74 7E 74 68 76 63 7A 61 7C 65 7A 6D 78 7B 76 8D 74 A0 74 B4 74 CA 74 D3 74 CA 74 C8 74 D0 72 C8 70 A5 70 74 70 5B 72 5F 72 60 72 5D 72 5D', '; GEO_DRIVER data +3984', None),
    (0x1A6E, '72 5D 72 5A 72 4C 74 4F 76 76 76 90 76 B2 76 D3 76 BE 78 9B 78 7F 76 68 76 6C 76 6B 74 57 74 4C 74 50 74 5F 72 6C 72 71 72 71 72 6F 72 69 74 62', '; GEO_DRIVER data +4032', None),
    (0x1A9E, '74 5D 74 5D 74 64 72 6E 72 73 72 71 72 6A 72 64 70 63 70 65 6E 69 6E 6A 6E 6C 6E 74 6C 77 6C 74 6C 76 6C 77 6C 7A 6C 8A 6C 94 6C 8C 6C 81 6A 85', '; GEO_DRIVER data +4080', None),
    (0x1ACE, '6A 84 6A 71 68 64 64 64 64 6D 64 7B 66 80 66 78 66 70 68 6E 6A 71 6C 74 6E 77 70 7A 72 7E 74 85 74 8E 74 90 76 8E 78 88 78 82 76 81 74 84 74 84', '; GEO_DRIVER data +4128', None),
    (0x1AFE, '76 83 78 83 78 86 76 8A 74 8E 76 90 78 93 7A 95 7A 97 7A 9C 78 A0 76 A2 76 A2 76 9D 78 98 7A 9A 7C 9F 7A 9B 78 8D 74 78 72 5B 72 49 70 50 70 6A', '; GEO_DRIVER data +4176', None),
    (0x1B2E, '72 80 72 8C 74 95 76 9A 76 9B 78 9C 78 9C 76 9B 74 96 70 84 6E 5B 6E 2F 72 25 6E 42 60 6E 54 96 54 AB 5C B3 66 BA 6C B9 70 A7 74 90 78 7F 7A 75', '; GEO_DRIVER data +4224', None),
    (0x1B5E, '7A 72 7A 75 7C 78 7A 7B 78 7F 76 85 74 8A 72 8F 72 93 72 97 74 99 76 99 76 95 78 91 78 8E 78 8D 76 82 74 72 72 70 72 7B 74 88 74 8E 72 8B 70 80', '; GEO_DRIVER data +4272', None),
    (0x1B8E, '6E 77 6C 7D 6C 8E 6E 99 70 98 72 8E 72 82 72 82 72 85 74 7A 74 6C 76 71 78 7B 7A 7C 7A 7D 7A 7B 78 75 76 75 76 79 76 7D 74 7F 74 75 74 64 74 60', '; GEO_DRIVER data +4320', None),
    (0x1BBE, '76 67 78 6E 78 74 7A 75 7A 75 7A 74 78 75 76 7C 76 8D 74 97 74 96 74 95 74 94 74 94 74 96 74 95 74 97 72 99 72 96 70 90 70 89 6E 82 6C 7C 6C 78', '; GEO_DRIVER data +4368', None),
    (0x1BEE, '6C 78 6A 77 6A 78 6A 7A 6A 77 6C 72 6C 71 6C 6D 6C 69 6A 67 6C 69 6C 6F 6E 76 70 77 72 78 72 7D 72 85 72 8A 74 8C 74 8D 76 90 76 90 76 87 78 75', '; GEO_DRIVER data +4416', None),
    (0x1C1E, '76 69 6C 69 66 6C 68 82 64 A5 56 B7 4E B5 56 AB 5E A0 64 97 66 8F 6A 88 6C 7C 6E 70 6E 6F 70 6F 70 6C 72 6A 76 8A 78 8B 78 98 76 9E 76 98 76 8D', '; GEO_DRIVER data +4464', None),
    (0x1C4E, '74 83 72 7B 72 75 72 6C 72 6D 72 75 72 7B 72 7E 72 7A 72 79 74 7F 74 85 76 8B 76 8F 76 92 76 93 76 8D 76 8D 74 92 74 91 74 91 74 91 74 92 74 95', '; GEO_DRIVER data +4512', None),
    (0x1C7E, '74 95 74 96 74 95 74 95 76 94 76 92 76 8E 76 8D 76 8C 76 88 76 88 76 8E 76 91 74 91 72 90 72 8F 72 8C 72 92 72 98 72 93 72 87 72 7D 72 75 72 6A', '; GEO_DRIVER data +4560', None),
    (0x1CAE, '72 60 72 59 72 55 70 57 70 5C 70 5C 72 60 74 73 74 8A 74 98 72 A1 72 A8 72 AD 70 AF 70 AE 70 A9 70 A3 70 9D 70 99 70 9A 72 9B 72 93 74 92 76 9B', '; GEO_DRIVER data +4608', None),
    (0x1CDE, '76 9B 78 90 76 87 76 85 76 84 76 80 76 7A 74 76 74 79 74 7D 74 7C 74 7C 74 81 70 83 6E 80 6E 81 6E 81 70 84 70 93 72 9D 72 9C 72 98 74 94 74 8D', '; GEO_DRIVER data +4656', None),
    (0x1D0E, '74 7E 76 6D 76 66 78 68 76 75 76 87 74 8E 74 8D 76 89 74 8A 72 96 70 9B 70 9A 6E 95 6E 8D 6E 8E 6E 93 6E 96 70 92 74 86 76 77 76 6E 76 75 76 84', '; GEO_DRIVER data +4704', None),
    (0x1D3E, '74 91 74 97 74 95 74 87 72 80 70 7E 70 69 70 58 70 5B 70 68 72 76 72 7F 72 84 74 85 74 80 74 78 72 77 72 79 74 7A 76 7B 76 80 74 81 74 79 74 79', '; GEO_DRIVER data +4752', None),
    (0x1D6E, '72 82 72 89 70 8E 70 90 70 8E 72 86 72 7A 72 74 72 72 74 6E 74 6A 74 6C 74 77 74 85 74 8C 74 8D 76 8B 74 85 74 80 72 7D 74 7E 74 81 74 7F 74 7A', '; GEO_DRIVER data +4800', None),
    (0x1D9E, '76 7C 76 85 78 8B 78 8C 78 8E 76 91 76 91 74 93 74 98 74 9A 75 9A 75 95 75 8E 75 85 73 7B 73 7B 71 73 71 63 71 5E 71 64 71 69 70 6D 72 76 72 79', '; GEO_DRIVER data +4848', None),
    (0x1DCE, '72 75 74 7D 74 8B 74 87 72 81 72 84 70 89 70 89 70 8E 72 95 74 96 74 8C 76 7D 76 74 74 6C 70 69 68 76 64 84 60 82 5E 76 5E 6C 62 6A 64 6A 68 67', '; GEO_DRIVER data +4896', None),
    (0x1DFE, '6A 65 6E 65 70 67 70 69 70 6E 72 74 72 77 74 7F 76 88 76 8D 76 91 74 97 74 9B 74 97 70 8F 6C 8C 6C 8C 6E 8E 70 90 70 90 70 8F 70 93 70 97 70 9E', '; GEO_DRIVER data +4944', None),
    (0x1E2E, '70 A4 72 A5 72 98 72 80 74 7B 74 87 76 89 76 7F 76 80 76 8B 47 45 4F 32 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +4992', None),
    (0x1E5E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +5040', None),
    (0x1E8E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +5088', None),
    (0x1EBE, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +5136', None),
    (0x1EEE, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +5184', None),
    (0x1F1E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +5232', None),
    (0x1F4E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +5280', None),
    (0x1F7E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +5328', None),
    (0x1FAE, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +5376', None),
    (0x1FDE, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +5424', None),
    (0x200E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +5472', None),
    (0x203E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +5520', None),
    (0x206E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +5568', None),
    (0x209E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +5616', None),
    (0x20CE, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +5664', None),
    (0x20FE, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +5712', None),
    (0x212E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +5760', None),
    (0x215E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +5808', None),
    (0x218E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +5856', None),
    (0x21BE, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +5904', None),
    (0x21EE, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +5952', None),
    (0x221E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +6000', None),
    (0x224E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +6048', None),
    (0x227E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +6096', None),
    (0x22AE, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +6144', None),
    (0x22DE, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +6192', None),
    (0x230E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +6240', None),
    (0x233E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +6288', None),
    (0x236E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +6336', None),
    (0x239E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +6384', None),
    (0x23CE, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +6432', None),
    (0x23FE, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +6480', None),
    (0x242E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +6528', None),
    (0x245E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +6576', None),
    (0x248E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +6624', None),
    (0x24BE, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +6672', None),
    (0x24EE, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +6720', None),
    (0x251E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +6768', None),
    (0x254E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +6816', None),
    (0x257E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +6864', None),
    (0x25AE, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +6912', None),
    (0x25DE, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +6960', None),
    (0x260E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +7008', None),
    (0x263E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +7056', None),
    (0x266E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +7104', None),
    (0x269E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +7152', None),
    (0x26CE, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +7200', None),
    (0x26FE, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +7248', None),
    (0x272E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +7296', None),
    (0x275E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +7344', None),
    (0x278E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +7392', None),
    (0x27BE, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +7440', None),
    (0x27EE, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +7488', None),
    (0x281E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +7536', None),
    (0x284E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +7584', None),
    (0x287E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +7632', None),
    (0x28AE, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +7680', None),
    (0x28DE, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +7728', None),
    (0x290E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +7776', None),
    (0x293E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +7824', None),
    (0x296E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +7872', None),
    (0x299E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +7920', None),
    (0x29CE, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +7968', None),
    (0x29FE, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +8016', None),
    (0x2A2E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +8064', None),
    (0x2A5E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +8112', None),
    (0x2A8E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +8160', None),
    (0x2ABE, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +8208', None),
    (0x2AEE, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +8256', None),
    (0x2B1E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +8304', None),
    (0x2B4E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +8352', None),
    (0x2B7E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +8400', None),
    (0x2BAE, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +8448', None),
    (0x2BDE, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +8496', None),
    (0x2C0E, '00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00 00', '; GEO_DRIVER data +8544', None),
    (0x2C3E, '00 00 00 00 00 00 00 00 00 00 00 00 47 45 4F 33 00 00 00 01 01 01 00 00 00 00 A0 40 00 00 40 C0 0A D7 A3 3C 6F 12 03 3B 00', '; GEO_DRIVER data +8592', None),
)
# <<< GEO_DRIVER


def emit_table(a, label, table):
    """Put a table of asm2py.py into the code: plain bytes, jumps inside it, calls and jumps out."""
    base = a.label(label)
    for off, hx, text, target in table:
        assert a.here == base + off, (label, hex(off))
        if text.startswith(":"):
            a.label(text[1:])
        elif text.startswith(";"):
            a.data(bytes.fromhex(hx), text[1:].strip())
        elif target is None:
            a.raw(hx, text)
        elif target[0] == "local":
            a.raw(hx, text % (base + target[1]))
        elif text == "call":
            a.call(target[1])
        else:
            a.jmp(target[1])


def build_payload(base, factors, pulls, known=None, version=None):
    """Assemble the new code. Returns (bytes, listing, labels).

    `factors` are the class factors of 200 cc and 250 cc, `pulls` their pull factors.
    The code refers to data that is emitted behind it. `known` holds the label
    addresses of a first pass, so the second pass can fill those references in.
    """
    a = Asm(base)
    known = known or {}

    def later(label):                    # address of a label that is only defined further down
        return known.get(label, base)

    # Absolute addresses without relocations: ebp = address of a label in this code.
    def pic_base(label):
        a.call(label)
        a.label(label)
        a.raw("5D", "pop         ebp")

    def ebp_disp(label, target):
        return (target - a.labels[label]) & 0xFFFFFFFF

    def lea_eax(label, target):
        disp = ebp_disp(label, target)
        a.raw("8D 85 " + _le(disp), "lea         eax,[ebp+%08Xh]" % disp)

    def call_import(label, slot):
        disp = ebp_disp(label, slot)
        a.raw("FF 95 " + _le(disp), "call        dword ptr [ebp+%08Xh]" % disp)

    # The tuning code is spread over several routines that call each other. They all take
    # their addresses relative to one label: `call tune_base` leaves it in ebp.
    a.label("tune_base")
    a.call("tune_T")
    a.label("tune_T")
    a.raw("5D", "pop         ebp")
    a.raw("C3", "ret")

    def tdisp(target):                   # displacement of an address from tune_T
        target = later(target) if isinstance(target, str) else target
        return (target - a.labels["tune_T"]) & 0xFFFFFFFF

    T_REG = {"eax": 0x85, "ecx": 0x8D, "edx": 0x95, "ebx": 0x9D, "esi": 0xB5, "edi": 0xBD}

    def t_mov(reg, target):              # mov reg,[ebp+disp]
        disp = tdisp(target)
        a.raw("8B %02X %s" % (T_REG[reg], _le(disp)), "mov         %s,dword ptr [ebp+%08Xh]" % (reg, disp))

    def t_lea(reg, target):              # lea reg,[ebp+disp]
        disp = tdisp(target)
        a.raw("8D %02X %s" % (T_REG[reg], _le(disp)), "lea         %s,[ebp+%08Xh]" % (reg, disp))

    def t_call_import(slot):
        disp = tdisp(slot)
        a.raw("FF 95 " + _le(disp), "call        dword ptr [ebp+%08Xh]" % disp)

    def get_text(text_push_hex, text_push_text):
        """GetText(temp string at [esp], id, line 0); the id is pushed by the given instruction.
        Needs 1Ch free bytes at [esp] for the temp string. Leaves eax = const char*."""
        a.raw("6A 00", "push        0")
        a.raw(text_push_hex, text_push_text)
        a.raw("8D 44 24 08", "lea         eax,[esp+8]")
        a.raw("50", "push        eax")
        a.call(TEXTMGR_GET)
        a.raw("8B C8", "mov         ecx,eax")
        a.call(GET_TEXT)
        a.raw("8B C8", "mov         ecx,eax")
        a.call(STR_CSTR)

    # -- record table slots ---------------------------------------------------
    # The game indexes its [3 classes][64 tracks] tables with (class << 6) + track.
    # Classes 3 to 5 would run past the end, so their rows are folded onto the
    # upper halves of stock rows, which are never used (there are only 8 tracks):
    # class 3 (0C0h) -> slots 160..191 (0A0h, tracks 32..63 of the 150 cc row),
    # class 4 (100h) -> slots  96..127 ( 60h, tracks 32..63 of the 100 cc row),
    # class 5 (140h) -> slots  32..63  ( 20h, tracks 32..63 of the 50 cc row).
    # All are 160h - (class << 6).
    def slot_thunk(name, shl, cmp_, neg, add, tail_hex, tail_text, reg):
        a.label(name)
        a.raw(shl, "shl         %s,6" % reg)
        a.raw(cmp_, "cmp         %s,0C0h" % reg)
        a.jcc_short("jb", name + "_ok")
        a.raw(neg, "neg         %s" % reg)
        a.raw(add, "add         %s,160h" % reg)
        a.label(name + "_ok")
        a.raw(tail_hex, tail_text)
        a.raw("C3", "ret")

    EDI = ("C1 E7 06", "81 FF C0 00 00 00", "F7 DF", "81 C7 60 01 00 00")
    EDX = ("C1 E2 06", "81 FA C0 00 00 00", "F7 DA", "81 C2 60 01 00 00")
    ECX = ("C1 E1 06", "81 F9 C0 00 00 00", "F7 D9", "81 C1 60 01 00 00")
    EAX = ("C1 E0 06", "3D C0 00 00 00", "F7 D8", "05 60 01 00 00")
    slot_thunk("slot_edi_ebp", *EDI, "03 FD", "add         edi,ebp", "edi")
    slot_thunk("slot_edx_esi", *EDX, "03 D6", "add         edx,esi", "edx")
    slot_thunk("slot_ecx_into_edx", *ECX, "03 D1", "add         edx,ecx", "ecx")
    slot_thunk("slot_ecx_edx", *ECX, "03 CA", "add         ecx,edx", "ecx")
    slot_thunk("slot_edx_ecx", *EDX, "03 D1", "add         edx,ecx", "edx")
    slot_thunk("slot_edx_eax_to_edi", *EDX, "8D 3C 02", "lea         edi,[edx+eax]", "edx")
    slot_thunk("slot_edx_eax", *EDX, "03 D0", "add         edx,eax", "edx")
    slot_thunk("slot_eax_ecx", *EAX, "03 C1", "add         eax,ecx", "eax")

    # Championship tables are [3 classes][20 championships], index class*20 + id.
    # Class 3 (60..) is folded onto 50..59 (ids 10..19 of the 150 cc row, unused),
    # class 4 (80..) onto 30..39 (100 cc row), class 5 (100..) onto 10..19 (50 cc row).
    def champ_fold(name, cmp60, sub10, cmp70, sub40, cmp50, reg):
        a.raw(cmp60, "cmp         %s,3Ch" % reg)
        a.jcc_short("jb", name + "_ok")
        a.raw(sub10, "sub         %s,0Ah" % reg)       # 60.. -> 50.. (class 3); 80.. -> 70..; 100.. -> 90..
        a.raw(cmp70, "cmp         %s,46h" % reg)
        a.jcc_short("jb", name + "_ok")
        a.raw(sub40, "sub         %s,28h" % reg)       # 70.. -> 30.. (class 4); 90.. -> 50..
        a.raw(cmp50, "cmp         %s,32h" % reg)
        a.jcc_short("jb", name + "_ok")
        a.raw(sub40, "sub         %s,28h" % reg)       # 50.. -> 10.. (class 5)
        a.label(name + "_ok")

    FOLD_ECX = ("83 F9 3C", "83 E9 0A", "83 F9 46", "83 E9 28", "83 F9 32", "ecx")
    FOLD_EDX = ("83 FA 3C", "83 EA 0A", "83 FA 46", "83 EA 28", "83 FA 32", "edx")

    a.label("champ_index_ecx")
    a.raw("8D 04 80", "lea         eax,[eax+eax*4]")
    a.raw("8D 0C 81", "lea         ecx,[ecx+eax*4]")
    champ_fold("champ_index_ecx", *FOLD_ECX)
    a.raw("C3", "ret")

    a.label("champ_offset_ecx")
    champ_fold("champ_offset_ecx", *FOLD_ECX)
    a.raw("69 C9 8C 00 00 00", "imul        ecx,ecx,8Ch")
    a.raw("C3", "ret")

    a.label("champ_offset_edx")
    champ_fold("champ_offset_edx", *FOLD_EDX)
    a.raw("69 D2 8C 00 00 00", "imul        edx,edx,8Ch")
    a.raw("C3", "ret")

    # -- computer karts: per-level AI tables only exist for 3 classes ----------
    # (reached through the retargeted `call LevelSettings::Instance`; edi = class)
    a.label("ai_class_clamp")
    a.raw("83 FF 02", "cmp         edi,2")
    a.jcc_short("jbe", "ai_class_clamp_ok")
    a.raw("BF 02 00 00 00", "mov         edi,2")
    a.label("ai_class_clamp_ok")
    a.jmp(LS_GET)

    # The computer karts' "Tempo" for this race, in percent: the value of the page "Gegner", or
    # for "Standard" (and for a save without the marker) the class's own. Returns eax, keeps
    # every other register.
    a.label("opp_tempo")
    a.raw("55", "push        ebp")
    a.call("tune_base")
    t_mov("eax", GP_POINTER)
    a.raw("51", "push        ecx")
    a.raw("8B 88 " + _le(OPP_VALUE), "mov         ecx,dword ptr [eax+%08Xh]" % OPP_VALUE)
    a.raw("81 B8 %s %s" % (_le(STD_MARK), _le(STD_MAGIC)),
          "cmp         dword ptr [eax+%08Xh],%s" % (STD_MARK, _imm(STD_MAGIC)))
    a.jcc_short("jne", "opp_tempo_class")
    a.raw("83 F9 %02X" % (OPP_STANDARD & 0xFF), "cmp         ecx,%s" % _imm(OPP_STANDARD))
    a.jcc_short("jne", "opp_tempo_done")
    a.label("opp_tempo_class")
    a.raw("8B 48 10", "mov         ecx,dword ptr [eax+10h]")                 # class
    a.raw("83 F9 05", "cmp         ecx,5")
    a.jcc_short("jbe", "opp_tempo_table")
    a.raw("33 C9", "xor         ecx,ecx")
    a.jmp_short("opp_tempo_done")
    a.label("opp_tempo_table")
    disp = tdisp("opp_class_tempo")
    a.raw("0F BE 8C 0D " + _le(disp), "movsx       ecx,byte ptr [ebp+ecx+%08Xh]" % disp)
    a.label("opp_tempo_done")
    a.raw("8B C1", "mov         eax,ecx")
    a.raw("59", "pop         ecx")
    a.raw("5D", "pop         ebp")
    a.raw("C3", "ret")

    # In place of the computer kart's "throttle factor * strength of this kart" (st0 = factor,
    # the strength is [eax+edx*4+54h]; the next instruction loads eax): the throttle t becomes
    # t + (1 - t) * g, below 0 t + t * g, g = "Tempo" in hundredths (see AI_CATCHUP). Keeps ecx, edx.
    a.label("ai_throttle")
    a.raw("D8 4C 90 54", "fmul        dword ptr [eax+edx*4+54h]")      # displaced
    a.call("opp_tempo")
    a.raw("85 C0", "test        eax,eax")
    a.jcc_short("je", "ai_throttle_done")                                    # 0 %: as the game has it
    a.raw("6A 64", "push        64h")
    a.raw("50", "push        eax")
    a.jcc_short("jl", "ai_throttle_slower")                                  # (the pushes keep the flags)
    a.raw("D9 E8", "fld1")
    a.raw("D8 E1", "fsub        st,st(1)")                                   # 1 - t
    a.jmp_short("ai_throttle_mul")
    a.label("ai_throttle_slower")                 # below 0: t + t * g
    a.raw("D9 C0", "fld         st(0)")
    a.label("ai_throttle_mul")
    a.raw("DA 0C 24", "fimul       dword ptr [esp]")
    a.raw("DA 74 24 04", "fidiv       dword ptr [esp+4]")
    a.raw("DE C1", "faddp       st(1),st")
    a.raw("83 C4 08", "add         esp,8")
    a.label("ai_throttle_done")
    a.raw("8B 46 10", "mov         eax,dword ptr [esi+10h]")                 # displaced
    a.raw("C3", "ret")

    # In place of "rand(800)" in the computer kart's decision to fire its power-up (the frame
    # time is the update's argument, [esp+88h] at the call site): rand(800 / 60 / frame time).
    a.label("ai_item_chance")
    a.call("ai_item_chance_pc")
    a.label("ai_item_chance_pc")
    a.raw("58", "pop         eax")
    disp = (later("ai_item_rate") - a.labels["ai_item_chance_pc"]) & 0xFFFFFFFF
    a.raw("D9 80 " + _le(disp), "fld         dword ptr [eax+%08Xh]" % disp)
    a.raw("D8 B4 24 8C 00 00 00", "fdiv        dword ptr [esp+0000008Ch]")   # the frame time
    a.raw("50", "push        eax")
    a.raw("DB 1C 24", "fistp       dword ptr [esp]")
    a.raw("58", "pop         eax")
    a.raw("83 F8 01", "cmp         eax,1")
    a.jcc_short("jge", "ai_item_chance_ok")             # (a zero frame time gives a negative number)
    a.raw("B8 01 00 00 00", "mov         eax,1")
    a.label("ai_item_chance_ok")
    a.raw("50", "push        eax")
    a.call(RAND_MOD)
    a.raw("83 C4 04", "add         esp,4")
    a.raw("C3", "ret")

    emit_table(a, "geo_ai", GEO_DRIVER)

    # -- engine sound: three samples (50/100/150), the new classes reuse the 150 one ---
    a.label("engine_sound")
    a.raw("83 FF 02", "cmp         edi,2")
    a.jcc_short("jbe", "engine_sound_ok")
    a.raw("BF 02 00 00 00", "mov         edi,2")
    a.label("engine_sound_ok")
    a.raw("8B 44 BC 18", "mov         eax,dword ptr [esp+edi*4+18h]")
    a.raw("53", "push        ebx")
    a.jmp(0x0042FC19)

    # -- kart physics: class factor (diff ratio /= f, torque curve *= f) -------
    a.label("class_factor")
    a.raw("DD D8", "fstp        st(0)")           # drop the stock default (1.3) loaded just before
    a.raw("8B 40 10", "mov         eax,dword ptr [eax+10h]")
    a.raw("83 F8 05", "cmp         eax,5")
    a.jcc_short("je", "class_factor_tuning")
    a.raw("83 F8 04", "cmp         eax,4")
    a.jcc_short("jbe", "class_factor_ok")
    a.raw("B8 02 00 00 00", "mov         eax,2")
    a.label("class_factor_ok")
    a.call("class_factor_pc")                 # position independent table access
    a.label("class_factor_pc")
    a.raw("5A", "pop         edx")
    table_disp = (later("class_factor_table") - a.labels["class_factor_pc"]) & 0xFFFFFFFF
    a.raw("D9 84 82 " + _le(table_disp), "fld         dword ptr [edx+eax*4+%08Xh]" % table_disp)
    a.jmp(0x00437742)
    a.label("class_factor_tuning")                # the tuning class: its own "Übersetzung"
    a.raw("55", "push        ebp")
    a.call("tune_base")
    a.call("tune_defaults")
    t_mov("eax", GP_POINTER)
    a.raw("DB 80 " + _le(TUNE_VALUES), "fild        dword ptr [eax+%08Xh]" % TUNE_VALUES)
    disp = tdisp("hundredth")
    a.raw("D8 8D " + _le(disp), "fmul        dword ptr [ebp+%08Xh]" % disp)
    a.raw("5D", "pop         ebp")
    a.jmp(0x00437742)

    # In place of the call that drops the kart's physics objects before they are built
    # again from the values just read (ecx = car): the tuning class scales some of them.
    a.label("tune_apply")
    a.raw("60", "pushad")
    a.raw("8B F1", "mov         esi,ecx")
    a.call("tune_base")
    t_mov("ebx", GP_POINTER)
    a.raw("83 7B 10 05", "cmp         dword ptr [ebx+10h],5")
    a.jcc_short("jne", "tune_apply_done")
    t_lea("edi", "tune_apply_table")
    a.label("tune_apply_next")
    a.raw("0F B6 07", "movzx       eax,byte ptr [edi]")              # value number, 0 ends the list
    a.raw("85 C0", "test        eax,eax")
    a.jcc_short("je", "tune_apply_done")
    a.raw("DB 84 83 " + _le(TUNE_VALUES), "fild        dword ptr [ebx+eax*4+%08Xh]" % TUNE_VALUES)
    disp = tdisp("hundredth")
    a.raw("D8 8D " + _le(disp), "fmul        dword ptr [ebp+%08Xh]" % disp)   # percent -> factor
    a.raw("0F B7 47 01", "movzx       eax,word ptr [edi+1]")         # offset in the car
    a.raw("D8 0C 06", "fmul        dword ptr [esi+eax]")
    a.raw("D9 1C 06", "fstp        dword ptr [esi+eax]")
    a.raw("83 C7 03", "add         edi,3")
    a.jmp_short("tune_apply_next")
    a.label("tune_apply_done")
    a.raw("61", "popad")
    a.jmp(CAR_REBUILD)

    # In place of the call of RwPhysics::Init at every race start (ecx = the physics manager):
    # in the tuning class the new world's gravity is scaled by "Schwerkraft".
    a.label("world_gravity")
    a.call(PHYS_INIT)
    a.raw("60", "pushad")
    a.call("tune_base")
    t_mov("ebx", GP_POINTER)
    a.raw("85 DB", "test        ebx,ebx")
    a.jcc_short("je", "world_gravity_done")
    a.raw("83 7B 10 05", "cmp         dword ptr [ebx+10h],5")
    a.jcc_short("jne", "world_gravity_done")
    a.call("tune_defaults")                       # a save from before 1.7 gets its gravity first
    t_mov("eax", PHYS_MANAGER)
    for _ in range(2):                            # manager -> world handle -> world
        a.raw("85 C0", "test        eax,eax")
        a.jcc_short("je", "world_gravity_done")
        a.raw("8B 40 04", "mov         eax,dword ptr [eax+4]")
    a.raw("85 C0", "test        eax,eax")
    a.jcc_short("je", "world_gravity_done")
    off = TUNE_VALUES + 4 * (ROW_GRAVITY - 1)
    a.raw("DB 83 " + _le(off), "fild        dword ptr [ebx+%08Xh]" % off)
    disp = tdisp("hundredth")
    a.raw("D8 8D " + _le(disp), "fmul        dword ptr [ebp+%08Xh]" % disp)
    disp = tdisp("stock_gravity")
    a.raw("D8 8D " + _le(disp), "fmul        dword ptr [ebp+%08Xh]" % disp)
    a.raw("D9 58 %02X" % WORLD_GRAVITY_Y, "fstp        dword ptr [eax+%s]" % _imm(WORLD_GRAVITY_Y))
    a.label("world_gravity_done")
    a.raw("61", "popad")
    a.raw("C3", "ret")

    # -- kart physics: pull of the class ---------------------------------------
    # The force function multiplies the drive torque and the traction limit by the
    # vehicle's "accel factor" (1.0, or what a power-up sets). Both places call this
    # instead and get the class's pull on top. edi = vehicle; keeps every register.
    a.label("pull_mul")
    a.raw("D8 8F 68 02 00 00", "fmul        dword ptr [edi+00000268h]")      # displaced
    a.raw("50", "push        eax")
    a.raw("51", "push        ecx")
    a.call("pull_mul_pc")
    a.label("pull_mul_pc")
    a.raw("59", "pop         ecx")
    gp_disp = (GP_POINTER - a.labels["pull_mul_pc"]) & 0xFFFFFFFF
    a.raw("8B 81 " + _le(gp_disp), "mov         eax,dword ptr [ecx+%08Xh]" % gp_disp)   # GameParameters*
    a.raw("8B 40 10", "mov         eax,dword ptr [eax+10h]")                 # class
    a.raw("83 F8 04", "cmp         eax,4")
    a.jcc_short("ja", "pull_mul_tuning")
    table_disp = (later("class_pull_table") - a.labels["pull_mul_pc"]) & 0xFFFFFFFF
    a.raw("D8 8C 81 " + _le(table_disp), "fmul        dword ptr [ecx+eax*4+%08Xh]" % table_disp)
    a.jmp_short("pull_mul_opp")
    a.label("pull_mul_tuning")                    # the tuning class: its own "Motorkraft", in percent
    a.raw("83 F8 05", "cmp         eax,5")
    a.jcc_short("jne", "pull_mul_done")
    a.raw("8B 81 " + _le(gp_disp), "mov         eax,dword ptr [ecx+%08Xh]" % gp_disp)
    a.raw("DA 88 " + _le(TUNE_VALUES + 4), "fimul       dword ptr [eax+%08Xh]" % (TUNE_VALUES + 4))
    disp = (later("hundredth") - a.labels["pull_mul_pc"]) & 0xFFFFFFFF
    a.raw("D8 89 " + _le(disp), "fmul        dword ptr [ecx+%08Xh]" % disp)
    # "Tempo" above 100 %, in any class: a computer kart pulls Tempo / 100 times as hard
    a.label("pull_mul_opp")
    a.call("opp_tempo")
    a.raw("83 F8 64", "cmp         eax,64h")
    a.jcc_short("jle", "pull_mul_done")
    a.raw("52", "push        edx")
    a.call("pull_human")
    a.raw("5A", "pop         edx")
    a.jcc_short("je", "pull_mul_done")
    a.raw("50", "push        eax")
    a.raw("DA 0C 24", "fimul       dword ptr [esp]")
    a.raw("58", "pop         eax")
    disp = (later("hundredth") - a.labels["pull_mul_pc"]) & 0xFFFFFFFF
    a.raw("D8 89 " + _le(disp), "fmul        dword ptr [ecx+%08Xh]" % disp)
    a.label("pull_mul_done")
    a.raw("59", "pop         ecx")
    a.raw("58", "pop         eax")
    a.raw("C3", "ret")

    # Is edi the vehicle of a human player's kart? ecx = pull_mul_pc. Returns "equal" if it is.
    # Clobbers edx.
    a.label("pull_human")
    race_disp = (RACE_POINTER - a.labels["pull_mul_pc"]) & 0xFFFFFFFF
    a.raw("8B 91 " + _le(race_disp), "mov         edx,dword ptr [ecx+%08Xh]" % race_disp)
    a.raw("85 D2", "test        edx,edx")
    a.jcc_short("je", "pull_human_no")
    a.raw("8B 52 10", "mov         edx,dword ptr [edx+10h]")             # the human players' cars
    a.raw("85 D2", "test        edx,edx")
    a.jcc_short("je", "pull_human_no")
    a.raw("52", "push        edx")
    a.raw("8B 12", "mov         edx,dword ptr [edx]")                   # player 1
    a.raw("85 D2", "test        edx,edx")
    a.jcc_short("je", "pull_human_2")
    a.raw("3B 7A 44", "cmp         edi,dword ptr [edx+44h]")
    a.jcc_short("jne", "pull_human_2")
    a.raw("5A", "pop         edx")                                       # (keeps "equal")
    a.raw("C3", "ret")
    a.label("pull_human_2")
    a.raw("5A", "pop         edx")
    a.raw("8B 52 04", "mov         edx,dword ptr [edx+4]")               # player 2, if taking part
    a.raw("85 D2", "test        edx,edx")
    a.jcc_short("je", "pull_human_no")
    a.raw("80 BA 08 03 00 00 00", "cmp         byte ptr [edx+00000308h],0")
    a.jcc_short("je", "pull_human_no")
    a.raw("3B 7A 44", "cmp         edi,dword ptr [edx+44h]")
    a.raw("C3", "ret")
    a.label("pull_human_no")
    a.raw("83 CA 01", "or          edx,1")                              # "not equal"
    a.raw("C3", "ret")

    # -- kart physics: the tuning class limits its downforce ----------------------
    # The force function pushes the chassis along its own "down" with coefficient * (forward
    # speed)^2, in the air as well. In place of loading the coefficient (st0 = forward speed,
    # edi = vehicle, the chassis' up axis in world coordinates at [esp+3Ch] of the caller):
    # in the tuning class the speed is limited to DOWNFORCE_SPEED * sqrt(Gewicht / Anpressdruck)
    # first, to DOWNFORCE_SPEED_AIR * ... while no wheel touches the ground, and to zero
    # while the kart is tilted further than DOWNFORCE_UPRIGHT allows. Only the square of the
    # speed is used afterwards, so its sign does not matter. Keeps every register.
    a.label("downforce_cap")
    a.raw("50", "push        eax")
    a.raw("51", "push        ecx")
    a.call("downforce_cap_pc")
    a.label("downforce_cap_pc")
    a.raw("59", "pop         ecx")
    gp_disp = (GP_POINTER - a.labels["downforce_cap_pc"]) & 0xFFFFFFFF
    a.raw("8B 81 " + _le(gp_disp), "mov         eax,dword ptr [ecx+%08Xh]" % gp_disp)   # GameParameters*
    a.raw("83 78 10 05", "cmp         dword ptr [eax+10h],5")
    a.jcc_short("jne", "downforce_cap_done")
    # y of the up axis (the caller's [esp+40h]) against DOWNFORCE_UPRIGHT. Compared as integers:
    # for positive floats that is the same order, and a negative one has the sign bit set.
    upright = struct.unpack("<I", struct.pack("<f", DOWNFORCE_UPRIGHT))[0]
    a.raw("81 7C 24 4C " + _le(upright), "cmp         dword ptr [esp+4Ch],%s" % _imm(upright))
    a.jcc_short("jge", "downforce_cap_upright")
    a.raw("DD D8", "fstp        st(0)")               # tilted too far: no downforce, it would shove the kart around
    a.raw("D9 EE", "fldz")
    a.jmp_short("downforce_cap_done")
    a.label("downforce_cap_upright")
    a.raw("83 B8 " + _le(TUNE_VALUES + 0x18) + " 00", "cmp         dword ptr [eax+%08Xh],0" % (TUNE_VALUES + 0x18))
    a.jcc_short("jle", "downforce_cap_done")          # no downforce: nothing to limit
    a.raw("DB 80 " + _le(TUNE_VALUES + 0x0C), "fild        dword ptr [eax+%08Xh]" % (TUNE_VALUES + 0x0C))    # Gewicht
    a.raw("DA B0 " + _le(TUNE_VALUES + 0x18), "fidiv       dword ptr [eax+%08Xh]" % (TUNE_VALUES + 0x18))    # / Anpressdruck
    a.raw("D9 FA", "fsqrt")
    a.raw("8B 47 4C", "mov         eax,dword ptr [edi+4Ch]")                 # the four wheels' "touched the ground in this step"
    a.raw("0B 87 D0 00 00 00", "or          eax,dword ptr [edi+000000D0h]")
    a.raw("0B 87 54 01 00 00", "or          eax,dword ptr [edi+00000154h]")
    a.raw("0B 87 D8 01 00 00", "or          eax,dword ptr [edi+000001D8h]")
    a.raw("83 F8 01", "cmp         eax,1")
    a.raw("1B C0", "sbb         eax,eax")
    a.raw("F7 D8", "neg         eax")                 # 1 = in the air, 0 = on the ground
    disp = (later("downforce_speed") - a.labels["downforce_cap_pc"]) & 0xFFFFFFFF
    a.raw("D8 8C 81 " + _le(disp), "fmul        dword ptr [ecx+eax*4+%08Xh]" % disp)   # st0 = limit, st1 = speed
    a.raw("D9 C1", "fld         st(1)")
    a.raw("D9 E1", "fabs")
    a.raw("D8 D9", "fcomp       st(1)")               # |speed| against the limit
    a.raw("DF E0", "fnstsw      ax")
    a.raw("F6 C4 41", "test        ah,41h")
    a.jcc_short("jne", "downforce_cap_keep")          # not above the limit (or not a number)
    a.raw("DD D9", "fstp        st(1)")               # the limit takes the speed's place
    a.jmp_short("downforce_cap_done")
    a.label("downforce_cap_keep")
    a.raw("DD D8", "fstp        st(0)")
    a.label("downforce_cap_done")
    a.raw("59", "pop         ecx")
    a.raw("58", "pop         eax")
    a.raw("D9 87 64 02 00 00", "fld         dword ptr [edi+00000264h]")          # displaced
    a.raw("C3", "ret")

    # -- phantom kart headers: scan phantom-4-NN.mhk2 into slots 160..191, --------
    # phantom-5-NN.mhk2 into slots 96..127 and phantom-6-NN.mhk2 into slots 32..63
    # (file names count classes from 1)
    a.label("phantom_inner_limit")
    a.raw("83 7C 24 14 04", "cmp         dword ptr [esp+14h],4")
    a.jcc_short("jl", "phantom_inner_normal")
    a.raw("83 F8 20", "cmp         eax,20h")    # the new classes own 32 slots each
    a.jmp_short("phantom_inner_cont")
    a.label("phantom_inner_normal")
    a.raw("83 F8 40", "cmp         eax,40h")
    a.label("phantom_inner_cont")
    a.raw("C7 44 24 34 0F 00 00 00", "mov         dword ptr [esp+34h],0Fh")
    a.jmp(0x00413059)

    a.label("phantom_outer_next")
    a.raw("8B D7", "mov         edx,edi")
    a.raw("83 F9 03", "cmp         ecx,3")
    a.jcc_near("jl", 0x00412F58)        # classes 1, 2 done: next class
    a.jcc_short("jne", "phantom_outer_last")
    a.raw("8D 97 80 F2 FF FF", "lea         edx,[edi+FFFFF280h]")  # table end - 32 slots
    a.jmp(0x00412F58)                   # class 3 done: extra pass for class 4
    a.label("phantom_outer_last")
    a.raw("83 F9 06", "cmp         ecx,6")
    a.jcc_near("jge", 0x00413076)       # class 6 done: leave the loop
    # class 4 ended at slot 192 and class 5 at slot 128: the next class starts 96 slots lower
    a.raw("8D 97 80 D7 FF FF", "lea         edx,[edi+FFFFD780h]")
    a.jmp(0x00412F58)

    # -- engine class menu: fourth and fifth entry ------------------------------
    # A class is a button once the "highest unlocked class" counter has reached
    # it, and a greyed-out label before. esi = menu, ebx = 0.
    def menu_item(text_id, add_fn, y):
        a.raw("53", "push        ebx")                       # line 0
        a.raw("8D 44 24 04", "lea         eax,[esp+4]")      # temp std::string
        a.raw("68 " + _le(text_id), "push        %s" % _imm(text_id))
        a.raw("50", "push        eax")
        a.call(TEXTMGR_GET)
        a.raw("8B C8", "mov         ecx,eax")
        a.call(GET_TEXT)
        a.raw("68 " + _le(y), "push        %s" % _imm(y))
        a.raw("8B C8", "mov         ecx,eax")
        a.call(STR_CSTR)
        a.raw("50", "push        eax")
        a.raw("8B CE", "mov         ecx,esi")
        a.call(add_fn)

    # "Alles freigeschaltet": what the menus and the track lock read of the progress.
    # unlock_level: eax = GameParameters; ecx = the highest unlocked class (5 while the switch
    # is on). Keeps every other register.
    a.label("unlock_level")
    a.raw("8B 88 08 FD 00 00", "mov         ecx,dword ptr [eax+0000FD08h]")
    a.raw("81 B8 %s %s" % (_le(UNLOCK_MARK), _le(UNLOCK_MAGIC)),
          "cmp         dword ptr [eax+%08Xh],%s" % (UNLOCK_MARK, _imm(UNLOCK_MAGIC)))
    a.jcc_short("jne", "unlock_level_done")
    a.raw("B9 05 00 00 00", "mov         ecx,5")
    a.label("unlock_level_done")
    a.raw("C3", "ret")
    # In place of "cmp dword ptr [eax+0FD08h],2" in the class menu (100 cc row): the same flags.
    a.label("unlock_cmp2")
    a.raw("51", "push        ecx")
    a.call("unlock_level")
    a.raw("83 F9 02", "cmp         ecx,2")
    a.raw("59", "pop         ecx")
    a.raw("C3", "ret")
    # In place of "test dword ptr [eax+0FD0Ch],edx" in the track lock (edx = the class's bit):
    # nonzero while the switch is on.
    a.label("unlock_test")
    a.raw("81 B8 %s %s" % (_le(UNLOCK_MARK), _le(UNLOCK_MAGIC)),
          "cmp         dword ptr [eax+%08Xh],%s" % (UNLOCK_MARK, _imm(UNLOCK_MAGIC)))
    a.jcc_short("je", "unlock_test_on")
    a.raw("85 90 0C FD 00 00", "test        dword ptr [eax+0000FD0Ch],edx")
    a.raw("C3", "ret")
    a.label("unlock_test_on")
    a.raw("85 D2", "test        edx,edx")
    a.raw("C3", "ret")

    a.label("engine_menu_item")
    a.raw("83 EC 1C", "sub         esp,1Ch")
    for cls, text_id, locked_id in ((3, TXT_200CC, TXT_200CC_LOCKED), (4, TXT_250CC, TXT_250CC_LOCKED)):
        a.call(GP_GET)
        a.call("unlock_level")
        a.raw("83 F9 %02X" % cls, "cmp         ecx,%d" % cls)
        a.jcc_short("jl", "engine_menu_locked_%d" % cls)
        menu_item(text_id, ADD_BUTTON, MENU_Y_CLASSES[cls])
        a.jmp_short("engine_menu_done_%d" % cls)
        a.label("engine_menu_locked_%d" % cls)
        menu_item(locked_id, ADD_LABEL, MENU_Y_CLASSES[cls])
        a.label("engine_menu_done_%d" % cls)
        a.raw("8B CC", "mov         ecx,esp")
        a.call(STR_DTOR)
    # the tuning class: an empty label (it is not shown) until championship 2 is won in 250 cc
    a.call(GP_GET)
    a.call("unlock_level")
    a.raw("83 F9 05", "cmp         ecx,5")
    a.jcc_short("jl", "engine_menu_locked_5")
    menu_item(TXT_TUNING, ADD_BUTTON, MENU_Y_CLASSES[5])
    a.jmp_short("engine_menu_done_5")
    a.label("engine_menu_locked_5")
    menu_item(TXT_TUNING_HIDDEN, ADD_LABEL, MENU_Y_CLASSES[5])
    a.label("engine_menu_done_5")
    a.raw("8B CC", "mov         ecx,esp")
    a.call(STR_DTOR)
    a.raw("83 C4 1C", "add         esp,1Ch")
    a.raw("53", "push        ebx")                                   # displaced
    a.raw("8D 84 24 E8 08 00 00", "lea         eax,[esp+000008E8h]")  # displaced
    a.jmp(0x0041B3FC)

    # -- unlock message: "championship 2 unlocked in this class" is text 580 + class,
    # but 584 is taken by another message (edi = class on entry, text id on return)
    a.label("unlock_text")
    a.raw("81 C7 " + _le(TXT_CHAMP2_UNLOCKED), "add         edi,%s" % _imm(TXT_CHAMP2_UNLOCKED))   # displaced
    a.raw("81 FF " + _le(TXT_CHAMP2_UNLOCKED + 4), "cmp         edi,%s" % _imm(TXT_CHAMP2_UNLOCKED + 4))
    a.jcc_short("jne", "unlock_text_ok")
    a.raw("BF " + _le(TXT_CHAMP2_UNLOCKED_250), "mov         edi,%s" % _imm(TXT_CHAMP2_UNLOCKED_250))
    a.label("unlock_text_ok")
    a.raw("C3", "ret")

    # "next class unlocked" is text 584 + class: 588 would be the 250 cc message above, so
    # winning championship 2 in 250 cc (it unlocks the tuning class) shows a text of its own
    a.label("unlock_class_text")
    a.raw("81 C7 48 02 00 00", "add         edi,248h")                   # displaced
    a.raw("81 FF " + _le(TXT_CHAMP2_UNLOCKED_250), "cmp         edi,%s" % _imm(TXT_CHAMP2_UNLOCKED_250))
    a.jcc_short("jne", "unlock_class_text_ok")
    a.raw("BF " + _le(TXT_TUNING_UNLOCKED), "mov         edi,%s" % _imm(TXT_TUNING_UNLOCKED))
    a.label("unlock_class_text_ok")
    a.raw("C3", "ret")

    # -- tuning class ------------------------------------------------------------
    # Choosing "Tuning" in the class menu opens the tuning page before the character
    # menu (in place of the call that opens the next page; edi = class, [esp+4] = page).
    a.label("class_selected")
    a.raw("83 FF 05", "cmp         edi,5")
    a.jcc_short("jne", "class_selected_go")
    a.raw("C7 44 24 04 " + _le(PAGE_TUNING), "mov         dword ptr [esp+4],%s" % _imm(PAGE_TUNING))
    a.label("class_selected_go")
    a.jmp(PAGE_SET)

    # First the own presets: they exist once their marker is there, a save from before gets
    # eight empty slots. Then the tuning values: once their marker is there, else the defaults.
    # ebp = tune_T. Clobbers eax, ecx, edx.
    a.label("tune_defaults")
    t_mov("eax", GP_POINTER)
    a.raw("81 B8 %s %s" % (_le(OWN_MARK), _le(OWN_MAGIC)),
          "cmp         dword ptr [eax+%08Xh],%s" % (OWN_MARK, _imm(OWN_MAGIC)))
    a.jcc_short("je", "own_defaults_done")
    a.raw("57", "push        edi")
    a.raw("8D B8 " + _le(OWN_BASE), "lea         edi,[eax+%08Xh]" % OWN_BASE)
    a.raw("33 C0", "xor         eax,eax")
    n = (OWN_FLAG + 4 - OWN_BASE) // 4
    a.raw("B9 " + _le(n), "mov         ecx,%s" % _imm(n))
    a.raw("F3 AB", "rep stos    dword ptr es:[edi]")          # slots, marker, slot shown, flag
    a.raw("5F", "pop         edi")
    t_mov("eax", GP_POINTER)
    a.raw("C7 80 %s %s" % (_le(OWN_MARK), _le(OWN_MAGIC)),
          "mov         dword ptr [eax+%08Xh],%s" % (OWN_MARK, _imm(OWN_MAGIC)))
    a.label("own_defaults_done")
    # Up to 1.6 there were seven values, and the dword behind them was the number of the preset
    # copied last (own slots from 14 on). Now the gravity is there: the number moves, the
    # gravity and every filled own slot's gravity (its "filled" word, 1 up to 1.6) become 100 %.
    a.raw("81 B8 %s %s" % (_le(VALUES8_MARK), _le(VALUES8_MAGIC)),
          "cmp         dword ptr [eax+%08Xh],%s" % (VALUES8_MARK, _imm(VALUES8_MAGIC)))
    a.jcc_short("je", "values8_done")
    a.raw("8B 88 " + _le(OLD_TUNE_LAST), "mov         ecx,dword ptr [eax+%08Xh]" % OLD_TUNE_LAST)
    a.raw("83 F9 %02X" % OLD_PRESETS, "cmp         ecx,%s" % _imm(OLD_PRESETS))
    a.jcc_short("jb", "values8_last")
    a.raw("83 C1 %02X" % (PRESETS_18 - OLD_PRESETS), "add         ecx,%s" % _imm(PRESETS_18 - OLD_PRESETS))   # 1.8 numbers
    a.label("values8_last")
    a.raw("89 88 " + _le(TUNE_LAST), "mov         dword ptr [eax+%08Xh],ecx" % TUNE_LAST)
    a.raw("C7 80 %s %s" % (_le(OLD_TUNE_LAST), _le(TUNE_ROWS[ROW_GRAVITY - 1][3])),
          "mov         dword ptr [eax+%08Xh],%s" % (OLD_TUNE_LAST, _imm(TUNE_ROWS[ROW_GRAVITY - 1][3])))
    a.raw("8D 90 " + _le(OWN_BASE + OWN_FILLED), "lea         edx,[eax+%08Xh]" % (OWN_BASE + OWN_FILLED))
    a.raw("B9 " + _le(OWN_SLOTS), "mov         ecx,%s" % _imm(OWN_SLOTS))
    a.label("values8_slot")
    a.raw("66 83 3A 00", "cmp         word ptr [edx],0")
    a.jcc_short("je", "values8_empty")
    a.raw("66 C7 02 " + struct.pack("<H", TUNE_ROWS[ROW_GRAVITY - 1][3]).hex(" "), "mov         word ptr [edx],%s" % _imm(TUNE_ROWS[ROW_GRAVITY - 1][3]))
    a.label("values8_empty")
    a.raw("83 C2 %02X" % OWN_SLOT, "add         edx,%s" % _imm(OWN_SLOT))
    a.raw("49", "dec         ecx")
    a.jcc_short("jne", "values8_slot")
    a.raw("C7 80 %s %s" % (_le(VALUES8_MARK), _le(VALUES8_MAGIC)),
          "mov         dword ptr [eax+%08Xh],%s" % (VALUES8_MARK, _imm(VALUES8_MAGIC)))
    a.label("values8_done")
    # Up to 1.8 there was no "Gegner" ("Tempo" gets its value further down)
    a.raw("81 B8 %s %s" % (_le(OPP_MARK), _le(OPP_MAGIC)),
          "cmp         dword ptr [eax+%08Xh],%s" % (OPP_MARK, _imm(OPP_MAGIC)))
    a.jcc_short("je", "opp_done")
    # ... and the own slots in the "Vorlage" row moved behind the 1.9 presets
    a.raw("8B 88 " + _le(TUNE_LAST), "mov         ecx,dword ptr [eax+%08Xh]" % TUNE_LAST)
    a.raw("83 F9 %02X" % PRESETS_18, "cmp         ecx,%s" % _imm(PRESETS_18))
    a.jcc_short("jb", "opp_last_done")
    a.raw("83 F9 %02X" % (PRESETS_18 + OWN_SLOTS), "cmp         ecx,%s" % _imm(PRESETS_18 + OWN_SLOTS))
    a.jcc_short("jae", "opp_last_done")
    a.raw("83 C1 %02X" % (len(TUNE_PRESETS) - PRESETS_18), "add         ecx,%s" % _imm(len(TUNE_PRESETS) - PRESETS_18))
    a.raw("89 88 " + _le(TUNE_LAST), "mov         dword ptr [eax+%08Xh],ecx" % TUNE_LAST)
    a.label("opp_last_done")
    a.raw("C7 80 %s %s" % (_le(OPP_MARK), _le(OPP_MAGIC)),
          "mov         dword ptr [eax+%08Xh],%s" % (OPP_MARK, _imm(OPP_MAGIC)))
    a.label("opp_done")
    # Up to 1.9 "Gegner" had one row: the second gets its default (a character number was there)
    a.raw("81 B8 %s %s" % (_le(NEW_MARK), _le(NEW_MAGIC)),
          "cmp         dword ptr [eax+%08Xh],%s" % (NEW_MARK, _imm(NEW_MAGIC)))
    a.jcc_short("je", "new_row_done")
    a.raw("C7 80 %s %s" % (_le(NEW_VALUE), _le(NEW_ROW[3])),
          "mov         dword ptr [eax+%08Xh],%s" % (NEW_VALUE, _imm(NEW_ROW[3])))
    a.raw("C7 80 %s %s" % (_le(NEW_MARK), _le(NEW_MAGIC)),
          "mov         dword ptr [eax+%08Xh],%s" % (NEW_MARK, _imm(NEW_MAGIC)))
    a.label("new_row_done")
    # Up to 1.9 "Tempo" was a value of the tuning class: it becomes "Standard" once
    a.raw("81 B8 %s %s" % (_le(STD_MARK), _le(STD_MAGIC)),
          "cmp         dword ptr [eax+%08Xh],%s" % (STD_MARK, _imm(STD_MAGIC)))
    a.jcc_short("je", "std_done")
    a.raw("C7 80 %s %s" % (_le(OPP_VALUE), _le(OPP_STANDARD)),
          "mov         dword ptr [eax+%08Xh],%s" % (OPP_VALUE, _imm(OPP_STANDARD)))
    a.raw("C7 80 %s %s" % (_le(STD_MARK), _le(STD_MAGIC)),
          "mov         dword ptr [eax+%08Xh],%s" % (STD_MARK, _imm(STD_MAGIC)))
    a.label("std_done")
    a.raw("81 B8 %s %s" % (_le(TUNE_MARK), _le(TUNE_MAGIC)),
          "cmp         dword ptr [eax+%08Xh],%s" % (TUNE_MARK, _imm(TUNE_MAGIC)))
    a.jcc_short("je", "tune_defaults_done")
    a.label("tune_reset")                         # eax = GameParameters
    a.raw("C7 80 %s %s" % (_le(TUNE_MARK), _le(TUNE_MAGIC)),
          "mov         dword ptr [eax+%08Xh],%s" % (TUNE_MARK, _imm(TUNE_MAGIC)))
    a.raw("C7 80 %s %s" % (_le(TUNE_LAST), _le(TUNE_PRESET_DEFAULT)),
          "mov         dword ptr [eax+%08Xh],%s" % (TUNE_LAST, _imm(TUNE_PRESET_DEFAULT)))
    a.raw("33 C9", "xor         ecx,ecx")           # the eight values; "Gegner" is not the tuning class's
    a.label("tune_defaults_next")
    disp = tdisp("tune_rows") + 6 & 0xFFFFFFFF
    a.raw("0F B7 94 CD " + _le(disp), "movzx       edx,word ptr [ebp+ecx*8+%08Xh]" % disp)   # the row's default
    a.raw("89 94 88 " + _le(TUNE_VALUES), "mov         dword ptr [eax+ecx*4+%08Xh],edx" % TUNE_VALUES)
    a.raw("41", "inc         ecx")
    a.raw("83 F9 %02X" % PRESET_VALUES, "cmp         ecx,%d" % PRESET_VALUES)
    a.jcc_short("jb", "tune_defaults_next")
    # tracks 5-8 and Meisterschaft 2 are open in the tuning class from the start
    a.raw("83 88 0C FD 00 00 20", "or          dword ptr [eax+0000FD0Ch],20h")
    a.label("tune_defaults_done")
    a.raw("C3", "ret")

    # wsprintf with a format from the text file: [esp+4] = buffer, [esp+8] = text id,
    # [esp+0Ch].. = up to ten arguments (the caller removes them). ebp = tune_T.
    # Clobbers eax, ecx, edx.
    PRINTF_ARGS = 10
    last = 0x28 + 4 * (PRINTF_ARGS - 1)
    a.label("tune_printf")
    a.raw("83 EC 1C", "sub         esp,1Ch")
    get_text("FF 74 24 28", "push        dword ptr [esp+28h]")
    for _ in range(PRINTF_ARGS):                  # the arguments, the last one first
        a.raw("FF 74 24 %02X" % last, "push        dword ptr [esp+%s]" % _imm(last))
    a.raw("50", "push        eax")                # the format
    a.raw("FF 74 24 %02X" % last, "push        dword ptr [esp+%s]" % _imm(last))              # the buffer
    t_call_import(IMP_WSPRINTF)
    a.raw("83 C4 %02X" % (4 * PRINTF_ARGS + 8), "add         esp,%s" % _imm(4 * PRINTF_ARGS + 8))
    a.raw("8B CC", "mov         ecx,esp")
    a.call(STR_DTOR)
    a.raw("83 C4 1C", "add         esp,1Ch")
    a.raw("C3", "ret")

    # Name of an own preset: the one it was given, else "Eigene N".
    # eax = slot, edx = buffer (at least 10h bytes), ebp = tune_T. Clobbers eax, ecx, edx.
    a.label("own_name")
    t_mov("ecx", GP_POINTER)
    a.raw("50", "push        eax")
    a.raw("C1 E0 05", "shl         eax,5")
    a.raw("8D 8C 01 " + _le(OWN_BASE + OWN_NAME), "lea         ecx,[ecx+eax+%08Xh]" % (OWN_BASE + OWN_NAME))
    a.raw("58", "pop         eax")
    a.raw("80 39 00", "cmp         byte ptr [ecx],0")
    a.jcc_short("je", "own_name_default")
    a.raw("6A 10", "push        10h")
    a.raw("51", "push        ecx")
    a.raw("52", "push        edx")
    t_call_import(IMP_LSTRCPYN)
    a.raw("C3", "ret")
    a.label("own_name_default")
    a.raw("40", "inc         eax")
    a.raw("50", "push        eax")
    a.raw("68 " + _le(TXT_OWN_DEFAULT), "push        %s" % _imm(TXT_OWN_DEFAULT))
    a.raw("52", "push        edx")
    a.call("tune_printf")
    a.raw("83 C4 0C", "add         esp,0Ch")
    a.raw("C3", "ret")

    # Where are the eight words of preset eax (built-in, then the own slots)? Returns
    # edi = the address, "equal" if it is an empty own slot. ebx = GameParameters, ebp = tune_T.
    a.label("tune_preset_ptr")
    a.raw("83 F8 %02X" % len(TUNE_PRESETS), "cmp         eax,%s" % _imm(len(TUNE_PRESETS)))
    a.jcc_short("jb", "tune_preset_ptr_builtin")
    a.raw("8B F8", "mov         edi,eax")
    a.raw("C1 E7 05", "shl         edi,5")
    disp = OWN_BASE - len(TUNE_PRESETS) * OWN_SLOT
    a.raw("8D BC 3B " + _le(disp), "lea         edi,[ebx+edi+%08Xh]" % disp)
    a.raw("66 83 7F %02X 00" % OWN_FILLED, "cmp         word ptr [edi+%s],0" % _imm(OWN_FILLED))
    a.raw("C3", "ret")
    a.label("tune_preset_ptr_builtin")
    a.raw("6B F8 %02X" % (2 * PRESET_VALUES), "imul        edi,eax,%s" % _imm(2 * PRESET_VALUES))
    a.raw("8D BC 3D " + _le(tdisp("tune_presets")), "lea         edi,[ebp+edi+%08Xh]" % tdisp("tune_presets"))
    a.raw("C3", "ret")                            # not zero: "not equal"

    # Do the preset at edi and the eight values agree? Returns "equal" if they do.
    # ebx = GameParameters. Clobbers ecx, edx.
    a.label("tune_equal")
    a.raw("33 C9", "xor         ecx,ecx")
    a.label("tune_equal_next")
    a.raw("0F B7 14 4F", "movzx       edx,word ptr [edi+ecx*2]")
    a.raw("3B 94 8B " + _le(TUNE_VALUES), "cmp         edx,dword ptr [ebx+ecx*4+%08Xh]" % TUNE_VALUES)
    a.jcc_short("jne", "tune_equal_done")
    a.raw("41", "inc         ecx")
    a.raw("83 F9 %02X" % PRESET_VALUES, "cmp         ecx,%d" % PRESET_VALUES)
    a.jcc_short("jb", "tune_equal_next")
    a.label("tune_equal_done")                    # (after the last value the count compares "equal")
    a.raw("C3", "ret")

    # The preset at edi into the eight values. ebx = GameParameters. Clobbers eax, ecx.
    a.label("preset_load")
    a.raw("33 C9", "xor         ecx,ecx")
    a.label("preset_load_next")
    a.raw("0F B7 04 4F", "movzx       eax,word ptr [edi+ecx*2]")
    a.raw("89 84 8B " + _le(TUNE_VALUES), "mov         dword ptr [ebx+ecx*4+%08Xh],eax" % TUNE_VALUES)
    a.raw("41", "inc         ecx")
    a.raw("83 F9 %02X" % PRESET_VALUES, "cmp         ecx,%d" % PRESET_VALUES)
    a.jcc_short("jb", "preset_load_next")
    a.raw("C3", "ret")

    # Which preset do the eight values equal? The one copied last if it still does, else the
    # first: built-in ones (0..15), then the filled own slots (16..23).
    # ebx = GameParameters, ebp = tune_T. Returns eax = its number, or -1. Clobbers ecx, edx.
    a.label("tune_match")
    a.raw("57", "push        edi")
    a.raw("8B 83 " + _le(TUNE_LAST), "mov         eax,dword ptr [ebx+%08Xh]" % TUNE_LAST)
    a.raw("83 F8 %02X" % PRESETS_ALL, "cmp         eax,%s" % _imm(PRESETS_ALL))
    a.jcc_short("jae", "tune_match_scan")
    a.call("tune_preset_ptr")
    a.jcc_short("je", "tune_match_scan")
    a.call("tune_equal")
    a.jcc_short("je", "tune_match_done")
    a.label("tune_match_scan")
    a.raw("33 C0", "xor         eax,eax")
    a.label("tune_match_next")
    a.call("tune_preset_ptr")
    a.jcc_short("je", "tune_match_skip")
    a.call("tune_equal")
    a.jcc_short("je", "tune_match_done")
    a.label("tune_match_skip")
    a.raw("40", "inc         eax")
    a.raw("83 F8 %02X" % PRESETS_ALL, "cmp         eax,%s" % _imm(PRESETS_ALL))
    a.jcc_short("jb", "tune_match_next")
    a.raw("83 C8 FF", "or          eax,0FFFFFFFFh")
    a.label("tune_match_done")
    a.raw("5F", "pop         edi")
    a.raw("C3", "ret")

    # Name for the "Vorlage" row: eax = preset number or -1 ("Ungespeichert"), edx = buffer
    # (at least 10h bytes), ebp = tune_T. Clobbers eax, ecx, edx.
    a.label("tune_preset_name")
    a.raw("83 F8 %02X" % len(TUNE_PRESETS), "cmp         eax,%s" % _imm(len(TUNE_PRESETS)))
    a.jcc_short("jae", "tune_preset_name_other")
    a.raw("83 F8 10", "cmp         eax,10h")
    a.jcc_short("jb", "tune_preset_name_text")
    d = (TXT_TUNE_PRESET16 - 16 - TXT_TUNE_PRESET0) & 0xFF    # presets 16..: their own range
    a.raw("83 C0 %02X" % d, "add         eax,%s" % _imm(d - 0x100 & 0xFFFFFFFF))
    a.jmp_short("tune_preset_name_text")
    a.label("tune_preset_name_other")
    a.raw("83 F8 FF", "cmp         eax,0FFFFFFFFh")
    a.jcc_short("jne", "tune_preset_name_own")
    a.raw("B8 " + _le(TXT_TUNE_OWN - TXT_TUNE_PRESET0), "mov         eax,%s" % _imm(TXT_TUNE_OWN - TXT_TUNE_PRESET0))   # -> "Ungespeichert"
    a.label("tune_preset_name_text")
    a.raw("05 " + _le(TXT_TUNE_PRESET0), "add         eax,%s" % _imm(TXT_TUNE_PRESET0))
    a.raw("50", "push        eax")
    a.raw("52", "push        edx")
    a.call("tune_printf")
    a.raw("83 C4 08", "add         esp,8")
    a.raw("C3", "ret")
    a.label("tune_preset_name_own")
    a.raw("83 E8 %02X" % len(TUNE_PRESETS), "sub         eax,%s" % _imm(len(TUNE_PRESETS)))
    a.jmp("own_name")

    # Text of a row: the format from the text file, filled in with the value (rows 1..8) or
    # with the name of the preset that equals the values (row 0, "Vorlage").
    # eax = row, edx = buffer (40h bytes), ebp = tune_T. Clobbers eax, ecx, edx.
    a.label("tune_text")
    a.raw("53", "push        ebx")
    a.raw("56", "push        esi")
    a.raw("57", "push        edi")
    a.raw("8B F8", "mov         edi,eax")
    a.raw("8B F2", "mov         esi,edx")
    t_mov("ebx", GP_POINTER)
    a.raw("85 FF", "test        edi,edi")
    a.jcc_short("jne", "tune_text_value")
    a.raw("83 EC 20", "sub         esp,20h")      # "Vorlage: %s"
    a.call("tune_match")
    a.raw("8B D4", "mov         edx,esp")
    a.call("tune_preset_name")
    a.raw("8B C4", "mov         eax,esp")
    a.raw("50", "push        eax")
    a.raw("68 " + _le(TXT_TUNE_PRESET), "push        %s" % _imm(TXT_TUNE_PRESET))
    a.raw("56", "push        esi")
    a.call("tune_printf")
    a.raw("83 C4 2C", "add         esp,2Ch")
    a.jmp_short("tune_text_done")
    a.label("tune_text_value")
    a.raw("8B 8C BB " + _le(TUNE_VALUES - 4), "mov         ecx,dword ptr [ebx+edi*4+%08Xh]" % (TUNE_VALUES - 4))
    a.raw("83 FF 01", "cmp         edi,1")
    a.jcc_short("jne", "tune_text_percent")
    a.raw("8B C1", "mov         eax,ecx")      # row 1 is in hundredths: "%d.%02d"
    a.raw("99", "cdq")
    a.raw("B9 64 00 00 00", "mov         ecx,64h")
    a.raw("F7 F9", "idiv        eax,ecx")
    a.raw("52", "push        edx")
    a.raw("50", "push        eax")
    a.jmp_short("tune_text_format")
    a.label("tune_text_percent")
    a.raw("6A 00", "push        0")
    a.raw("51", "push        ecx")
    a.label("tune_text_format")
    a.raw("8D 87 " + _le(TXT_TUNE_ROW0 - 1), "lea         eax,[edi+%08Xh]" % (TXT_TUNE_ROW0 - 1))
    a.raw("83 FF %02X" % KART_ROWS, "cmp         edi,%d" % KART_ROWS)
    a.jcc_short("jbe", "tune_text_id")
    disp = TXT_TUNE_ROW8 - ROW_GRAVITY
    a.raw("8D 87 " + _le(disp), "lea         eax,[edi+%08Xh]" % disp)    # row 8: text 233
    a.raw("83 FF %02X" % ROW_GRAVITY, "cmp         edi,%d" % ROW_GRAVITY)
    a.jcc_short("jbe", "tune_text_id")
    a.raw("B8 " + _le(TXT_NEW_ROW), "mov         eax,%s" % _imm(TXT_NEW_ROW))   # row 10
    a.raw("83 FF %02X" % ROW_OPP, "cmp         edi,%d" % ROW_OPP)
    a.jcc_short("ja", "tune_text_id")
    a.raw("B8 " + _le(TXT_OPP_ROW), "mov         eax,%s" % _imm(TXT_OPP_ROW))   # row 9: "Tempo" ...
    a.raw("83 F9 %02X" % (OPP_STANDARD & 0xFF), "cmp         ecx,%s" % _imm(OPP_STANDARD))
    a.jcc_short("jne", "tune_text_id")
    a.raw("B8 " + _le(TXT_OPP_ROW_STD), "mov         eax,%s" % _imm(TXT_OPP_ROW_STD))   # ... or "Standard", its lowest step
    a.label("tune_text_id")
    a.raw("50", "push        eax")
    a.raw("56", "push        esi")
    a.call("tune_printf")
    a.raw("83 C4 10", "add         esp,10h")
    a.label("tune_text_done")
    a.raw("5F", "pop         edi")
    a.raw("5E", "pop         esi")
    a.raw("5B", "pop         ebx")
    a.raw("C3", "ret")

    # Text of the two upper items of the page of own presets: item 0 the slot ("Platz 3:
    # name"), item 1 its values or "(leer)". eax = item, edx = buffer (100h bytes),
    # ebp = tune_T. Clobbers eax, ecx, edx.
    a.label("own_text")
    a.raw("53", "push        ebx")
    a.raw("57", "push        edi")
    a.raw("8B FA", "mov         edi,edx")
    t_mov("ebx", GP_POINTER)
    a.raw("8B 8B " + _le(OWN_CUR), "mov         ecx,dword ptr [ebx+%08Xh]" % OWN_CUR)
    a.raw("83 E1 07", "and         ecx,7")
    a.raw("85 C0", "test        eax,eax")
    a.jcc_short("jne", "own_text_values")
    a.raw("83 EC 20", "sub         esp,20h")
    a.raw("51", "push        ecx")
    a.raw("8B C1", "mov         eax,ecx")
    a.raw("8D 54 24 04", "lea         edx,[esp+4]")
    a.call("own_name")
    a.raw("59", "pop         ecx")
    a.raw("8B C4", "mov         eax,esp")
    a.raw("50", "push        eax")
    a.raw("41", "inc         ecx")
    a.raw("51", "push        ecx")
    a.raw("68 " + _le(TXT_OWN_SLOT), "push        %s" % _imm(TXT_OWN_SLOT))
    a.raw("57", "push        edi")
    a.call("tune_printf")
    a.raw("83 C4 30", "add         esp,30h")
    a.jmp_short("own_text_done")
    a.label("own_text_values")
    a.raw("C1 E1 05", "shl         ecx,5")
    a.raw("8D 94 0B " + _le(OWN_BASE), "lea         edx,[ebx+ecx+%08Xh]" % OWN_BASE)
    a.raw("66 83 7A %02X 00" % OWN_FILLED, "cmp         word ptr [edx+%s],0" % _imm(OWN_FILLED))
    a.jcc_short("jne", "own_text_full")
    a.raw("68 " + _le(TXT_OWN_EMPTY), "push        %s" % _imm(TXT_OWN_EMPTY))
    a.raw("57", "push        edi")
    a.call("tune_printf")
    a.raw("83 C4 08", "add         esp,8")
    a.jmp_short("own_text_done")
    a.label("own_text_full")
    a.raw("8B C7", "mov         eax,edi")
    a.call("values_text")
    a.label("own_text_done")
    a.raw("5F", "pop         edi")
    a.raw("5B", "pop         ebx")
    a.raw("C3", "ret")

    # The values text of an own slot (text 269, grouped "Kart" / "Welt"). edx = the
    # eight values as words, eax = buffer (OWN_VALUES_BUF bytes),
    # ebp = tune_T. Clobbers eax, ecx, edx.
    a.label("values_text")
    a.raw("56", "push        esi")
    a.raw("BE " + _le(TXT_OWN_VALUES), "mov         esi,%s" % _imm(TXT_OWN_VALUES))
    a.call("values_text_id")
    a.raw("5E", "pop         esi")
    a.raw("C3", "ret")
    # The same with the format esi (the pause page's, TXT_PAUSE_VALUES).
    a.label("values_text_id")
    a.raw("57", "push        edi")
    a.raw("8B F8", "mov         edi,eax")
    a.raw("51", "push        ecx")                # (one argument more than the formats take; up to 1.9 "Tempo")
    a.raw("B9 %s" % _le(PRESET_VALUES - 1), "mov         ecx,%d" % (PRESET_VALUES - 1))
    a.label("values_text_push")                   # the percent values, the last one first
    a.raw("0F B7 04 4A", "movzx       eax,word ptr [edx+ecx*2]")
    a.raw("50", "push        eax")
    a.raw("49", "dec         ecx")
    a.jcc_short("jne", "values_text_push")
    a.raw("0F B7 02", "movzx       eax,word ptr [edx]")    # the gearing, in hundredths
    a.raw("B9 64 00 00 00", "mov         ecx,64h")
    a.raw("99", "cdq")
    a.raw("F7 F9", "idiv        eax,ecx")
    a.raw("52", "push        edx")
    a.raw("50", "push        eax")
    a.raw("56", "push        esi")
    a.raw("57", "push        edi")
    a.call("tune_printf")
    n = 4 * (1 + PRESET_VALUES - 1 + 2 + 2)
    a.raw("83 C4 %02X" % n, "add         esp,%s" % _imm(n))
    a.raw("5F", "pop         edi")
    a.raw("C3", "ret")

    # The values of one group of the tuning page: eax = 0 "Kart" (seven values), 1 "Welt";
    # edx = buffer (100h bytes), ebp = tune_T. Clobbers eax, ecx, edx.
    a.label("group_text")
    a.raw("53", "push        ebx")
    a.raw("56", "push        esi")
    a.raw("57", "push        edi")
    a.raw("8B F2", "mov         esi,edx")
    a.raw("8B FC", "mov         edi,esp")
    t_mov("ebx", GP_POINTER)
    a.raw("85 C0", "test        eax,eax")
    a.jcc_short("jne", "group_text_one")
    a.raw("B9 %s" % _le(KART_ROWS - 1), "mov         ecx,%d" % (KART_ROWS - 1))
    a.label("group_text_push")                    # the percent values, the last one first
    a.raw("FF B4 8B " + _le(TUNE_VALUES), "push        dword ptr [ebx+ecx*4+%08Xh]" % TUNE_VALUES)
    a.raw("49", "dec         ecx")
    a.jcc_short("jne", "group_text_push")
    a.raw("8B 83 " + _le(TUNE_VALUES), "mov         eax,dword ptr [ebx+%08Xh]" % TUNE_VALUES)
    a.raw("99", "cdq")
    a.raw("B9 64 00 00 00", "mov         ecx,64h")
    a.raw("F7 F9", "idiv        eax,ecx")
    a.raw("52", "push        edx")
    a.raw("50", "push        eax")
    a.raw("68 " + _le(TXT_GROUP_TEXTS[0]), "push        %s" % _imm(TXT_GROUP_TEXTS[0]))
    a.jmp_short("group_text_print")
    a.label("group_text_one")                     # "Welt": value 8
    off = TUNE_VALUES + 4 * (ROW_GRAVITY - 1)
    a.raw("FF B3 " + _le(off), "push        dword ptr [ebx+%08Xh]" % off)
    a.raw("68 " + _le(TXT_GROUP_TEXTS[1]), "push        %s" % _imm(TXT_GROUP_TEXTS[1]))
    a.label("group_text_print")
    a.raw("56", "push        esi")
    a.call("tune_printf")
    a.raw("8B E7", "mov         esp,edi")
    a.raw("5F", "pop         edi")
    a.raw("5E", "pop         esi")
    a.raw("5B", "pop         ebx")
    a.raw("C3", "ret")

    # The two values of "Gegner" in one line ("Tempo Standard, verbessert 0"), without tags; a
    # save without the marker shows "Standard" and 0, as opp_tempo and the driver take it.
    # edx = buffer (40h bytes), ebp = tune_T. Clobbers eax, ecx, edx.
    a.label("opp_text")
    a.raw("57", "push        edi")
    a.raw("8B FC", "mov         edi,esp")
    t_mov("eax", GP_POINTER)
    a.raw("81 B8 %s %s" % (_le(STD_MARK), _le(STD_MAGIC)),
          "cmp         dword ptr [eax+%08Xh],%s" % (STD_MARK, _imm(STD_MAGIC)))
    a.jcc_short("je", "opp_text_values")
    a.raw("6A 00", "push        0")
    a.jmp_short("opp_text_std")
    a.label("opp_text_values")
    a.raw("FF B0 " + _le(NEW_VALUE), "push        dword ptr [eax+%08Xh]" % NEW_VALUE)
    a.raw("8B 88 " + _le(OPP_VALUE), "mov         ecx,dword ptr [eax+%08Xh]" % OPP_VALUE)
    a.raw("83 F9 %02X" % (OPP_STANDARD & 0xFF), "cmp         ecx,%s" % _imm(OPP_STANDARD))
    a.jcc_short("je", "opp_text_std")
    a.raw("51", "push        ecx")
    a.raw("68 " + _le(TXT_OPP_VALUES), "push        %s" % _imm(TXT_OPP_VALUES))
    a.jmp_short("opp_text_print")
    a.label("opp_text_std")
    a.raw("68 " + _le(TXT_OPP_VALUES_STD), "push        %s" % _imm(TXT_OPP_VALUES_STD))
    a.label("opp_text_print")
    a.raw("52", "push        edx")
    a.call("tune_printf")
    a.raw("8B E7", "mov         esp,edi")
    a.raw("5F", "pop         edi")
    a.raw("C3", "ret")

    # ecx = a std::string, edx = a text: the string gets the text. Clobbers eax, ecx, edx.
    a.label("str_setc")
    a.raw("53", "push        ebx")
    a.raw("8B D9", "mov         ebx,ecx")
    a.raw("83 EC 1C", "sub         esp,1Ch")
    a.raw("52", "push        edx")
    a.raw("8D 4C 24 04", "lea         ecx,[esp+4]")
    a.call(STR_CTOR)
    a.raw("8B C4", "mov         eax,esp")
    a.raw("50", "push        eax")
    a.raw("8B CB", "mov         ecx,ebx")
    a.call(STR_ASSIGN)
    a.raw("8B CC", "mov         ecx,esp")
    a.call(STR_DTOR)
    a.raw("83 C4 1C", "add         esp,1Ch")
    a.raw("5B", "pop         ebx")
    a.raw("C3", "ret")

    # eax = item, edx = a text, esi = menu: the item shows the text. Clobbers eax, ecx, edx.
    a.label("item_setstr")
    a.raw("6B C8 %02X" % MENU_ITEM_SIZE, "imul        ecx,eax,%s" % _imm(MENU_ITEM_SIZE))
    a.raw("03 8E 34 01 00 00", "add         ecx,dword ptr [esi+00000134h]")
    a.raw("83 C1 08", "add         ecx,8")
    a.jmp_short("str_setc")

    # A button with a text from the text file. eax = text id, edx = y, esi = menu.
    a.label("tune_button")
    a.raw("52", "push        edx")
    a.raw("83 EC 1C", "sub         esp,1Ch")
    get_text("50", "push        eax")
    a.raw("FF 74 24 1C", "push        dword ptr [esp+1Ch]")          # y
    a.raw("50", "push        eax")
    a.raw("8B CE", "mov         ecx,esi")
    a.call(ADD_BUTTON)
    a.raw("8B CC", "mov         ecx,esp")
    a.call(STR_DTOR)
    a.raw("83 C4 20", "add         esp,20h")
    a.raw("C3", "ret")

    # The page title from the text file. eax = text id, esi = menu.
    a.label("tune_title")
    a.raw("83 EC 1C", "sub         esp,1Ch")
    get_text("50", "push        eax")
    a.raw("50", "push        eax")
    a.raw("8B CE", "mov         ecx,esi")
    a.call(SET_TITLE)
    a.raw("8B CC", "mov         ecx,esp")
    a.call(STR_DTOR)
    a.raw("83 C4 1C", "add         esp,1Ch")
    a.raw("C3", "ret")

    # In place of the last page builder that Menu::SetPage calls (ecx = menu,
    # [esp+4] = address of the page number; the menu's own page number is still the old
    # one): builds the tuning page, the pages "Kart", "Welt" and "Gegner" and the page of own
    # presets, and adds to the main menu, the name page and the championship page.
    # Any page that is built ends a renaming on the name page.
    def limit_label(y_push_hex, y_push_text, eax_hex, eax_text, routine="tune_limit_text", size=0x100):
        """Adds the "Am Limit" label (an empty text while the values are not am Limit), or the label
        of another text routine (edx = buffer of `size` bytes, eax set by the given instruction).
        esi = menu, ebp = tune_T.
        The y is pushed after the text is made, so it must not be in eax, ecx or edx."""
        a.raw("81 EC " + _le(size), "sub         esp,%s" % _imm(size))
        a.raw("8B D4", "mov         edx,esp")
        a.raw(eax_hex, eax_text)
        a.call(routine)
        a.raw(y_push_hex, y_push_text)
        a.raw("8D 44 24 04", "lea         eax,[esp+4]")
        a.raw("50", "push        eax")
        a.raw("8B CE", "mov         ecx,esi")
        a.call(ADD_LABEL)
        a.raw("81 C4 " + _le(size), "add         esp,%s" % _imm(size))

    def arrow_row(y_push_hex, y_push_text):
        """Adds an arrow item (like "Qualität") with the text at [esp]; the text buffer is 40h
        bytes at [esp], the y is pushed by the given instruction."""
        a.raw(y_push_hex, y_push_text)
        a.raw("8D 44 24 04", "lea         eax,[esp+4]")
        a.raw("50", "push        eax")
        a.raw("8B CE", "mov         ecx,esi")
        a.call(ADD_BUTTON)
        a.raw("C7 00 03 00 00 00", "mov         dword ptr [eax],3")
        a.raw("83 C4 40", "add         esp,40h")

    a.label("page_build")
    a.raw("55", "push        ebp")
    a.call("tune_base")
    t_mov("eax", GP_POINTER)
    a.raw("85 C0", "test        eax,eax")
    a.jcc_short("je", "page_build_flag")
    a.raw("83 A0 %s 00" % _le(OWN_FLAG), "and         dword ptr [eax+%08Xh],0" % OWN_FLAG)
    a.label("page_build_flag")
    a.raw("5D", "pop         ebp")
    a.raw("8B 44 24 04", "mov         eax,dword ptr [esp+4]")
    a.raw("8B 00", "mov         eax,dword ptr [eax]")
    a.raw("85 C0", "test        eax,eax")
    a.jcc_near("je", "main_build")
    a.raw("83 F8 %02X" % PAGE_NAME, "cmp         eax,%s" % _imm(PAGE_NAME))
    a.jcc_near("je", "name_build")
    a.raw("83 F8 %02X" % PAGE_CH, "cmp         eax,%s" % _imm(PAGE_CH))
    a.jcc_near("je", "ch_build")
    a.raw("83 F8 %02X" % PAGE_MODE, "cmp         eax,%s" % _imm(PAGE_MODE))
    a.jcc_near("je", "mode_build")
    a.raw("83 F8 %02X" % PAGE_CHAMP, "cmp         eax,%s" % _imm(PAGE_CHAMP))
    a.jcc_near("je", "champ_build")
    a.raw("83 F8 %02X" % PAGE_OWN, "cmp         eax,%s" % _imm(PAGE_OWN))
    a.jcc_near("je", "own_build")
    for page, _, _ in SUB_PAGES:
        a.raw("83 F8 %02X" % page, "cmp         eax,%s" % _imm(page))
        a.jcc_near("je", "sub_build")
    a.raw("83 F8 %02X" % PAGE_TUNING, "cmp         eax,%s" % _imm(PAGE_TUNING))
    a.jcc_near("jne", PAGE_BUILD_LAST)
    # the tuning page: item 0 "Vorlage" (arrows), then the buttons
    a.raw("60", "pushad")
    a.raw("8B F1", "mov         esi,ecx")
    a.call("tune_base")
    a.raw("8D 8E 30 01 00 00", "lea         ecx,[esi+00000130h]")
    a.call(ITEMS_CLEAR)
    a.call("tune_defaults")
    a.raw("83 EC 40", "sub         esp,40h")
    a.raw("33 C0", "xor         eax,eax")
    a.raw("8B D4", "mov         edx,esp")
    a.call("tune_text")
    arrow_row("68 " + _le(TUNE_Y_PRESET), "push        %s" % _imm(TUNE_Y_PRESET))
    buttons = (TXT_KART_BUTTON, TXT_WORLD_BUTTON, TXT_TUNE_RESET, TXT_OWN_BUTTON, TXT_NEXT, TXT_BACK)
    assert len(buttons) == len(TUNE_Y_BUTTONS) == TUNE_ITEM_BACK
    for text_id, y in zip(buttons, TUNE_Y_BUTTONS):   # items 1..6
        a.raw("B8 " + _le(text_id), "mov         eax,%s" % _imm(text_id))
        a.raw("BA " + _le(y), "mov         edx,%s" % _imm(y))
        a.call("tune_button")
    y = TUNE_Y_LIMIT["tuning"]
    assert TUNE_LIMIT_ITEM["tuning"] == TUNE_ITEM_BACK + 1 and TUNE_ITEM_GROUPS == TUNE_ITEM_BACK + 2
    limit_label("68 " + _le(y), "push        %s" % _imm(y),
               "B8 " + _le(PAGE_TUNING), "mov         eax,%s" % _imm(PAGE_TUNING))   # item 7
    for k, y in enumerate(TUNE_Y_GROUPS):                       # items 8..9: under "Kart", "Welt"
        limit_label("68 " + _le(y), "push        %s" % _imm(y),
                   "B8 " + _le(k), "mov         eax,%s" % _imm(k), "group_text")
    a.raw("B8 " + _le(TXT_TUNE_TITLE), "mov         eax,%s" % _imm(TXT_TUNE_TITLE))
    a.call("tune_title")
    a.raw("C7 86 48 01 00 00 %s" % _le(TUNE_ITEM_NEXT),
          "mov         dword ptr [esi+00000148h],%s" % _imm(TUNE_ITEM_NEXT))   # "Weiter" is selected
    a.raw("61", "popad")
    a.raw("C2 04 00", "ret         4")

    # The championship page, after the game built it (ecx = menu): with the tuning class unlocked
    # the championship row moves to the top and the four track rows to the right column (the
    # picture goes left in champ_rect), and the button "Gegner" (CHAMP_ITEM_OPP) and a label with
    # its two values follow as the last items. The game builds this page in every frame it shows.
    def item_float(item, field, value):           # a float of an item: +24h its x from the middle, +28h its y
        off = MENU_ITEM_SIZE * item + field
        bits = struct.unpack("<I", struct.pack("<f", value))[0]
        a.raw("C7 80 %s %s" % (_le(off), _le(bits)), "mov         dword ptr [eax+%08Xh],%s" % (off, _imm(bits)))

    a.label("champ_build")
    a.raw("51", "push        ecx")
    a.raw("FF 74 24 08", "push        dword ptr [esp+8]")
    a.call(PAGE_BUILD_LAST)
    a.raw("59", "pop         ecx")
    a.raw("60", "pushad")
    a.raw("8B F1", "mov         esi,ecx")
    a.call("tune_base")
    t_mov("ebx", GP_POINTER)
    a.raw("85 DB", "test        ebx,ebx")
    a.jcc_near("je", "champ_build_done")
    a.raw("8B C3", "mov         eax,ebx")
    a.call("unlock_level")
    a.raw("83 F9 05", "cmp         ecx,5")
    a.jcc_near("jl", "champ_build_done")
    a.raw("8B 86 34 01 00 00", "mov         eax,dword ptr [esi+00000134h]")
    a.raw("8B 8E 38 01 00 00", "mov         ecx,dword ptr [esi+00000138h]")
    a.raw("2B C8", "sub         ecx,eax")
    a.raw("81 F9 " + _le(CHAMP_ITEMS * MENU_ITEM_SIZE), "cmp         ecx,%s" % _imm(CHAMP_ITEMS * MENU_ITEM_SIZE))
    a.jcc_near("jne", "champ_build_done")
    item_float(0, 0x28, CHAMP_Y_CHAMP)
    for k, y in enumerate(CHAMP_Y_TRACKS):        # items 1..4
        item_float(k + 1, 0x24, CHAMP_X_TRACKS)
        item_float(k + 1, 0x28, y)
    a.call("tune_defaults")
    a.raw("B8 " + _le(TXT_CHAMP_OPP), "mov         eax,%s" % _imm(TXT_CHAMP_OPP))
    a.raw("BA " + _le(CHAMP_Y_OPP), "mov         edx,%s" % _imm(CHAMP_Y_OPP))
    a.call("tune_button")
    a.raw("81 EC C0 00 00 00", "sub         esp,0C0h")       # +0 the values (40h), +40h the label's text
    a.raw("8B D4", "mov         edx,esp")
    a.call("opp_text")
    a.raw("8B C4", "mov         eax,esp")
    a.raw("50", "push        eax")
    a.raw("68 " + _le(TXT_CHAMP_OPP_VALUES), "push        %s" % _imm(TXT_CHAMP_OPP_VALUES))
    a.raw("8D 44 24 48", "lea         eax,[esp+48h]")
    a.raw("50", "push        eax")
    a.call("tune_printf")
    a.raw("83 C4 0C", "add         esp,0Ch")
    a.raw("68 " + _le(CHAMP_Y_OPP_VALUES), "push        %s" % _imm(CHAMP_Y_OPP_VALUES))
    a.raw("8D 44 24 44", "lea         eax,[esp+44h]")
    a.raw("50", "push        eax")
    a.raw("8B CE", "mov         ecx,esi")
    a.call(ADD_LABEL)
    a.raw("81 C4 C0 00 00 00", "add         esp,0C0h")
    a.label("champ_build_done")
    a.raw("61", "popad")
    a.raw("C2 04 00", "ret         4")

    # In place of the four pushes of the championship page's picture (height, width, y, x; esi =
    # menu): on the left while the page has the button "Gegner", else where the game has it.
    a.label("champ_rect")
    a.raw("8B 86 38 01 00 00", "mov         eax,dword ptr [esi+00000138h]")
    a.raw("2B 86 34 01 00 00", "sub         eax,dword ptr [esi+00000134h]")
    size = (CHAMP_ITEM_OPP + 2) * MENU_ITEM_SIZE
    a.raw("3D " + _le(size), "cmp         eax,%s" % _imm(size))
    a.jcc_short("je", "champ_rect_left")
    for v in reversed(CHAMP_PICTURE_STOCK):
        bits = struct.unpack("<I", struct.pack("<f", v))[0]
        a.raw("68 " + _le(bits), "push        %s" % _imm(bits))
    a.jmp(CHAMP_RECT_BACK)
    a.label("champ_rect_left")
    for v in reversed(CHAMP_PICTURE):
        bits = struct.unpack("<I", struct.pack("<f", v))[0]
        a.raw("68 " + _le(bits), "push        %s" % _imm(bits))
    a.jmp(CHAMP_RECT_BACK)

    # The main menu: the game's page, then the patch version under the buttons. ecx = menu.
    a.label("main_build")
    a.raw("51", "push        ecx")
    a.raw("FF 74 24 08", "push        dword ptr [esp+8]")
    a.call(PAGE_BUILD_LAST)
    a.raw("59", "pop         ecx")
    a.raw("60", "pushad")
    a.raw("8B F1", "mov         esi,ecx")
    a.call("tune_base")
    t_mov("eax", MAIN_PROGRAM)                    # only the main menu itself (a race's overlay menu
    a.raw("85 C0", "test        eax,eax")         # also goes to page 0 when it closes)
    a.jcc_short("je", "main_build_done")
    a.raw("3B 70 04", "cmp         esi,dword ptr [eax+4]")
    a.jcc_short("jne", "main_build_done")
    a.call("ch_disarm")                           # a challenge drawn before ends here
    a.raw("83 EC 1C", "sub         esp,1Ch")
    get_text("68 " + _le(TXT_VERSION), "push        %s" % _imm(TXT_VERSION))
    a.raw("68 " + _le(MAIN_Y_VERSION), "push        %s" % _imm(MAIN_Y_VERSION))
    a.raw("50", "push        eax")
    a.raw("8B CE", "mov         ecx,esi")
    a.call(ADD_LABEL)
    a.raw("8B CC", "mov         ecx,esp")
    a.call(STR_DTOR)
    a.raw("83 C4 1C", "add         esp,1Ch")
    a.label("main_build_done")
    a.raw("61", "popad")
    a.raw("C2 04 00", "ret         4")

    # The name page (highscores, and renaming an own preset): the game's page, then the name typed
    # last goes into the field, the cursor behind it. Renaming puts the slot's name there afterwards.
    a.label("name_build")
    a.raw("51", "push        ecx")
    a.raw("FF 74 24 08", "push        dword ptr [esp+8]")
    a.call(PAGE_BUILD_LAST)
    a.raw("59", "pop         ecx")
    a.raw("60", "pushad")
    a.raw("8B F1", "mov         esi,ecx")
    a.call("tune_base")
    t_mov("ebx", GP_POINTER)
    a.call("name_prefill")
    a.raw("61", "popad")
    a.raw("C2 04 00", "ret         4")

    # The stored name into the name field, cursor at its end (if a name was stored).
    # esi = menu, ebx = GameParameters. Clobbers eax, ecx, edx.
    a.label("name_prefill")
    a.raw("81 BB %s %s" % (_le(NAME_MARK_OFFSET), _le(NAME_MARK)),
          "cmp         dword ptr [ebx+%08Xh],%s" % (NAME_MARK_OFFSET, _imm(NAME_MARK)))
    a.jcc_short("jne", "name_prefill_done")
    a.raw("8D 93 " + _le(NAME_OFFSET), "lea         edx,[ebx+%08Xh]" % NAME_OFFSET)
    a.raw("8D 8E 7C 01 00 00", "lea         ecx,[esi+0000017Ch]")
    a.call("str_setc")
    a.raw("8B 86 90 01 00 00", "mov         eax,dword ptr [esi+00000190h]")
    a.raw("89 86 74 01 00 00", "mov         dword ptr [esi+00000174h],eax")
    a.label("name_prefill_done")
    a.raw("C3", "ret")

    # First row and the row behind the last of a page "Kart" (rows 1..7), "Welt" (8) or
    # "Gegner" (9). ecx = page. Returns ecx, edx (0, 0 for any other page). Keeps eax.
    a.label("sub_rows")
    for page, first, end in SUB_PAGES:
        a.raw("83 F9 %02X" % page, "cmp         ecx,%s" % _imm(page))
        a.jcc_short("jne", "sub_rows_%X" % page)
        a.raw("B9 " + _le(first), "mov         ecx,%s" % _imm(first))
        a.raw("BA " + _le(end), "mov         edx,%s" % _imm(end))
        a.raw("C3", "ret")
        a.label("sub_rows_%X" % page)
    a.raw("33 C9", "xor         ecx,ecx")
    a.raw("33 D2", "xor         edx,edx")
    a.raw("C3", "ret")

    # The pages "Kart", "Welt" and "Gegner": one arrow item per row, then "Zurück", the "Am Limit" line,
    # the explanation of the selected row and the title. eax = the page.
    a.label("sub_build")
    a.raw("60", "pushad")
    a.raw("8B F1", "mov         esi,ecx")
    a.raw("8B D8", "mov         ebx,eax")
    a.call("tune_base")
    a.raw("8D 8E 30 01 00 00", "lea         ecx,[esi+00000130h]")
    a.call(ITEMS_CLEAR)
    a.call("tune_defaults")
    a.raw("8B CB", "mov         ecx,ebx")
    a.call("sub_rows")
    a.raw("8B F9", "mov         edi,ecx")
    a.label("sub_build_row")
    a.raw("83 EC 40", "sub         esp,40h")
    a.raw("8B C7", "mov         eax,edi")
    a.raw("8B D4", "mov         edx,esp")
    a.call("tune_text")
    a.raw("8B CB", "mov         ecx,ebx")      # y of the n-th row of the page
    a.call("sub_rows")
    a.raw("8B C7", "mov         eax,edi")
    a.raw("2B C1", "sub         eax,ecx")
    a.raw("6B C0 %02X" % TUNE_Y_STEP, "imul        eax,eax,%s" % _imm(TUNE_Y_STEP))
    a.raw("05 " + _le(TUNE_Y0), "add         eax,%s" % _imm(TUNE_Y0))
    arrow_row("50", "push        eax")
    a.raw("47", "inc         edi")
    a.raw("8B CB", "mov         ecx,ebx")
    a.call("sub_rows")
    a.raw("3B FA", "cmp         edi,edx")
    a.jcc_short("jb", "sub_build_row")
    a.raw("B8 " + _le(TXT_BACK), "mov         eax,%s" % _imm(TXT_BACK))
    a.raw("BA " + _le(TUNE_Y_BACK), "mov         edx,%s" % _imm(TUNE_Y_BACK))
    a.call("tune_button")
    a.raw("BF " + _le(TUNE_Y_LIMIT["kart"]), "mov         edi,%s" % _imm(TUNE_Y_LIMIT["kart"]))   # (the text routine clobbers eax)
    a.raw("83 FB %02X" % PAGE_KART, "cmp         ebx,%s" % _imm(PAGE_KART))
    a.jcc_short("je", "sub_build_limit")
    a.raw("BF " + _le(TUNE_Y_LIMIT["world"]), "mov         edi,%s" % _imm(TUNE_Y_LIMIT["world"]))
    a.raw("83 FB %02X" % PAGE_WORLD, "cmp         ebx,%s" % _imm(PAGE_WORLD))
    a.jcc_short("je", "sub_build_limit")
    a.raw("BF " + _le(TUNE_Y_LIMIT["opp"]), "mov         edi,%s" % _imm(TUNE_Y_LIMIT["opp"]))
    a.label("sub_build_limit")
    limit_label("57", "push        edi", "8B C3", "mov         eax,ebx")   # behind "Zurück"
    # the explanation of the selected row: empty here, page_update fills it in
    a.raw("BF " + _le(TUNE_Y_INFO["kart"]), "mov         edi,%s" % _imm(TUNE_Y_INFO["kart"]))
    a.raw("83 FB %02X" % PAGE_KART, "cmp         ebx,%s" % _imm(PAGE_KART))
    a.jcc_short("je", "sub_build_info")
    a.raw("BF " + _le(TUNE_Y_INFO["world"]), "mov         edi,%s" % _imm(TUNE_Y_INFO["world"]))
    a.raw("83 FB %02X" % PAGE_WORLD, "cmp         ebx,%s" % _imm(PAGE_WORLD))
    a.jcc_short("je", "sub_build_info")
    a.raw("BF " + _le(TUNE_Y_INFO["opp"]), "mov         edi,%s" % _imm(TUNE_Y_INFO["opp"]))
    a.label("sub_build_info")
    a.raw("6A 00", "push        0")
    a.raw("57", "push        edi")
    a.raw("8D 44 24 04", "lea         eax,[esp+4]")
    a.raw("50", "push        eax")
    a.raw("8B CE", "mov         ecx,esi")
    a.call(ADD_LABEL)
    a.raw("59", "pop         ecx")
    t_mov("eax", GP_POINTER)
    a.raw("83 88 %s FF" % _le(INFO_SHOWN), "or          dword ptr [eax+%08Xh],0FFFFFFFFh" % INFO_SHOWN)
    a.raw("B8 " + _le(TXT_KART_TITLE), "mov         eax,%s" % _imm(TXT_KART_TITLE))
    a.raw("83 FB %02X" % PAGE_KART, "cmp         ebx,%s" % _imm(PAGE_KART))
    a.jcc_short("je", "sub_build_title")
    a.raw("B8 " + _le(TXT_WORLD_TITLE), "mov         eax,%s" % _imm(TXT_WORLD_TITLE))
    a.raw("83 FB %02X" % PAGE_WORLD, "cmp         ebx,%s" % _imm(PAGE_WORLD))
    a.jcc_short("je", "sub_build_title")
    a.raw("B8 " + _le(TXT_OPP_TITLE), "mov         eax,%s" % _imm(TXT_OPP_TITLE))
    a.label("sub_build_title")
    a.call("tune_title")
    a.raw("C7 86 48 01 00 00 00 00 00 00", "mov         dword ptr [esi+00000148h],0")
    a.raw("61", "popad")
    a.raw("C2 04 00", "ret         4")

    # The page of own presets: item 0 the slot (arrows), 1 its values (a label), 2 "Laden",
    # 3 "Speichern", 4 "Umbenennen", 5 "Löschen", 6 "Zurück", 7 the title.
    a.label("own_build")
    a.raw("60", "pushad")
    a.raw("8B F1", "mov         esi,ecx")
    a.call("tune_base")
    a.raw("8D 8E 30 01 00 00", "lea         ecx,[esi+00000130h]")
    a.call(ITEMS_CLEAR)
    a.call("tune_defaults")
    a.raw("81 EC " + _le(OWN_VALUES_BUF), "sub         esp,%s" % _imm(OWN_VALUES_BUF))
    a.raw("33 C0", "xor         eax,eax")
    a.raw("8B D4", "mov         edx,esp")
    a.call("own_text")
    a.raw("68 " + _le(OWN_Y_SLOT), "push        %s" % _imm(OWN_Y_SLOT))
    a.raw("8D 44 24 04", "lea         eax,[esp+4]")
    a.raw("50", "push        eax")
    a.raw("8B CE", "mov         ecx,esi")
    a.call(ADD_BUTTON)
    a.raw("C7 00 03 00 00 00", "mov         dword ptr [eax],3")
    a.raw("B8 01 00 00 00", "mov         eax,1")
    a.raw("8B D4", "mov         edx,esp")
    a.call("own_text")
    a.raw("68 " + _le(OWN_Y_VALUES), "push        %s" % _imm(OWN_Y_VALUES))
    a.raw("8D 44 24 04", "lea         eax,[esp+4]")
    a.raw("50", "push        eax")
    a.raw("8B CE", "mov         ecx,esi")
    a.call(ADD_LABEL)
    a.raw("81 C4 " + _le(OWN_VALUES_BUF), "add         esp,%s" % _imm(OWN_VALUES_BUF))
    for k, y in enumerate(OWN_Y_BUTTONS):         # items 2..5
        a.raw("B8 " + _le(TXT_OWN_LOAD + k), "mov         eax,%s" % _imm(TXT_OWN_LOAD + k))
        a.raw("BA " + _le(y), "mov         edx,%s" % _imm(y))
        a.call("tune_button")
    a.raw("B8 " + _le(TXT_BACK), "mov         eax,%s" % _imm(TXT_BACK))       # item 6
    a.raw("BA " + _le(OWN_Y_BACK), "mov         edx,%s" % _imm(OWN_Y_BACK))
    a.call("tune_button")
    a.raw("B8 " + _le(TXT_OWN_TITLE), "mov         eax,%s" % _imm(TXT_OWN_TITLE))
    a.call("tune_title")
    a.raw("C7 86 48 01 00 00 00 00 00 00", "mov         dword ptr [esi+00000148h],0")
    a.raw("61", "popad")
    a.raw("C2 04 00", "ret         4")

    # The pause page, after the game built it (esi = menu): a line with the class and the 60 FPS
    # switch, in the tuning class with the preset the values match, and then the values. In a
    # race with opponents the two values of "Gegner" follow the top speed, in every class.
    # Stack: +0 class name, +20h "An"/"Aus", +40h preset name, +60h the line (tuning class),
    # +160h the eight values (words in the tuning class, else dwords), +180h the values text
    # (tuning class) or the line with the top speed (the others).
    a.label("pause_info")
    a.raw("C7 86 44 01 00 00 FF FF FF FF", "mov         dword ptr [esi+00000144h],0FFFFFFFFh")   # displaced
    a.raw("60", "pushad")
    a.call("tune_base")
    t_mov("ebx", GP_POINTER)
    a.raw("81 EC 00 03 00 00", "sub         esp,300h")
    a.raw("8B 4B 10", "mov         ecx,dword ptr [ebx+10h]")                     # the class
    a.raw("81 C1 " + _le(TXT_CLASS0), "add         ecx,%s" % _imm(TXT_CLASS0))
    a.raw("51", "push        ecx")
    a.raw("8D 44 24 04", "lea         eax,[esp+4]")
    a.raw("50", "push        eax")
    a.call("tune_printf")
    a.raw("83 C4 08", "add         esp,8")
    a.raw("8B 43 %02X" % PHYS_FLAG_OFFSET, "mov         eax,dword ptr [ebx+%s]" % _imm(PHYS_FLAG_OFFSET))
    a.raw("C1 E8 08", "shr         eax,8")
    a.raw("3D " + _le(PHYS_MAGIC), "cmp         eax,%s" % _imm(PHYS_MAGIC))
    a.raw("0F 94 C0", "sete        al")
    a.raw("0F B6 C0", "movzx       eax,al")
    a.raw("05 " + _le(TXT_PHYS_OFF), "add         eax,%s" % _imm(TXT_PHYS_OFF))
    a.raw("50", "push        eax")
    a.raw("8D 44 24 24", "lea         eax,[esp+24h]")
    a.raw("50", "push        eax")
    a.call("tune_printf")
    a.raw("83 C4 08", "add         esp,8")
    a.raw("83 7B 10 05", "cmp         dword ptr [ebx+10h],5")
    a.jcc_near("jne", "pause_info_plain")
    a.call("tune_match")
    a.raw("8D 54 24 40", "lea         edx,[esp+40h]")
    a.call("tune_preset_name")
    a.raw("8D 44 24 20", "lea         eax,[esp+20h]")                      # "An" / "Aus"
    a.raw("50", "push        eax")
    a.raw("8D 44 24 44", "lea         eax,[esp+44h]")                      # the preset
    a.raw("50", "push        eax")
    a.raw("8D 44 24 08", "lea         eax,[esp+8]")                        # the class
    a.raw("50", "push        eax")
    a.raw("68 " + _le(TXT_PAUSE_TUNING), "push        %s" % _imm(TXT_PAUSE_TUNING))
    a.raw("8D 44 24 70", "lea         eax,[esp+70h]")
    a.raw("50", "push        eax")
    a.call("tune_printf")
    a.raw("83 C4 14", "add         esp,14h")
    a.raw("68 " + _le(PAUSE_Y_HEAD), "push        %s" % _imm(PAUSE_Y_HEAD))
    a.raw("8D 44 24 64", "lea         eax,[esp+64h]")
    a.raw("50", "push        eax")
    a.raw("8B CE", "mov         ecx,esi")
    a.call(ADD_LABEL)
    a.raw("33 C9", "xor         ecx,ecx")
    a.label("pause_info_words")
    a.raw("8B 84 8B " + _le(TUNE_VALUES), "mov         eax,dword ptr [ebx+ecx*4+%08Xh]" % TUNE_VALUES)
    a.raw("66 89 84 4C 60 01 00 00", "mov         word ptr [esp+ecx*2+00000160h],ax")
    a.raw("41", "inc         ecx")
    a.raw("83 F9 %02X" % PRESET_VALUES, "cmp         ecx,%d" % PRESET_VALUES)
    a.jcc_short("jb", "pause_info_words")
    a.raw("8D 94 24 60 01 00 00", "lea         edx,[esp+00000160h]")
    a.raw("8D 84 24 80 01 00 00", "lea         eax,[esp+00000180h]")
    a.raw("56", "push        esi")
    a.raw("BE " + _le(TXT_PAUSE_VALUES), "mov         esi,%s" % _imm(TXT_PAUSE_VALUES))
    a.call("values_text_id")
    a.raw("5E", "pop         esi")
    a.raw("8D BC 24 80 01 00 00", "lea         edi,[esp+00000180h]")
    a.raw("8D 93 " + _le(TUNE_VALUES), "lea         edx,[ebx+%08Xh]" % TUNE_VALUES)
    a.raw("B8 " + _le(TXT_TOP_PAUSE[0]), "mov         eax,%s" % _imm(TXT_TOP_PAUSE[0]))
    a.call("top_text")
    a.raw("B8 " + _le(TXT_PAUSE_OPP[0]), "mov         eax,%s" % _imm(TXT_PAUSE_OPP[0]))
    a.call("pause_opp")
    a.raw("68 " + _le(PAUSE_Y_VALUES), "push        %s" % _imm(PAUSE_Y_VALUES))
    a.raw("8D 84 24 84 01 00 00", "lea         eax,[esp+00000184h]")
    a.raw("50", "push        eax")
    a.raw("8B CE", "mov         ecx,esi")
    a.call(ADD_LABEL)
    a.jmp("pause_info_done")
    a.label("pause_info_plain")
    a.raw("8D 44 24 20", "lea         eax,[esp+20h]")                      # "An" / "Aus"
    a.raw("50", "push        eax")
    a.raw("8D 44 24 04", "lea         eax,[esp+4]")                        # the class
    a.raw("50", "push        eax")
    a.raw("68 " + _le(TXT_PAUSE_PLAIN), "push        %s" % _imm(TXT_PAUSE_PLAIN))
    a.raw("8D 84 24 8C 01 00 00", "lea         eax,[esp+0000018Ch]")
    a.raw("50", "push        eax")
    a.call("tune_printf")
    a.raw("83 C4 10", "add         esp,10h")
    # the top speed of a stock class: the built-in preset of the same number holds its values
    assert all(TUNE_PRESETS[n][1][0] == round(100 * f) for n, f in enumerate((0.9, 1.1, 1.3)))
    assert PRESET_VALUES == 8
    a.raw("8B 4B 10", "mov         ecx,dword ptr [ebx+10h]")
    a.raw("C1 E1 04", "shl         ecx,4")
    t_lea("edx", "tune_presets")
    a.raw("03 D1", "add         edx,ecx")
    a.raw("B9 " + _le(PRESET_VALUES - 1), "mov         ecx,%d" % (PRESET_VALUES - 1))
    a.label("pause_info_class_values")
    a.raw("0F BF 04 4A", "movsx       eax,word ptr [edx+ecx*2]")
    a.raw("89 84 8C 60 01 00 00", "mov         dword ptr [esp+ecx*4+00000160h],eax")
    a.raw("49", "dec         ecx")
    a.jcc_short("jns", "pause_info_class_values")
    a.raw("8D BC 24 80 01 00 00", "lea         edi,[esp+00000180h]")
    a.raw("8D 94 24 60 01 00 00", "lea         edx,[esp+00000160h]")
    a.raw("B8 " + _le(TXT_TOP_PAUSE[1]), "mov         eax,%s" % _imm(TXT_TOP_PAUSE[1]))
    a.call("top_text")
    a.raw("B8 " + _le(TXT_PAUSE_OPP[1]), "mov         eax,%s" % _imm(TXT_PAUSE_OPP[1]))
    a.call("pause_opp")
    a.raw("68 " + _le(PAUSE_Y_HEAD), "push        %s" % _imm(PAUSE_Y_HEAD))
    a.raw("8D 84 24 84 01 00 00", "lea         eax,[esp+00000184h]")
    a.raw("50", "push        eax")
    a.raw("8B CE", "mov         ecx,esi")
    a.call(ADD_LABEL)
    a.label("pause_info_done")
    a.raw("81 C4 00 03 00 00", "add         esp,300h")
    a.raw("61", "popad")
    a.jmp(PAUSE_PAGE_DONE)

    # Appends the two values of "Gegner" to the text at edi, with the format eax (one %s). Not
    # in a time trial (no opponents). ebx = GameParameters, ebp = tune_T. Clobbers eax, ecx, edx.
    a.label("pause_opp")
    a.raw("83 7B 1C 00", "cmp         dword ptr [ebx+1Ch],0")
    a.jcc_short("je", "pause_opp_done")
    a.raw("83 EC 40", "sub         esp,40h")
    a.raw("50", "push        eax")
    a.raw("8D 54 24 04", "lea         edx,[esp+4]")
    a.call("opp_text")
    a.raw("59", "pop         ecx")                # the format
    a.raw("8B C4", "mov         eax,esp")          # its argument
    a.raw("8B D7", "mov         edx,edi")
    a.call("top_text_end")
    a.raw("83 C4 40", "add         esp,40h")
    a.label("pause_opp_done")
    a.raw("C3", "ret")

    # Was the action pressed in this frame? eax = its name. Returns "equal" if it was.
    a.label("tune_pressed")
    a.raw("50", "push        eax")
    a.call(INPUT_GET)
    a.raw("8B C8", "mov         ecx,eax")
    a.call(INPUT_READ)
    a.raw("D9 EE", "fldz")
    a.raw("DA E9", "fucompp")
    a.raw("DF E0", "fnstsw      ax")
    a.raw("F6 C4 40", "test        ah,40h")       # C3: the value is zero, not pressed
    a.raw("C3", "ret")

    # Is the set of values "am Limit"? ebx = GameParameters, ebp = tune_T. Returns eax = the text
    # id of the line (TXT_LIMIT, TXT_LIMIT_LOW or TXT_LIMIT_OVER), ecx = risk, edx = challenge. Adds up the points of every channel from tune_limit_tab (one entry of
    # len(LIMIT_CHANNELS) signed bytes per grid step of a row, the row's block found through
    # tune_limit_rows: word last step, word offset), then the pairs; see LIMIT_POINTS. Clobbers ecx, edx.
    NCH = len(LIMIT_CHANNELS)

    def esp_ref(c):
        return "[esp]" if c == 0 else "[esp+%s]" % _imm(4 * c)

    def esp_modrm(reg, c):             # ModRM (+SIB, disp8) of [esp+4c] with the given reg field
        return ("%02X 24" % (0x04 | reg << 3)) if c == 0 else ("%02X 24 %02X" % (0x44 | reg << 3, 4 * c))
    a.label("tune_limit")
    a.raw("56", "push        esi")
    a.raw("57", "push        edi")
    a.raw("83 EC %02X" % (4 * NCH), "sub         esp,%s" % _imm(4 * NCH))
    a.raw("33 C0", "xor         eax,eax")
    for c in range(NCH):
        a.raw("89 " + esp_modrm(0, c), "mov         dword ptr %s,eax" % esp_ref(c))
    a.raw("33 FF", "xor         edi,edi")                            # the row
    a.label("tune_limit_row")
    t_lea("esi", "tune_rows")
    a.raw("0F BF 04 FE", "movsx       eax,word ptr [esi+edi*8]")     # minimum
    a.raw("8B 8C BB " + _le(TUNE_VALUES), "mov         ecx,dword ptr [ebx+edi*4+%08Xh]" % TUNE_VALUES)
    a.raw("2B C8", "sub         ecx,eax")
    a.jcc_short("jge", "tune_limit_pos")
    a.raw("33 C9", "xor         ecx,ecx")
    a.label("tune_limit_pos")
    a.raw("8B C1", "mov         eax,ecx")
    a.raw("99", "cdq")
    a.raw("0F BF 4C FE 04", "movsx       ecx,word ptr [esi+edi*8+4]")   # step
    a.raw("F7 F9", "idiv        eax,ecx")
    t_lea("esi", "tune_limit_rows")
    a.raw("0F B7 0C BE", "movzx       ecx,word ptr [esi+edi*4]")     # the row's last step
    a.raw("3B C1", "cmp         eax,ecx")
    a.jcc_short("jle", "tune_limit_step")
    a.raw("8B C1", "mov         eax,ecx")
    a.label("tune_limit_step")
    a.raw("6B C0 %02X" % NCH, "imul        eax,eax,%s" % _imm(NCH))
    a.raw("0F B7 4C BE 02", "movzx       ecx,word ptr [esi+edi*4+2]")   # the row's block
    a.raw("03 C1", "add         eax,ecx")
    t_lea("esi", "tune_limit_tab")
    a.raw("03 F0", "add         esi,eax")
    for c in range(NCH):
        if c:
            a.raw("0F BE 46 %02X" % c, "movsx       eax,byte ptr [esi+%s]" % _imm(c))
        else:
            a.raw("0F BE 06", "movsx       eax,byte ptr [esi]")
        a.raw("01 " + esp_modrm(0, c), "add         dword ptr %s,eax" % esp_ref(c))
    a.raw("47", "inc         edi")
    a.raw("83 FF %02X" % PRESET_VALUES, "cmp         edi,%s" % _imm(PRESET_VALUES))
    a.jcc_short("jl", "tune_limit_row")
    for n, (pa, pb, shift) in enumerate(LIMIT_PAIRS):
        ca, cb = LIMIT_CHANNELS.index(pa), LIMIT_CHANNELS.index(pb)
        a.raw("8B " + esp_modrm(0, ca), "mov         eax,dword ptr %s" % esp_ref(ca))
        a.raw("85 C0", "test        eax,eax")
        a.jcc_short("jle", "tune_limit_pair%d" % n)
        a.raw("8B " + esp_modrm(1, cb), "mov         ecx,dword ptr %s" % esp_ref(cb))   # may be negative
        a.raw("0F AF C1", "imul        eax,ecx")
        a.raw("C1 F8 %02X" % shift, "sar         eax,%s" % _imm(shift))
        a.raw("01 04 24", "add         dword ptr [esp],eax")
        a.label("tune_limit_pair%d" % n)
    assert LIMIT_CHANNELS[:2] == ("risk", "push")
    assert all(-128 <= x <= 127 for x in (LIMIT_PUSH_MIN, LIMIT_RISK_HARD, LIMIT_RISK_MAX))
    a.raw("8B 0C 24", "mov         ecx,dword ptr [esp]")
    a.raw("8B 54 24 04", "mov         edx,dword ptr [esp+4]")
    a.raw("B8 " + _le(TXT_LIMIT_OVER), "mov         eax,%s" % _imm(TXT_LIMIT_OVER))
    a.raw("83 F9 %02X" % (LIMIT_RISK_MAX & 0xFF), "cmp         ecx,%s" % _imm(LIMIT_RISK_MAX))
    a.jcc_short("jge", "tune_limit_done")
    a.raw("B8 " + _le(TXT_LIMIT_LOW), "mov         eax,%s" % _imm(TXT_LIMIT_LOW))
    a.raw("83 FA %02X" % (LIMIT_PUSH_MIN & 0xFF), "cmp         edx,%s" % _imm(LIMIT_PUSH_MIN))
    a.jcc_short("jl", "tune_limit_done")
    a.raw("B8 " + _le(TXT_LIMIT[0]), "mov         eax,%s" % _imm(TXT_LIMIT[0]))
    a.raw("83 F9 %02X" % (LIMIT_RISK_HARD & 0xFF), "cmp         ecx,%s" % _imm(LIMIT_RISK_HARD))
    a.jcc_short("jl", "tune_limit_done")
    a.raw("B8 " + _le(TXT_LIMIT[1]), "mov         eax,%s" % _imm(TXT_LIMIT[1]))
    a.label("tune_limit_done")
    a.raw("83 C4 %02X" % (4 * NCH), "add         esp,%s" % _imm(4 * NCH))
    a.raw("5F", "pop         edi")
    a.raw("5E", "pop         esi")
    a.raw("C3", "ret")

    # The "Am Limit" line's text (the same on the tuning pages, empty on "Gegner") with the
    # challenge and risk points (shown from 0 up). eax = the page, edx = buffer (100h bytes),
    # ebp = tune_T. Clobbers eax, ecx, edx.
    a.label("tune_limit_text")
    a.raw("83 F8 %02X" % PAGE_OPP, "cmp         eax,%s" % _imm(PAGE_OPP))
    a.jcc_short("jne", "tune_limit_text_go")
    a.raw("C6 02 00", "mov         byte ptr [edx],0")
    a.raw("C3", "ret")
    a.label("tune_limit_text_go")
    a.raw("53", "push        ebx")
    a.raw("56", "push        esi")
    a.raw("8B F2", "mov         esi,edx")
    t_mov("ebx", GP_POINTER)
    a.call("tune_limit")
    a.raw("85 C9", "test        ecx,ecx")
    a.jcc_short("jge", "tune_limit_text_risk")
    a.raw("33 C9", "xor         ecx,ecx")
    a.label("tune_limit_text_risk")
    a.raw("85 D2", "test        edx,edx")
    a.jcc_short("jge", "tune_limit_text_push")
    a.raw("33 D2", "xor         edx,edx")
    a.label("tune_limit_text_push")
    a.raw("51", "push        ecx")
    a.raw("52", "push        edx")
    a.raw("50", "push        eax")
    a.raw("56", "push        esi")
    a.call("tune_printf")
    a.raw("83 C4 10", "add         esp,10h")
    a.raw("57", "push        edi")
    a.raw("8B FE", "mov         edi,esi")
    a.raw("8D 93 " + _le(TUNE_VALUES), "lea         edx,[ebx+%08Xh]" % TUNE_VALUES)
    a.raw("B8 " + _le(TXT_TOP), "mov         eax,%s" % _imm(TXT_TOP))
    a.call("top_text")
    a.raw("5F", "pop         edi")
    a.raw("5E", "pop         esi")
    a.raw("5B", "pop         ebx")
    a.raw("C3", "ret")

    # Appends the top speed to a text: eax = text id of the format (one %d, km/h), edx = the
    # values (dwords, as at GameParameters+TUNE_VALUES), edi = the text, ebx = GameParameters,
    # ebp = tune_T. Clobbers eax, ecx, edx.
    a.label("top_text")
    a.raw("50", "push        eax")
    a.call("tune_top")
    a.raw("59", "pop         ecx")
    a.raw("8B D7", "mov         edx,edi")
    a.label("top_text_end")
    a.raw("80 3A 00", "cmp         byte ptr [edx],0")
    a.jcc_short("je", "top_text_print")
    a.raw("42", "inc         edx")
    a.jmp_short("top_text_end")
    a.label("top_text_print")
    a.raw("50", "push        eax")
    a.raw("51", "push        ecx")
    a.raw("52", "push        edx")
    a.call("tune_printf")
    a.raw("83 C4 0C", "add         esp,0Ch")
    a.raw("C3", "ret")

    # Top speed in km/h of a set of values for player 1's character; the model and its numbers
    # are at TOP_CHARS, top_speed() is the same in Python. edx = the values (dwords), ebx =
    # GameParameters, ebp = tune_T. Returns eax. Clobbers ecx, edx.
    # Locals: +4 Gewicht, +8 mass, +0Ch rpm per unit/s, +10h high and +14h low end of the
    # bisection, +18h drive per torque, +1Ch largest drive, +20h speed limit of the downforce,
    # +24h load above the chassis' limit at speed 0, +28h rubbing, +2Ch speed, +30h scratch.
    def c_disp(name):
        return tdisp("top_consts") + 4 * TOP_CONSTS.index(name) & 0xFFFFFFFF

    def fc(op, name):                            # x87 op with a constant of top_consts
        modrm = {"fld": ("D9", 0x85), "fmul": ("D8", 0x8D), "fadd": ("D8", 0x85), "fsub": ("D8", 0xA5),
                 "fsubr": ("D8", 0xAD), "fdivr": ("D8", 0xBD), "fcom": ("D8", 0x95)}[op]
        d = c_disp(name)
        a.raw("%s %02X %s" % (modrm[0], modrm[1], _le(d)), "%-11s dword ptr [ebp+%08Xh]" % (op, d))

    def fl(op, off):                             # x87 op with a local [esp+off]
        modrm = {"fld": ("D9", 0x44), "fstp": ("D9", 0x5C), "fst": ("D9", 0x54), "fmul": ("D8", 0x4C),
                 "fadd": ("D8", 0x44), "fdiv": ("D8", 0x74), "fcom": ("D8", 0x54)}[op]
        a.raw("%s %02X 24 %02X" % (modrm[0], modrm[1], off), "%-11s dword ptr [esp+%s]" % (op, _imm(off)))

    def fmin(kind, ref, label):                  # st0 = min(st0, operand)
        (fc if kind == "c" else fl)("fcom", ref)
        a.raw("DF E0", "fnstsw      ax")
        a.raw("F6 C4 41", "test        ah,41h")
        a.jcc_short("jne", label)                # not above it (or not a number): keep
        a.raw("DD D8", "fstp        st(0)")
        (fc if kind == "c" else fl)("fld", ref)
        a.label(label)

    chars = tdisp("top_chars")
    a.label("tune_top")
    a.raw("83 EC 34", "sub         esp,34h")
    a.raw("DB 42 0C", "fild        dword ptr [edx+0Ch]")         # Gewicht
    fc("fmul", "hundredth")
    fl("fstp", 0x04)
    a.raw("8B 4B 58", "mov         ecx,dword ptr [ebx+58h]")      # player 1's character
    a.raw("83 F9 %02X" % (len(TOP_CHARS) - 1), "cmp         ecx,%d" % (len(TOP_CHARS) - 1))
    a.jcc_short("jbe", "tune_top_char")
    a.raw("33 C9", "xor         ecx,ecx")
    a.label("tune_top_char")
    a.raw("D9 84 CD " + _le(chars), "fld         dword ptr [ebp+ecx*8+%08Xh]" % chars)   # its mass
    fl("fmul", 0x04)
    fl("fstp", 0x08)
    a.raw("DB 02", "fild        dword ptr [edx]")             # Übersetzung
    fc("fmul", "hundredth")
    fl("fstp", 0x30)
    a.raw("D9 84 CD " + _le(chars + 4), "fld         dword ptr [ebp+ecx*8+%08Xh]" % (chars + 4))   # its k
    fl("fdiv", 0x30)
    fl("fst", 0x0C)
    fc("fdivr", "rpm_max")
    fl("fstp", 0x10)
    a.raw("D9 EE", "fldz")
    fl("fstp", 0x14)
    a.raw("DB 42 04", "fild        dword ptr [edx+4]")           # Motorkraft
    fc("fmul", "hundredth")
    a.raw("D9 C0", "fld         st(0)")
    a.raw("D8 8C CD " + _le(chars + 4), "fmul        dword ptr [ebp+ecx*8+%08Xh]" % (chars + 4))
    fc("fmul", "drive")
    fl("fstp", 0x18)
    fc("fmul", "traction")
    fmin("c", "drive_max", "tune_top_drive_max")
    fl("fstp", 0x1C)
    fc("fld", "no_limit")
    a.raw("83 7A 18 00", "cmp         dword ptr [edx+18h],0")      # Anpressdruck
    a.jcc_short("jle", "tune_top_vcl")
    a.raw("DD D8", "fstp        st(0)")
    a.raw("DB 42 0C", "fild        dword ptr [edx+0Ch]")
    a.raw("DA 72 18", "fidiv       dword ptr [edx+18h]")
    a.raw("D9 FA", "fsqrt")
    fc("fmul", "downforce_speed")
    a.label("tune_top_vcl")
    fl("fstp", 0x20)
    a.raw("DB 42 1C", "fild        dword ptr [edx+1Ch]")         # Schwerkraft
    fc("fmul", "hundredth")
    fl("fst", 0x30)
    fc("fmul", "load_g")
    fc("fsub", "cap")
    fc("fmul", "gravity")
    fl("fmul", 0x08)
    fl("fstp", 0x24)
    fl("fld", 0x30)
    fl("fmul", 0x08)
    fc("fmul", "rub_g")
    fc("fld", "rub_light")
    fl("fdiv", 0x04)
    a.raw("DE C1", "faddp       st(1),st")
    fc("fadd", "rub")
    fl("fstp", 0x28)
    a.raw("DB 42 18", "fild        dword ptr [edx+18h]")
    fc("fmul", "downforce")
    fl("fstp", 0x30)
    a.raw("B9 " + _le(TOP_STEPS), "mov         ecx,%s" % _imm(TOP_STEPS))
    a.label("tune_top_step")
    fl("fld", 0x14)
    fl("fadd", 0x10)
    fc("fmul", "half")
    fl("fst", 0x2C)
    fl("fmul", 0x0C)                                             # engine speed
    fc("fcom", "rpm_mid")
    a.raw("DF E0", "fnstsw      ax")
    a.raw("F6 C4 01", "test        ah,1")
    a.jcc_short("je", "tune_top_high")
    fc("fmul", "torque_slope1")
    fc("fsubr", "torque_at0")
    a.jmp_short("tune_top_drive")
    a.label("tune_top_high")
    fc("fmul", "torque_slope2")
    fc("fsubr", "torque_at0_2")
    a.label("tune_top_drive")
    fl("fmul", 0x18)
    fmin("l", 0x1C, "tune_top_drive_cap")                        # st0 = drive
    fl("fld", 0x2C)
    fmin("l", 0x20, "tune_top_vd")
    a.raw("D8 C8", "fmul        st,st(0)")
    fl("fmul", 0x30)
    fl("fadd", 0x24)                                             # load above the limit
    a.raw("D9 E4", "ftst")
    a.raw("DF E0", "fnstsw      ax")
    a.raw("F6 C4 41", "test        ah,41h")
    a.jcc_short("je", "tune_top_rub")
    a.raw("DD D8", "fstp        st(0)")
    a.raw("D9 EE", "fldz")
    a.jmp_short("tune_top_air")
    a.label("tune_top_rub")
    fc("fmul", "rub_load")
    fl("fadd", 0x28)
    a.label("tune_top_air")
    fl("fld", 0x2C)
    a.raw("D8 C8", "fmul        st,st(0)")
    fc("fmul", "air")
    a.raw("DE C1", "faddp       st(1),st")                       # st0 = resistance, st1 = drive
    a.raw("DE D9", "fcompp")
    a.raw("DF E0", "fnstsw      ax")
    a.raw("8B 54 24 2C", "mov         edx,dword ptr [esp+2Ch]")
    a.raw("F6 C4 01", "test        ah,1")
    a.jcc_short("je", "tune_top_slower")
    a.raw("89 54 24 14", "mov         dword ptr [esp+14h],edx")   # faster than this speed
    a.jmp_short("tune_top_next")
    a.label("tune_top_slower")
    a.raw("89 54 24 10", "mov         dword ptr [esp+10h],edx")
    a.label("tune_top_next")
    a.raw("49", "dec         ecx")
    a.jcc_near("jne", "tune_top_step")
    fl("fld", 0x14)
    fc("fmul", "kmh")
    a.raw("DB 5C 24 30", "fistp       dword ptr [esp+30h]")
    a.raw("8B 44 24 30", "mov         eax,dword ptr [esp+30h]")
    a.raw("83 C4 34", "add         esp,34h")
    a.raw("C3", "ret")

    # The speed in the race, below "Runde" / "Position" (see HUD_SPEED_HOOK); esi = the Hud.
    # Stack: +0 scratch, +4 the y, +8 the text (100h bytes); the caller's frame starts at +128h.
    frame = 0x108 + 0x20
    a.label("hud_speed")
    a.raw("60", "pushad")
    a.call("tune_base")
    a.raw("81 EC 08 01 00 00", "sub         esp,108h")
    t_mov("eax", CAR_MANAGER)
    a.raw("85 C0", "test        eax,eax")
    a.jcc_near("je", "hud_speed_done")
    a.raw("8B 4E 04", "mov         ecx,dword ptr [esi+4]")
    a.raw("8B 50 10", "mov         edx,dword ptr [eax+10h]")
    a.raw("8B 40 14", "mov         eax,dword ptr [eax+14h]")
    a.raw("2B C2", "sub         eax,edx")
    a.raw("C1 F8 02", "sar         eax,2")
    a.raw("3B C8", "cmp         ecx,eax")
    a.jcc_near("jae", "hud_speed_done")
    a.raw("8B 14 8A", "mov         edx,dword ptr [edx+ecx*4]")
    a.raw("85 D2", "test        edx,edx")
    a.jcc_near("je", "hud_speed_done")
    for k in range(3):
        off = CAR_VELOCITY + 4 * k
        a.raw("D9 82 " + _le(off), "fld         dword ptr [edx+%08Xh]" % off)
        a.raw("D8 C8", "fmul        st,st(0)")
        if k:
            a.raw("DE C1", "faddp       st(1),st")
    a.raw("D9 FA", "fsqrt")
    fc("fmul", "kmh")
    a.raw("DB 1C 24", "fistp       dword ptr [esp]")
    a.raw("FF 34 24", "push        dword ptr [esp]")
    a.raw("68 " + _le(TXT_SPEED), "push        %s" % _imm(TXT_SPEED))
    a.raw("8D 44 24 10", "lea         eax,[esp+10h]")
    a.raw("50", "push        eax")
    a.call("tune_printf")
    a.raw("83 C4 0C", "add         esp,0Ch")
    a.call(HUD_GAME_MODE)
    a.raw("33 C9", "xor         ecx,ecx")
    a.raw("83 78 1C 00", "cmp         dword ptr [eax+1Ch],0")
    a.raw("0F 95 C1", "setne       cl")
    a.raw("D9 84 24 " + _le(frame + 0x10), "fld         dword ptr [esp+%08Xh]" % (frame + 0x10))   # the y scale
    ydisp = tdisp("hud_speed_y")
    a.raw("D8 8C 8D " + _le(ydisp), "fmul        dword ptr [ebp+ecx*4+%08Xh]" % ydisp)
    a.raw("D9 5C 24 04", "fstp        dword ptr [esp+4]")
    a.raw("FF 74 24 04", "push        dword ptr [esp+4]")
    a.raw("FF B4 24 " + _le(frame + 0x20 + 4), "push        dword ptr [esp+%08Xh]" % (frame + 0x20 + 4))   # the x of "Runde"
    a.raw("8D 44 24 10", "lea         eax,[esp+10h]")
    a.raw("50", "push        eax")
    a.call(HUD_FONT)
    a.raw("8B C8", "mov         ecx,eax")
    a.call(HUD_DRAW_TEXT)
    a.label("hud_speed_done")
    a.raw("81 C4 08 01 00 00", "add         esp,108h")
    a.raw("61", "popad")
    a.raw("57", "push        edi")                       # displaced
    a.raw("8D 4C 24 28", "lea         ecx,[esp+28h]")
    a.jmp(HUD_SPEED_BACK)

    # -- challenges (see CH_DATA) ---------------------------------------------
    # x87 or plain ops on [ebp+disp] (ebp = tune_T): op = opcode hex, r = ModRM reg field.
    def t_mem(op, r, target, text):
        disp = tdisp(target)
        a.raw("%s %02X %s" % (op, 0x85 | r << 3, _le(disp)), text % ("[ebp+%08Xh]" % disp))

    def t_active():                      # flags: equal = no challenge
        disp = tdisp(CH_ACTIVE)
        a.raw("83 BD %s 00" % _le(disp), "cmp         dword ptr [ebp+%08Xh],0" % disp)

    def fpu_flags(mask):                 # after an x87 compare: test the C0 (1) / C3 (40h) bits
        a.raw("DF E0", "fnstsw      ax")
        a.raw("F6 C4 %02X" % mask, "test        ah,%s" % _imm(mask))

    # Race start, the grid (fn 0x4061E0): eax = LevelSettings; the value goes to [esp+18h].
    a.label("ch_grid")
    a.raw("55", "push        ebp")
    a.raw("51", "push        ecx")
    a.call("tune_base")
    t_active()
    a.jcc_short("je", "ch_grid_stock")
    t_mem("8B", 0, CH_START, "mov         eax,dword ptr %s")
    t_mem("89", 0, CH_LAST, "mov         dword ptr %s,eax")
    a.raw("33 C9", "xor         ecx,ecx")
    t_mem("89", 1, CH_DONE, "mov         dword ptr %s,ecx")
    t_mem("D9", 0, CH_LEN, "fld         dword ptr %s")
    a.raw("D9 C0", "fld         st(0)")
    t_mem("D8", 4, "ch_band", "fsub        dword ptr %s")
    t_mem("D9", 3, CH_LO, "fstp        dword ptr %s")
    t_mem("D8", 0, "ch_band", "fadd        dword ptr %s")
    t_mem("D9", 3, CH_HI, "fstp        dword ptr %s")
    a.jmp_short("ch_grid_store")
    a.label("ch_grid_stock")
    a.raw("8B 40 50", "mov         eax,dword ptr [eax+50h]")   # displaced: "start spline offset"
    a.label("ch_grid_store")
    a.raw("59", "pop         ecx")
    a.raw("5D", "pop         ebp")
    a.raw("89 44 24 18", "mov         dword ptr [esp+18h],eax")
    a.jmp(CH_GRID_BACK)

    # Race update, per car in car state 2 (fn 0x4067B0): esi = car, ebx = its index; eax, ecx,
    # edx are free. Stock: finished at 3 laps. Challenge: car 0 sums its progress steps (each
    # taken into -0.5..0.5, so the wrap at 0 and set-backs count right) and is through at "length".
    a.label("ch_finish")
    a.raw("55", "push        ebp")
    a.call("tune_base")
    t_active()
    a.jcc_short("je", "ch_finish_stock")
    a.raw("85 DB", "test        ebx,ebx")
    a.jcc_short("jne", "ch_finish_not")
    a.raw("D9 86 24 02 00 00", "fld         dword ptr [esi+00000224h]")
    a.raw("D9 C0", "fld         st(0)")
    t_mem("D8", 4, CH_LAST, "fsub        dword ptr %s")
    a.raw("D9 C9", "fxch        st(1)")
    t_mem("D9", 3, CH_LAST, "fstp        dword ptr %s")
    t_mem("D8", 2, "ch_half", "fcom        dword ptr %s")
    fpu_flags(0x41)
    a.jcc_short("jne", "ch_finish_up")           # step <= 0.5
    t_mem("D8", 4, "ch_one", "fsub        dword ptr %s")
    a.label("ch_finish_up")
    t_mem("D8", 2, "ch_mhalf", "fcom        dword ptr %s")
    fpu_flags(0x01)
    a.jcc_short("je", "ch_finish_sum")           # step >= -0.5
    t_mem("D8", 0, "ch_one", "fadd        dword ptr %s")
    a.label("ch_finish_sum")
    t_mem("D8", 0, CH_DONE, "fadd        dword ptr %s")
    t_mem("D9", 2, CH_DONE, "fst         dword ptr %s")
    t_mem("D8", 3, CH_LEN, "fcomp       dword ptr %s")
    fpu_flags(0x01)
    a.jcc_short("jne", "ch_finish_not")          # done < length
    # the time: the game sums the three lap times (fn 0x4378D0), and a challenge counts no lap,
    # so its lap timer becomes lap 1
    a.raw("8B 86 50 02 00 00", "mov         eax,dword ptr [esi+00000250h]")
    a.raw("89 86 58 02 00 00", "mov         dword ptr [esi+00000258h],eax")
    a.raw("33 C0", "xor         eax,eax")
    a.raw("89 86 5C 02 00 00", "mov         dword ptr [esi+0000025Ch],eax")
    a.raw("89 86 60 02 00 00", "mov         dword ptr [esi+00000260h],eax")
    a.raw("5D", "pop         ebp")
    a.jmp(CH_FINISH_GO)
    a.label("ch_finish_not")
    a.raw("5D", "pop         ebp")
    a.jmp(CH_FINISH_NOT)
    a.label("ch_finish_stock")
    a.raw("5D", "pop         ebp")
    a.raw("83 BE 64 02 00 00 03", "cmp         dword ptr [esi+00000264h],3")   # displaced
    a.jcc_near("jl", CH_FINISH_NOT)
    a.jmp(CH_FINISH_GO)

    # Hud::Draw, the lap line: text 100 or, in a challenge, TXT_CH_LEFT. edx = the string, eax =
    # the font, ecx free.
    a.label("ch_lapid")
    a.raw("55", "push        ebp")
    a.call("tune_base")
    t_active()
    a.raw("5D", "pop         ebp")
    a.jcc_short("jne", "ch_lapid_ch")
    a.raw("6A 64", "push        64h")                # displaced
    a.jmp_short("ch_lapid_rest")
    a.label("ch_lapid_ch")
    a.raw("6A %02X" % TXT_CH_LEFT, "push        %s" % _imm(TXT_CH_LEFT))
    a.label("ch_lapid_rest")
    a.raw("52", "push        edx")                   # displaced
    a.raw("89 78 34", "mov         dword ptr [eax+34h],edi")
    a.jmp(CH_LAPID_BACK)

    # ... and its number: the lap, or (length - done) * path length in metres (1 unit = 1 m).
    # ecx = the player, eax = the text: both kept.
    a.label("ch_lapnum")
    a.raw("8B 54 8E 20", "mov         edx,dword ptr [esi+ecx*4+20h]")   # displaced
    a.raw("42", "inc         edx")
    a.raw("55", "push        ebp")
    a.call("tune_base")
    t_active()
    a.jcc_short("je", "ch_lapnum_done")
    a.raw("50", "push        eax")
    a.raw("51", "push        ecx")
    t_mov("eax", CAR_MANAGER)
    a.raw("33 D2", "xor         edx,edx")
    a.raw("85 C0", "test        eax,eax")
    a.jcc_short("je", "ch_lapnum_pop")
    a.raw("8B 48 1C", "mov         ecx,dword ptr [eax+1Ch]")
    a.call(PATH_LENGTH)
    t_mem("D9", 0, CH_LEN, "fld         dword ptr %s")
    t_mem("D8", 4, CH_DONE, "fsub        dword ptr %s")
    a.raw("DE C9", "fmulp       st(1),st")
    a.raw("52", "push        edx")
    a.raw("DB 1C 24", "fistp       dword ptr [esp]")
    a.raw("5A", "pop         edx")
    a.raw("85 D2", "test        edx,edx")
    a.jcc_short("jge", "ch_lapnum_store")
    a.raw("33 D2", "xor         edx,edx")
    a.label("ch_lapnum_store")
    t_mem("89", 2, CH_METRES, "mov         dword ptr %s,edx")      # for the tests
    a.label("ch_lapnum_pop")
    a.raw("59", "pop         ecx")
    a.raw("58", "pop         eax")
    a.label("ch_lapnum_done")
    a.raw("5D", "pop         ebp")
    a.jmp(CH_LAPNUM_BACK)

    # Hud::DisplayTrack, the colour of track-line vertex k: eax = the vertex array, ecx = 1Ch * (k + 1),
    # [esp+10h] = k / 2 (the path point), st0 = the number of points; edx is free. In a challenge
    # the point's place (k / 2) / n behind the start picks the colour: stretch, finish, rest.
    a.label("ch_mapcol")
    a.raw("55", "push        ebp")
    a.call("tune_base")
    a.raw("BA " + _le(0xFFC0C0C0), "mov         edx,%s" % _imm(0xFFC0C0C0))   # the stock colour
    t_active()
    a.jcc_short("je", "ch_mapcol_store")
    a.raw("50", "push        eax")
    a.raw("DB 44 24 18", "fild        dword ptr [esp+18h]")
    a.raw("D8 F1", "fdiv        st,st(1)")
    t_mem("D8", 4, CH_START, "fsub        dword ptr %s")
    a.raw("D9 E4", "ftst")
    fpu_flags(0x01)
    a.jcc_short("je", "ch_mapcol_pos")
    t_mem("D8", 0, "ch_one", "fadd        dword ptr %s")
    a.label("ch_mapcol_pos")
    for color, bound, mask in (("rest", CH_HI, 0x41),          # beyond the finish band
                               ("finish", CH_LO, 0x01)):       # in the finish band
        a.raw("BA " + _le(CH_COLORS[color]), "mov         edx,%s" % _imm(CH_COLORS[color]))
        t_mem("D8", 2, bound, "fcom        dword ptr %s")
        fpu_flags(mask)
        a.jcc_short("je", "ch_mapcol_pop")
    a.raw("BA " + _le(CH_COLORS["stretch"]), "mov         edx,%s" % _imm(CH_COLORS["stretch"]))
    a.label("ch_mapcol_pop")
    a.raw("DD D8", "fstp        st(0)")
    a.raw("58", "pop         eax")
    a.label("ch_mapcol_store")
    a.raw("89 54 01 F4", "mov         dword ptr [ecx+eax-0Ch],edx")
    a.raw("5D", "pop         ebp")
    a.jmp(CH_MAP_BACK)

    # The result pages' "top five?" (in place of the call): never in a challenge.
    a.label("ch_top5")
    a.raw("55", "push        ebp")
    a.call("tune_base")
    t_active()
    a.raw("5D", "pop         ebp")
    a.jcc_near("je", TOP_FIVE)
    a.raw("32 C0", "xor         al,al")
    a.raw("C2 0C 00", "ret         0Ch")

    # The ghost's file name at race start and restart: in a challenge, an empty name.
    for k, (va, orig, str_off) in enumerate(CH_GHOST_HOOKS):
        a.label("ch_ghost%d" % k)
        raw = bytes.fromhex(orig)
        disp, value = struct.unpack_from("<II", raw, 6)
        a.raw("83 C4 10", "add         esp,10h")                                   # displaced
        a.raw(raw[3:].hex(" "), "mov         dword ptr [esp+%08Xh],%s" % (disp, _imm(value)))
        a.raw("60", "pushad")
        a.call("tune_base")
        t_active()
        a.jcc_short("je", "ch_ghost%d_done" % k)
        t_mem("8B", 0, CH_DAY, "mov         eax,dword ptr %s")
        a.raw("50", "push        eax")
        t_lea("ecx", "ch_no_file")                    # random: no ghost
        a.raw("85 C0", "test        eax,eax")
        a.jcc_short("je", "ch_ghost%d_fmt" % k)
        t_lea("ecx", "ch_daily_fmt")                  # daily: the best run of the day
        a.label("ch_ghost%d_fmt" % k)
        a.raw("51", "push        ecx")
        a.raw("8D 84 24 " + _le(str_off + 0x28), "lea         eax,[esp+%08Xh]" % (str_off + 0x28))
        a.raw("50", "push        eax")
        a.call(STR_FORMAT)
        a.raw("83 C4 0C", "add         esp,0Ch")
        a.label("ch_ghost%d_done" % k)
        a.raw("61", "popad")
        a.jmp(va + len(raw))

    def t_store(target, value):          # mov dword ptr [ebp+disp],imm32
        disp = tdisp(target)
        a.raw("C7 85 %s %s" % (_le(disp), _le(value)), "mov         dword ptr [ebp+%08Xh],%s" % (disp, _imm(value)))

    def ch_page(page):                   # Menu::SetPage(page), esi = menu
        a.raw("6A %02X" % page, "push        %s" % _imm(page))
        a.raw("8B CE", "mov         ecx,esi")
        a.call(PAGE_SET)

    def ch_select(item):
        a.raw("C7 86 48 01 00 00 %s" % _le(item), "mov         dword ptr [esi+00000148h],%s" % _imm(item))

    def ch_label(y, buf):                # Menu::AddLabel(text at [esp+buf], y), esi = menu
        a.raw("68 " + _le(y), "push        %s" % _imm(y))
        a.raw("8D 84 24 " + _le(buf + 4), "lea         eax,[esp+%08Xh]" % (buf + 4))
        a.raw("50", "push        eax")
        a.raw("8B CE", "mov         ecx,esi")
        a.call(ADD_LABEL)

    # Swaps the fields CH_SWAP of GameParameters with CH_SAVE. Keeps all registers.
    a.label("ch_swap")
    a.raw("60", "pushad")
    a.call("tune_base")
    t_mov("ebx", GP_POINTER)
    a.raw("85 DB", "test        ebx,ebx")
    a.jcc_near("je", "ch_swap_done")
    for k, off in enumerate(CH_SWAP):
        a.raw("8B 83 " + _le(off), "mov         eax,dword ptr [ebx+%08Xh]" % off)
        t_mem("8B", 1, CH_SAVE + 4 * k, "mov         ecx,dword ptr %s")
        a.raw("89 8B " + _le(off), "mov         dword ptr [ebx+%08Xh],ecx" % off)
        t_mem("89", 0, CH_SAVE + 4 * k, "mov         dword ptr %s,eax")
    a.label("ch_swap_done")
    a.raw("61", "popad")
    a.raw("C3", "ret")

    # ... only while a challenge is drawn (around the two writes of settings.dat). Keeps all registers.
    a.label("ch_swap_if")
    a.raw("60", "pushad")
    a.call("tune_base")
    t_active()
    a.jcc_short("je", "ch_swap_if_done")
    a.call("ch_swap")
    a.label("ch_swap_if_done")
    a.raw("61", "popad")
    a.raw("C3", "ret")

    # A draw begins: the player's settings go to CH_SAVE (once). Keeps all registers.
    a.label("ch_arm")
    a.raw("60", "pushad")
    a.call("tune_base")
    t_active()
    a.jcc_short("jne", "ch_arm_done")
    a.call("tune_defaults")              # the player's tuning values get their marker first: else
    a.call("ch_swap")                    # the race start would put the defaults over the challenge's
    t_store(CH_ACTIVE, 1)
    a.label("ch_arm_done")
    a.raw("61", "popad")
    a.raw("C3", "ret")

    # The challenge ends (back to the race mode page or the main menu): the player's settings
    # come back. Keeps all registers.
    a.label("ch_disarm")
    a.raw("60", "pushad")
    a.call("tune_base")
    t_active()
    a.jcc_short("je", "ch_disarm_done")
    a.call("ch_swap")
    t_store(CH_ACTIVE, 0)
    a.label("ch_disarm_done")
    a.raw("61", "popad")
    a.raw("C3", "ret")

    # In place of "mov ecx,esi / call [eax+14h]" (File::Write of GameParameters, at both places
    # that save settings.dat): the file gets the player's own settings, never the challenge's.
    for k, va in enumerate(CH_SAVE_HOOKS):
        a.label("ch_save%d" % k)
        a.call("ch_swap_if")
        a.raw("8B CE", "mov         ecx,esi")
        a.raw("FF 50 14", "call        dword ptr [eax+14h]")
        a.call("ch_swap_if")
        a.jmp(va + 5)

    # xorshift32 on CH_SEED: eax = the next number. ebp = tune_T. Clobbers edx.
    a.label("ch_next")
    t_mem("8B", 0, CH_SEED, "mov         eax,dword ptr %s")
    for op, sh in (("shl", 13), ("shr", 17), ("shl", 5)):
        a.raw("8B D0", "mov         edx,eax")
        a.raw("C1 %s %02X" % ("E2" if op == "shl" else "EA", sh), "%-11s edx,%s" % (op, _imm(sh)))
        a.raw("33 C2", "xor         eax,edx")
    t_mem("89", 0, CH_SEED, "mov         dword ptr %s,eax")
    a.raw("C3", "ret")

    def ch_mod(n):                       # eax = edx = the next number % n (unsigned)
        a.call("ch_next")
        a.raw("33 D2", "xor         edx,edx")
        a.raw("B9 " + _le(n), "mov         ecx,%s" % _imm(n))
        a.raw("F7 F1", "div         eax,ecx")
        a.raw("8B C2", "mov         eax,edx")

    # The draw: eax = seed, ebx = GameParameters, ebp = tune_T. Writes the challenge's settings
    # into GameParameters (see challenge_draw). Clobbers eax, ecx, edx.
    a.label("ch_draw")
    a.raw("85 C0", "test        eax,eax")
    a.jcc_short("jne", "ch_draw_seed")
    a.raw("40", "inc         eax")
    a.label("ch_draw_seed")
    t_mem("89", 0, CH_SEED, "mov         dword ptr %s,eax")
    ch_mod(8)
    a.raw("89 43 20", "mov         dword ptr [ebx+20h],eax")         # track
    ch_mod(1000)
    t_mem("89", 0, CH_TMP, "mov         dword ptr %s,eax")
    t_mem("DB", 0, CH_TMP, "fild        dword ptr %s")
    t_mem("D8", 1, "ch_milli", "fmul        dword ptr %s")
    t_mem("D9", 3, CH_START, "fstp        dword ptr %s")
    ch_mod(CH_METRES_SPAN)
    a.raw("05 " + _le(CH_METRES_MIN), "add         eax,%s" % _imm(CH_METRES_MIN))
    t_mem("89", 0, CH_TMP, "mov         dword ptr %s,eax")
    t_mem("DB", 0, CH_TMP, "fild        dword ptr %s")
    a.raw("8B 4B 20", "mov         ecx,dword ptr [ebx+20h]")
    disp = tdisp("ch_paths")
    a.raw("D8 B4 8D " + _le(disp), "fdiv        dword ptr [ebp+ecx*4+%08Xh]" % disp)
    t_mem("D8", 2, "ch_len_min", "fcom        dword ptr %s")
    fpu_flags(0x01)
    a.jcc_short("je", "ch_draw_min")                 # share >= minimum
    a.raw("DD D8", "fstp        st(0)")
    t_mem("D9", 0, "ch_len_min", "fld         dword ptr %s")
    a.label("ch_draw_min")
    disp = tdisp("ch_len_min") + 4
    a.raw("D8 95 " + _le(disp), "fcom        dword ptr [ebp+%08Xh]" % disp)
    fpu_flags(0x41)
    a.jcc_short("jne", "ch_draw_max")                # share <= maximum
    a.raw("DD D8", "fstp        st(0)")
    a.raw("D9 85 " + _le(disp), "fld         dword ptr [ebp+%08Xh]" % disp)
    a.label("ch_draw_max")
    t_mem("D9", 3, CH_LEN, "fstp        dword ptr %s")
    ch_mod(7)
    a.raw("89 43 58", "mov         dword ptr [ebx+58h],eax")         # player 1's character
    ch_mod(CH_SET_COUNT)
    a.raw("C1 E0 04", "shl         eax,4")
    t_lea("ecx", "ch_sets")
    a.raw("03 C8", "add         ecx,eax")
    for k in range(PRESET_VALUES):
        if k:
            a.raw("0F B7 41 %02X" % (2 * k), "movzx       eax,word ptr [ecx+%s]" % _imm(2 * k))
        else:
            a.raw("0F B7 01", "movzx       eax,word ptr [ecx]")
        a.raw("89 83 " + _le(TUNE_VALUES + 4 * k), "mov         dword ptr [ebx+%08Xh],eax" % (TUNE_VALUES + 4 * k))
    a.raw("C7 43 10 05 00 00 00", "mov         dword ptr [ebx+10h],5")       # the tuning class
    a.raw("C7 43 1C 00 00 00 00", "mov         dword ptr [ebx+1Ch],0")       # time trial
    # 60 FPS physics on; the low byte is the game's own bool, which must stay the player's: with
    # 0 the race start (0x408777) takes the debug path (track from the config's "level", 150 cc,
    # Moorhuhn)
    assert CH_SWAP[3] == PHYS_FLAG_OFFSET
    t_mem("8B", 0, CH_SAVE + 4 * 3, "mov         eax,dword ptr %s")
    a.raw("25 FF 00 00 00", "and         eax,0FFh")
    a.raw("0D " + _le(PHYS_MAGIC << 8), "or          eax,%s" % _imm(PHYS_MAGIC << 8))
    a.raw("89 43 %02X" % PHYS_FLAG_OFFSET, "mov         dword ptr [ebx+%s],eax" % _imm(PHYS_FLAG_OFFSET))
    a.raw("C3", "ret")

    # eax = today, in days since 1601 (UTC). ebp = tune_T. Clobbers ecx, edx.
    a.label("ch_today")
    a.raw("83 EC 08", "sub         esp,8")
    a.raw("54", "push        esp")
    t_call_import(IMP_SYSTIME)
    a.raw("DF 2C 24", "fild        qword ptr [esp]")
    t_mem("DC", 6, "ch_day_len", "fdiv        qword ptr %s")
    t_mem("D8", 4, "ch_half", "fsub        dword ptr %s")               # rounding to nearest: floor
    a.raw("DB 1C 24", "fistp       dword ptr [esp]")
    a.raw("58", "pop         eax")
    a.raw("59", "pop         ecx")
    a.raw("C3", "ret")

    # eax = text id, edx = room for a std::string (1Ch bytes, not built yet): eax = the text.
    # Clobbers ecx, edx.
    a.label("ch_text")
    a.raw("6A 00", "push        0")
    a.raw("50", "push        eax")
    a.raw("52", "push        edx")
    a.call(TEXTMGR_GET)
    a.raw("8B C8", "mov         ecx,eax")
    a.call(GET_TEXT)
    a.raw("8B C8", "mov         ecx,eax")
    a.call(STR_CSTR)
    a.raw("C3", "ret")

    # The race mode page (4), after the game built it (ecx = menu): in the main menu its item 3,
    # the label "Zwei Spieler", becomes the button "Herausforderung", and the label comes again
    # behind the items. A challenge drawn before ends here.
    a.label("mode_build")
    a.raw("51", "push        ecx")
    a.raw("FF 74 24 08", "push        dword ptr [esp+8]")
    a.call(PAGE_BUILD_LAST)
    a.raw("59", "pop         ecx")
    a.raw("60", "pushad")
    a.raw("8B F1", "mov         esi,ecx")
    a.call("tune_base")
    t_mov("eax", MAIN_PROGRAM)
    a.raw("85 C0", "test        eax,eax")
    a.jcc_near("je", "mode_build_done")
    a.raw("3B 70 04", "cmp         esi,dword ptr [eax+4]")
    a.jcc_near("jne", "mode_build_done")
    a.call("ch_disarm")
    a.raw("8B 86 34 01 00 00", "mov         eax,dword ptr [esi+00000134h]")
    a.raw("8B 8E 38 01 00 00", "mov         ecx,dword ptr [esi+00000138h]")
    a.raw("2B C8", "sub         ecx,eax")
    a.raw("81 F9 " + _le(7 * MENU_ITEM_SIZE), "cmp         ecx,%s" % _imm(7 * MENU_ITEM_SIZE))
    a.jcc_near("jb", "mode_build_done")
    item = MODE_ITEM_CH * MENU_ITEM_SIZE
    a.raw("C7 80 %s 01 00 00 00" % _le(item), "mov         dword ptr [eax+%08Xh],1" % item)   # a button
    bits = struct.unpack("<I", struct.pack("<f", MODE_Y_CH))[0]
    a.raw("C7 80 %s %s" % (_le(item + 0x28), _le(bits)), "mov         dword ptr [eax+%08Xh],%s" % (item + 0x28, _imm(bits)))
    a.raw("83 EC 1C", "sub         esp,1Ch")
    a.raw("B8 " + _le(TXT_CH_MODE), "mov         eax,%s" % _imm(TXT_CH_MODE))
    a.raw("8B D4", "mov         edx,esp")
    a.call("ch_text")
    a.raw("8B D0", "mov         edx,eax")
    a.raw("8B 8E 34 01 00 00", "mov         ecx,dword ptr [esi+00000134h]")
    a.raw("81 C1 " + _le(item + 8), "add         ecx,%s" % _imm(item + 8))
    a.call("str_setc")
    a.raw("8B CC", "mov         ecx,esp")
    a.call(STR_DTOR)
    a.raw("B8 " + _le(TXT_TWO_PLAYERS), "mov         eax,%s" % _imm(TXT_TWO_PLAYERS))
    a.raw("8B D4", "mov         edx,esp")
    a.call("ch_text")
    a.raw("68 " + _le(MODE_Y_TWO), "push        %s" % _imm(MODE_Y_TWO))
    a.raw("50", "push        eax")
    a.raw("8B CE", "mov         ecx,esi")
    a.call(ADD_LABEL)
    a.raw("8B CC", "mov         ecx,esp")
    a.call(STR_DTOR)
    a.raw("83 C4 1C", "add         esp,1Ch")
    disp = tdisp(CH_FROM)
    a.raw("83 BD %s 00" % _le(disp), "cmp         dword ptr [ebp+%08Xh],0" % disp)
    a.jcc_short("je", "mode_build_done")
    t_store(CH_FROM, 0)
    ch_select(MODE_ITEM_CH)
    a.label("mode_build_done")
    a.raw("61", "popad")
    a.raw("C2 04 00", "ret         4")

    # The challenge page (ecx = menu): the four buttons, and after a draw the lines with the
    # challenge. Stack: +0 and +20h two std::strings (track, character), +40h one for the time,
    # +60h the eight values as words, +70h two numbers, +80h the text (200h bytes).
    CH_FRAME, CH_BUF = 0x280, 0x80
    a.label("ch_build")
    a.raw("60", "pushad")
    a.raw("8B F1", "mov         esi,ecx")
    a.call("tune_base")
    t_mov("ebx", GP_POINTER)
    a.raw("8D 8E 30 01 00 00", "lea         ecx,[esi+00000130h]")
    a.call(ITEMS_CLEAR)
    for text_id, y in zip((TXT_CH_RANDOM, TXT_CH_DAILY, TXT_NEXT, TXT_BACK), CH_Y_BUTTONS):   # items 0..3
        a.raw("B8 " + _le(text_id), "mov         eax,%s" % _imm(text_id))
        a.raw("BA " + _le(y), "mov         edx,%s" % _imm(y))
        a.call("tune_button")
    t_active()
    a.jcc_near("je", "ch_build_title")
    a.raw("81 EC " + _le(CH_FRAME), "sub         esp,%s" % _imm(CH_FRAME))
    # track, metres, start, driver
    a.raw("8B 43 20", "mov         eax,dword ptr [ebx+20h]")
    a.raw("05 " + _le(TXT_TRACK0), "add         eax,%s" % _imm(TXT_TRACK0))
    a.raw("8B D4", "mov         edx,esp")
    a.call("ch_text")
    a.raw("8B F8", "mov         edi,eax")
    a.raw("8B 43 58", "mov         eax,dword ptr [ebx+58h]")
    a.raw("05 " + _le(TXT_CH_CHAR0), "add         eax,%s" % _imm(TXT_CH_CHAR0))
    a.raw("8D 54 24 20", "lea         edx,[esp+20h]")
    a.call("ch_text")
    a.raw("8B 4B 20", "mov         ecx,dword ptr [ebx+20h]")
    t_mem("D9", 0, CH_LEN, "fld         dword ptr %s")
    disp = tdisp("ch_paths")
    a.raw("D8 8C 8D " + _le(disp), "fmul        dword ptr [ebp+ecx*4+%08Xh]" % disp)
    a.raw("DB 5C 24 70", "fistp       dword ptr [esp+70h]")
    t_mem("D9", 0, CH_START, "fld         dword ptr %s")
    t_mem("D8", 1, "ch_hundred", "fmul        dword ptr %s")
    a.raw("DB 5C 24 74", "fistp       dword ptr [esp+74h]")
    a.raw("50", "push        eax")                                   # the driver
    a.raw("FF 74 24 78", "push        dword ptr [esp+78h]")           # start in percent
    a.raw("FF 74 24 78", "push        dword ptr [esp+78h]")           # metres
    a.raw("57", "push        edi")                                   # the track
    a.raw("68 " + _le(TXT_CH_DRAW), "push        %s" % _imm(TXT_CH_DRAW))
    a.raw("8D 84 24 " + _le(CH_BUF + 0x14), "lea         eax,[esp+%08Xh]" % (CH_BUF + 0x14))
    a.raw("50", "push        eax")
    a.call("tune_printf")
    a.raw("83 C4 18", "add         esp,18h")
    ch_label(CH_Y_LINES[0], CH_BUF)
    a.raw("8B CC", "mov         ecx,esp")
    a.call(STR_DTOR)
    a.raw("8D 4C 24 20", "lea         ecx,[esp+20h]")
    a.call(STR_DTOR)
    # the tuning values and the top speed, as on the pause page
    for k in range(PRESET_VALUES):
        a.raw("8B 83 " + _le(TUNE_VALUES + 4 * k), "mov         eax,dword ptr [ebx+%08Xh]" % (TUNE_VALUES + 4 * k))
        a.raw("66 89 44 24 %02X" % (0x60 + 2 * k), "mov         word ptr [esp+%Xh],ax" % (0x60 + 2 * k))
    a.raw("8D 54 24 60", "lea         edx,[esp+60h]")
    a.raw("8D 84 24 " + _le(CH_BUF), "lea         eax,[esp+%08Xh]" % CH_BUF)
    a.raw("56", "push        esi")
    a.raw("BE " + _le(TXT_PAUSE_VALUES), "mov         esi,%s" % _imm(TXT_PAUSE_VALUES))
    a.call("values_text_id")
    a.raw("5E", "pop         esi")
    a.raw("8D BC 24 " + _le(CH_BUF), "lea         edi,[esp+%08Xh]" % CH_BUF)
    a.raw("8D 93 " + _le(TUNE_VALUES), "lea         edx,[ebx+%08Xh]" % TUNE_VALUES)
    a.raw("B8 " + _le(TXT_TOP_PAUSE[0]), "mov         eax,%s" % _imm(TXT_TOP_PAUSE[0]))
    a.call("top_text")
    ch_label(CH_Y_LINES[1], CH_BUF)
    # the daily challenge: the best time of the day
    t_mem("8B", 0, CH_DAY, "mov         eax,dword ptr %s")
    a.raw("85 C0", "test        eax,eax")
    a.jcc_near("je", "ch_build_lines_done")
    a.raw("81 BB %s %s" % (_le(DAILY_ENTRY), _le(DAILY_MAGIC)),
          "cmp         dword ptr [ebx+%08Xh],%s" % (DAILY_ENTRY, _imm(DAILY_MAGIC)))
    a.jcc_short("jne", "ch_build_no_best")
    a.raw("3B 83 " + _le(DAILY_ENTRY + 4), "cmp         eax,dword ptr [ebx+%08Xh]" % (DAILY_ENTRY + 4))
    a.jcc_short("jne", "ch_build_no_best")
    a.raw("FF B3 " + _le(DAILY_ENTRY + 8), "push        dword ptr [ebx+%08Xh]" % (DAILY_ENTRY + 8))
    a.raw("8D 44 24 44", "lea         eax,[esp+44h]")
    a.raw("50", "push        eax")
    a.call(TIME_TEXT)
    a.raw("8B C8", "mov         ecx,eax")
    a.call(STR_CSTR)
    a.raw("50", "push        eax")
    a.raw("68 " + _le(TXT_CH_BEST), "push        %s" % _imm(TXT_CH_BEST))
    a.raw("8D 84 24 " + _le(CH_BUF + 8), "lea         eax,[esp+%08Xh]" % (CH_BUF + 8))
    a.raw("50", "push        eax")
    a.call("tune_printf")
    a.raw("83 C4 0C", "add         esp,0Ch")
    a.raw("8D 4C 24 40", "lea         ecx,[esp+40h]")
    a.call(STR_DTOR)
    a.jmp_short("ch_build_best")
    a.label("ch_build_no_best")
    a.raw("68 " + _le(TXT_CH_BEST_NONE), "push        %s" % _imm(TXT_CH_BEST_NONE))
    a.raw("8D 84 24 " + _le(CH_BUF + 4), "lea         eax,[esp+%08Xh]" % (CH_BUF + 4))
    a.raw("50", "push        eax")
    a.call("tune_printf")
    a.raw("83 C4 08", "add         esp,8")
    a.label("ch_build_best")
    ch_label(CH_Y_LINES[2], CH_BUF)
    a.label("ch_build_lines_done")
    a.raw("81 C4 " + _le(CH_FRAME), "add         esp,%s" % _imm(CH_FRAME))
    a.label("ch_build_title")
    a.raw("B8 " + _le(TXT_CH_TITLE), "mov         eax,%s" % _imm(TXT_CH_TITLE))
    a.call("tune_title")
    ch_select(CH_ITEM_RANDOM)
    t_active()
    a.jcc_short("je", "ch_build_done")
    ch_select(CH_ITEM_NEXT)                         # after a draw: "Weiter"
    a.label("ch_build_done")
    a.raw("61", "popad")
    a.raw("C2 04 00", "ret         4")

    # The challenge page's input (ecx = menu, [esp+4] = frame time).
    a.label("ch_update")
    a.raw("53", "push        ebx")
    a.raw("56", "push        esi")
    a.raw("57", "push        edi")
    a.raw("55", "push        ebp")
    a.raw("8B F1", "mov         esi,ecx")
    a.call("tune_base")
    a.raw("FF 74 24 14", "push        dword ptr [esp+14h]")
    a.raw("8B CE", "mov         ecx,esi")
    a.call(MENU_NAVIGATE)
    t_mov("ebx", GP_POINTER)
    t_lea("eax", STR_MENU_BACK)
    a.call("tune_pressed")
    a.jcc_near("je", "ch_update_back")
    t_lea("eax", STR_MENU_SELECT)
    a.call("tune_pressed")
    a.jcc_near("jne", "tune_out")
    a.raw("8B 86 48 01 00 00", "mov         eax,dword ptr [esi+00000148h]")
    for item, label in ((CH_ITEM_RANDOM, "ch_update_random"), (CH_ITEM_DAILY, "ch_update_daily"),
                        (CH_ITEM_NEXT, "ch_update_go"), (CH_ITEM_BACK, "ch_update_back")):
        a.raw("83 F8 %02X" % item, "cmp         eax,%s" % _imm(item))
        a.jcc_near("je", label)
    a.jmp("tune_out")
    a.label("ch_update_random")
    t_store(CH_DAY, 0)
    t_call_import(IMP_TICKS)
    a.jmp_short("ch_update_draw")
    a.label("ch_update_daily")
    a.call("ch_today")
    t_mem("89", 0, CH_DAY, "mov         dword ptr %s,eax")
    a.raw("69 C0 " + _le(CH_DAILY_MUL), "imul        eax,eax,%s" % _imm(CH_DAILY_MUL))
    a.raw("35 " + _le(CH_DAILY_XOR), "xor         eax,%s" % _imm(CH_DAILY_XOR))
    a.label("ch_update_draw")
    a.call("ch_arm")
    a.raw("85 DB", "test        ebx,ebx")
    a.jcc_near("je", "tune_out")
    a.call("ch_draw")
    ch_page(PAGE_CH)
    a.jmp("tune_out")
    a.label("ch_update_go")
    t_active()
    a.jcc_near("je", "tune_out")
    a.raw("8B CE", "mov         ecx,esi")
    a.call(START_RACE)
    a.jmp("tune_out")
    a.label("ch_update_back")
    a.call("ch_disarm")
    t_store(CH_FROM, 1)
    ch_page(PAGE_MODE)
    a.jmp("tune_out")

    # The race mode page's input (ecx = menu): "menu select" on "Herausforderung" opens the
    # challenge page; everything else goes to the game's handler.
    a.label("mode_update")
    a.raw("53", "push        ebx")
    a.raw("56", "push        esi")
    a.raw("57", "push        edi")
    a.raw("55", "push        ebp")
    a.raw("8B F1", "mov         esi,ecx")
    a.call("tune_base")
    a.raw("83 BE 48 01 00 00 %02X" % MODE_ITEM_CH, "cmp         dword ptr [esi+00000148h],%s" % _imm(MODE_ITEM_CH))
    a.jcc_short("jne", "mode_update_game")
    t_lea("eax", STR_MENU_SELECT)
    a.call("tune_pressed")
    a.jcc_short("jne", "mode_update_game")
    ch_page(PAGE_CH)
    a.jmp("tune_out")
    a.label("mode_update_game")
    a.raw("8B CE", "mov         ecx,esi")
    a.raw("5D", "pop         ebp")
    a.raw("5F", "pop         edi")
    a.raw("5E", "pop         esi")
    a.raw("5B", "pop         ebx")
    a.jmp(PAGE_UPDATE_MAIN)

    # Which row does an item of the current page show? eax = item, esi = menu.
    # Returns eax = the row (0 "Vorlage", 1..9 the values) or -1. Clobbers ecx, edx.
    a.label("tune_item_row")
    a.raw("8B 8E 40 01 00 00", "mov         ecx,dword ptr [esi+00000140h]")
    a.raw("83 F9 %02X" % PAGE_TUNING, "cmp         ecx,%s" % _imm(PAGE_TUNING))
    a.jcc_short("je", "tune_item_row_tuning")
    a.call("sub_rows")
    a.raw("03 C1", "add         eax,ecx")
    a.raw("3B C1", "cmp         eax,ecx")
    a.jcc_short("jl", "tune_item_row_none")       # no item selected (-1)
    a.raw("3B C2", "cmp         eax,edx")
    a.jcc_short("jge", "tune_item_row_none")
    a.raw("C3", "ret")
    a.label("tune_item_row_tuning")
    a.raw("85 C0", "test        eax,eax")
    a.jcc_short("je", "tune_item_row_done")
    a.label("tune_item_row_none")
    a.raw("83 C8 FF", "or          eax,0FFFFFFFFh")
    a.label("tune_item_row_done")
    a.raw("C3", "ret")

    # The item shows its text again (after a value changed), on any of the pages.
    # eax = item, esi = menu, ebp = tune_T. Clobbers eax, ecx, edx.
    a.label("tune_settext")
    a.raw("57", "push        edi")
    a.raw("8B F8", "mov         edi,eax")
    a.raw("81 EC " + _le(OWN_VALUES_BUF), "sub         esp,%s" % _imm(OWN_VALUES_BUF))
    a.raw("8B D4", "mov         edx,esp")
    a.raw("83 BE 40 01 00 00 %02X" % PAGE_OWN, "cmp         dword ptr [esi+00000140h],%s" % _imm(PAGE_OWN))
    a.jcc_short("jne", "tune_settext_tuning")
    a.call("own_text")
    a.jmp_short("tune_settext_set")
    a.label("tune_settext_tuning")
    a.call("tune_item_row")
    a.raw("8B D4", "mov         edx,esp")
    a.call("tune_text")
    a.label("tune_settext_set")
    a.raw("8B C7", "mov         eax,edi")
    a.raw("8B D4", "mov         edx,esp")
    a.call("item_setstr")
    a.raw("81 C4 " + _le(OWN_VALUES_BUF), "add         esp,%s" % _imm(OWN_VALUES_BUF))
    a.raw("5F", "pop         edi")
    a.raw("C3", "ret")

    # Every arrow item of the current page shows its text again (they are the first items).
    # esi = menu, ebp = tune_T. Clobbers eax, ecx, edx.
    a.label("tune_refresh")
    a.raw("57", "push        edi")
    a.raw("33 FF", "xor         edi,edi")
    a.label("tune_refresh_next")
    a.raw("8B C7", "mov         eax,edi")
    a.call("tune_item_row")
    a.raw("85 C0", "test        eax,eax")
    a.jcc_short("jl", "tune_refresh_done")
    a.raw("8B C7", "mov         eax,edi")
    a.call("tune_settext")
    a.raw("47", "inc         edi")
    a.jmp_short("tune_refresh_next")
    a.label("tune_refresh_done")
    a.raw("B8 " + _le(TUNE_LIMIT_ITEM["tuning"]), "mov         eax,%s" % _imm(TUNE_LIMIT_ITEM["tuning"]))   # the "Am Limit" label
    a.raw("8B 8E 40 01 00 00", "mov         ecx,dword ptr [esi+00000140h]")
    for name, page in (("kart", PAGE_KART), ("world", PAGE_WORLD), ("opp", PAGE_OPP)):
        a.raw("83 F9 %02X" % page, "cmp         ecx,%s" % _imm(page))
        a.jcc_short("jne", "tune_refresh_not_" + name)
        a.raw("B8 " + _le(TUNE_LIMIT_ITEM[name]), "mov         eax,%s" % _imm(TUNE_LIMIT_ITEM[name]))
        a.label("tune_refresh_not_" + name)
    a.label("tune_refresh_limit")
    a.raw("50", "push        eax")
    a.raw("81 EC 00 01 00 00", "sub         esp,100h")
    a.raw("8B D4", "mov         edx,esp")
    a.raw("8B 86 40 01 00 00", "mov         eax,dword ptr [esi+00000140h]")
    a.call("tune_limit_text")
    a.raw("8B 84 24 00 01 00 00", "mov         eax,dword ptr [esp+00000100h]")
    a.raw("8B D4", "mov         edx,esp")
    a.call("item_setstr")
    a.raw("83 BE 40 01 00 00 %02X" % PAGE_TUNING, "cmp         dword ptr [esi+00000140h],%s" % _imm(PAGE_TUNING))
    a.jcc_short("jne", "tune_refresh_end")
    for k in range(len(TUNE_Y_GROUPS)):          # the tuning page: the values under its two buttons
        a.raw("B8 " + _le(k), "mov         eax,%s" % _imm(k))
        a.raw("8B D4", "mov         edx,esp")
        a.call("group_text")
        a.raw("B8 " + _le(TUNE_ITEM_GROUPS + k), "mov         eax,%s" % _imm(TUNE_ITEM_GROUPS + k))
        a.raw("8B D4", "mov         edx,esp")
        a.call("item_setstr")
    a.label("tune_refresh_end")
    a.raw("81 C4 04 01 00 00", "add         esp,104h")
    a.raw("5F", "pop         edi")
    a.raw("C3", "ret")

    # The explanation on a detail page follows the selected item: the text of its row, or
    # nothing while "Zurück" (or no item) is selected. esi = menu, ebx = GameParameters,
    # ebp = tune_T. Clobbers eax, ecx, edx.
    a.label("tune_info")
    a.raw("8B 86 48 01 00 00", "mov         eax,dword ptr [esi+00000148h]")
    a.raw("3B 83 " + _le(INFO_SHOWN), "cmp         eax,dword ptr [ebx+%08Xh]" % INFO_SHOWN)
    a.jcc_short("je", "tune_info_done")
    a.raw("89 83 " + _le(INFO_SHOWN), "mov         dword ptr [ebx+%08Xh],eax" % INFO_SHOWN)
    a.call("tune_item_row")
    a.raw("B9 " + _le(TXT_TUNING_HIDDEN), "mov         ecx,%s" % _imm(TXT_TUNING_HIDDEN))
    a.raw("85 C0", "test        eax,eax")
    a.jcc_short("jle", "tune_info_set")
    disp = tdisp("tune_info_texts") - 2 & 0xFFFFFFFF
    a.raw("0F B7 8C 45 " + _le(disp), "movzx       ecx,word ptr [ebp+eax*2+%08Xh]" % disp)
    a.label("tune_info_set")
    a.raw("83 EC 1C", "sub         esp,1Ch")
    get_text("51", "push        ecx")
    a.raw("8B D0", "mov         edx,eax")
    a.raw("B8 " + _le(TUNE_LIMIT_ITEM["kart"] + 1), "mov         eax,%s" % _imm(TUNE_LIMIT_ITEM["kart"] + 1))
    a.raw("83 BE 40 01 00 00 %02X" % PAGE_KART, "cmp         dword ptr [esi+00000140h],%s" % _imm(PAGE_KART))
    a.jcc_short("je", "tune_info_item")
    a.raw("B8 " + _le(TUNE_LIMIT_ITEM["world"] + 1), "mov         eax,%s" % _imm(TUNE_LIMIT_ITEM["world"] + 1))
    a.raw("83 BE 40 01 00 00 %02X" % PAGE_WORLD, "cmp         dword ptr [esi+00000140h],%s" % _imm(PAGE_WORLD))
    a.jcc_short("je", "tune_info_item")
    a.raw("B8 " + _le(TUNE_LIMIT_ITEM["opp"] + 1), "mov         eax,%s" % _imm(TUNE_LIMIT_ITEM["opp"] + 1))
    a.label("tune_info_item")
    a.call("item_setstr")
    a.raw("8B CC", "mov         ecx,esp")
    a.call(STR_DTOR)
    a.raw("83 C4 1C", "add         esp,1Ch")
    a.label("tune_info_done")
    a.raw("C3", "ret")

    # Left / right on an arrow row. eax = row (0..9), edx = +1 or -1, esi = menu, ebp = tune_T.
    a.label("tune_change")
    a.raw("85 C0", "test        eax,eax")
    a.jcc_near("jne", "tune_step")
    # Row 0, "Vorlage": the next or previous preset (built-in ones, then the filled own
    # slots), counted from the one the values equal (see tune_match), or else from the one
    # copied last.
    # Its values go into the rows.
    a.raw("53", "push        ebx")
    a.raw("57", "push        edi")
    t_mov("ebx", GP_POINTER)
    a.raw("52", "push        edx")
    a.call("tune_match")
    a.raw("5A", "pop         edx")
    a.raw("85 C0", "test        eax,eax")
    a.jcc_short("jge", "tune_preset_next")
    a.raw("8B 83 " + _le(TUNE_LAST), "mov         eax,dword ptr [ebx+%08Xh]" % TUNE_LAST)
    a.raw("83 F8 %02X" % PRESETS_ALL, "cmp         eax,%s" % _imm(PRESETS_ALL))
    a.jcc_short("jb", "tune_preset_next")
    a.raw("B8 " + _le(TUNE_PRESET_DEFAULT), "mov         eax,%s" % _imm(TUNE_PRESET_DEFAULT))
    a.label("tune_preset_next")
    a.raw("03 C2", "add         eax,edx")
    a.jcc_short("jge", "tune_preset_low_ok")
    a.raw("83 C0 %02X" % PRESETS_ALL, "add         eax,%s" % _imm(PRESETS_ALL))   # before the first: the last
    a.label("tune_preset_low_ok")
    a.raw("83 F8 %02X" % PRESETS_ALL, "cmp         eax,%s" % _imm(PRESETS_ALL))
    a.jcc_short("jb", "tune_preset_high_ok")
    a.raw("33 C0", "xor         eax,eax")                                   # behind the last: the first
    a.label("tune_preset_high_ok")
    a.call("tune_preset_ptr")
    a.jcc_short("je", "tune_preset_next")                                  # an empty slot: one further
    a.raw("89 83 " + _le(TUNE_LAST), "mov         dword ptr [ebx+%08Xh],eax" % TUNE_LAST)
    a.call("preset_load")
    a.jmp_short("tune_step_refresh")

    # One step up or down for a value, then its row shows the new value.
    # eax = row (1..8), edx = +1 or -1, esi = menu, ebp = tune_T.
    a.label("tune_step")
    a.raw("53", "push        ebx")
    a.raw("57", "push        edi")
    a.raw("8B F8", "mov         edi,eax")
    t_mov("ebx", GP_POINTER)
    disp = tdisp("tune_rows") - 8 & 0xFFFFFFFF
    a.raw("8D 8C FD " + _le(disp), "lea         ecx,[ebp+edi*8+%08Xh]" % disp)
    a.raw("0F B7 41 04", "movzx       eax,word ptr [ecx+4]")         # step
    a.raw("0F AF C2", "imul        eax,edx")
    a.raw("03 84 BB " + _le(TUNE_VALUES - 4), "add         eax,dword ptr [ebx+edi*4+%08Xh]" % (TUNE_VALUES - 4))
    a.raw("0F BF 11", "movsx       edx,word ptr [ecx]")              # minimum (may be negative)
    a.raw("3B C2", "cmp         eax,edx")
    a.jcc_short("jge", "tune_step_min_ok")
    a.raw("8B C2", "mov         eax,edx")
    a.label("tune_step_min_ok")
    a.raw("0F B7 51 02", "movzx       edx,word ptr [ecx+2]")         # maximum
    a.raw("3B C2", "cmp         eax,edx")
    a.jcc_short("jle", "tune_step_max_ok")
    a.raw("8B C2", "mov         eax,edx")
    a.label("tune_step_max_ok")
    a.raw("89 84 BB " + _le(TUNE_VALUES - 4), "mov         dword ptr [ebx+edi*4+%08Xh],eax" % (TUNE_VALUES - 4))
    a.label("tune_step_refresh")
    a.call("tune_refresh")
    a.label("tune_step_done")
    a.call("play_toggle")
    a.raw("5F", "pop         edi")
    a.raw("5B", "pop         ebx")
    a.raw("C3", "ret")

    # In place of the call that handles the input of the main menu pages
    # (ecx = menu, [esp+4] = frame time): the tuning page and the page of own presets.
    def open_page(page):
        a.raw("6A %02X" % page, "push        %s" % _imm(page))
        a.raw("8B CE", "mov         ecx,esi")
        a.call(PAGE_SET)

    def select_item(item):
        a.raw("C7 86 48 01 00 00 %s" % _le(item), "mov         dword ptr [esi+00000148h],%s" % _imm(item))

    a.label("page_update")
    a.raw("8B 81 40 01 00 00", "mov         eax,dword ptr [ecx+00000140h]")
    a.raw("83 F8 %02X" % PAGE_CH, "cmp         eax,%s" % _imm(PAGE_CH))
    a.jcc_near("je", "ch_update")
    a.raw("83 F8 %02X" % PAGE_MODE, "cmp         eax,%s" % _imm(PAGE_MODE))
    a.jcc_near("je", "mode_update")
    a.raw("83 F8 %02X" % PAGE_CHAMP, "cmp         eax,%s" % _imm(PAGE_CHAMP))
    a.jcc_near("je", "champ_update")
    for page in (PAGE_OWN, PAGE_TUNING, PAGE_KART, PAGE_WORLD):
        a.raw("83 F8 %02X" % page, "cmp         eax,%s" % _imm(page))
        a.jcc_short("je", "page_update_go")
    a.raw("83 F8 %02X" % PAGE_OPP, "cmp         eax,%s" % _imm(PAGE_OPP))
    a.jcc_near("jne", PAGE_UPDATE_MAIN)
    a.label("page_update_go")
    a.raw("53", "push        ebx")
    a.raw("56", "push        esi")
    a.raw("57", "push        edi")
    a.raw("55", "push        ebp")
    a.raw("8B F1", "mov         esi,ecx")
    a.call("tune_base")
    a.raw("FF 74 24 14", "push        dword ptr [esp+14h]")          # the frame time
    a.raw("8B CE", "mov         ecx,esi")
    a.call(MENU_NAVIGATE)
    t_mov("ebx", GP_POINTER)
    a.raw("83 BE 40 01 00 00 %02X" % PAGE_OWN, "cmp         dword ptr [esi+00000140h],%s" % _imm(PAGE_OWN))
    a.jcc_near("je", "own_update")
    a.raw("83 BE 40 01 00 00 %02X" % PAGE_TUNING, "cmp         dword ptr [esi+00000140h],%s" % _imm(PAGE_TUNING))
    a.jcc_short("je", "page_update_input")
    a.call("tune_info")                           # a detail page: the explanation of the selected row
    a.label("page_update_input")
    t_lea("eax", STR_MENU_BACK)
    a.call("tune_pressed")
    a.jcc_short("jne", "tune_no_back")
    a.label("tune_back")                          # "menu back", or "Zurück" on "Kart", "Welt" and "Gegner"
    a.raw("83 BE 40 01 00 00 %02X" % PAGE_TUNING, "cmp         dword ptr [esi+00000140h],%s" % _imm(PAGE_TUNING))
    a.jcc_short("jne", "tune_sub_back")
    open_page(PAGE_CLASS)
    a.jmp("tune_out")
    a.label("tune_sub_back")                      # back to the page and the button that led here
    a.raw("BF " + _le(TUNE_ITEM_KART), "mov         edi,%s" % _imm(TUNE_ITEM_KART))
    a.raw("83 BE 40 01 00 00 %02X" % PAGE_KART, "cmp         dword ptr [esi+00000140h],%s" % _imm(PAGE_KART))
    a.jcc_short("je", "tune_sub_back_open")
    a.raw("BF " + _le(TUNE_ITEM_WORLD), "mov         edi,%s" % _imm(TUNE_ITEM_WORLD))
    a.raw("83 BE 40 01 00 00 %02X" % PAGE_WORLD, "cmp         dword ptr [esi+00000140h],%s" % _imm(PAGE_WORLD))
    a.jcc_short("je", "tune_sub_back_open")
    open_page(PAGE_CHAMP)                         # "Gegner": the championship page
    select_item(CHAMP_ITEM_OPP)
    a.jmp("tune_out")
    a.label("tune_sub_back_open")
    open_page(PAGE_TUNING)
    a.raw("89 BE 48 01 00 00", "mov         dword ptr [esi+00000148h],edi")
    a.jmp("tune_out")
    a.label("tune_no_back")
    t_lea("eax", STR_MENU_SELECT)
    a.call("tune_pressed")
    a.jcc_near("jne", "tune_no_select")
    a.raw("8B 86 48 01 00 00", "mov         eax,dword ptr [esi+00000148h]")   # the selected item
    a.call("tune_item_row")
    a.raw("85 C0", "test        eax,eax")
    a.jcc_short("jl", "tune_buttons")
    a.raw("8B 96 4C 01 00 00", "mov         edx,dword ptr [esi+0000014Ch]")   # arrow under the mouse: 1 left, 2 right
    a.raw("83 FA 01", "cmp         edx,1")
    a.jcc_short("jne", "tune_select_up")
    a.raw("C6 86 9D 01 00 00 01", "mov         byte ptr [esi+0000019Dh],1")   # clicked an arrow: keep the mouse on it
    a.jmp("tune_left")
    a.label("tune_select_up")
    a.raw("83 FA 02", "cmp         edx,2")
    a.jcc_near("jne", "tune_out")                 # "select" on the row itself does nothing, as for "Qualität"
    a.raw("C6 86 9D 01 00 00 01", "mov         byte ptr [esi+0000019Dh],1")
    a.jmp("tune_right")
    a.label("tune_buttons")
    a.raw("83 BE 40 01 00 00 %02X" % PAGE_TUNING, "cmp         dword ptr [esi+00000140h],%s" % _imm(PAGE_TUNING))
    a.jcc_near("jne", "tune_sub_button")          # "Kart", "Welt" and "Gegner" have one button: "Zurück"
    a.raw("8B 86 48 01 00 00", "mov         eax,dword ptr [esi+00000148h]")
    for item, page in ((TUNE_ITEM_KART, PAGE_KART), (TUNE_ITEM_WORLD, PAGE_WORLD),
                       (TUNE_ITEM_OWN, PAGE_OWN),
                       (TUNE_ITEM_NEXT, PAGE_CHARACTER), (TUNE_ITEM_BACK, PAGE_CLASS)):
        a.raw("83 F8 %02X" % item, "cmp         eax,%s" % _imm(item))
        a.jcc_short("jne", "tune_not_%d" % item)
        open_page(page)
        a.jmp("tune_out")
        a.label("tune_not_%d" % item)
    a.raw("83 F8 %02X" % TUNE_ITEM_RESET, "cmp         eax,%s" % _imm(TUNE_ITEM_RESET))
    a.jcc_near("jne", "tune_out")
    t_mov("eax", GP_POINTER)                      # "Zurücksetzen": the defaults, then the page again
    a.call("tune_reset")
    open_page(PAGE_TUNING)
    select_item(TUNE_ITEM_RESET)
    a.jmp("tune_out")
    a.label("tune_sub_button")                    # a detail page: "Zurück", unless no item is selected
    a.raw("83 BE 48 01 00 00 00", "cmp         dword ptr [esi+00000148h],0")   # (a click beside every item)
    a.jcc_near("jl", "tune_out")
    a.jmp("tune_sub_back")
    a.label("tune_no_select")
    t_lea("eax", STR_MENU_LEFT)
    a.call("tune_pressed")
    a.jcc_short("jne", "tune_no_left")
    a.raw("8B 86 48 01 00 00", "mov         eax,dword ptr [esi+00000148h]")
    a.call("tune_item_row")
    a.raw("85 C0", "test        eax,eax")
    a.jcc_near("jl", "tune_out")
    a.label("tune_left")
    a.raw("83 CA FF", "or          edx,0FFFFFFFFh")
    a.call("tune_change")
    a.jmp("tune_out")
    a.label("tune_no_left")
    t_lea("eax", STR_MENU_RIGHT)
    a.call("tune_pressed")
    a.jcc_near("jne", "tune_out")
    a.raw("8B 86 48 01 00 00", "mov         eax,dword ptr [esi+00000148h]")
    a.call("tune_item_row")
    a.raw("85 C0", "test        eax,eax")
    a.jcc_near("jl", "tune_out")
    a.label("tune_right")
    a.raw("BA 01 00 00 00", "mov         edx,1")
    a.call("tune_change")
    a.jmp("tune_out")

    # The page of own presets. ebx = GameParameters.
    a.label("own_update")
    t_lea("eax", STR_MENU_BACK)
    a.call("tune_pressed")
    a.jcc_short("jne", "own_no_back")
    a.label("own_back")
    open_page(PAGE_TUNING)
    select_item(TUNE_ITEM_OWN)                    # "Eigene Vorlagen"
    a.jmp("tune_out")
    a.label("own_no_back")
    t_lea("eax", STR_MENU_SELECT)
    a.call("tune_pressed")
    a.jcc_near("jne", "own_no_select")
    a.raw("8B 86 48 01 00 00", "mov         eax,dword ptr [esi+00000148h]")   # the selected item
    a.raw("85 C0", "test        eax,eax")
    a.jcc_short("jne", "own_buttons")
    a.raw("8B 96 4C 01 00 00", "mov         edx,dword ptr [esi+0000014Ch]")   # arrow under the mouse
    a.raw("83 FA 01", "cmp         edx,1")
    a.jcc_short("jne", "own_select_up")
    a.raw("C6 86 9D 01 00 00 01", "mov         byte ptr [esi+0000019Dh],1")
    a.jmp("own_left")
    a.label("own_select_up")
    a.raw("83 FA 02", "cmp         edx,2")
    a.jcc_near("jne", "tune_out")
    a.raw("C6 86 9D 01 00 00 01", "mov         byte ptr [esi+0000019Dh],1")
    a.jmp("own_right")
    a.label("own_buttons")
    a.raw("8B 8B " + _le(OWN_CUR), "mov         ecx,dword ptr [ebx+%08Xh]" % OWN_CUR)
    a.raw("83 E1 07", "and         ecx,7")
    a.raw("C1 E1 05", "shl         ecx,5")
    a.raw("8D BC 0B " + _le(OWN_BASE), "lea         edi,[ebx+ecx+%08Xh]" % OWN_BASE)   # the slot
    a.raw("83 F8 02", "cmp         eax,2")
    a.jcc_short("jne", "own_not_load")
    # "Laden": the slot's values into the tuning values, back to the tuning page
    a.raw("66 83 7F %02X 00" % OWN_FILLED, "cmp         word ptr [edi+%s],0" % _imm(OWN_FILLED))
    a.jcc_near("je", "tune_out")
    a.call("preset_load")
    a.raw("8B 83 " + _le(OWN_CUR), "mov         eax,dword ptr [ebx+%08Xh]" % OWN_CUR)
    a.raw("83 E0 07", "and         eax,7")
    a.raw("83 C0 %02X" % len(TUNE_PRESETS), "add         eax,%s" % _imm(len(TUNE_PRESETS)))
    a.raw("89 83 " + _le(TUNE_LAST), "mov         dword ptr [ebx+%08Xh],eax" % TUNE_LAST)
    a.call("play_toggle")
    open_page(PAGE_TUNING)
    select_item(0)
    a.jmp("tune_out")
    a.label("own_not_load")
    a.raw("83 F8 03", "cmp         eax,3")
    a.jcc_short("jne", "own_not_save")
    # "Speichern": the tuning values into the slot
    a.raw("33 C9", "xor         ecx,ecx")
    a.label("own_save_copy")
    a.raw("8B 84 8B " + _le(TUNE_VALUES), "mov         eax,dword ptr [ebx+ecx*4+%08Xh]" % TUNE_VALUES)
    a.raw("66 89 04 4F", "mov         word ptr [edi+ecx*2],ax")
    a.raw("41", "inc         ecx")
    a.raw("83 F9 %02X" % PRESET_VALUES, "cmp         ecx,%d" % PRESET_VALUES)
    a.jcc_short("jb", "own_save_copy")            # the last value (never 0) marks the slot as filled
    a.jmp("own_refresh")
    a.label("own_not_save")
    a.raw("83 F8 04", "cmp         eax,4")
    a.jcc_near("jne", "own_not_rename")
    # "Umbenennen": the game's name page, with the slot's name in the field
    open_page(PAGE_NAME)
    a.raw("C7 83 %s 01 00 00 00" % _le(OWN_FLAG), "mov         dword ptr [ebx+%08Xh],1" % OWN_FLAG)
    a.raw("81 EC 00 01 00 00", "sub         esp,100h")
    a.raw("8B 83 " + _le(OWN_CUR), "mov         eax,dword ptr [ebx+%08Xh]" % OWN_CUR)
    a.raw("83 E0 07", "and         eax,7")
    a.raw("8B D4", "mov         edx,esp")
    a.call("own_name")
    a.raw("8D 8E 7C 01 00 00", "lea         ecx,[esi+0000017Ch]")    # the typed name
    a.raw("8B D4", "mov         edx,esp")
    a.call("str_setc")
    a.raw("8B 86 90 01 00 00", "mov         eax,dword ptr [esi+00000190h]")   # its length
    a.raw("89 86 74 01 00 00", "mov         dword ptr [esi+00000174h],eax")   # = the cursor
    a.raw("68 " + _le(TXT_OWN_RENAME_TITLE), "push        %s" % _imm(TXT_OWN_RENAME_TITLE))
    a.raw("8D 44 24 04", "lea         eax,[esp+4]")
    a.raw("50", "push        eax")
    a.call("tune_printf")
    a.raw("83 C4 08", "add         esp,8")
    a.raw("B8 03 00 00 00", "mov         eax,3")                  # the title
    a.raw("8B D4", "mov         edx,esp")
    a.call("item_setstr")
    a.raw("8B 83 " + _le(OWN_CUR), "mov         eax,dword ptr [ebx+%08Xh]" % OWN_CUR)
    a.raw("83 E0 07", "and         eax,7")
    a.raw("40", "inc         eax")
    a.raw("50", "push        eax")
    a.raw("68 " + _le(TXT_OWN_RENAME), "push        %s" % _imm(TXT_OWN_RENAME))
    a.raw("8D 44 24 08", "lea         eax,[esp+8]")
    a.raw("50", "push        eax")
    a.call("tune_printf")
    a.raw("83 C4 0C", "add         esp,0Ch")
    a.raw("B8 02 00 00 00", "mov         eax,2")                  # the prompt
    a.raw("8B D4", "mov         edx,esp")
    a.call("item_setstr")
    a.raw("81 C4 00 01 00 00", "add         esp,100h")
    a.jmp("tune_out")
    a.label("own_not_rename")
    a.raw("83 F8 05", "cmp         eax,5")
    a.jcc_short("jne", "own_not_delete")
    # "Löschen": values, mark and name of the slot
    a.raw("33 C0", "xor         eax,eax")
    a.raw("B9 %s" % _le(OWN_SLOT // 4), "mov         ecx,%s" % _imm(OWN_SLOT // 4))
    a.raw("F3 AB", "rep stos    dword ptr es:[edi]")
    a.jmp_short("own_refresh")
    a.label("own_not_delete")
    a.raw("83 F8 06", "cmp         eax,6")
    a.jcc_near("je", "own_back")                  # "Zurück"
    a.jmp("tune_out")
    a.label("own_no_select")
    t_lea("eax", STR_MENU_LEFT)
    a.call("tune_pressed")
    a.jcc_short("jne", "own_no_left")
    a.raw("83 BE 48 01 00 00 00", "cmp         dword ptr [esi+00000148h],0")
    a.jcc_near("jne", "tune_out")
    a.label("own_left")
    a.raw("83 CA FF", "or          edx,0FFFFFFFFh")
    a.jmp_short("own_move")
    a.label("own_no_left")
    t_lea("eax", STR_MENU_RIGHT)
    a.call("tune_pressed")
    a.jcc_near("jne", "tune_out")
    a.raw("83 BE 48 01 00 00 00", "cmp         dword ptr [esi+00000148h],0")
    a.jcc_near("jne", "tune_out")
    a.label("own_right")
    a.raw("BA 01 00 00 00", "mov         edx,1")
    a.label("own_move")                           # the next or previous slot, round
    a.raw("01 93 " + _le(OWN_CUR), "add         dword ptr [ebx+%08Xh],edx" % OWN_CUR)
    a.raw("83 A3 %s 07" % _le(OWN_CUR), "and         dword ptr [ebx+%08Xh],7" % OWN_CUR)
    a.label("own_refresh")                        # the slot and its values show their new texts
    a.raw("33 C0", "xor         eax,eax")
    a.call("tune_settext")
    a.raw("B8 01 00 00 00", "mov         eax,1")
    a.call("tune_settext")
    a.call("play_toggle")
    a.label("tune_out")
    a.raw("B8 9D FF FF FF", "mov         eax,0FFFFFF9Dh")            # what the stock handler returns
    a.raw("5D", "pop         ebp")
    a.raw("5F", "pop         edi")
    a.raw("5E", "pop         esi")
    a.raw("5B", "pop         ebx")
    a.raw("C2 04 00", "ret         4")

    # The championship page (ecx = menu, [esp+4] = frame time) with the button "Gegner" behind
    # the game's items (and a label behind it). The game steps through the items by their number, so "menu down" would reach
    # the button behind "Zurück". Before the game's handler runs, the selected item is set so
    # that the game's step lands where the page shows it: the last track row (the championship,
    # while the tracks are labels) -> the button -> "Starte Meisterschaft". "menu select" on the
    # button opens the page "Gegner"; the game's handler does nothing for that item.
    def champ_step(frm, to, label):               # from item `frm`: the game steps on from `to`
        a.raw("B8 " + _le(to), "mov         eax,%s" % _imm(to))
        a.raw("83 FF %02X" % frm, "cmp         edi,%s" % _imm(frm))
        a.jcc_short("je", label)

    a.label("champ_update")
    a.raw("53", "push        ebx")
    a.raw("56", "push        esi")
    a.raw("57", "push        edi")
    a.raw("55", "push        ebp")
    a.raw("8B F1", "mov         esi,ecx")
    a.call("tune_base")
    a.raw("8B 86 38 01 00 00", "mov         eax,dword ptr [esi+00000138h]")
    a.raw("2B 86 34 01 00 00", "sub         eax,dword ptr [esi+00000134h]")
    size = (CHAMP_ITEM_OPP + 2) * MENU_ITEM_SIZE
    a.raw("3D " + _le(size), "cmp         eax,%s" % _imm(size))
    a.jcc_near("jne", "champ_update_game")        # no button (the tuning class is locked)
    a.raw("8B BE 48 01 00 00", "mov         edi,dword ptr [esi+00000148h]")   # the selected item
    t_lea("eax", STR_MENU_DOWN)
    a.call("tune_pressed")
    a.jcc_short("jne", "champ_no_down")
    champ_step(CHAMP_ITEM_OPP, CHAMP_ITEM_START - 1, "champ_set")
    champ_step(CHAMP_ITEM_BACK, -1, "champ_set")
    champ_step(4, CHAMP_ITEM_OPP - 1, "champ_set")
    a.raw("85 FF", "test        edi,edi")
    a.jcc_short("jne", "champ_select")
    a.raw("8B 8E 34 01 00 00", "mov         ecx,dword ptr [esi+00000134h]")
    a.raw("83 79 %02X 00" % MENU_ITEM_SIZE, "cmp         dword ptr [ecx+%s],0" % _imm(MENU_ITEM_SIZE))   # item 1: a label?
    a.jcc_short("jne", "champ_select")
    a.jmp_short("champ_set")
    a.label("champ_no_down")
    t_lea("eax", STR_MENU_UP)
    a.call("tune_pressed")
    a.jcc_short("jne", "champ_select")
    champ_step(CHAMP_ITEM_START, CHAMP_ITEM_OPP + 1, "champ_set")
    champ_step(CHAMP_ITEM_OPP, CHAMP_ITEM_START, "champ_set")   # (the game skips the tracks while they are labels)
    champ_step(0, CHAMP_ITEM_BACK + 1, "champ_set")
    a.jmp_short("champ_select")
    a.label("champ_set")
    a.raw("89 86 48 01 00 00", "mov         dword ptr [esi+00000148h],eax")
    a.label("champ_select")
    t_lea("eax", STR_MENU_SELECT)
    a.call("tune_pressed")
    a.jcc_short("jne", "champ_update_game")
    a.raw("83 BE 48 01 00 00 %02X" % CHAMP_ITEM_OPP, "cmp         dword ptr [esi+00000148h],%s" % _imm(CHAMP_ITEM_OPP))
    a.jcc_short("jne", "champ_update_game")
    open_page(PAGE_OPP)
    a.jmp("tune_out")
    a.label("champ_update_game")
    a.raw("8B CE", "mov         ecx,esi")
    a.raw("5D", "pop         ebp")
    a.raw("5F", "pop         edi")
    a.raw("5E", "pop         esi")
    a.raw("5B", "pop         ebx")
    a.jmp(PAGE_UPDATE_MAIN)

    # In place of the call that handles the result pages, the name entry among them
    # (ecx = menu, [esp+4] = frame time): while a slot is renamed, "Weiter" stores the typed
    # name in the slot and "menu back" leaves it as it was; both return to the page of own
    # presets. Typing is left to the game.
    a.label("result_update")
    a.raw("83 B9 40 01 00 00 %02X" % PAGE_NAME, "cmp         dword ptr [ecx+00000140h],%s" % _imm(PAGE_NAME))
    a.jcc_near("jne", RESULT_UPDATE)
    a.raw("53", "push        ebx")
    a.raw("56", "push        esi")
    a.raw("57", "push        edi")
    a.raw("55", "push        ebp")
    a.raw("8B F1", "mov         esi,ecx")
    a.call("tune_base")
    t_mov("ebx", GP_POINTER)
    a.raw("83 BB %s 01" % _le(OWN_FLAG), "cmp         dword ptr [ebx+%08Xh],1" % OWN_FLAG)
    a.jcc_near("jne", "name_confirm_check")
    t_lea("eax", STR_MENU_BACK)
    a.call("tune_pressed")
    a.jcc_short("je", "rename_done")
    t_lea("eax", STR_MENU_SELECT)
    a.call("tune_pressed")
    a.jcc_near("jne", "rename_game")
    a.raw("83 BE 48 01 00 00 00", "cmp         dword ptr [esi+00000148h],0")   # "Weiter"
    a.jcc_near("jne", "rename_game")
    a.raw("8D 8E 7C 01 00 00", "lea         ecx,[esi+0000017Ch]")
    a.call(STR_CSTR)
    a.raw("8B 8B " + _le(OWN_CUR), "mov         ecx,dword ptr [ebx+%08Xh]" % OWN_CUR)
    a.raw("83 E1 07", "and         ecx,7")
    a.raw("C1 E1 05", "shl         ecx,5")
    a.raw("8D 8C 0B " + _le(OWN_BASE + OWN_NAME), "lea         ecx,[ebx+ecx+%08Xh]" % (OWN_BASE + OWN_NAME))
    a.raw("6A 10", "push        10h")
    a.raw("50", "push        eax")
    a.raw("51", "push        ecx")
    t_call_import(IMP_LSTRCPYN)
    a.label("rename_done")
    open_page(PAGE_OWN)                           # ends the renaming
    select_item(4)
    a.jmp("tune_out")
    # A highscore name: "Weiter" with an empty field takes the stored name; a typed one is stored
    # (time trial names are stored again in name_confirm, which also stamps the phantom).
    a.label("name_confirm_check")
    t_lea("eax", STR_MENU_SELECT)
    a.call("tune_pressed")
    a.jcc_near("jne", "rename_game")
    a.raw("83 BE 48 01 00 00 00", "cmp         dword ptr [esi+00000148h],0")   # "Weiter"
    a.jcc_near("jne", "rename_game")
    a.raw("83 BE 90 01 00 00 00", "cmp         dword ptr [esi+00000190h],0")   # the typed name's length
    a.jcc_short("jne", "name_confirm_store")
    a.call("name_prefill")
    a.jmp_short("rename_game")
    a.label("name_confirm_store")
    a.raw("8D 8E 7C 01 00 00", "lea         ecx,[esi+0000017Ch]")
    a.call(STR_CSTR)
    a.raw("8D BB " + _le(NAME_OFFSET), "lea         edi,[ebx+%08Xh]" % NAME_OFFSET)
    a.raw("33 C9", "xor         ecx,ecx")
    for off in (0, 4, 8, 12):
        a.raw("89 4F %02X" % off if off else "89 0F",
              "mov         dword ptr [edi+%s],ecx" % _imm(off) if off else "mov         dword ptr [edi],ecx")
    a.raw("6A %02X" % (PHANTOM_NAME_LEN + 1), "push        %s" % _imm(PHANTOM_NAME_LEN + 1))
    a.raw("50", "push        eax")
    a.raw("57", "push        edi")
    t_call_import(IMP_LSTRCPYN)
    a.raw("C7 83 %s %s" % (_le(NAME_MARK_OFFSET), _le(NAME_MARK)),
          "mov         dword ptr [ebx+%08Xh],%s" % (NAME_MARK_OFFSET, _imm(NAME_MARK)))
    a.label("rename_game")
    a.raw("8B CE", "mov         ecx,esi")
    a.raw("5D", "pop         ebp")
    a.raw("5F", "pop         edi")
    a.raw("5E", "pop         esi")
    a.raw("5B", "pop         ebx")
    a.jmp(RESULT_UPDATE)

    # -- "60 FPS physics" switch -------------------------------------------------
    magic = _le(PHYS_MAGIC)

    def phys_flag():                     # flags: equal = switched on; clobbers eax, ecx
        a.call(GP_GET)
        a.raw("8B 40 4C", "mov         eax,dword ptr [eax+4Ch]")
        a.raw("C1 E8 08", "shr         eax,8")
        a.raw("3D " + magic, "cmp         eax,%s" % _imm(PHYS_MAGIC))

    def unlock_flag():                   # flags: equal = "Alles freigeschaltet" is on; clobbers eax, ecx
        a.call(GP_GET)
        a.raw("81 B8 %s %s" % (_le(UNLOCK_MARK), _le(UNLOCK_MAGIC)),
              "cmp         dword ptr [eax+%08Xh],%s" % (UNLOCK_MARK, _imm(UNLOCK_MAGIC)))

    # Wheel spring/damper -> the solver's soft-contact pair, once per wheel and step.
    # Stock:  P0 = 1 / (dt * (c + k*dt))      P1 = k*dt / (c + k*dt)
    # The solver uses 1/P0 as damper and P1/(P0*dt) as spring, i.e. the spring is
    # k*dt: at 200 FPS (dt = 5 ms) it is 3.3 times softer than at 60 FPS.
    # Switched on: P0 = 1 / (h0 * (c + k*h0)), P1 = k*dt / (c + k*h0) with h0 = 1/60 s,
    # which is the 60 FPS spring and damper at any step length.
    # In: st0 = k, st1 = c, eax = &P0/P1, dt at [esp+0E8h].
    a.label("suspension")
    a.raw("50", "push        eax")
    a.raw("51", "push        ecx")
    phys_flag()
    a.raw("59", "pop         ecx")
    a.raw("58", "pop         eax")
    a.jcc_short("je", "suspension_fixed")
    a.raw("D8 8C 24 E8 00 00 00", "fmul        dword ptr [esp+000000E8h]")   # displaced; stock path
    a.jmp(0x0043FB8F)
    a.label("suspension_fixed")
    a.raw("68 " + _le(REFERENCE_STEP), "push        %s" % _imm(REFERENCE_STEP))  # h0
    a.raw("D9 C0", "fld         st(0)")
    a.raw("D8 0C 24", "fmul        dword ptr [esp]")
    a.raw("DE C2", "faddp       st(2),st")                               # k, s = c + k*h0
    a.raw("D8 8C 24 EC 00 00 00", "fmul        dword ptr [esp+000000ECh]")   # k*dt
    a.raw("D9 54 24 14", "fst         dword ptr [esp+14h]")              # the stock code leaves k*dt here
    a.raw("D8 F1", "fdiv        st,st(1)")
    a.raw("D9 58 04", "fstp        dword ptr [eax+4]")                   # P1
    a.raw("D8 0C 24", "fmul        dword ptr [esp]")                     # h0 * s
    a.raw("D9 E8", "fld1")
    a.raw("DE F1", "fdivrp      st(1),st")
    a.raw("D9 18", "fstp        dword ptr [eax]")                        # P0
    a.raw("83 C4 04", "add         esp,4")
    a.raw("8B 5C 24 40", "mov         ebx,dword ptr [esp+40h]")          # what the skipped stock code sets up
    a.raw("33 ED", "xor         ebp,ebp")
    a.raw("8B D0", "mov         edx,eax")
    a.raw("8B 4C 24 44", "mov         ecx,dword ptr [esp+44h]")
    a.jmp(0x0043FBCF)

    # Options menu: the stock loop now stops after item 6 (quality); this adds the
    # heading (7), the switch (8) and "Zurück" (9). edi = menu, ebx = 0.
    def text_to_item(y, add_fn):         # GetText arguments are on the stack already
        a.call(TEXTMGR_GET)
        a.raw("8B C8", "mov         ecx,eax")
        a.call(GET_TEXT)
        a.raw("68 " + _le(y), "push        %s" % _imm(y))
        a.raw("8B C8", "mov         ecx,eax")
        a.call(STR_CSTR)
        a.raw("50", "push        eax")
        a.raw("8B CF", "mov         ecx,edi")
        a.call(add_fn)

    def add_item(text_id, y, add_fn):
        a.raw("53", "push        ebx")                       # line 0
        a.raw("8D 44 24 04", "lea         eax,[esp+4]")      # temp std::string
        a.raw("68 " + _le(text_id), "push        %s" % _imm(text_id))
        a.raw("50", "push        eax")
        text_to_item(y, add_fn)

    def drop_temp():
        a.raw("8B CC", "mov         ecx,esp")
        a.call(STR_DTOR)

    def switch_value(flag_fn, y):        # the value item of a switch: "Aus" / "An" with arrows
        flag_fn()
        a.raw("0F 94 C0", "sete        al")
        a.raw("0F B6 C0", "movzx       eax,al")
        a.raw("05 " + _le(TXT_PHYS_OFF), "add         eax,%s" % _imm(TXT_PHYS_OFF))
        a.raw("53", "push        ebx")
        a.raw("50", "push        eax")
        a.raw("8D 44 24 08", "lea         eax,[esp+8]")
        a.raw("50", "push        eax")
        text_to_item(y, ADD_BUTTON)
        a.raw("C7 00 03 00 00 00", "mov         dword ptr [eax],3")      # value item with arrows, like "Qualität"
        drop_temp()

    a.label("options_items")
    a.raw("83 EC 1C", "sub         esp,1Ch")
    add_item(TXT_UNLOCK_LABEL, OPTIONS_Y_UNLOCK_LABEL, ADD_LABEL)
    drop_temp()
    switch_value(unlock_flag, OPTIONS_Y_UNLOCK_VALUE)
    add_item(TXT_PHYS_LABEL, OPTIONS_Y_PHYS_LABEL, ADD_LABEL)
    drop_temp()
    switch_value(phys_flag, OPTIONS_Y_PHYS_VALUE)
    add_item(TXT_BACK_OPTIONS, OPTIONS_Y_BACK, ADD_BUTTON)
    drop_temp()
    a.raw("83 C4 1C", "add         esp,1Ch")
    a.raw("53", "push        ebx")                                   # displaced
    a.raw("8D 8C 24 A0 01 00 00", "lea         ecx,[esp+000001A0h]")  # displaced
    a.jmp(0x004206F8)

    # Flip a switch, refresh its menu text, play the menu's toggle sound.
    # esi = menu; keeps ebx, esi, edi, ebp.
    a.label("phys_toggle")
    a.call(GP_GET)
    a.raw("8B 48 4C", "mov         ecx,dword ptr [eax+4Ch]")
    a.raw("8B D1", "mov         edx,ecx")
    a.raw("C1 EA 08", "shr         edx,8")
    a.raw("81 E1 FF 00 00 00", "and         ecx,0FFh")               # keep the game's own bool
    a.raw("81 FA " + magic, "cmp         edx,%s" % _imm(PHYS_MAGIC))
    a.jcc_short("je", "phys_toggle_store")
    a.raw("81 C9 " + _le(PHYS_MAGIC << 8), "or          ecx,%s" % _imm(PHYS_MAGIC << 8))
    a.label("phys_toggle_store")
    a.raw("89 48 4C", "mov         dword ptr [eax+4Ch],ecx")
    a.raw("C1 E9 08", "shr         ecx,8")
    a.raw("BA " + _le(OPTIONS_ITEM_PHYS * MENU_ITEM_SIZE + 8),
          "mov         edx,%s" % _imm(OPTIONS_ITEM_PHYS * MENU_ITEM_SIZE + 8))
    a.jmp_short("switch_text")

    a.label("unlock_toggle")
    a.call(GP_GET)
    a.raw("33 C9", "xor         ecx,ecx")
    a.raw("81 B8 %s %s" % (_le(UNLOCK_MARK), _le(UNLOCK_MAGIC)),
          "cmp         dword ptr [eax+%08Xh],%s" % (UNLOCK_MARK, _imm(UNLOCK_MAGIC)))
    a.jcc_short("je", "unlock_toggle_store")
    a.raw("B9 " + _le(UNLOCK_MAGIC), "mov         ecx,%s" % _imm(UNLOCK_MAGIC))
    a.label("unlock_toggle_store")
    a.raw("89 88 " + _le(UNLOCK_MARK), "mov         dword ptr [eax+%08Xh],ecx" % UNLOCK_MARK)
    a.raw("BA " + _le(OPTIONS_ITEM_UNLOCK * MENU_ITEM_SIZE + 8),
          "mov         edx,%s" % _imm(OPTIONS_ITEM_UNLOCK * MENU_ITEM_SIZE + 8))

    # ecx = the switch's new state (nonzero: on), edx = offset of its item's text in the item list
    a.label("switch_text")
    a.raw("85 C9", "test        ecx,ecx")
    a.raw("0F 95 C1", "setne       cl")
    a.raw("0F B6 C9", "movzx       ecx,cl")
    a.raw("81 C1 " + _le(TXT_PHYS_OFF), "add         ecx,%s" % _imm(TXT_PHYS_OFF))
    a.raw("83 EC 1C", "sub         esp,1Ch")
    a.raw("52", "push        edx")
    a.raw("6A 00", "push        0")
    a.raw("51", "push        ecx")
    a.raw("8D 44 24 0C", "lea         eax,[esp+0Ch]")
    a.raw("50", "push        eax")
    a.call(TEXTMGR_GET)
    a.raw("8B C8", "mov         ecx,eax")
    a.call(GET_TEXT)
    a.raw("50", "push        eax")
    a.raw("8B 8E 34 01 00 00", "mov         ecx,dword ptr [esi+00000134h]")
    a.raw("03 4C 24 04", "add         ecx,dword ptr [esp+4]")
    a.call(STR_ASSIGN)
    a.raw("5A", "pop         edx")
    drop_temp()
    a.raw("83 C4 1C", "add         esp,1Ch")
    a.label("play_toggle")                    # also called on its own: the menu's toggle sound
    a.raw("6A 01", "push        1")
    a.call("phys_toggle_pc")                  # position independent address of "MENU_toggle"
    a.label("phys_toggle_pc")
    a.raw("58", "pop         eax")
    disp = (STR_MENU_TOGGLE - a.labels["phys_toggle_pc"]) & 0xFFFFFFFF
    a.raw("8D 80 " + _le(disp), "lea         eax,[eax+%08Xh]" % disp)
    a.raw("50", "push        eax")
    a.call(SOUNDMGR_GET)
    a.raw("8B C8", "mov         ecx,eax")
    a.call(FIND_SOUND)
    a.raw("85 C0", "test        eax,eax")
    a.jcc_short("je", "phys_toggle_done")
    a.raw("8B 10", "mov         edx,dword ptr [eax]")
    a.raw("8B C8", "mov         ecx,eax")
    a.raw("FF 52 28", "call        dword ptr [edx+28h]")
    a.label("phys_toggle_done")
    a.raw("C3", "ret")

    # "menu select": returns the item number for the stock jump table in eax.
    a.label("options_select")
    a.raw("8B 86 48 01 00 00", "mov         eax,dword ptr [esi+00000148h]")
    a.raw("83 F8 07", "cmp         eax,7")
    a.jcc_short("jb", "options_select_done")          # 1..6: stock items
    a.raw("83 F8 %02X" % OPTIONS_ITEM_BACK, "cmp         eax,%s" % _imm(OPTIONS_ITEM_BACK))
    a.jcc_short("ja", "options_select_done")
    a.jcc_short("je", "options_select_back")
    a.raw("8B D0", "mov         edx,eax")
    a.raw("A8 01", "test        al,1")
    a.jcc_short("jne", "options_select_none")         # 7, 9: the headings; 8, 10: the switches
    a.raw("8B 86 4C 01 00 00", "mov         eax,dword ptr [esi+0000014Ch]")
    a.raw("48", "dec         eax")
    a.raw("83 F8 01", "cmp         eax,1")
    a.jcc_short("ja", "options_select_toggle")
    a.raw("C6 86 9D 01 00 00 01", "mov         byte ptr [esi+0000019Dh],1")   # clicked an arrow: keep the mouse on it
    a.label("options_select_toggle")
    a.raw("8B C2", "mov         eax,edx")
    a.call("options_toggle")
    a.label("options_select_none")
    a.raw("B8 02 00 00 00", "mov         eax,2")      # item 2 is a heading: the stock table does nothing
    a.raw("C3", "ret")
    a.label("options_select_back")
    a.raw("B8 07 00 00 00", "mov         eax,7")      # "Zurück" moved from item 7 to OPTIONS_ITEM_BACK
    a.label("options_select_done")
    a.raw("C3", "ret")

    # eax = item: flips the switch of that item, if it is one. Keeps ebx, esi, edi, ebp.
    a.label("options_toggle")
    a.raw("83 F8 %02X" % OPTIONS_ITEM_UNLOCK, "cmp         eax,%s" % _imm(OPTIONS_ITEM_UNLOCK))
    a.jcc_near("je", "unlock_toggle")
    a.raw("83 F8 %02X" % OPTIONS_ITEM_PHYS, "cmp         eax,%s" % _imm(OPTIONS_ITEM_PHYS))
    a.jcc_near("je", "phys_toggle")
    a.raw("C3", "ret")

    # "menu left" / "menu right" on a switch
    a.label("options_left")
    a.raw("8B 86 48 01 00 00", "mov         eax,dword ptr [esi+00000148h]")
    a.call("options_toggle")
    a.raw("8B 86 48 01 00 00", "mov         eax,dword ptr [esi+00000148h]")   # displaced
    a.raw("C3", "ret")

    a.label("options_right")
    a.raw("8B 86 48 01 00 00", "mov         eax,dword ptr [esi+00000148h]")
    a.call("options_toggle")
    a.raw("8B B6 48 01 00 00", "mov         esi,dword ptr [esi+00000148h]")   # displaced
    a.raw("C3", "ret")

    # -- phantom karts ------------------------------------------------------------
    def stored_name_to(reg_hex, reg):    # copy the 12 name bytes at edi to [reg+8]
        for i in range(0, PHANTOM_NAME_LEN, 4):
            a.raw("8B 07" if i == 0 else "8B 47 %02X" % i,
                  "mov         eax,dword ptr [edi%s]" % ("+%s" % _imm(i) if i else ""))
            a.raw("89 %s %02X" % (reg_hex, PHANTOM_NAME + i),
                  "mov         dword ptr [%s+%s],eax" % (reg, _imm(PHANTOM_NAME + i)))

    def table_entry(modrm, reg):         # reg = table entry for the class and track of the header at esi; ebx = GameParameters
        a.raw("8B 46 50", "mov         eax,dword ptr [esi+50h]")
        a.raw("8B 4E 4C", "mov         ecx,dword ptr [esi+4Ch]")
        a.call("slot_eax_ecx")
        a.raw("6B C0 6C", "imul        eax,eax,6Ch")
        disp = PHANTOM_TABLE - PHANTOM_SIZE              # track numbers start at 1
        a.raw("8D %s 03 %s" % (modrm, _le(disp)), "lea         %s,[ebx+eax+%08Xh]" % (reg, disp))

    def phantom_path(pc):                # 40h bytes on the stack: "data\Phantom\phantom-<class+1>-<track>.mhk2"
        a.raw("83 EC 40", "sub         esp,40h")
        a.raw("FF 76 4C", "push        dword ptr [esi+4Ch]")
        a.raw("8B 46 50", "mov         eax,dword ptr [esi+50h]")
        a.raw("40", "inc         eax")
        a.raw("50", "push        eax")
        lea_eax(pc, STR_PHANTOM_FMT)
        a.raw("50", "push        eax")
        a.raw("8D 44 24 0C", "lea         eax,[esp+0Ch]")
        a.raw("50", "push        eax")
        call_import(pc, IMP_WSPRINTF)
        a.raw("83 C4 10", "add         esp,10h")

    # Time trial finish, just before the header of new-phantom.mhk2 is written.
    # The game has filled in version, id, track, class, character and the times,
    # but bytes 5..31 are still those of the ghost it loaded at the start (with
    # mhk2_manager: the other driver's name and checksum). esi = header.
    a.label("phantom_stamp")
    a.raw("33 C0", "xor         eax,eax")
    for off in range(4, 0x20, 4):
        a.raw("89 46 %02X" % off, "mov         dword ptr [esi+%s],eax" % _imm(off))
    a.call(GP_GET)
    a.raw("81 B8 %s %s" % (_le(NAME_MARK_OFFSET), _le(NAME_MARK)),
          "cmp         dword ptr [eax+%08Xh],%s" % (NAME_MARK_OFFSET, _imm(NAME_MARK)))
    a.jcc_short("jne", "phantom_stamp_done")
    for i in range(0, PHANTOM_NAME_LEN, 4):
        a.raw("8B 88 " + _le(NAME_OFFSET + i), "mov         ecx,dword ptr [eax+%08Xh]" % (NAME_OFFSET + i))
        a.raw("89 4E %02X" % (PHANTOM_NAME + i), "mov         dword ptr [esi+%s],ecx" % _imm(PHANTOM_NAME + i))
    a.label("phantom_stamp_done")
    a.raw("8B 45 00", "mov         eax,dword ptr [ebp]")     # displaced
    a.raw("6A 6C", "push        6Ch")                          # displaced
    a.jmp(0x00406C6E)

    # Time trial finish, in place of the call that closes new-phantom.mhk2: a run
    # that is faster than the phantom of its track and class replaces it. A track
    # without phantom file has 10:39.99 in the table, so the first run always wins.
    a.label("phantom_promote")
    a.raw("FF 74 24 04", "push        dword ptr [esp+4]")
    a.call(FILE_CLOSE)
    a.raw("60", "pushad")
    a.call("tune_base")
    t_active()
    a.jcc_near("jne", "ch_promote")               # a challenge run is no record
    pic_base("promote_pc")
    a.call(GP_GET)
    a.raw("8B D8", "mov         ebx,eax")
    a.raw("8D B3 " + _le(PHANTOM_RUN), "lea         esi,[ebx+%08Xh]" % PHANTOM_RUN)
    table_entry("BC", "edi")
    a.raw("D9 46 58", "fld         dword ptr [esi+58h]")
    a.raw("D8 5F 58", "fcomp       dword ptr [edi+58h]")
    a.raw("DF E0", "fnstsw      ax")
    a.raw("80 E4 45", "and         ah,45h")
    a.raw("80 FC 01", "cmp         ah,1")                 # strictly faster
    a.jcc_short("jne", "phantom_promote_done")
    phantom_path("promote_pc")
    a.raw("6A 00", "push        0")                       # replace an existing file
    a.raw("8D 44 24 04", "lea         eax,[esp+4]")
    a.raw("50", "push        eax")
    lea_eax("promote_pc", STR_NEW_PHANTOM)
    a.raw("50", "push        eax")
    call_import("promote_pc", IMP_COPYFILE)
    a.raw("83 C4 40", "add         esp,40h")
    a.raw("85 C0", "test        eax,eax")
    a.jcc_short("je", "phantom_promote_done")
    a.raw("B9 %s" % _le(PHANTOM_SIZE // 4), "mov         ecx,%s" % _imm(PHANTOM_SIZE // 4))
    a.raw("F3 A5", "rep movs    dword ptr es:[edi],dword ptr [esi]")   # the menus read the table, not the file
    a.label("phantom_promote_done")
    a.raw("61", "popad")
    a.raw("C2 04 00", "ret         4")

    # ... a challenge run (ebp = tune_T, inside the pushad above): only a daily one that beats
    # the best time of the day is kept, as data\Phantom\daily-<day>.mhk2, its time in DAILY_ENTRY.
    a.label("ch_promote")
    t_mem("8B", 0, CH_DAY, "mov         eax,dword ptr %s")
    a.raw("85 C0", "test        eax,eax")
    a.jcc_near("je", "phantom_promote_done")
    t_mov("ebx", GP_POINTER)
    a.raw("8D B3 " + _le(PHANTOM_RUN), "lea         esi,[ebx+%08Xh]" % PHANTOM_RUN)
    a.raw("81 BB %s %s" % (_le(DAILY_ENTRY), _le(DAILY_MAGIC)),
          "cmp         dword ptr [ebx+%08Xh],%s" % (DAILY_ENTRY, _imm(DAILY_MAGIC)))
    a.jcc_short("jne", "ch_promote_save")
    a.raw("3B 83 " + _le(DAILY_ENTRY + 4), "cmp         eax,dword ptr [ebx+%08Xh]" % (DAILY_ENTRY + 4))
    a.jcc_short("jne", "ch_promote_save")
    a.raw("D9 46 58", "fld         dword ptr [esi+58h]")
    a.raw("D8 9B " + _le(DAILY_ENTRY + 8), "fcomp       dword ptr [ebx+%08Xh]" % (DAILY_ENTRY + 8))
    a.raw("DF E0", "fnstsw      ax")
    a.raw("F6 C4 01", "test        ah,1")
    a.jcc_near("je", "phantom_promote_done")        # not faster than the best of the day
    a.label("ch_promote_save")
    a.raw("83 EC 40", "sub         esp,40h")
    t_mem("FF", 6, CH_DAY, "push        dword ptr %s")
    t_lea("eax", "ch_daily_fmt")
    a.raw("50", "push        eax")
    a.raw("8D 44 24 08", "lea         eax,[esp+8]")
    a.raw("50", "push        eax")
    t_call_import(IMP_WSPRINTF)
    a.raw("83 C4 0C", "add         esp,0Ch")
    a.raw("6A 00", "push        0")                       # replace the file of the day
    a.raw("8D 44 24 04", "lea         eax,[esp+4]")
    a.raw("50", "push        eax")
    t_lea("eax", STR_NEW_PHANTOM)
    a.raw("50", "push        eax")
    t_call_import(IMP_COPYFILE)
    a.raw("83 C4 40", "add         esp,40h")
    a.raw("85 C0", "test        eax,eax")
    a.jcc_near("je", "phantom_promote_done")
    a.raw("C7 83 %s %s" % (_le(DAILY_ENTRY), _le(DAILY_MAGIC)),
          "mov         dword ptr [ebx+%08Xh],%s" % (DAILY_ENTRY, _imm(DAILY_MAGIC)))
    t_mem("8B", 0, CH_DAY, "mov         eax,dword ptr %s")
    a.raw("89 83 " + _le(DAILY_ENTRY + 4), "mov         dword ptr [ebx+%08Xh],eax" % (DAILY_ENTRY + 4))
    a.raw("8B 46 58", "mov         eax,dword ptr [esi+58h]")
    a.raw("89 83 " + _le(DAILY_ENTRY + 8), "mov         dword ptr [ebx+%08Xh],eax" % (DAILY_ENTRY + 8))
    a.jmp("phantom_promote_done")

    # A name was typed for a new time trial highscore (in place of the call that
    # stores the highscore; ecx = menu, [esp+4] = kart). Remember the name for the
    # phantoms of later runs. The phantom of this run is on disk already, without
    # it: write the name into new-phantom.mhk2, and into the track's phantom file
    # if that is this run and no mhk2_manager checksum covers its header.
    a.label("name_confirm")
    a.raw("60", "pushad")
    a.raw("8B F1", "mov         esi,ecx")
    pic_base("name_pc")
    a.call(GP_GET)
    a.raw("8B D8", "mov         ebx,eax")
    a.raw("83 BE 90 01 00 00 00", "cmp         dword ptr [esi+00000190h],0")   # an empty name: the stored one
    a.jcc_short("jne", "name_confirm_typed")
    a.call("name_prefill")
    a.label("name_confirm_typed")
    a.raw("83 7B 1C 00", "cmp         dword ptr [ebx+1Ch],0")        # time trial, not a duel
    a.jcc_near("jne", "name_confirm_done")
    a.raw("83 7C 24 24 00", "cmp         dword ptr [esp+24h],0")
    a.jcc_near("jne", "name_confirm_done")
    a.raw("8D 8E 7C 01 00 00", "lea         ecx,[esi+0000017Ch]")
    a.call(STR_CSTR)
    a.raw("8D BB " + _le(NAME_OFFSET), "lea         edi,[ebx+%08Xh]" % NAME_OFFSET)
    a.raw("33 C9", "xor         ecx,ecx")
    a.raw("89 0F", "mov         dword ptr [edi],ecx")
    for off in (4, 8, 12):
        a.raw("89 4F %02X" % off, "mov         dword ptr [edi+%s],ecx" % _imm(off))
    a.raw("6A %02X" % (PHANTOM_NAME_LEN + 1), "push        %s" % _imm(PHANTOM_NAME_LEN + 1))
    a.raw("50", "push        eax")
    a.raw("57", "push        edi")
    call_import("name_pc", IMP_LSTRCPYN)                  # at most 12 characters, zero padded
    a.raw("C7 83 %s %s" % (_le(NAME_MARK_OFFSET), _le(NAME_MARK)),
          "mov         dword ptr [ebx+%08Xh],%s" % (NAME_MARK_OFFSET, _imm(NAME_MARK)))
    a.raw("8D B3 " + _le(PHANTOM_RUN), "lea         esi,[ebx+%08Xh]" % PHANTOM_RUN)
    a.raw("8B 43 74", "mov         eax,dword ptr [ebx+74h]")         # the time this highscore is for
    a.raw("3B 46 58", "cmp         eax,dword ptr [esi+58h]")         # ... is the run the header describes?
    a.jcc_near("jne", "name_confirm_done")
    stored_name_to("46", "esi")
    lea_eax("name_pc", STR_NEW_PHANTOM)
    a.call("stamp_file")
    table_entry("94", "edx")
    a.raw("83 7A 14 00", "cmp         dword ptr [edx+14h],0")        # mhk2_manager's checksum
    a.jcc_short("jne", "name_confirm_done")
    a.raw("B9 4C 00 00 00", "mov         ecx,4Ch")                   # track, class, character, four times
    a.label("name_confirm_same")
    a.raw("8B 04 0E", "mov         eax,dword ptr [esi+ecx]")
    a.raw("3B 04 0A", "cmp         eax,dword ptr [edx+ecx]")
    a.jcc_short("jne", "name_confirm_done")
    a.raw("83 C1 04", "add         ecx,4")
    a.raw("83 F9 68", "cmp         ecx,68h")
    a.jcc_short("jb", "name_confirm_same")
    stored_name_to("42", "edx")
    phantom_path("name_pc")
    a.raw("8B C4", "mov         eax,esp")
    a.call("stamp_file")
    a.raw("83 C4 40", "add         esp,40h")
    a.label("name_confirm_done")
    a.raw("61", "popad")
    a.jmp(HIGHSCORE_INSERT)

    # Write the stored name into bytes 8..19 of a phantom file.
    # eax = file name, ebx = GameParameters, ebp = name_pc.
    a.label("stamp_file")
    a.raw("57", "push        edi")
    a.raw("6A 00", "push        0")
    a.raw("68 80 00 00 00", "push        80h")
    a.raw("6A 03", "push        3")                       # the file must exist
    a.raw("6A 00", "push        0")
    a.raw("6A 01", "push        1")                       # others may read it meanwhile
    a.raw("68 00 00 00 40", "push        40000000h")      # write access
    a.raw("50", "push        eax")
    call_import("name_pc", IMP_CREATEFILE)
    a.raw("83 F8 FF", "cmp         eax,0FFFFFFFFh")
    a.jcc_short("je", "stamp_file_done")
    a.raw("8B F8", "mov         edi,eax")
    a.raw("6A 00", "push        0")                       # from the start of the file
    a.raw("6A 00", "push        0")
    a.raw("6A %02X" % PHANTOM_NAME, "push        %s" % _imm(PHANTOM_NAME))
    a.raw("57", "push        edi")
    call_import("name_pc", IMP_SETFILEPOINTER)
    a.raw("6A 00", "push        0")                       # receives the number of bytes written
    a.raw("8B C4", "mov         eax,esp")
    a.raw("6A 00", "push        0")
    a.raw("50", "push        eax")
    a.raw("6A %02X" % PHANTOM_NAME_LEN, "push        %s" % _imm(PHANTOM_NAME_LEN))
    a.raw("8D 83 " + _le(NAME_OFFSET), "lea         eax,[ebx+%08Xh]" % NAME_OFFSET)
    a.raw("50", "push        eax")
    a.raw("57", "push        edi")
    call_import("name_pc", IMP_WRITEFILE)
    a.raw("58", "pop         eax")
    a.raw("57", "push        edi")
    call_import("name_pc", IMP_CLOSEHANDLE)
    a.label("stamp_file_done")
    a.raw("5F", "pop         edi")
    a.raw("C3", "ret")

    # Highscore lists: the phantom's row says "PHANTOM KART". Show the name from its
    # header instead if there is one (in place of the call that sets the row's name;
    # ecx = the row's name string, [esp+4] = "PHANTOM KART", edi = table index).
    a.label("phantom_row_name")
    a.raw("51", "push        ecx")
    a.call(GP_GET)
    a.raw("6B D7 6C", "imul        edx,edi,6Ch")
    disp = PHANTOM_TABLE + PHANTOM_NAME
    a.raw("8D 84 10 " + _le(disp), "lea         eax,[eax+edx+%08Xh]" % disp)
    a.raw("59", "pop         ecx")
    a.raw("83 78 44 00", "cmp         dword ptr [eax+44h],0")        # track 0: no phantom file for this row
    a.jcc_near("je", STR_ASSIGN)
    a.raw("80 38 00", "cmp         byte ptr [eax],0")
    a.jcc_near("je", STR_ASSIGN)
    a.raw("83 EC 2C", "sub         esp,2Ch")                         # 16 bytes of text, then a std::string
    a.raw("8B 10", "mov         edx,dword ptr [eax]")
    a.raw("89 14 24", "mov         dword ptr [esp],edx")
    a.raw("8B 50 04", "mov         edx,dword ptr [eax+4]")
    a.raw("89 54 24 04", "mov         dword ptr [esp+4],edx")
    a.raw("8B 50 08", "mov         edx,dword ptr [eax+8]")
    a.raw("89 54 24 08", "mov         dword ptr [esp+8],edx")
    a.raw("C6 44 24 0C 00", "mov         byte ptr [esp+0Ch],0")      # a 12 character name has no terminator
    a.raw("51", "push        ecx")
    a.raw("8D 44 24 04", "lea         eax,[esp+4]")
    a.raw("50", "push        eax")
    a.raw("8D 4C 24 18", "lea         ecx,[esp+18h]")
    a.call(STR_CTOR)
    a.raw("59", "pop         ecx")
    a.raw("8D 44 24 10", "lea         eax,[esp+10h]")
    a.raw("50", "push        eax")
    a.call(STR_ASSIGN)
    a.raw("8D 4C 24 10", "lea         ecx,[esp+10h]")
    a.call(STR_DTOR)
    a.raw("83 C4 2C", "add         esp,2Ch")
    a.raw("C2 04 00", "ret         4")

    # Startup, after the data files are mounted (in place of the call that loads
    # settings.dat): which data version is this? The game looks files up in the
    # newest mhk2-NN.dat first, so do the same for one that differs between the
    # versions, and let new phantom files say "V1.1" where it applies.
    a.label("version_detect")
    a.raw("60", "pushad")
    pic_base("version_pc")
    a.call(FILEMGR_GET)
    a.raw("8B F0", "mov         esi,eax")
    a.raw("8D 4E 04", "lea         ecx,[esi+4]")
    a.call(ARCHIVE_COUNT)
    a.raw("8B F8", "mov         edi,eax")
    a.label("version_next")
    a.raw("4F", "dec         edi")
    a.jcc_short("js", "version_done")
    a.raw("6B C7 54", "imul        eax,edi,54h")
    a.raw("03 46 08", "add         eax,dword ptr [esi+8]")
    disp = ebp_disp("version_pc", later("v11_file"))
    a.raw("8D 95 " + _le(disp), "lea         edx,[ebp+%08Xh]" % disp)
    a.raw("52", "push        edx")
    a.raw("50", "push        eax")
    a.raw("8B CE", "mov         ecx,esi")
    a.call(ARCHIVE_FIND)
    a.raw("85 C0", "test        eax,eax")
    a.jcc_short("je", "version_next")
    a.raw("81 78 6C " + _le(V11_FILE_SIZE), "cmp         dword ptr [eax+6Ch],%s" % _imm(V11_FILE_SIZE))
    a.jcc_short("jne", "version_done")
    disp = ebp_disp("version_pc", VERSION_STRING + 3)
    a.raw("C6 85 %s 31" % _le(disp), "mov         byte ptr [ebp+%08Xh],31h" % disp)   # "V1.0" -> "V1.1"
    a.label("version_done")
    a.raw("61", "popad")
    a.jmp(SETTINGS_LOAD)

    # -- data (kept behind the code) -------------------------------------------
    a.label("class_factor_table")
    a.data(struct.pack("<5f", 0.9, 1.1, 1.3, *factors), "float 0.9, 1.1, 1.3, %g, %g" % tuple(factors))
    a.label("class_pull_table")
    a.data(struct.pack("<5f", 1.0, 1.0, 1.0, *pulls), "float 1, 1, 1, %g, %g" % tuple(pulls))
    a.label("ai_item_rate")
    a.data(struct.pack("<f", AI_ITEM_UPDATES / 60.0), "float %g: the game's 800 updates, in seconds at 60 FPS" % (AI_ITEM_UPDATES / 60.0))
    a.label("opp_class_tempo")
    a.data(struct.pack("<6b", *OPP_CLASS_TEMPO) + b"\0\0",
           "\"Tempo\" of the computer karts at \"Standard\", per class in percent: %d, %d, %d, %d, %d, %d" % OPP_CLASS_TEMPO)
    a.label("hundredth")
    a.data(struct.pack("<f", 0.01), "float 0.01")
    a.label("stock_gravity")
    a.data(struct.pack("<f", STOCK_GRAVITY_Y), "float %g: the world's gravity" % STOCK_GRAVITY_Y)
    a.label("downforce_speed")
    a.data(struct.pack("<2f", DOWNFORCE_SPEED, DOWNFORCE_SPEED_AIR),
           "float %g, %g: where the downforce of the tuning class stops growing, on the ground and in the air" % (DOWNFORCE_SPEED, DOWNFORCE_SPEED_AIR))
    a.label("top_consts")
    a.data(struct.pack("<%df" % len(TOP_CONSTS), *(top_const(n) for n in TOP_CONSTS)),
           "top speed: " + ", ".join("%s %g" % (n, top_const(n)) for n in TOP_CONSTS))
    a.label("hud_speed_y")
    a.data(struct.pack("<2f", *HUD_SPEED_Y), "float %g, %g: y of the speed in the race without / with the position" % HUD_SPEED_Y)
    a.label("ch_band")
    a.data(struct.pack("<f", CH_BAND), "float %g: challenge, finish band on the minimap" % CH_BAND)
    a.label("ch_one")
    a.data(struct.pack("<f", 1.0), "float 1")
    a.label("ch_half")
    a.data(struct.pack("<f", 0.5), "float 0.5")
    a.label("ch_mhalf")
    a.data(struct.pack("<f", -0.5), "float -0.5")
    a.label("ch_no_file")
    a.data(b"\0", "empty string: the ghost of a random challenge")
    a.label("ch_daily_fmt")
    a.data(STR_DAILY_FMT.encode() + b"\0", "the phantom of the day: " + STR_DAILY_FMT.replace("\\", "\\\\"))
    a.label("ch_milli")
    a.data(struct.pack("<f", 0.001), "float 0.001")
    a.label("ch_hundred")
    a.data(struct.pack("<f", 100.0), "float 100")
    a.label("ch_len_min")
    a.data(struct.pack("<2f", CH_LEN_MIN, CH_LEN_MAX), "float %g, %g: a challenge's share of the path" % (CH_LEN_MIN, CH_LEN_MAX))
    a.label("ch_day_len")
    a.data(struct.pack("<d", DAY_100NS), "double %g: a day in FILETIME units" % DAY_100NS)
    a.label("ch_paths")
    a.data(struct.pack("<8f", *CH_PATHS), "float: path length of the eight tracks")
    a.label("ch_sets")
    a.data(b"".join(struct.pack("<8H", *vals) for vals in challenge_sets()),
           "the %d sets of tuning values of the challenges, 8 words each" % CH_SET_COUNT)
    a.label("top_chars")
    a.data(b"".join(struct.pack("<2f", m, TOP_K * gd) for m, gd in TOP_CHARS),
           "top speed: mass and rpm per unit/s in top gear of the seven characters")
    a.label("tune_rows")
    a.data(b"".join(struct.pack("<4h", *row) for row in TUNE_ROWS + (NEW_ROW,)),
           "tuning rows: minimum, maximum, step, default (the last: the second row of Gegner)")
    a.label("tune_presets")
    a.data(b"".join(struct.pack("<%dh" % PRESET_VALUES, *vals) for _, vals in TUNE_PRESETS),
           "tuning presets: the eight values of " + ", ".join(name for name, _ in TUNE_PRESETS))
    tab = limit_table()
    a.label("tune_limit_rows")
    rows, off = b"", 0
    for steps in tab:
        rows += struct.pack("<2H", len(steps) - 1, off)
        off += len(steps) * len(LIMIT_CHANNELS)
    a.data(rows, "Am Limit: per row the last grid step and the offset of its block in tune_limit_tab")
    a.label("tune_limit_tab")
    a.data(b"".join(struct.pack("<%db" % len(LIMIT_CHANNELS), *pts) for steps in tab for pts in steps),
           "Am Limit: points of %s per grid step of every row" % ", ".join(LIMIT_CHANNELS))
    a.label("tune_info_texts")
    a.data(struct.pack("<%dH" % len(TXT_INFO), *TXT_INFO), "text ids of the explanations of rows 1..10")
    a.label("tune_apply_table")
    a.data(b"".join(struct.pack("<BH", n, off) for n, off in TUNE_APPLY) + b"\0",
           "tuning: value number and the car field it scales")
    signature = SIGNATURE_PREFIX + b" " + (version or PATCH_VERSION).encode() + b"\0"
    a.data(signature, "signature")
    a.label("v11_file")
    a.data(V11_FILE, "a file that differs between the data versions")

    code, listing = a.finish()
    if a.labels != known:
        return build_payload(base, factors, pulls, dict(a.labels), version)   # second pass: forward references are known now
    assert len(code) <= SECTION_SIZE
    return code, listing, a.labels


def site_patches(labels):
    """(va, original bytes, new bytes, description) for everything outside the new section."""
    L = labels
    P = []

    def rel(op, va, target):
        return bytes([op]) + struct.pack("<i", target - (va + 5))

    def call(va, orig_hex, label, what):
        orig = bytes.fromhex(orig_hex)
        new = rel(0xE8, va, L[label]) + b"\x90" * (len(orig) - 5)
        P.append((va, orig, new, what))

    def jump(va, orig_hex, label, what):
        orig = bytes.fromhex(orig_hex)
        new = rel(0xE9, va, L[label]) + b"\x90" * (len(orig) - 5)
        P.append((va, orig, new, what))

    def retarget(va, old_target, label, what):
        P.append((va, rel(0xE8, va, old_target), rel(0xE8, va, L[label]), what))

    def data(va, orig_hex, new_hex, what):
        P.append((va, bytes.fromhex(orig_hex), bytes.fromhex(new_hex), what))

    # record table slots
    call(0x004099A4, "C1 E7 06 03 FD", "slot_edi_ebp", "race start: phantom header slot")
    call(0x00412A9E, "C1 E2 06 03 D6", "slot_edx_esi", "time trial: is new highscore")
    call(0x00412B0B, "C1 E1 06 03 D1", "slot_ecx_into_edx", "time trial: insert highscore")
    call(0x0041C788, "C1 E1 06 03 CA", "slot_ecx_edx", "highscore browser: best lap")
    call(0x0041C816, "C1 E2 06 03 D1", "slot_edx_ecx", "highscore browser: best lap holder")
    call(0x0041C976, "C1 E1 06 03 CA", "slot_ecx_edx", "highscore browser: character")
    call(0x00420817, "C1 E2 06 8D 3C 02", "slot_edx_eax_to_edi", "time trial highscore rows")
    call(0x00423B2F, "C1 E2 06 03 D0", "slot_edx_eax", "result page: best lap")
    call(0x00423BCE, "C1 E0 06 03 C1", "slot_eax_ecx", "result page: best lap holder")
    call(0x00423D2C, "C1 E1 06 03 CA", "slot_ecx_edx", "result page: character")
    call(0x00412D0F, "8D 04 80 8D 0C 81", "champ_index_ecx", "championship: is new highscore")
    call(0x00412D9B, "69 C9 8C 00 00 00", "champ_offset_ecx", "championship: insert highscore")
    call(0x00420DDA, "69 D2 8C 00 00 00", "champ_offset_edx", "championship highscore rows")

    # AI tables / engine sound / physics
    retarget(0x0043A504, LS_GET, "ai_class_clamp", "AI speed factors: clamp class")
    retarget(0x0043A5BB, LS_GET, "ai_class_clamp", "AI target ranking: clamp class")
    call(0x0043A5CA, "D8 4C 90 54 8B 46 10", "ai_throttle", "AI throttle: 200 cc, 250 cc and 'Gegner' catch up")
    call(0x0043A5E5, "68 20 03 00 00 E8 E1 7C 05 00 83 C4 04", "ai_item_chance",
         "AI fires its power-up with the same chance per second at any frame rate")
    jump(GEO_HOOK, GEO_HOOK_ORIG, "geo_ai", "AI: corner speed from the track's centre line (geometric driver)")
    jump(GEO_LINE_HOOK, GEO_LINE_ORIG, "geo_line", "AI path planner: a line to the inside of the bends")
    jump(CHAMP_RECT_HOOK, CHAMP_RECT_ORIG, "champ_rect", "championship page: the picture on the left while the page has 'Gegner'")
    jump(0x0043996A, "D9 5C 24 54 D9 44 24 50", "geo_obst",
         "AI path planner: a larger obstacle box for a slow kart ahead (learned driver; off by default)")
    jump(0x0043A708, "8B 4E 10 8B 81 D0 02 00 00", "geo_watch",
         "AI: a kart without progress for 5 s goes back to the road (200 cc, 250 cc, tuning class)")
    data(0x0040976D, "68 C0 00 00 00", "68 C8 00 00 00", "AI controller: 8 bytes more (the watch's place and time)")
    jump(0x0042FC14, "8B 44 BC 18 53", "engine_sound", "engine sample selection")
    jump(0x00437724, "8B 40 10 3B C3", "class_factor", "class factor table")
    call(0x0043F7F4, "D8 8F 68 02 00 00", "pull_mul", "drive torque: pull of the class")
    call(0x0043FAFF, "D8 8F 68 02 00 00", "pull_mul", "traction limit: pull of the class")
    call(0x0043FCE0, "D9 87 64 02 00 00", "downforce_cap", "downforce: limited in the tuning class")

    # phantom header scan
    jump(0x0041304E, "83 F8 40 C7 44 24 34 0F 00 00 00", "phantom_inner_limit", "phantom scan: slots per class")
    jump(0x0041306B, "83 F9 03 8B D7 0F 8C E2 FE FF FF", "phantom_outer_next", "phantom scan: fourth to sixth class")

    # engine class menu: two more entries, so the rows move closer to the top
    def push_imm(va, old, new, what):
        data(va, "68 " + _le(old), "68 " + _le(new), "engine menu: " + what)

    jump(0x0041B3F4, "53 8D 84 24 E8 08 00 00", "engine_menu_item", "engine menu: add the 200 cc, 250 cc and tuning entries")
    push_imm(0x0041B3FC, 0x14F, TXT_BACK, "'Zurück' comes from text 323 (335 is '200 cc' now)")
    push_imm(0x0041B448, 0x150, TXT_HINT, "the hint comes from text 342 (336 and 337 are class names now)")
    push_imm(0x0041B0ED, 200, MENU_Y_HEADING, "heading")
    push_imm(0x0041B48D, 240, MENU_Y_TOP_LINE, "upper separator")
    push_imm(0x0041B13C, 260, MENU_Y_CLASSES[0], "50 cc")
    push_imm(0x0041B19C, 300, MENU_Y_CLASSES[1], "100 cc")
    push_imm(0x0041B255, 300, MENU_Y_CLASSES[1], "100 cc, locked")
    push_imm(0x0041B2DC, 340, MENU_Y_CLASSES[2], "150 cc")
    push_imm(0x0041B395, 340, MENU_Y_CLASSES[2], "150 cc, locked")
    push_imm(0x0041B49A, 400, MENU_Y_LINE, "lower separator")
    push_imm(0x0041B45A, 430, MENU_Y_HINT, "hint text")
    push_imm(0x0041B40E, 520, MENU_Y_BACK, "'Zurück'")
    data(0x0041E1EF, "83 F8 03", "83 F8 06", "engine menu: items 1..6 select a class")
    data(0x0041E1F4, "83 F8 04", "83 F8 07", "engine menu: item 7 is 'back'")

    # tuning class: its own page between the class menu and the character menu, and the kart values
    retarget(0x0041E233, PAGE_SET, "class_selected", "engine menu: 'Tuning' opens the tuning page")
    retarget(0x00413E20, PAGE_BUILD_LAST, "page_build", "menu: builder of the tuning page")
    retarget(0x004149EA, PAGE_UPDATE_MAIN, "page_update", "menu: input of the tuning page and the own presets")
    retarget(0x004149CC, RESULT_UPDATE, "result_update", "menu: the name page renames an own preset")
    retarget(0x00437772, CAR_REBUILD, "tune_apply", "kart values of the tuning class")
    retarget(0x00409048, PHYS_INIT, "world_gravity", "race start: gravity of the tuning class")

    # winning championship 2 in 150 cc unlocks 200 cc, in 200 cc 250 cc, in 250 cc the tuning class
    data(0x00414571, "83 FF 02", "83 FF 05", "unlock chain: 200 cc, 250 cc and the tuning class")
    call(0x0041457A, "81 C7 48 02 00 00", "unlock_class_text", "unlock message for the tuning class")
    call(0x00414540, "81 C7 44 02 00 00", "unlock_text", "unlock message for championship 2 in 250 cc")
    # "Alles freigeschaltet": the class menu and the track lock (Meisterschaft 2, tracks 5-8) read
    # the progress through the switch; the unlock chain above keeps the real one
    call(0x0041B173, "8B 88 08 FD 00 00", "unlock_level", "class menu: 100 cc row reads the switch")
    call(0x0041B2B9, "83 B8 08 FD 00 00 02", "unlock_cmp2", "class menu: 150 cc row reads the switch")
    call(0x00413110, "85 90 0C FD 00 00", "unlock_test", "track lock: open while the switch is on")

    # highscore browser cycles through six classes
    for va in (0x0041ED48, 0x0041EEB9, 0x0041EF70, 0x0041F0A4, 0x0041F0DE, 0x0041F1DC, 0x0041F293):
        data(va, "B9 03 00 00 00", "B9 06 00 00 00", "highscore browser: class modulo 6")
    for va in (0x0041ED8E, 0x0041EEB5, 0x0041F0DA, 0x0041F1D8):
        data(va, "83 C0 02", "83 C0 05", "highscore browser: previous class = +5 mod 6")

    # "60 FPS physics" switch
    jump(0x0043FB88, "D8 8C 24 E8 00 00 00", "suspension", "wheel spring/damper: optional 60 FPS reference step")
    data(0x0040318C, "88 5E 4C", "89 5E 4C", "new settings: clear the padding bytes that hold the switch")
    data(0x004206CD, "45 83 FD 08", "45 83 FD 07", "options menu: the stock loop stops after 'quality'")
    jump(0x004206F0, "53 8D 8C 24 A0 01 00 00", "options_items", "options menu: add the switch and 'Zurück'")
    for row, (old, new) in enumerate(zip(OPTIONS_Y_STOCK, OPTIONS_Y)):
        slot = "C7 44 24 %02X " % (0x48 + 4 * row)
        data(0x00420328 + 8 * row, slot + _le(old), slot + _le(new), "options menu: row %d moves up to make room" % row)
    call(0x0041FB88, "8B 86 48 01 00 00", "options_select", "options menu: select on the new items")
    call(0x0041FD71, "8B 86 48 01 00 00", "options_left", "options menu: left flips the switch")
    call(0x0041FE2D, "8B B6 48 01 00 00", "options_right", "options menu: right flips the switch")

    # pause page: class, switch, tuning preset and values above the stock items, which move down
    jump(0x004142FC, "C7 86 44 01 00 00 FF FF FF FF", "pause_info", "pause page: class, switch, tuning values")
    jump(HUD_SPEED_HOOK, "57 8D 4C 24 28", "hud_speed", "race: the speed below lap and position")
    jump(CH_GRID_HOOK, "8B 40 50 89 44 24 18", "ch_grid", "challenge: the grid at the challenge's start")
    jump(CH_FINISH_HOOK, "83 BE 64 02 00 00 03 0F 8C 71 02 00 00", "ch_finish",
         "challenge: finished after the challenge's stretch instead of 3 laps")
    jump(CH_LAPID_HOOK, "6A 64 52 89 78 34", "ch_lapid", "challenge: metres left instead of the lap (text)")
    jump(CH_LAPNUM_HOOK, "8B 54 8E 20 42", "ch_lapnum", "challenge: metres left instead of the lap (number)")
    jump(CH_MAP_HOOK, "C7 44 01 F4 C0 C0 C0 FF", "ch_mapcol", "challenge: the stretch in colour on the minimap")
    for va in TOP_FIVE_CALLS:
        retarget(va, TOP_FIVE, "ch_top5", "challenge: no highscore entry")
    for k, (va, orig, _) in enumerate(CH_GHOST_HOOKS):
        jump(va, orig, "ch_ghost%d" % k, "challenge: no phantom of the track (daily: the phantom of the day)")
    for k, va in enumerate(CH_SAVE_HOOKS):
        jump(va, CH_SAVE_ORIG, "ch_save%d" % k, "challenge: settings.dat gets the player's own settings")
    for row, y in enumerate(PAUSE_Y_STOCK[:5]):
        slot = "C7 44 24 %02X " % (0x30 + 4 * row)
        data(0x00413E92 + 8 * row, slot + _le(y), slot + _le(y + PAUSE_Y_SHIFT), "pause page: item %d moves down" % row)
    for va, y in ((0x00413FE1, PAUSE_Y_STOCK[5]), (0x0041405B, PAUSE_Y_STOCK[5]), (0x004140D2, PAUSE_Y_STOCK[6])):
        data(va, "68 " + _le(y), "68 " + _le(y + PAUSE_Y_SHIFT), "pause page: button at %d moves down" % y)

    # phantom karts
    # The stock game compares the id in a phantom file with its own and skips the file
    # if they are equal: it never shows a ghost that was recorded on the same PC.
    data(0x00409BAF, "74 1E", "90 90", "race start: load the phantom even if it is from this PC")
    data(0x0040736E, "74 1E", "90 90", "race restart: load the phantom even if it is from this PC")
    data(0x0040C406, "0F 84 C1 00 00 00", "90 90 90 90 90 90", "phantom import (MHK2-XXL.exe file.mhk2): accept own files")
    jump(0x00406C69, "8B 45 00 6A 6C", "phantom_stamp", "time trial finish: clean header, player name")
    retarget(0x00406C91, FILE_CLOSE, "phantom_promote", "time trial finish: a faster run becomes the phantom")
    retarget(0x00422340, HIGHSCORE_INSERT, "name_confirm", "name entry: remember the name, add it to this run's phantom")
    retarget(0x00420B70, STR_ASSIGN, "phantom_row_name", "highscore lists: name of the phantom's driver")
    retarget(0x0046F857, SETTINGS_LOAD, "version_detect", "startup: new phantoms say V1.1 with the V1.1 data")
    return P


class PE:
    def __init__(self, data):
        self.data = bytearray(data)
        self.pe = struct.unpack_from("<I", self.data, 0x3C)[0]
        assert self.data[self.pe:self.pe + 4] == b"PE\0\0"
        self.nsec = struct.unpack_from("<H", self.data, self.pe + 6)[0]
        self.optsz = struct.unpack_from("<H", self.data, self.pe + 20)[0]
        self.opt = self.pe + 24
        self.sectab = self.opt + self.optsz

    def sections(self):
        for i in range(self.nsec):
            o = self.sectab + 40 * i
            name = bytes(self.data[o:o + 8])
            vsize, rva, rsize, roff = struct.unpack_from("<IIII", self.data, o + 8)
            yield name, rva, vsize, roff, rsize

    def va_to_off(self, va):
        rva = va - IMAGE_BASE
        for name, srva, vsize, roff, rsize in self.sections():
            if srva <= rva < srva + rsize:
                return roff + (rva - srva)
        raise ValueError("VA %08X is not backed by the file" % va)

    def relocated_addresses(self):
        """VAs of all dwords the loader would fix up if the image were rebased."""
        rva, size = struct.unpack_from("<II", self.data, self.opt + 96 + 8 * 5)
        off, end, out = self.va_to_off(IMAGE_BASE + rva), 0, set()
        end = off + size
        while off < end:
            page, block = struct.unpack_from("<II", self.data, off)
            if block < 8:
                break
            for i in range((block - 8) // 2):
                entry = struct.unpack_from("<H", self.data, off + 8 + 2 * i)[0]
                if entry >> 12 == 3:   # IMAGE_REL_BASED_HIGHLOW
                    out.add(IMAGE_BASE + page + (entry & 0xFFF))
            off += block
        return out

    def add_section(self, name, rva, raw_off, size, characteristics, content):
        hdr = self.sectab + 40 * self.nsec
        assert not any(self.data[hdr:hdr + 40]), "no room for another section header"
        assert hdr + 40 <= struct.unpack_from("<I", self.data, self.opt + 60)[0]  # SizeOfHeaders
        assert len(self.data) == raw_off
        assert struct.unpack_from("<I", self.data, self.opt + 56)[0] == rva       # SizeOfImage
        struct.pack_into("<8sIIIIIIHHI", self.data, hdr, name, len(content), rva, size, raw_off,
                         0, 0, 0, 0, characteristics)
        self.nsec += 1
        struct.pack_into("<H", self.data, self.pe + 6, self.nsec)
        struct.pack_into("<I", self.data, self.opt + 56, rva + size)              # SizeOfImage
        code = struct.unpack_from("<I", self.data, self.opt + 4)[0]
        struct.pack_into("<I", self.data, self.opt + 4, code + size)              # SizeOfCode
        self.data += content.ljust(size, b"\0")


def patch_exe(src, factors, pulls, version=None):
    data = open(src, "rb").read()
    digest = hashlib.sha256(data).hexdigest()
    if len(data) != ORIGINAL_SIZE or not digest.startswith(ORIGINAL_SHA256):
        if SIGNATURE_PREFIX in data:
            raise SystemExit("%s already contains the 200 cc mod - start from the original exe." % src)
        raise SystemExit("%s is not the expected MHK2-XXL.exe V1.0 (German, build Mar 23 2004).\n"
                         "  this file: %d bytes, sha256 %s\n"
                         "  expected:  %d bytes, sha256 %s...\n"
                         "See 'Other versions of the exe' in the README."
                         % (src, len(data), digest, ORIGINAL_SIZE, ORIGINAL_SHA256))
    pe = PE(data)
    base = IMAGE_BASE + SECTION_RVA
    code, listing, labels = build_payload(base, factors, pulls, version=version)
    patches = site_patches(labels)
    relocs = pe.relocated_addresses()
    for va, orig, new, what in patches:
        # the new bytes hold no absolute addresses, so they must not sit on a relocation
        clash = [r for r in range(va - 3, va + len(orig)) if r in relocs]
        assert not clash, "patch at %08X overlaps relocation %08X" % (va, clash[0])
        off = pe.va_to_off(va)
        found = bytes(pe.data[off:off + len(orig)])
        if found != orig:
            raise SystemExit("unexpected bytes at %08X (%s): %s" % (va, what, found.hex(" ")))
        assert len(new) == len(orig)
        pe.data[off:off + len(new)] = new
    # code | execute | read
    pe.add_section(SECTION_NAME, SECTION_RVA, SECTION_RAW, SECTION_SIZE, 0x60000020, code)
    return bytes(pe.data), listing, patches


def read_settings(settings_path):
    data = bytearray(open(settings_path, "rb").read())
    if len(data) != 0xFD0C or struct.unpack_from("<I", data, 0)[0] != 0x100:
        raise SystemExit("%s does not look like a Moorhuhn Kart 2 settings.dat" % settings_path)
    return data


def unlock(settings_path, tuning=False):
    """Open 50 cc to 250 cc (and with `tuning` the tuning class): the 'highest unlocked class'
    counter, and in each of these classes championship 2 and tracks 5-8 (one bit per class)."""
    data = read_settings(settings_path)
    off = 0xFD08 - 4   # file = GameParameters object without its vtable pointer
    old, bits = struct.unpack_from("<iI", data, off)
    new = max(old, 5 if tuning else 4)
    new_bits = bits | 0x1F
    struct.pack_into("<iI", data, off, new, new_bits)
    open(settings_path, "wb").write(data)
    print("%s: highest unlocked class %d -> %d, championship 2 open in classes %02Xh -> %02Xh"
          % (settings_path, old, new, bits, new_bits))


def lock(settings_path):
    """Lock 200 cc and up again, as before they were won: the 'highest unlocked class' counter
    goes down to 150 cc, championship 2 of 200 cc and 250 cc closes, and the switch
    'Alles freigeschaltet' goes off. The tuning class's bit stays: its values set it once, and
    the class stays hidden until the counter reaches it again. Records and phantoms stay."""
    data = read_settings(settings_path)
    off = 0xFD08 - 4   # file = GameParameters object without its vtable pointer
    old, bits = struct.unpack_from("<iI", data, off)
    new = min(old, 2)
    new_bits = bits & ~0x18
    struct.pack_into("<iI", data, off, new, new_bits)
    mark = UNLOCK_MARK - 4
    was_on = struct.unpack_from("<I", data, mark)[0] == UNLOCK_MAGIC
    struct.pack_into("<I", data, mark, 0)
    open(settings_path, "wb").write(data)
    print("%s: highest unlocked class %d -> %d, championship 2 open in classes %02Xh -> %02Xh, "
          "Alles freigeschaltet %s -> off" % (settings_path, old, new, bits, new_bits, "on" if was_on else "off"))


def physics60(settings_path, state):
    """Set the "60-FPS-Fahrphysik" switch the way the options menu does."""
    data = read_settings(settings_path)
    off = PHYS_FLAG_OFFSET + 1 - 4
    magic = struct.pack("<I", PHYS_MAGIC)[:3]
    old = bytes(data[off:off + 3]) == magic
    data[off:off + 3] = magic if state == "on" else b"\0\0\0"
    open(settings_path, "wb").write(data)
    print("%s: 60 FPS physics %s -> %s" % (settings_path, "on" if old else "off", state))


def player_name(settings_path, name):
    """Set the name that new phantom files get (the game sets it when a highscore name is typed)."""
    raw = name.encode("cp1252")
    if len(raw) > PHANTOM_NAME_LEN:
        raise SystemExit("the name can have at most %d characters" % PHANTOM_NAME_LEN)
    data = read_settings(settings_path)
    off, mark = NAME_OFFSET - 4, NAME_MARK_OFFSET - 4
    old = None
    if struct.unpack_from("<I", data, mark)[0] == NAME_MARK:
        old = bytes(data[off:off + PHANTOM_NAME_LEN]).split(b"\0")[0].decode("cp1252")
    data[off:off + 16] = raw.ljust(16, b"\0")
    struct.pack_into("<I", data, mark, NAME_MARK)
    open(settings_path, "wb").write(data)
    print("%s: player name %s -> %r" % (settings_path, "(none)" if old is None else repr(old), name))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("exe", nargs="?", help="original MHK2-XXL.exe")
    ap.add_argument("outdir", nargs="?", help="directory for the patched files")
    ap.add_argument("--factor", "--factor-200", type=float, default=FACTOR_200, dest="factor",
                    help="200 cc class factor (150 cc is 1.3; default %(default)s)")
    ap.add_argument("--factor-250", type=float, default=FACTOR_250, dest="factor_250",
                    help="250 cc class factor (default %(default)s)")
    ap.add_argument("--pull", "--pull-200", type=float, default=PULL_200, dest="pull",
                    help="200 cc pull: thrust and traction limit, 1 = like 150 cc (default %(default)s)")
    ap.add_argument("--pull-250", type=float, default=PULL_250, dest="pull_250",
                    help="250 cc pull (default %(default)s)")
    ap.add_argument("--lang", choices=sorted(TEXTS), default="de",
                    help="language of the patch's own menu texts in text-20.csv (default %(default)s)")
    ap.add_argument("--listing", help="write the assembled payload + patch list to this file")
    ap.add_argument("--unlock", metavar="SETTINGS.DAT",
                    help="open 50 cc to 250 cc with both championships in a settings.dat and exit")
    ap.add_argument("--unlock-tuning", metavar="SETTINGS.DAT",
                    help="the same, and the tuning class too")
    ap.add_argument("--lock", metavar="SETTINGS.DAT",
                    help="lock 200 cc, 250 cc and the tuning class again in a settings.dat and exit")
    ap.add_argument("--physics60", nargs=2, metavar=("on|off", "SETTINGS.DAT"),
                    help="set the 60 FPS physics switch in a settings.dat and exit")
    ap.add_argument("--player-name", nargs=2, metavar=("NAME", "SETTINGS.DAT"),
                    help="set the name written into new phantom files and exit")
    args = ap.parse_args()
    if args.unlock or args.unlock_tuning:
        unlock(args.unlock or args.unlock_tuning, tuning=bool(args.unlock_tuning))
        return
    if args.lock:
        lock(args.lock)
        return
    if args.physics60:
        if args.physics60[0] not in ("on", "off"):
            ap.error("--physics60 takes on or off")
        physics60(args.physics60[1], args.physics60[0])
        return
    if args.player_name:
        player_name(args.player_name[1], args.player_name[0])
        return
    if not args.exe or not args.outdir:
        ap.error("need the original exe and an output directory")
    factors = (args.factor, args.factor_250)
    pulls = (args.pull, args.pull_250)
    version = patch_version()
    patched, listing, patches = patch_exe(args.exe, factors, pulls, version)
    os.makedirs(os.path.join(args.outdir, "data", "MK2"), exist_ok=True)
    exe_out = os.path.join(args.outdir, "MHK2-XXL.exe")
    txt_out = os.path.join(args.outdir, "data", "MK2", "text-20.csv")
    if os.path.abspath(exe_out) == os.path.abspath(args.exe):
        raise SystemExit("refusing to overwrite the original exe - choose another output directory")
    open(exe_out, "wb").write(patched)
    open(txt_out, "wb").write(text_overrides(args.lang, version).encode("cp1252"))
    if args.listing:
        with open(args.listing, "w", encoding="utf-8") as f:
            for va, text in listing:
                f.write("%08X: %s\n" % (va, text))
            f.write("\n")
            for va, orig, new, what in patches:
                f.write("%08X: %-32s -> %-32s ; %s\n" % (va, orig.hex(" "), new.hex(" "), what))
    print("wrote %s (version %s, %d site patches, %d listing lines, class factors %g / %g, pull %g / %g)"
          % (exe_out, version, len(patches), len(listing), factors[0], factors[1], pulls[0], pulls[1]))
    print("wrote %s" % txt_out)


if __name__ == "__main__":
    main()
