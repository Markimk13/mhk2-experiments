"""Helpers for unattended tests of the phantom kart changes (sandbox only, no keyboard, no focus)."""
import ctypes
import ctypes.wintypes as wt
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H
import optest as O
import remote_test as R

k32 = H.kernel32

NAME_INJ = 0x00884F50
INJECT = 0x00884F00          # steer, brake, throttle
PH_RUN, PH_TABLE, PH_SIZE = 0xFB04, 0xAA04, 0x6C
NAME_OFF, MARK_OFF, MARK = 0x2F10, 0x2F30, 0x454D414E


def wait_free(*args, **kw):
    """Kept for the older scripts that call it before a start: does nothing now.

    Every start goes through gameslot.spawn (optest.launch / optest.start call it), which
    claims the game folder, never starts next to the user's real game, lets test builds
    without the single-instance lock run side by side (up to gameslot.MAX_GAMES) and lets a
    build with the lock run only alone.
    """


def f32(h, a):
    return struct.unpack("<f", H.read(h, a, 4))[0]


class Game:
    def __init__(self, exe):
        self.exe = os.path.abspath(exe)
        self.dir = os.path.dirname(self.exe)
        self.log = os.path.join(self.dir, "log.txt")
        wait_free()
        O.start(self.exe)
        self.r = R.Remote()
        self.h = self.r.h
        self.gp = self.r.gp

    # -- memory ---------------------------------------------------------------
    def u32(self, a):
        return H.u32(self.h, a)

    def read(self, a, n):
        return H.read(self.h, a, n)

    def write(self, a, data):
        self.r.write(a, data)

    @property
    def menu(self):
        return O.menu_ptr(self.h)

    def menu_state(self):
        return struct.unpack("<i", self.read(self.menu + 0x140, 4))[0]

    def menu_items(self):
        m = self.menu
        begin, end = struct.unpack("<II", self.read(m + 0x134, 8))
        n = (end - begin) // 0x54 if begin else 0
        return [(struct.unpack("<i", self.read(begin + i * 0x54, 4))[0], O.read_str(self.h, begin + i * 0x54 + 8)) for i in range(n)]

    def page(self, state):
        self.write(O.CMD_VA, struct.pack("<i", state + 1))
        time.sleep(0.6)

    def header(self):
        return self.read(self.gp + PH_RUN, PH_SIZE)

    def table(self, cls, track):          # track 1-based; 200 cc is folded onto slots 160..
        slot = (160 if cls == 3 else cls * 64) + track - 1
        return self.read(self.gp + PH_TABLE + slot * PH_SIZE, PH_SIZE)

    def stored_name(self):
        raw = self.read(self.gp + NAME_OFF, 16)
        return self.u32(self.gp + MARK_OFF) == MARK, raw

    def version(self):
        return self.read(0x5C38B8, 5)

    # -- races ----------------------------------------------------------------
    def init_count(self):
        return O.init_count(self.log)

    def start_time_trial(self, cls, track, mode=0):
        """track is 0-based here (position in the track list)."""
        self.write(INJECT, struct.pack("<3f", 0.0, 0.0, 0.0))
        self.r.gp_i32(0x1C, mode)
        self.r.gp_i32(0x10, cls)
        self.r.gp_i32(0x20, track)
        n0 = self.init_count()
        menu = self.menu
        self.r.call(R.START_RACE, ecx=menu)
        t0 = time.time()
        while self.init_count() == n0:
            if time.time() - t0 > 90 or not H.alive():
                raise SystemExit("race did not load")
            time.sleep(0.5)
        cm = self.u32(0x5E8520)
        t0 = time.time()
        while f32(self.h, cm + 0x20) <= 0.0:
            if time.time() - t0 > 60 or not H.alive():
                raise SystemExit("race did not start")
            time.sleep(0.05)
        return self.init_count()

    def car(self):
        cm = self.u32(0x5E8520)
        return self.u32(self.u32(cm + 0x10))

    def race_time(self):
        return f32(self.h, self.u32(0x5E8520) + 0x20)

    def force_finish(self, laps):
        self.write(self.car() + 0x258, struct.pack("<3fi", *laps, 3))

    def wait_menu(self, n0, timeout=90):
        """Wait until the game is back in the menu after a race (init count goes up)."""
        t0 = time.time()
        while self.init_count() == n0:
            if time.time() - t0 > timeout or not H.alive():
                return False
            time.sleep(0.5)
        time.sleep(2.0)
        return True

    # -- result pages (they are drawn over the finished race) -------------------
    def race_state(self):
        return O.menu_ptr(self.h)            # the current game state object

    def race_phase(self):
        return self.u32(self.race_state() + 0x118)

    def overlay(self):
        """Menu object of the result pages while the race state is active."""
        return self.u32(self.race_state() + 0x144)

    def overlay_state(self):
        return struct.unpack("<i", self.read(self.overlay() + 0x140, 4))[0]

    def overlay_items(self):
        m = self.overlay()
        begin, end = struct.unpack("<II", self.read(m + 0x134, 8))
        n = (end - begin) // 0x54 if begin else 0
        return [(struct.unpack("<i", self.read(begin + i * 0x54, 4))[0], O.read_str(self.h, begin + i * 0x54 + 8)) for i in range(n)]

    def wait_overlay(self, state, timeout=30):
        t0 = time.time()
        while time.time() - t0 < timeout:
            try:
                if self.race_phase() == 5 and self.overlay_state() == state:
                    time.sleep(0.4)
                    return True
            except OSError:
                pass
            time.sleep(0.2)
        return False

    def select(self, item=0, tries=5):
        """Press "menu select" on an item of the result pages; returns the page state afterwards.

        The selection is written right before the key: while the real mouse moves, the menu
        clears it every frame.
        """
        m = self.overlay()
        before = self.overlay_state()
        n0 = self.init_count()

        def effect():
            try:
                return self.init_count() != n0 or self.race_phase() != 5 or self.overlay_state() != before
            except OSError:
                return True                  # the race state is gone: back in the main menu

        for _ in range(tries):
            self.write(m + 0x148, struct.pack("<i", item))
            self.write(NAME_INJ, struct.pack("<f", 1.0))
            time.sleep(0.7)
            if effect():
                break
        time.sleep(0.5)
        try:
            return self.overlay_state() if self.race_phase() == 5 else None
        except OSError:
            return None

    def set_name(self, name):
        """Type a name into the name entry page (the std::string at menu+17Ch)."""
        raw = name.encode("cp1252")
        assert len(raw) <= 15
        m = self.overlay()
        s = bytearray(0x1C)
        s[0:4] = self.read(m + 0x17C, 4)
        s[4:4 + len(raw)] = raw
        struct.pack_into("<II", s, 0x14, len(raw), 15)
        self.write(m + 0x17C, bytes(s))
        self.write(m + 0x174, struct.pack("<i", len(raw)))    # the cursor behind it, as after typing

    def shot(self, path):
        O.shot(path)

    def kill(self):
        if H.alive():
            k32.TerminateProcess(H.open_proc(0x0001), 0)
        time.sleep(1.5)


def phantom_info(path):
    d = open(path, "rb").read()
    trk, cls, ch = struct.unpack_from("<3i", d, 0x4C)
    tot = struct.unpack_from("<4f", d, 0x58)
    return {"size": len(d), "version": d[:8], "name": d[8:20], "hash": d[20:32], "id": d[0x28:0x48],
            "track": trk, "class": cls, "char": ch, "times": tuple(round(x, 2) for x in tot)}
