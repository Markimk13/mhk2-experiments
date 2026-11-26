"""From a 'next track' / 'start' button: load the race, skip intro, force a win, step to the next overview page.

usage: champ_race.py <logfile> <lap1> <lap2> <lap3> <shot prefix>
"""
import ctypes
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H


def init_count(log):
    try:
        return open(log, "r", encoding="latin-1").read().count("GameMK2::Init done")
    except OSError:
        return 0


def player_car(h):
    cm = H.u32(h, 0x5E8520)
    return H.u32(h, H.u32(h, cm + 0x10))


def main():
    log, laps, prefix = sys.argv[1], [float(x) for x in sys.argv[2:5]], sys.argv[5]
    h = H.open_proc()
    n0 = init_count(log)
    H.keys(["enter"])                                   # start / next track
    t0 = time.time()
    while init_count(log) == n0:
        if time.time() - t0 > 90:
            raise SystemExit("level did not load")
        time.sleep(0.5)
    print(f"level loaded after {time.time() - t0:.1f}s")
    time.sleep(3.0)
    H.keys(["enter"])                                   # skip the intro camera
    time.sleep(6.5)                                     # countdown
    car = player_car(h)
    state, lap = H.u32(h, car + 0x2D0), H.u32(h, car + 0x264)
    print(f"player car state={state} lap={lap}")
    n = ctypes.c_size_t()
    data = struct.pack("<3fi", *laps, 3)
    H.kernel32.WriteProcessMemory(h, ctypes.c_void_p(car + 0x258), data, len(data), ctypes.byref(n))
    time.sleep(9.0)
    H.shot(prefix + "_1_result.png", 520)
    H.keys(["enter"])
    time.sleep(2.0)
    H.shot(prefix + "_2_track.png", 520)
    H.keys(["enter"])
    time.sleep(2.5)
    H.shot(prefix + "_3_overview.png", 1032)


if __name__ == "__main__":
    main()
