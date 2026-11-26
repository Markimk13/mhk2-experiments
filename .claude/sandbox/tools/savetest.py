"""Does the options switch survive the game's own save / load of settings.dat?

usage: savetest.py <gamedir> <exe built with prep_opt.py --fresh>

Runs without a settings.dat first (the sandbox copy is put back at the end):
  fresh start -> switch must be off -> switch it on in the menu -> leave the menu (race start saves)
  -> file must hold the flag -> restart -> menu must show it on -> switch off -> save -> file clean.
"""
import os
import struct
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H
import optest as O
import remote_test as R

OK = True


def check(label, got, want):
    global OK
    good = got == want
    OK &= good
    print(f"  {'ok  ' if good else 'FAIL'} {label}: {got!r}" + ("" if good else f"  (expected {want!r})"))


def item8(h):
    m = O.menu_ptr(h)
    begin = H.u32(h, m + 0x134)
    return O.read_str(h, begin + 8 * 0x54 + 8)


def flag(h):
    return "%06X" % (H.u32(h, H.u32(h, 0x5E84EC) + 0x4C) >> 8)


def press(h, key):
    O.wr(h, O.MENU_INJ + 4 * O.KEYS[key], struct.pack("<f", 1.0))
    time.sleep(0.3)


def page(h, state):
    O.wr(h, O.CMD_VA, struct.pack("<i", state + 1))
    time.sleep(0.5)


def leave_menu(exe):
    """Start a time trial the way the menu does; leaving the menu writes settings.dat."""
    log = os.path.join(os.path.dirname(exe), "log.txt")
    r = R.Remote()
    r.gp_i32(0x1C, 0)
    r.gp_i32(0x10, 0)
    r.gp_i32(0x20, 0)
    menu = O.menu_ptr(r.h)
    n0 = O.init_count(log)
    r.call(R.START_RACE, ecx=menu)
    t0 = time.time()
    while O.init_count(log) == n0:
        if time.time() - t0 > 90 or not H.alive():
            raise SystemExit("race did not load")
        time.sleep(0.5)
    time.sleep(1.0)


def kill():
    if H.alive():
        H.kernel32.TerminateProcess(H.open_proc(0x0001), 0)
    time.sleep(1.0)


def file_flag(path):
    d = open(path, "rb").read()
    return len(d), d[0x49:0x4C].hex()


def main():
    game, exe = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    settings = os.path.join(game, "settings.dat")
    keep = os.path.join(game, "settings.sandbox-keep.dat")
    os.replace(settings, keep)
    try:
        print("1. first start without settings.dat")
        O.start(exe)
        h = H.open_proc(0x0438)
        page(h, 1)
        check("switch text", item8(h), "Aus")
        check("flag bits in memory", flag(h), "000000")
        O.wr(h, O.menu_ptr(h) + 0x148, struct.pack("<i", 8))
        time.sleep(0.2)
        press(h, "select")
        check("after select: text", item8(h), "An")
        check("after select: flag bits", flag(h), "463036")
        press(h, "back")
        check("back in the main menu", H.u32(h, O.menu_ptr(h) + 0x140), 0)
        leave_menu(exe)
        check("settings.dat written by the game (size, flag bytes)", file_flag(settings), (0xFD0C, "363046"))
        check("flag still set during the race", flag(h), "463036")
        kill()

        print("2. restart with the file the game wrote")
        O.start(exe)
        h = H.open_proc(0x0438)
        check("flag bits loaded", flag(h), "463036")
        page(h, 1)
        check("switch text", item8(h), "An")
        O.wr(h, O.menu_ptr(h) + 0x148, struct.pack("<i", 8))
        time.sleep(0.2)
        press(h, "left")
        check("after left: text", item8(h), "Aus")
        check("after left: flag bits", flag(h), "000000")
        press(h, "back")
        leave_menu(exe)
        check("settings.dat (size, flag bytes)", file_flag(settings), (0xFD0C, "000000"))
        kill()
    finally:
        kill()
        if os.path.exists(settings):
            os.replace(settings, os.path.join(game, "settings.fresh-test.dat"))
        os.replace(keep, settings)
    print("ALL OK" if OK else "FAILURES")


if __name__ == "__main__":
    main()
