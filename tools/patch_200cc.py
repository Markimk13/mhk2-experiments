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
  * computer karts use the 150 cc AI / target ranking settings of each level
  * time trial + championship highscores, phantom karts and the highscore
    browser work for the new classes
  * settings.dat keeps its format: the new records live in table slots the game
    never uses (tracks 33-64 / championships 11-20 of the 150 cc rows for
    200 cc, of the 100 cc rows for 250 cc, of the 50 cc rows for the tuning class)

And a sixth class, "Tuning", that is always open: choosing it shows a page where
gearing, pull, grip, weight, brakes, steering and downforce of the kart are set.
The values are kept in settings.dat and apply to every kart in the race. The page's
top row, "Vorlage", copies built-in presets (the five classes and nine more) into them.

It also adds a switch "60-FPS-Fahrphysik" to the options menu (off by default).
The stock game derives the wheel springs from the length of the physics step,
so above ~100 FPS the kart sags onto its chassis: it gets slower, slippery and
hops. Switched on, the springs are always the ones the game has at 60 FPS.

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
    patch_200cc.py --unlock <settings.dat>      (make 200 cc and 250 cc selectable)
    patch_200cc.py --physics60 on|off <settings.dat>   (same as the menu switch)
    patch_200cc.py --player-name NAME <settings.dat>   (name for new phantoms, max 12 characters)

The output dir receives the patched MHK2-XXL.exe and data/MK2/text-20.csv
(text overrides; the game merges text-NN.csv on top of its text.csv), in German or,
with --lang en, in English (only the patch's own texts; the rest stays German).
Copy both into the game folder. Nothing is written next to the original exe.
"""
import argparse
import hashlib
import os
import struct
import sys

PATCH_VERSION = "1.8"           # the version in README / CHANGELOG and in the release zips' names
ORIGINAL_SHA256 = "272bfad50336ec4c"  # first 16 hex digits are enough to pin the build
ORIGINAL_SIZE = 0x224000
IMAGE_BASE = 0x400000
SECTION_NAME = b".mod200\0"
SECTION_RVA = 0x4C0000          # == SizeOfImage of the original
SECTION_RAW = ORIGINAL_SIZE     # appended at the end of the file
SECTION_SIZE = 0x2000
SIGNATURE_PREFIX = b"MHK2 200cc mod"
SIGNATURE = SIGNATURE_PREFIX + b" 1.8\0"
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
)
KART_ROWS = 7                   # the first seven values are on the page "Kart", the others on "Welt"
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
# Items of the tuning page: 0 "Vorlage", 1 "Kart", 2 "Welt", 3 "Zurücksetzen",
# 4 "Eigene Vorlagen", 5 "Weiter", 6 "Zurück", 7 the warning, 8 the values (the title is the
# last item).
# Page "Kart": items 0..6 the kart values, 7 "Zurück"; page "Welt": item 0 "Schwerkraft",
# 1 "Zurück". A "row" counts 0 "Vorlage", 1..8 the values.
TUNE_ITEM_KART, TUNE_ITEM_WORLD, TUNE_ITEM_RESET, TUNE_ITEM_OWN, TUNE_ITEM_NEXT, TUNE_ITEM_BACK = range(1, 7)
TUNE_Y_PRESET = 130
TUNE_Y_VALUES = 168             # the values as on the page of own presets, grouped "Kart" / "Welt"
TUNE_ITEM_VALUES = 8
TUNE_Y_BUTTONS = (262, 296, 338, 372, 482, 526)   # Kart, Welt, Zurücksetzen, Eigene Vorlagen, Weiter, Zurück
TUNE_Y0, TUNE_Y_STEP = 152, 33  # the value rows of the pages "Kart" and "Welt"
TUNE_Y_BACK = 526
# Warnings: combinations of values that do not break the physics but hardly make a race (the
# computer karts stand stuck for long, ...), found in races with computer karts. Each page has a
# label that shows the text of the first rule whose conditions all hold, or nothing. A condition
# is (value number 0..7, ">=" or "<=", limit). The label is the item behind the page's buttons.
# Measured on 2026-11-19 (45 s races, six computer karts, first and second track; "stuck" =
# seconds they stood nearly still, all six added up; the defaults: 4 to 6 s):
# - Gewicht 400 % with Motorkraft 400 % or more: 17 to 31 s (Gewicht 400 with 200: 8 s,
#   Gewicht 300 with 500: 7 s).
# - Anpressdruck 0 % with Übersetzung 3.00 or more: 24 to 26 s (at 2.50: 8.5 s; Anpressdruck 25
#   at 4.00: 11 s).
# - Übersetzung 4.00 with Motorkraft 1000 % and Anpressdruck 100 % or less: 8 to 28 s,
#   "Dragster" 14 to 27 s; with Anpressdruck 800, Haftung 400 ("Wahnsinn") 3 to 8 s.
TUNE_WARNINGS = (
    ("Hohes Gewicht und viel Motorkraft:<br>die Computer-Karts bleiben oft stecken",
     ((3, ">=", 400), (1, ">=", 400))),
    ("Kein Anpressdruck bei langer Übersetzung:<br>die Computer-Karts bleiben oft stecken",
     ((6, "<=", 0), (0, ">=", 300))),
    ("Volle Übersetzung und Motorkraft bei wenig Anpressdruck:<br>"
     "die Computer-Karts bleiben oft stecken",
     ((0, ">=", 400), (1, ">=", 1000), (6, "<=", 100))),
)
TXT_TUNE_WARN = (224, 225, 226, 227, 228, 229, 238, 239)    # one text per rule
assert len(TUNE_WARNINGS) <= len(TXT_TUNE_WARN)
TUNE_WARN_ITEM = {"tuning": 7, "kart": 8, "world": 2}      # the label's item on each page
TUNE_Y_WARN = {"tuning": 418, "kart": 400, "world": 230}
# Built-in presets of the "Vorlage" row: name and the eight values in the order of TUNE_ROWS.
# Left / right on the row copies the previous / next one into the values. The row shows the
# first preset that equals the values, or "Ungespeichert". The classes' gearing (1.468, 1.545)
# does not fit two decimals, so their copies read 1.47 and 1.55.
TUNE_PRESETS = (
    ("50 cc",         (90, 100, 100, 100, 100, 100, 100, 100)),
    ("100 cc",        (110, 100, 100, 100, 100, 100, 100, 100)),
    ("150 cc",        (130, 100, 100, 100, 100, 100, 100, 100)),
    ("200 cc",        (147, 150, 100, 100, 100, 100, 100, 100)),
    ("250 cc",        (155, 200, 100, 100, 100, 100, 100, 100)),   # = the defaults
    ("Rakete",        (250, 500, 200, 100, 200, 100, 100, 100)),
    ("Formel 1",      (200, 600, 300, 100, 300, 100, 300, 100)),
    ("Rallye",        (155, 300, 75, 100, 100, 150, 50, 100)),
    ("Glatteis",      (155, 200, 50, 100, 100, 100, 50, 100)),
    ("Schwergewicht", (155, 200, 100, 300, 200, 100, 100, 100)),
    ("Federgewicht",  (155, 100, 100, 50, 100, 100, 100, 100)),
    ("Dragster",      (400, 1000, 200, 150, 100, 50, 50, 100)),
    ("Schnecke",      (50, 100, 100, 100, 100, 100, 100, 100)),
    ("Wahnsinn",      (400, 1000, 400, 50, 400, 200, 800, 100)),
    ("Mondfahrt",     (155, 200, 100, 100, 100, 100, 100, 25)),
    ("Jupiter",       (155, 200, 100, 100, 100, 100, 100, 250)),
)
TUNE_PRESET_DEFAULT = 4         # "250 cc"
assert TUNE_VALUES + 4 * len(TUNE_ROWS) <= TUNE_MARK - 0x10   # rank 5's name ends 10h bytes before the marker
assert TUNE_PRESETS[TUNE_PRESET_DEFAULT][1] == tuple(row[3] for row in TUNE_ROWS)
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
assert OWN_FILLED == 2 * (len(TUNE_ROWS) - 1) and OWN_NAME >= 2 * len(TUNE_ROWS)
assert TUNE_ROWS[-1][0] > 0         # so a filled slot never has a zero there
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
assert TUNE_LAST + 4 <= TUNE_VALUES - 0x80     # entry 62 (the tuning values' entry) starts at 2DCCh
PRESETS_ALL = len(TUNE_PRESETS) + OWN_SLOTS    # numbers of the "Vorlage" row: built-in, then own slots
PAGE_OWN = 0x1E
PAGE_NAME = 0x13                # the game's name entry page; renames a slot while OWN_FLAG is set
OWN_Y_SLOT, OWN_Y_VALUES = 130, 184
OWN_Y_BUTTONS = (290, 330, 370, 410)            # Laden, Speichern, Umbenennen, Löschen
OWN_Y_BACK = 526

# --- addresses inside the original executable -------------------------------
GP_GET = 0x00403790        # GameParameters* GameParameters::Instance()   (clobbers eax, ecx)
GP_POINTER = 0x005E84EC    # where Instance() keeps the object once it exists
LS_GET = 0x00401940        # LevelSettings*  LevelSettings::Instance()
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
TXT_KART_BUTTON, TXT_WORLD_BUTTON = 234, 235    # the tuning page's buttons to the two pages
TXT_KART_TITLE, TXT_WORLD_TITLE = 236, 237
TXT_TUNE_RESET = 0xF8      # 248: "Zurücksetzen"
TXT_TUNE_PRESET = 0xF9     # 249: the "Vorlage" row, a wsprintf format for the name
TXT_TUNE_PRESET0 = 0xFA    # 250..265: names of the presets
TXT_TUNE_OWN = 278         # "Ungespeichert"
TXT_OWN_DEFAULT = 279      # default name of a slot, "Eigene %d"
TXT_OWN_TITLE = 266        # 266..277 without 270: the page of own presets (the game takes every
                           # text with an id from 400 to 499 as a track name, so 4xx is out)
TXT_OWN_BUTTON = 267       # the tuning page's button
TXT_OWN_SLOT = 268         # "Platz %d: %s"
TXT_OWN_VALUES = 269       # the values of a slot or of the tuning page, 9 numbers (at most 228 characters)
TXT_OWN_EMPTY = 271
assert TXT_TUNE_PRESET0 + len(TUNE_PRESETS) <= TXT_OWN_TITLE
assert len(TUNE_ROWS) == 8          # rows 9.. would need text ids behind 233
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
TXT_BACK_OPTIONS = 0xD9    # 217: the options menu's own "Zurück"
# options menu rows; the stock page uses 160/200, 250/290, 350, 410/450, 520
OPTIONS_Y = (128, 166, 210, 248, 296, 344, 382)   # music, effects, resolution, quality
OPTIONS_Y_STOCK = (160, 200, 250, 290, 350, 410, 450)
OPTIONS_Y_PHYS_LABEL = 426
OPTIONS_Y_PHYS_VALUE = 464
OPTIONS_Y_BACK = 526
OPTIONS_ITEM_PHYS = 8      # items 0..6 as before, 7 heading, 8 value, 9 "Zurück"
MENU_ITEM_SIZE = 0x54

TXT_GROUP = "<color 255 170 0 255>%s</color>"     # "Kart:" / "Welt:" in the values text

# The patch's texts in German (the game's language) and English. Only these texts change; the
# rest of the menus comes from the game's own text.csv. Both go into text-20.csv, the file the
# German game reads; --lang picks one. Each language has the same keys.
TEXTS = {
    "de": {
        "phys": "60-FPS-Fahrphysik", "off": "Aus", "on": "An", "tuning": "Tuning",
        "rows": ("Übersetzung", "Motorkraft", "Haftung", "Gewicht", "Bremsen", "Lenkung",
                 "Anpressdruck", "Schwerkraft"),
        "warn": tuple(text for text, _ in TUNE_WARNINGS),
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
    },
    "en": {
        "phys": "60 FPS driving physics", "off": "Off", "on": "On", "tuning": "Tuning",
        "rows": ("Gearing", "Engine power", "Grip", "Weight", "Brakes", "Steering",
                 "Downforce", "Gravity"),
        "warn": ("High weight and much engine power:<br>the computer karts often get stuck",
                 "No downforce with long gearing:<br>the computer karts often get stuck",
                 "Full gearing and engine power with little downforce:<br>"
                 "the computer karts often get stuck"),
        "kart": "Kart", "world": "World", "reset": "Reset", "preset": "Preset",
        "presets": ("50 cc", "100 cc", "150 cc", "200 cc", "250 cc", "Rocket", "Formula 1",
                    "Rally", "Black Ice", "Heavyweight", "Featherweight", "Dragster", "Snail",
                    "Madness", "Moon Ride", "Jupiter"),
        "unsaved": "Unsaved", "own_default": "Custom", "own": "Own presets",
        "slot": "Slot", "empty": "(empty)", "load": "Load", "save": "Save",
        "rename": "Rename", "delete": "Delete", "rename_title": "Rename preset",
        "rename_prompt": "New name for slot %d:<br>(leave empty for the default name)",
        "hint": "Before you can choose a higher engine class,"
                "<br>you have to win both championships first!",
        "unlock": "You have unlocked the %s championship<br>in the %scc class!",
        "first": "first", "second": "second",
    },
}
assert all(TEXTS[lang].keys() == TEXTS["de"].keys() for lang in TEXTS)
assert all(len(TEXTS[lang]["presets"]) == len(TUNE_PRESETS) and len(TEXTS[lang]["warn"]) == len(TUNE_WARNINGS)
           and len(TEXTS[lang]["rows"]) == len(TUNE_ROWS) for lang in TEXTS)


def text_overrides(lang="de"):
    """The contents of text-20.csv in one language."""
    t = TEXTS[lang]
    title = "<font 30px_redoutline>%s</font>"
    row = dict(zip(range(TXT_TUNE_ROW0, TXT_TUNE_ROW0 + 7), t["rows"][:7]))
    r = t["rows"]
    lines = [
        (221, title % t["phys"]), (222, t["off"]), (223, t["on"]),
        (240, title % t["tuning"]),
        (TXT_TUNE_ROW0, r[0] + ": %d.%02d"),
    ] + [(n, row[n] + ": %d %%") for n in range(TXT_TUNE_ROW0 + 1, TXT_TUNE_ROW0 + 7)] + [
        (TXT_TUNE_ROW8, r[7] + ": %d %%"),
    ] + [(TXT_TUNE_WARN[n], "<scale 0.6><color 255 210 64 255>%s</color></scale>" % text)
         for n, text in enumerate(t["warn"])] + [
        (234, t["kart"]), (235, t["world"]),
        (236, title % t["kart"]), (237, title % t["world"]),
        (248, t["reset"]), (249, t["preset"] + ": %s"),
    ] + [(TXT_TUNE_PRESET0 + n, name) for n, name in enumerate(t["presets"])] + [
        (TXT_TUNE_OWN, t["unsaved"]),
        (TXT_OWN_DEFAULT, t["own_default"] + " %d"),
        (266, title % t["own"]), (267, t["own"]),
        (268, t["slot"] + " %d: %s"),
        (269, "<scale 0.6>" + TXT_GROUP % (t["kart"] + ":")
         + " %s %%d.%%02d, %s %%d %%%%, %s %%d %%%%,<br>" % r[0:3]
         + "%s %%d %%%%, %s %%d %%%%, %s %%d %%%%, %s %%d %%%%<br>" % r[3:7]
         + TXT_GROUP % (t["world"] + ":") + " %s %%d %%%%</scale>" % r[7]),
        (271, "<scale 0.6>%s</scale>" % t["empty"]),
        (272, t["load"]), (273, t["save"]), (274, t["rename"]), (275, t["delete"]),
        (276, title % t["rename_title"]),
        (277, t["rename_prompt"]),
        (335, "200 cc"), (336, "250 cc"), (337, t["tuning"]),
        (338, "<color 128 128 128 255>200 cc</color>"),
        (339, "<color 128 128 128 255>250 cc</color>"),
        (342, "<font 30px_redoutline><scale 0.5>%s</scale></font>" % t["hint"]),
        (583, t["unlock"] % (t["second"], "200")),
        (586, t["unlock"] % (t["first"], "200")),
        (587, t["unlock"] % (t["first"], "250")),
        (588, t["unlock"] % (t["second"], "250")),
    ]
    # the game lists every text with an id from 400 to 499 as a track ("Available tracks" in log.txt)
    assert not any(400 <= n < 500 for n, _ in lines)
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


def build_payload(base, factors, pulls, known=None):
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
    off = TUNE_VALUES + 4 * (len(TUNE_ROWS) - 1)
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
    a.jmp_short("pull_mul_done")
    a.label("pull_mul_tuning")                    # the tuning class: its own "Motorkraft", in percent
    a.raw("83 F8 05", "cmp         eax,5")
    a.jcc_short("jne", "pull_mul_done")
    a.raw("8B 81 " + _le(gp_disp), "mov         eax,dword ptr [ecx+%08Xh]" % gp_disp)
    a.raw("DA 88 " + _le(TUNE_VALUES + 4), "fimul       dword ptr [eax+%08Xh]" % (TUNE_VALUES + 4))
    disp = (later("hundredth") - a.labels["pull_mul_pc"]) & 0xFFFFFFFF
    a.raw("D8 89 " + _le(disp), "fmul        dword ptr [ecx+%08Xh]" % disp)
    a.label("pull_mul_done")
    a.raw("59", "pop         ecx")
    a.raw("58", "pop         eax")
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

    a.label("engine_menu_item")
    a.raw("83 EC 1C", "sub         esp,1Ch")
    for cls, text_id, locked_id in ((3, TXT_200CC, TXT_200CC_LOCKED), (4, TXT_250CC, TXT_250CC_LOCKED)):
        a.call(GP_GET)
        a.raw("83 B8 08 FD 00 00 %02X" % cls, "cmp         dword ptr [eax+0000FD08h],%d" % cls)
        a.jcc_short("jl", "engine_menu_locked_%d" % cls)
        menu_item(text_id, ADD_BUTTON, MENU_Y_CLASSES[cls])
        a.jmp_short("engine_menu_done_%d" % cls)
        a.label("engine_menu_locked_%d" % cls)
        menu_item(locked_id, ADD_LABEL, MENU_Y_CLASSES[cls])
        a.label("engine_menu_done_%d" % cls)
        a.raw("8B CC", "mov         ecx,esp")
        a.call(STR_DTOR)
    menu_item(TXT_TUNING, ADD_BUTTON, MENU_Y_CLASSES[5])            # the tuning class is never locked
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
    a.raw("83 C1 %02X" % (len(TUNE_PRESETS) - OLD_PRESETS), "add         ecx,%s" % _imm(len(TUNE_PRESETS) - OLD_PRESETS))
    a.label("values8_last")
    a.raw("89 88 " + _le(TUNE_LAST), "mov         dword ptr [eax+%08Xh],ecx" % TUNE_LAST)
    a.raw("C7 80 %s %s" % (_le(OLD_TUNE_LAST), _le(TUNE_ROWS[-1][3])),
          "mov         dword ptr [eax+%08Xh],%s" % (OLD_TUNE_LAST, _imm(TUNE_ROWS[-1][3])))
    a.raw("8D 90 " + _le(OWN_BASE + OWN_FILLED), "lea         edx,[eax+%08Xh]" % (OWN_BASE + OWN_FILLED))
    a.raw("B9 " + _le(OWN_SLOTS), "mov         ecx,%s" % _imm(OWN_SLOTS))
    a.label("values8_slot")
    a.raw("66 83 3A 00", "cmp         word ptr [edx],0")
    a.jcc_short("je", "values8_empty")
    a.raw("66 C7 02 " + struct.pack("<H", TUNE_ROWS[-1][3]).hex(" "), "mov         word ptr [edx],%s" % _imm(TUNE_ROWS[-1][3]))
    a.label("values8_empty")
    a.raw("83 C2 %02X" % OWN_SLOT, "add         edx,%s" % _imm(OWN_SLOT))
    a.raw("49", "dec         ecx")
    a.jcc_short("jne", "values8_slot")
    a.raw("C7 80 %s %s" % (_le(VALUES8_MARK), _le(VALUES8_MAGIC)),
          "mov         dword ptr [eax+%08Xh],%s" % (VALUES8_MARK, _imm(VALUES8_MAGIC)))
    a.label("values8_done")
    a.raw("81 B8 %s %s" % (_le(TUNE_MARK), _le(TUNE_MAGIC)),
          "cmp         dword ptr [eax+%08Xh],%s" % (TUNE_MARK, _imm(TUNE_MAGIC)))
    a.jcc_short("je", "tune_defaults_done")
    a.label("tune_reset")                         # eax = GameParameters
    a.raw("C7 80 %s %s" % (_le(TUNE_MARK), _le(TUNE_MAGIC)),
          "mov         dword ptr [eax+%08Xh],%s" % (TUNE_MARK, _imm(TUNE_MAGIC)))
    a.raw("C7 80 %s %s" % (_le(TUNE_LAST), _le(TUNE_PRESET_DEFAULT)),
          "mov         dword ptr [eax+%08Xh],%s" % (TUNE_LAST, _imm(TUNE_PRESET_DEFAULT)))
    a.raw("33 C9", "xor         ecx,ecx")
    a.label("tune_defaults_next")
    disp = tdisp("tune_rows") + 6 & 0xFFFFFFFF
    a.raw("0F B7 94 CD " + _le(disp), "movzx       edx,word ptr [ebp+ecx*8+%08Xh]" % disp)   # the row's default
    a.raw("89 94 88 " + _le(TUNE_VALUES), "mov         dword ptr [eax+ecx*4+%08Xh],edx" % TUNE_VALUES)
    a.raw("41", "inc         ecx")
    a.raw("83 F9 %02X" % len(TUNE_ROWS), "cmp         ecx,%d" % len(TUNE_ROWS))
    a.jcc_short("jb", "tune_defaults_next")
    # tracks 5-8 and Meisterschaft 2 are open in the tuning class from the start
    a.raw("83 88 0C FD 00 00 20", "or          dword ptr [eax+0000FD0Ch],20h")
    a.label("tune_defaults_done")
    a.raw("C3", "ret")

    # wsprintf with a format from the text file: [esp+4] = buffer, [esp+8] = text id,
    # [esp+0Ch].. = up to nine arguments (the caller removes them). ebp = tune_T.
    # Clobbers eax, ecx, edx.
    a.label("tune_printf")
    a.raw("83 EC 1C", "sub         esp,1Ch")
    get_text("FF 74 24 28", "push        dword ptr [esp+28h]")
    for _ in range(9):                            # the arguments, the last one first
        a.raw("FF 74 24 48", "push        dword ptr [esp+48h]")
    a.raw("50", "push        eax")                # the format
    a.raw("FF 74 24 48", "push        dword ptr [esp+48h]")              # the buffer
    t_call_import(IMP_WSPRINTF)
    a.raw("83 C4 2C", "add         esp,2Ch")
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

    # Where are the eight words of preset eax (0..15 built-in, 16..23 own slots)? Returns
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
    a.raw("6B F8 %02X" % (2 * len(TUNE_ROWS)), "imul        edi,eax,%s" % _imm(2 * len(TUNE_ROWS)))
    a.raw("8D BC 3D " + _le(tdisp("tune_presets")), "lea         edi,[ebp+edi+%08Xh]" % tdisp("tune_presets"))
    a.raw("C3", "ret")                            # not zero: "not equal"

    # Do the eight words at edi equal the eight values? Returns "equal" if they do.
    # ebx = GameParameters. Clobbers ecx, edx.
    a.label("tune_equal")
    a.raw("33 C9", "xor         ecx,ecx")
    a.label("tune_equal_next")
    a.raw("0F B7 14 4F", "movzx       edx,word ptr [edi+ecx*2]")
    a.raw("3B 94 8B " + _le(TUNE_VALUES), "cmp         edx,dword ptr [ebx+ecx*4+%08Xh]" % TUNE_VALUES)
    a.jcc_short("jne", "tune_equal_done")
    a.raw("41", "inc         ecx")
    a.raw("83 F9 %02X" % len(TUNE_ROWS), "cmp         ecx,%d" % len(TUNE_ROWS))
    a.jcc_short("jb", "tune_equal_next")
    a.raw("33 C9", "xor         ecx,ecx")         # "equal"
    a.label("tune_equal_done")
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
    a.jcc_short("jb", "tune_preset_name_text")
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
    disp = TXT_TUNE_ROW8 - (KART_ROWS + 1)
    a.raw("8D 87 " + _le(disp), "lea         eax,[edi+%08Xh]" % disp)    # rows 8..: from text 233 on
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

    # The values text (text 269, grouped "Kart" / "Welt") of eight values as words.
    # edx = the words, eax = buffer (100h bytes), ebp = tune_T. Clobbers eax, ecx, edx.
    a.label("values_text")
    a.raw("57", "push        edi")
    a.raw("8B F8", "mov         edi,eax")
    a.raw("B9 %s" % _le(len(TUNE_ROWS) - 1), "mov         ecx,%d" % (len(TUNE_ROWS) - 1))
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
    a.raw("68 " + _le(TXT_OWN_VALUES), "push        %s" % _imm(TXT_OWN_VALUES))
    a.raw("57", "push        edi")
    a.call("tune_printf")
    n = 4 * (len(TUNE_ROWS) - 1 + 2 + 2)
    a.raw("83 C4 %02X" % n, "add         esp,%s" % _imm(n))
    a.raw("5F", "pop         edi")
    a.raw("C3", "ret")

    # The values text of the tuning values. edx = buffer (100h bytes), ebp = tune_T.
    # Clobbers eax, ecx, edx.
    a.label("tune_values_text")
    a.raw("52", "push        edx")
    words = 2 * len(TUNE_ROWS)
    a.raw("83 EC %02X" % words, "sub         esp,%s" % _imm(words))
    t_mov("eax", GP_POINTER)
    a.raw("B9 %s" % _le(len(TUNE_ROWS) - 1), "mov         ecx,%d" % (len(TUNE_ROWS) - 1))
    a.label("tune_values_text_copy")
    a.raw("8B 94 88 " + _le(TUNE_VALUES), "mov         edx,dword ptr [eax+ecx*4+%08Xh]" % TUNE_VALUES)
    a.raw("66 89 14 4C", "mov         word ptr [esp+ecx*2],dx")
    a.raw("49", "dec         ecx")
    a.jcc_short("jns", "tune_values_text_copy")
    a.raw("8B D4", "mov         edx,esp")
    a.raw("8B 44 24 %02X" % words, "mov         eax,dword ptr [esp+%s]" % _imm(words))
    a.call("values_text")
    a.raw("83 C4 %02X" % (words + 4), "add         esp,%s" % _imm(words + 4))
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
    # one): builds the tuning page, the pages "Kart" and "Welt" and the page of own presets.
    # Any page that is built ends a renaming on the name page.
    def warn_label(y_push_hex, y_push_text, routine="tune_warn_text"):
        """Adds the warning label (an empty text while no rule holds), or the label of another
        text routine (edx = buffer). esi = menu, ebp = tune_T.
        The y is pushed after the text is made, so it must not be in eax, ecx or edx."""
        a.raw("81 EC 00 01 00 00", "sub         esp,100h")
        a.raw("8B D4", "mov         edx,esp")
        a.call(routine)
        a.raw(y_push_hex, y_push_text)
        a.raw("8D 44 24 04", "lea         eax,[esp+4]")
        a.raw("50", "push        eax")
        a.raw("8B CE", "mov         ecx,esi")
        a.call(ADD_LABEL)
        a.raw("81 C4 00 01 00 00", "add         esp,100h")

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
    a.raw("83 F8 %02X" % PAGE_OWN, "cmp         eax,%s" % _imm(PAGE_OWN))
    a.jcc_near("je", "own_build")
    a.raw("83 F8 %02X" % PAGE_KART, "cmp         eax,%s" % _imm(PAGE_KART))
    a.jcc_near("je", "sub_build")
    a.raw("83 F8 %02X" % PAGE_WORLD, "cmp         eax,%s" % _imm(PAGE_WORLD))
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
    for text_id, y in zip((TXT_KART_BUTTON, TXT_WORLD_BUTTON, TXT_TUNE_RESET, TXT_OWN_BUTTON, TXT_NEXT, TXT_BACK),
                          TUNE_Y_BUTTONS):        # items 1..6
        a.raw("B8 " + _le(text_id), "mov         eax,%s" % _imm(text_id))
        a.raw("BA " + _le(y), "mov         edx,%s" % _imm(y))
        a.call("tune_button")
    y = TUNE_Y_WARN["tuning"]
    warn_label("68 " + _le(y), "push        %s" % _imm(y))   # item 7
    warn_label("68 " + _le(TUNE_Y_VALUES), "push        %s" % _imm(TUNE_Y_VALUES),
               "tune_values_text")                              # item 8
    a.raw("B8 " + _le(TXT_TUNE_TITLE), "mov         eax,%s" % _imm(TXT_TUNE_TITLE))
    a.call("tune_title")
    a.raw("C7 86 48 01 00 00 %s" % _le(TUNE_ITEM_NEXT),
          "mov         dword ptr [esi+00000148h],%s" % _imm(TUNE_ITEM_NEXT))   # "Weiter" is selected
    a.raw("61", "popad")
    a.raw("C2 04 00", "ret         4")

    # The pages "Kart" (rows 1..7) and "Welt" (rows 8..): one arrow item per row, then
    # "Zurück" and the title. eax = the page.
    a.label("sub_build")
    a.raw("60", "pushad")
    a.raw("8B F1", "mov         esi,ecx")
    a.raw("8B D8", "mov         ebx,eax")
    a.call("tune_base")
    a.raw("8D 8E 30 01 00 00", "lea         ecx,[esi+00000130h]")
    a.call(ITEMS_CLEAR)
    a.call("tune_defaults")
    a.raw("BF 01 00 00 00", "mov         edi,1")
    a.raw("83 FB %02X" % PAGE_KART, "cmp         ebx,%s" % _imm(PAGE_KART))
    a.jcc_short("je", "sub_build_row")
    a.raw("BF " + _le(KART_ROWS + 1), "mov         edi,%s" % _imm(KART_ROWS + 1))
    a.label("sub_build_row")
    a.raw("83 EC 40", "sub         esp,40h")
    a.raw("8B C7", "mov         eax,edi")
    a.raw("8B D4", "mov         edx,esp")
    a.call("tune_text")
    a.raw("8B C7", "mov         eax,edi")      # y of the n-th row of the page
    a.raw("83 FB %02X" % PAGE_KART, "cmp         ebx,%s" % _imm(PAGE_KART))
    a.jcc_short("je", "sub_build_y")
    a.raw("83 E8 %02X" % KART_ROWS, "sub         eax,%s" % _imm(KART_ROWS))
    a.label("sub_build_y")
    a.raw("6B C0 %02X" % TUNE_Y_STEP, "imul        eax,eax,%s" % _imm(TUNE_Y_STEP))
    a.raw("05 " + _le(TUNE_Y0 - TUNE_Y_STEP), "add         eax,%s" % _imm(TUNE_Y0 - TUNE_Y_STEP))
    arrow_row("50", "push        eax")
    a.raw("47", "inc         edi")
    a.raw("83 FB %02X" % PAGE_KART, "cmp         ebx,%s" % _imm(PAGE_KART))
    a.jcc_short("jne", "sub_build_world_end")
    a.raw("83 FF %02X" % (KART_ROWS + 1), "cmp         edi,%s" % _imm(KART_ROWS + 1))
    a.jcc_short("jb", "sub_build_row")
    a.jmp_short("sub_build_done")
    a.label("sub_build_world_end")
    a.raw("83 FF %02X" % (len(TUNE_ROWS) + 1), "cmp         edi,%s" % _imm(len(TUNE_ROWS) + 1))
    a.jcc_short("jb", "sub_build_row")
    a.label("sub_build_done")
    a.raw("B8 " + _le(TXT_BACK), "mov         eax,%s" % _imm(TXT_BACK))
    a.raw("BA " + _le(TUNE_Y_BACK), "mov         edx,%s" % _imm(TUNE_Y_BACK))
    a.call("tune_button")
    a.raw("BF " + _le(TUNE_Y_WARN["kart"]), "mov         edi,%s" % _imm(TUNE_Y_WARN["kart"]))   # (the text routine clobbers eax)
    a.raw("83 FB %02X" % PAGE_KART, "cmp         ebx,%s" % _imm(PAGE_KART))
    a.jcc_short("je", "sub_build_warn")
    a.raw("BF " + _le(TUNE_Y_WARN["world"]), "mov         edi,%s" % _imm(TUNE_Y_WARN["world"]))
    a.label("sub_build_warn")
    warn_label("57", "push        edi")              # behind "Zurück"
    a.raw("B8 " + _le(TXT_KART_TITLE), "mov         eax,%s" % _imm(TXT_KART_TITLE))
    a.raw("83 FB %02X" % PAGE_KART, "cmp         ebx,%s" % _imm(PAGE_KART))
    a.jcc_short("je", "sub_build_title")
    a.raw("B8 " + _le(TXT_WORLD_TITLE), "mov         eax,%s" % _imm(TXT_WORLD_TITLE))
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
    a.raw("81 EC 00 01 00 00", "sub         esp,100h")
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
    a.raw("81 C4 00 01 00 00", "add         esp,100h")
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

    # Which warning do the values call for? ebx = GameParameters, ebp = tune_T.
    # Returns eax = the text id of the first rule whose conditions all hold, or 0. Clobbers ecx, edx.
    a.label("tune_warning")
    a.raw("56", "push        esi")
    a.raw("57", "push        edi")
    t_lea("esi", "tune_warnings")
    a.label("tune_warning_rule")
    a.raw("0F B6 0E", "movzx       ecx,byte ptr [esi]")              # number of conditions, 0 ends the table
    a.raw("85 C9", "test        ecx,ecx")
    a.jcc_short("je", "tune_warning_none")
    a.raw("0F B7 7E 01", "movzx       edi,word ptr [esi+1]")         # the text; 0 once a condition fails
    a.raw("83 C6 03", "add         esi,3")
    a.label("tune_warning_cond")
    a.raw("0F B6 16", "movzx       edx,byte ptr [esi]")              # value number, 80h: "<="
    a.raw("0F B7 46 01", "movzx       eax,word ptr [esi+1]")         # the limit
    a.raw("83 C6 03", "add         esi,3")
    a.raw("F6 C2 80", "test        dl,80h")
    a.jcc_short("jne", "tune_warning_le")
    a.raw("39 84 93 " + _le(TUNE_VALUES), "cmp         dword ptr [ebx+edx*4+%08Xh],eax" % TUNE_VALUES)
    a.jcc_short("jge", "tune_warning_ok")
    a.raw("33 FF", "xor         edi,edi")
    a.jmp_short("tune_warning_ok")
    a.label("tune_warning_le")
    a.raw("83 E2 7F", "and         edx,7Fh")
    a.raw("39 84 93 " + _le(TUNE_VALUES), "cmp         dword ptr [ebx+edx*4+%08Xh],eax" % TUNE_VALUES)
    a.jcc_short("jle", "tune_warning_ok")
    a.raw("33 FF", "xor         edi,edi")
    a.label("tune_warning_ok")
    a.raw("49", "dec         ecx")
    a.jcc_short("jne", "tune_warning_cond")
    a.raw("85 FF", "test        edi,edi")
    a.jcc_short("je", "tune_warning_rule")
    a.raw("8B C7", "mov         eax,edi")
    a.jmp_short("tune_warning_done")
    a.label("tune_warning_none")
    a.raw("33 C0", "xor         eax,eax")
    a.label("tune_warning_done")
    a.raw("5F", "pop         edi")
    a.raw("5E", "pop         esi")
    a.raw("C3", "ret")

    # The warning's text, or an empty one. edx = buffer (100h bytes), ebp = tune_T.
    # Clobbers eax, ecx, edx.
    a.label("tune_warn_text")
    a.raw("53", "push        ebx")
    a.raw("56", "push        esi")
    a.raw("8B F2", "mov         esi,edx")
    t_mov("ebx", GP_POINTER)
    a.call("tune_warning")
    a.raw("C6 06 00", "mov         byte ptr [esi],0")
    a.raw("85 C0", "test        eax,eax")
    a.jcc_short("je", "tune_warn_text_done")
    a.raw("50", "push        eax")
    a.raw("56", "push        esi")
    a.call("tune_printf")
    a.raw("83 C4 08", "add         esp,8")
    a.label("tune_warn_text_done")
    a.raw("5E", "pop         esi")
    a.raw("5B", "pop         ebx")
    a.raw("C3", "ret")

    # Which row does an item of the current page show? eax = item, esi = menu.
    # Returns eax = the row (0 "Vorlage", 1..8 the values) or -1. Clobbers ecx.
    a.label("tune_item_row")
    a.raw("8B 8E 40 01 00 00", "mov         ecx,dword ptr [esi+00000140h]")
    a.raw("83 F9 %02X" % PAGE_KART, "cmp         ecx,%s" % _imm(PAGE_KART))
    a.jcc_short("jne", "tune_item_row_world")
    a.raw("83 F8 %02X" % (KART_ROWS - 1), "cmp         eax,%d" % (KART_ROWS - 1))
    a.jcc_short("ja", "tune_item_row_none")
    a.raw("40", "inc         eax")
    a.raw("C3", "ret")
    a.label("tune_item_row_world")
    a.raw("83 F9 %02X" % PAGE_WORLD, "cmp         ecx,%s" % _imm(PAGE_WORLD))
    a.jcc_short("jne", "tune_item_row_tuning")
    a.raw("83 F8 %02X" % (len(TUNE_ROWS) - KART_ROWS - 1), "cmp         eax,%d" % (len(TUNE_ROWS) - KART_ROWS - 1))
    a.jcc_short("ja", "tune_item_row_none")
    a.raw("83 C0 %02X" % (KART_ROWS + 1), "add         eax,%s" % _imm(KART_ROWS + 1))
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
    a.raw("81 EC 00 01 00 00", "sub         esp,100h")
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
    a.raw("81 C4 00 01 00 00", "add         esp,100h")
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
    a.raw("B8 " + _le(TUNE_WARN_ITEM["tuning"]), "mov         eax,%s" % _imm(TUNE_WARN_ITEM["tuning"]))   # the warning label
    a.raw("8B 8E 40 01 00 00", "mov         ecx,dword ptr [esi+00000140h]")
    a.raw("83 F9 %02X" % PAGE_KART, "cmp         ecx,%s" % _imm(PAGE_KART))
    a.jcc_short("jne", "tune_refresh_world")
    a.raw("B8 " + _le(TUNE_WARN_ITEM["kart"]), "mov         eax,%s" % _imm(TUNE_WARN_ITEM["kart"]))
    a.label("tune_refresh_world")
    a.raw("83 F9 %02X" % PAGE_WORLD, "cmp         ecx,%s" % _imm(PAGE_WORLD))
    a.jcc_short("jne", "tune_refresh_warn")
    a.raw("B8 " + _le(TUNE_WARN_ITEM["world"]), "mov         eax,%s" % _imm(TUNE_WARN_ITEM["world"]))
    a.label("tune_refresh_warn")
    a.raw("50", "push        eax")
    a.raw("81 EC 00 01 00 00", "sub         esp,100h")
    a.raw("8B D4", "mov         edx,esp")
    a.call("tune_warn_text")
    a.raw("8B 84 24 00 01 00 00", "mov         eax,dword ptr [esp+00000100h]")
    a.raw("8B D4", "mov         edx,esp")
    a.call("item_setstr")
    a.raw("83 BE 40 01 00 00 %02X" % PAGE_TUNING, "cmp         dword ptr [esi+00000140h],%s" % _imm(PAGE_TUNING))
    a.jcc_short("jne", "tune_refresh_end")
    a.raw("8B D4", "mov         edx,esp")      # the tuning page: its values label
    a.call("tune_values_text")
    a.raw("B8 " + _le(TUNE_ITEM_VALUES), "mov         eax,%s" % _imm(TUNE_ITEM_VALUES))
    a.raw("8B D4", "mov         edx,esp")
    a.call("item_setstr")
    a.label("tune_refresh_end")
    a.raw("81 C4 04 01 00 00", "add         esp,104h")
    a.raw("5F", "pop         edi")
    a.raw("C3", "ret")

    # Left / right on an arrow row. eax = row (0..8), edx = +1 or -1, esi = menu, ebp = tune_T.
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
    a.raw("33 C9", "xor         ecx,ecx")
    a.label("tune_preset_copy")
    a.raw("0F B7 04 4F", "movzx       eax,word ptr [edi+ecx*2]")
    a.raw("89 84 8B " + _le(TUNE_VALUES), "mov         dword ptr [ebx+ecx*4+%08Xh],eax" % TUNE_VALUES)
    a.raw("41", "inc         ecx")
    a.raw("83 F9 %02X" % len(TUNE_ROWS), "cmp         ecx,%d" % len(TUNE_ROWS))
    a.jcc_short("jb", "tune_preset_copy")
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
    a.raw("0F B7 11", "movzx       edx,word ptr [ecx]")              # minimum
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
    for page in (PAGE_OWN, PAGE_TUNING, PAGE_KART):
        a.raw("83 F8 %02X" % page, "cmp         eax,%s" % _imm(page))
        a.jcc_short("je", "page_update_go")
    a.raw("83 F8 %02X" % PAGE_WORLD, "cmp         eax,%s" % _imm(PAGE_WORLD))
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
    t_lea("eax", STR_MENU_BACK)
    a.call("tune_pressed")
    a.jcc_short("jne", "tune_no_back")
    a.label("tune_back")                          # "menu back", or "Zurück" on "Kart" and "Welt"
    a.raw("83 BE 40 01 00 00 %02X" % PAGE_TUNING, "cmp         dword ptr [esi+00000140h],%s" % _imm(PAGE_TUNING))
    a.jcc_short("jne", "tune_sub_back")
    open_page(PAGE_CLASS)
    a.jmp("tune_out")
    a.label("tune_sub_back")                      # back to the tuning page, on the button that led here
    a.raw("BF " + _le(TUNE_ITEM_KART), "mov         edi,%s" % _imm(TUNE_ITEM_KART))
    a.raw("83 BE 40 01 00 00 %02X" % PAGE_KART, "cmp         dword ptr [esi+00000140h],%s" % _imm(PAGE_KART))
    a.jcc_short("je", "tune_sub_back_open")
    a.raw("BF " + _le(TUNE_ITEM_WORLD), "mov         edi,%s" % _imm(TUNE_ITEM_WORLD))
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
    a.jcc_short("jne", "tune_sub_back")           # "Kart" and "Welt" have one button: "Zurück"
    a.raw("8B 86 48 01 00 00", "mov         eax,dword ptr [esi+00000148h]")
    for item, page in ((TUNE_ITEM_KART, PAGE_KART), (TUNE_ITEM_WORLD, PAGE_WORLD), (TUNE_ITEM_OWN, PAGE_OWN),
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
    a.raw("33 C9", "xor         ecx,ecx")
    a.label("own_load_copy")
    a.raw("0F B7 04 4F", "movzx       eax,word ptr [edi+ecx*2]")
    a.raw("89 84 8B " + _le(TUNE_VALUES), "mov         dword ptr [ebx+ecx*4+%08Xh],eax" % TUNE_VALUES)
    a.raw("41", "inc         ecx")
    a.raw("83 F9 %02X" % len(TUNE_ROWS), "cmp         ecx,%d" % len(TUNE_ROWS))
    a.jcc_short("jb", "own_load_copy")
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
    a.raw("83 F9 %02X" % len(TUNE_ROWS), "cmp         ecx,%d" % len(TUNE_ROWS))
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
    a.jcc_short("jne", "rename_game")
    t_lea("eax", STR_MENU_BACK)
    a.call("tune_pressed")
    a.jcc_short("je", "rename_done")
    t_lea("eax", STR_MENU_SELECT)
    a.call("tune_pressed")
    a.jcc_short("jne", "rename_game")
    a.raw("83 BE 48 01 00 00 00", "cmp         dword ptr [esi+00000148h],0")   # "Weiter"
    a.jcc_short("jne", "rename_game")
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

    a.label("options_items")
    a.raw("83 EC 1C", "sub         esp,1Ch")
    add_item(TXT_PHYS_LABEL, OPTIONS_Y_PHYS_LABEL, ADD_LABEL)
    drop_temp()
    phys_flag()
    a.raw("0F 94 C0", "sete        al")
    a.raw("0F B6 C0", "movzx       eax,al")
    a.raw("05 " + _le(TXT_PHYS_OFF), "add         eax,%s" % _imm(TXT_PHYS_OFF))
    a.raw("53", "push        ebx")
    a.raw("50", "push        eax")
    a.raw("8D 44 24 08", "lea         eax,[esp+8]")
    a.raw("50", "push        eax")
    text_to_item(OPTIONS_Y_PHYS_VALUE, ADD_BUTTON)
    a.raw("C7 00 03 00 00 00", "mov         dword ptr [eax],3")      # value item with arrows, like "Qualität"
    drop_temp()
    add_item(TXT_BACK_OPTIONS, OPTIONS_Y_BACK, ADD_BUTTON)
    drop_temp()
    a.raw("83 C4 1C", "add         esp,1Ch")
    a.raw("53", "push        ebx")                                   # displaced
    a.raw("8D 8C 24 A0 01 00 00", "lea         ecx,[esp+000001A0h]")  # displaced
    a.jmp(0x004206F8)

    # Flip the switch, refresh its menu text, play the menu's toggle sound.
    # esi = menu; keeps ebx, esi, edi, ebp.
    item_text = OPTIONS_ITEM_PHYS * MENU_ITEM_SIZE + 8
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
    a.raw("83 EC 1C", "sub         esp,1Ch")
    a.raw("C1 E9 08", "shr         ecx,8")
    a.raw("0F 95 C1", "setne       cl")
    a.raw("0F B6 C9", "movzx       ecx,cl")
    a.raw("81 C1 " + _le(TXT_PHYS_OFF), "add         ecx,%s" % _imm(TXT_PHYS_OFF))
    a.raw("6A 00", "push        0")
    a.raw("51", "push        ecx")
    a.raw("8D 44 24 08", "lea         eax,[esp+8]")
    a.raw("50", "push        eax")
    a.call(TEXTMGR_GET)
    a.raw("8B C8", "mov         ecx,eax")
    a.call(GET_TEXT)
    a.raw("50", "push        eax")
    a.raw("8B 8E 34 01 00 00", "mov         ecx,dword ptr [esi+00000134h]")
    a.raw("81 C1 " + _le(item_text), "add         ecx,%s" % _imm(item_text))
    a.call(STR_ASSIGN)
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
    a.raw("83 F8 09", "cmp         eax,9")
    a.jcc_short("ja", "options_select_done")
    a.jcc_short("je", "options_select_back")
    a.raw("83 F8 08", "cmp         eax,8")
    a.jcc_short("jne", "options_select_none")
    a.raw("8B 86 4C 01 00 00", "mov         eax,dword ptr [esi+0000014Ch]")
    a.raw("48", "dec         eax")
    a.raw("83 F8 01", "cmp         eax,1")
    a.jcc_short("ja", "options_select_toggle")
    a.raw("C6 86 9D 01 00 00 01", "mov         byte ptr [esi+0000019Dh],1")   # clicked an arrow: keep the mouse on it
    a.label("options_select_toggle")
    a.call("phys_toggle")
    a.label("options_select_none")
    a.raw("B8 02 00 00 00", "mov         eax,2")      # item 2 is a heading: the stock table does nothing
    a.raw("C3", "ret")
    a.label("options_select_back")
    a.raw("B8 07 00 00 00", "mov         eax,7")      # "Zurück" moved from item 7 to 9
    a.label("options_select_done")
    a.raw("C3", "ret")

    # "menu left" / "menu right" on the switch
    a.label("options_left")
    a.raw("83 BE 48 01 00 00 08", "cmp         dword ptr [esi+00000148h],8")
    a.jcc_short("jne", "options_left_plain")
    a.call("phys_toggle")
    a.label("options_left_plain")
    a.raw("8B 86 48 01 00 00", "mov         eax,dword ptr [esi+00000148h]")   # displaced
    a.raw("C3", "ret")

    a.label("options_right")
    a.raw("83 BE 48 01 00 00 08", "cmp         dword ptr [esi+00000148h],8")
    a.jcc_short("jne", "options_right_plain")
    a.call("phys_toggle")
    a.label("options_right_plain")
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
    a.label("hundredth")
    a.data(struct.pack("<f", 0.01), "float 0.01")
    a.label("stock_gravity")
    a.data(struct.pack("<f", STOCK_GRAVITY_Y), "float %g: the world's gravity" % STOCK_GRAVITY_Y)
    a.label("downforce_speed")
    a.data(struct.pack("<2f", DOWNFORCE_SPEED, DOWNFORCE_SPEED_AIR),
           "float %g, %g: where the downforce of the tuning class stops growing, on the ground and in the air" % (DOWNFORCE_SPEED, DOWNFORCE_SPEED_AIR))
    a.label("tune_rows")
    a.data(b"".join(struct.pack("<4H", *row) for row in TUNE_ROWS), "tuning rows: minimum, maximum, step, default")
    a.label("tune_presets")
    a.data(b"".join(struct.pack("<%dH" % len(TUNE_ROWS), *vals) for _, vals in TUNE_PRESETS),
           "tuning presets: the eight values of " + ", ".join(name for name, _ in TUNE_PRESETS))
    a.label("tune_warnings")
    blob = b""
    for n, (_, conds) in enumerate(TUNE_WARNINGS):
        blob += struct.pack("<BH", len(conds), TXT_TUNE_WARN[n])
        for value, op, limit in conds:
            assert op in (">=", "<=") and 0 <= value < len(TUNE_ROWS)
            blob += struct.pack("<BH", value | (0x80 if op == "<=" else 0), limit)
    a.data(blob + b"\0", "tuning warnings: conditions, text, then (value | 80h for <=, limit) per condition")
    a.label("tune_apply_table")
    a.data(b"".join(struct.pack("<BH", n, off) for n, off in TUNE_APPLY) + b"\0",
           "tuning: value number and the car field it scales")
    a.data(SIGNATURE, "signature")
    a.label("v11_file")
    a.data(V11_FILE, "a file that differs between the data versions")

    code, listing = a.finish()
    if a.labels != known:
        return build_payload(base, factors, pulls, dict(a.labels))   # second pass: forward references are known now
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

    # winning championship 2 in 150 cc unlocks 200 cc, in 200 cc unlocks 250 cc
    data(0x00414571, "83 FF 02", "83 FF 04", "unlock chain: two more classes")
    call(0x00414540, "81 C7 44 02 00 00", "unlock_text", "unlock message for championship 2 in 250 cc")

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


def patch_exe(src, factors, pulls):
    data = open(src, "rb").read()
    digest = hashlib.sha256(data).hexdigest()
    if len(data) != ORIGINAL_SIZE or not digest.startswith(ORIGINAL_SHA256):
        if SIGNATURE_PREFIX in data:
            raise SystemExit("%s already contains the 200 cc mod - start from the original exe." % src)
        raise SystemExit("%s is not the expected MHK2-XXL.exe V1.0 (sha256 %s...)." % (src, digest[:16]))
    pe = PE(data)
    base = IMAGE_BASE + SECTION_RVA
    code, listing, labels = build_payload(base, factors, pulls)
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


def unlock(settings_path):
    """Set the 'highest unlocked class' counter so that 50 cc to 250 cc are all selectable."""
    data = read_settings(settings_path)
    off = 0xFD08 - 4   # file = GameParameters object without its vtable pointer
    old = struct.unpack_from("<i", data, off)[0]
    struct.pack_into("<i", data, off, max(old, 4))
    open(settings_path, "wb").write(data)
    print("%s: highest unlocked class %d -> %d" % (settings_path, old, max(old, 4)))


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
    ap.add_argument("--unlock", metavar="SETTINGS.DAT", help="unlock all classes in a settings.dat and exit")
    ap.add_argument("--physics60", nargs=2, metavar=("on|off", "SETTINGS.DAT"),
                    help="set the 60 FPS physics switch in a settings.dat and exit")
    ap.add_argument("--player-name", nargs=2, metavar=("NAME", "SETTINGS.DAT"),
                    help="set the name written into new phantom files and exit")
    args = ap.parse_args()
    if args.unlock:
        unlock(args.unlock)
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
    patched, listing, patches = patch_exe(args.exe, factors, pulls)
    os.makedirs(os.path.join(args.outdir, "data", "MK2"), exist_ok=True)
    exe_out = os.path.join(args.outdir, "MHK2-XXL.exe")
    txt_out = os.path.join(args.outdir, "data", "MK2", "text-20.csv")
    if os.path.abspath(exe_out) == os.path.abspath(args.exe):
        raise SystemExit("refusing to overwrite the original exe - choose another output directory")
    open(exe_out, "wb").write(patched)
    open(txt_out, "wb").write(text_overrides(args.lang).encode("cp1252"))
    if args.listing:
        with open(args.listing, "w", encoding="utf-8") as f:
            for va, text in listing:
                f.write("%08X: %s\n" % (va, text))
            f.write("\n")
            for va, orig, new, what in patches:
                f.write("%08X: %-32s -> %-32s ; %s\n" % (va, orig.hex(" "), new.hex(" "), what))
    print("wrote %s (%d site patches, %d listing lines, class factors %g / %g, pull %g / %g)"
          % (exe_out, len(patches), len(listing), factors[0], factors[1], pulls[0], pulls[1]))
    print("wrote %s" % txt_out)


if __name__ == "__main__":
    main()
