"""Launch one sandbox exe, start a time trial and record the player's kart frame by frame.

usage: run_variant.py <exe> <out.csv> [--track N] [--cls N] [--seconds S] [--keys up] [--delay 0.5] [--keep]

Records one row per game frame (detected by the lap timer changing):
  wall, race_time, lap_time, x, y, z, vx, vy, vz, rpm, f30c, f320
"""
import argparse
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


class Game:
    def __init__(self):
        self.h = H.open_proc()

    def gp(self, off):
        return struct.unpack("<i", H.read(self.h, H.u32(self.h, 0x5E84EC) + off, 4))[0]

    def car(self, i=0):
        cm = H.u32(self.h, 0x5E8520)
        return cm, H.u32(self.h, H.u32(self.h, cm + 0x10) + 4 * i)


def tap(key, gap=0.6):
    H.keys([key], gap=gap)


def tap_until(key, cond, tries=6, gap=0.6):
    for _ in range(tries):
        if cond():
            return True
        tap(key, gap)
    return cond()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exe")
    ap.add_argument("out")
    ap.add_argument("--track", type=int, default=0)
    ap.add_argument("--cls", type=int, default=2)
    ap.add_argument("--seconds", type=float, default=4.0)
    ap.add_argument("--keys", default="up")
    ap.add_argument("--delay", type=float, default=0.5)
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()

    exe = os.path.abspath(a.exe)
    log = os.path.join(os.path.dirname(exe), "log.txt")
    if os.path.exists(log):
        os.remove(log)
    import gameslot
    p = gameslot.spawn(exe)
    t0 = time.time()
    while init_count(log) < 1:
        if time.time() - t0 > 60 or p.poll() is not None:
            raise SystemExit("game did not reach the menu")
        time.sleep(0.5)
    time.sleep(3.0)
    g = Game()

    tap("enter", 1.2)                 # Rennmodus
    tap("enter", 1.5)                 # Zeitfahren -> engine class menu
    assert g.gp(0x1C) == 0, "not in time trial mode"
    # engine menu: selection starts on 50 cc; pick the class and verify
    for _ in range(a.cls):
        tap("down", 0.5)
    g_cls_before = g.gp(0x10)
    tap("enter", 1.5)
    assert g.gp(0x10) == a.cls, f"class is {g.gp(0x10)}, wanted {a.cls}"
    tap("down", 0.5)                  # character: Ok
    tap("enter", 1.8)
    # track selection: left/right on the selector changes GP+0x20
    for _ in range(12):
        if g.gp(0x20) == a.track:
            break
        tap("right", 0.7)
    assert g.gp(0x20) == a.track, f"track is {g.gp(0x20)}"
    tap("down", 0.5)                  # Rennen starten
    n0 = init_count(log)
    tap("enter", 0.5)
    t0 = time.time()
    while init_count(log) == n0:
        if time.time() - t0 > 90:
            raise SystemExit("race did not load")
        time.sleep(0.5)
    time.sleep(3.0)
    tap("enter", 0.2)                 # skip the intro camera
    cm, car = g.car()
    t0 = time.time()
    while struct.unpack("<f", H.read(g.h, cm + 0x20, 4))[0] < a.delay:
        if time.time() - t0 > 30:
            raise SystemExit("race did not start")
        time.sleep(0.001)

    hwnd = H.main_window()
    assert H.focus(hwnd)
    held = [k for k in a.keys.split("+") if k and k != "none"]
    for k in held:
        H.send_scan(*H.SCAN[k], False)
    rows = []
    last = None
    phys = H.u32(g.h, car + 0x44)          # physics-side car instance (0x2C0 bytes)
    qpf = ctypes.c_int64()
    H.kernel32.QueryPerformanceFrequency(ctypes.byref(qpf))
    qpc = ctypes.c_int64()
    H.kernel32.QueryPerformanceCounter(ctypes.byref(qpc))
    start = qpc.value
    while True:
        H.kernel32.QueryPerformanceCounter(ctypes.byref(qpc))
        wall = (qpc.value - start) / qpf.value
        if wall > a.seconds:
            break
        raw = H.read(g.h, car, 0x360)
        lap = raw[0x250:0x254]
        if lap != last:
            last = lap
            rt = struct.unpack("<f", H.read(g.h, cm + 0x20, 4))[0]
            x, y, z = struct.unpack_from("<3f", raw, 0x10)
            vx, vy, vz = struct.unpack_from("<3f", raw, 0x2B4)
            pc = H.read(g.h, phys, 0x2C0)
            wheels = []
            for w in range(4):
                o = 0x34 + w * 0x84
                wheels += [struct.unpack_from("<i", pc, o + 0x18)[0],      # had ground contact in the last step
                           struct.unpack_from("<f", pc, o + 0x40)[0],      # contact load from the solver
                           struct.unpack_from("<f", pc, o + 0x0C)[0]]      # spin (deg/s)
            rows.append((wall, rt, struct.unpack("<f", lap)[0], x, y, z, vx, vy, vz,
                         struct.unpack_from("<f", pc, 0x244)[0],           # engine rpm
                         struct.unpack_from("<i", pc, 0x250)[0],           # gear
                         struct.unpack_from("<f", pc, 0x248)[0],           # throttle
                         *wheels))
    for k in held:
        H.send_scan(*H.SCAN[k], True)
    with open(a.out, "w") as f:
        f.write("wall,race_time,lap_time,x,y,z,vx,vy,vz,rpm,gear,throttle,"
                + ",".join(f"c{w},load{w},spin{w}" for w in range(4)) + "\n")
        for r in rows:
            f.write(",".join("%.6f" % v if isinstance(v, float) else str(v) for v in r) + "\n")
    fps = struct.unpack("<f", H.read(g.h, 0x0087B0CC, 4))[0]
    print(f"{os.path.basename(exe)}: {len(rows)} frames in {a.seconds}s, game fps stat {fps:.1f}")
    if not a.keep:
        H.kernel32.TerminateProcess(g.h, 0)


if __name__ == "__main__":
    try:
        main()
    except BaseException as e:
        # never leave a game instance behind
        try:
            if H.alive():
                H.kernel32.TerminateProcess(H.open_proc(0x0001), 0)
        except Exception:
            pass
        if not isinstance(e, SystemExit) or e.code not in (None, 0):
            print("FAILED:", e)
            sys.exit(1)
