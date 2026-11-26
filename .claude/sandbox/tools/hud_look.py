r"""Picture of the race HUD while the kart drives (sandbox; no keys, no focus, no mouse).

usage: hud_look.py <out.png> [--cls 5] [--track 0] [--mode 0] [--seconds 4] [--exe path] [--tune v1,..,v9]

Starts a race through the test build's command slot (mode 0 time trial, 1 with computer karts),
gives full throttle through the test build's input slot from the start, and after --seconds
takes a screenshot and prints the car's speed (|velocity| * 3.6, what the speed line shows)
just before and after it. The HUD's text is drawn, not kept anywhere, so compare the picture
with the printed numbers.
"""
import math
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ghostlib as G     # noqa: E402
import ghosttest as T    # noqa: E402
import pause_look as PL  # noqa: E402

INJECT = 0x00884F00      # steer, brake, throttle (test builds)
SANDBOX = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def car_speed(g, index=0):
    cm = g.u32(0x5E8520)
    car = g.u32(g.u32(cm + 0x10) + 4 * index)
    v = struct.unpack("<3f", g.read(car + 0x2B4, 12))
    return math.sqrt(sum(c * c for c in v)) * 3.6


def drive_and_shoot(g, out, cls=5, track=0, mode=0, seconds=4.0):
    g.write(INJECT, struct.pack("<3f", 0.0, 0.0, 0.0))
    g.start_time_trial(cls, track, mode)
    cm = g.u32(0x5E8520)
    t0 = time.time()
    while struct.unpack("<f", g.read(cm + 0x20, 4))[0] <= 0.0:
        if time.time() - t0 > 40:
            raise SystemExit("race did not start")
        time.sleep(0.05)
    g.write(INJECT, struct.pack("<3f", 0.0, 0.0, 1.0))
    time.sleep(seconds)
    before = car_speed(g)
    g.shot(out)
    after = car_speed(g)
    g.write(INJECT, struct.pack("<3f", 0.0, 0.0, 0.0))
    return before, after


def main():
    a = sys.argv[1:]

    def opt(name, default):
        if name in a:
            i = a.index(name)
            v = a[i + 1]
            del a[i:i + 2]
            return v
        return default
    cls, track, mode = int(opt("--cls", "5")), int(opt("--track", "0")), int(opt("--mode", "0"))
    seconds = float(opt("--seconds", "4"))
    exe = opt("--exe", os.path.join(SANDBOX, os.environ.get("MHK2_GAME", "game"), "c5_new60.exe"))
    tune = opt("--tune", None)
    g = G.Game(exe)
    try:
        if tune:
            vals = list(map(int, tune.split(",")))
            g.write(g.gp + PL.TUNE_VALUES, struct.pack("<9i", *vals))
            for off, magic in ((PL.P.TUNE_MARK, PL.P.TUNE_MAGIC), (PL.P.VALUES8_MARK, PL.P.VALUES8_MAGIC),
                               (PL.P.OPP_MARK, PL.P.OPP_MAGIC)):
                g.write(g.gp + off, struct.pack("<I", magic))
        before, after = drive_and_shoot(g, a[0], cls, track, mode, seconds)
        print("car speed around the picture: %.1f .. %.1f km/h" % (before, after))
    finally:
        g.kill()


if __name__ == "__main__":
    main()
