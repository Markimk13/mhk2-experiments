"""A challenge in a test build of the patch: start, metres left, minimap, finish (sandbox only).

usage: challenge_test.py <game folder> <out dir> --start 0.985 --length 0.05
                         [--track 0] [--cls 2] [--seconds 20] [--exe ch60.exe] [--shots 1,3]

Writes the patch's challenge block (CH_DATA in tools/patch_200cc.py: active, start, length)
before the race, then drives a time trial with full throttle and no steering. Records one row per
frame (race time, position, speed, path progress, the block's "done", the race phase) into
<out dir>\\run.csv, takes a picture of the game at the given race times (shot_<t>.png) and one
after the finish (shot_end.png). Stops at the finish (race phase 4 or more) or after --seconds.
"""
import argparse
import os
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "tools"))
import harness as H
import remote_test as R
from drive import INJECT, f32, init_count
import patch_200cc as P


NAME_INJ = 0x00884F50          # the test builds' one-shot "menu select" of the result pages (prep_ghost.py)


def result_weiter(h, r, timeout=30):
    """Wait for the result overlay (page 0Eh, race phase 5), press 'Weiter', return the next page."""
    def overlay():
        state = H.u32(h, H.u32(h, 0x5E851C) + 4)
        return state, H.u32(h, state + 0x144)
    t0 = time.time()
    while time.time() - t0 < timeout:
        state, m = overlay()
        if H.u32(h, state + 0x118) == 5 and m and H.u32(h, m + 0x140) == 0x0E:
            break
        time.sleep(0.2)
    else:
        return None
    time.sleep(0.5)
    for _ in range(5):
        r.write(m + 0x148, struct.pack("<i", 0))
        r.write(NAME_INJ, struct.pack("<f", 1.0))
        time.sleep(0.8)
        if H.u32(h, m + 0x140) != 0x0E:
            break
    return H.u32(h, m + 0x140)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("out")
    ap.add_argument("--start", type=float, required=True)
    ap.add_argument("--length", type=float, required=True)
    ap.add_argument("--track", type=int, default=0)
    ap.add_argument("--cls", type=int, default=2)
    ap.add_argument("--seconds", type=float, default=20.0)
    ap.add_argument("--exe", default="ch60.exe")
    ap.add_argument("--shots", default="1")
    ap.add_argument("--off", action="store_true", help="leave the challenge off (stock race, for comparison)")
    ap.add_argument("--weiter", action="store_true",
                    help="after the finish press 'Weiter' on the result overlay and print the next page "
                         "(0Fh result list, 13h name entry for a highscore)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    shots = sorted(float(s) for s in a.shots.split(",") if s)
    exe = os.path.join(os.path.abspath(a.folder), a.exe)
    log = os.path.join(os.path.dirname(exe), "log.txt")
    if os.path.exists(log):
        os.remove(log)
    import optest
    p = optest.launch(exe)
    t0 = time.time()
    while init_count(log) < 1:
        if time.time() - t0 > 60 or p.poll() is not None:
            raise SystemExit("game did not reach the menu")
        time.sleep(0.5)
    time.sleep(3.0)
    r = R.Remote()
    h = r.h
    try:
        r.write(INJECT, struct.pack("<3f", 0.0, 0.0, 0.0))
        r.write(P.CH_DATA, struct.pack("<I2f4f", 0 if a.off else 1, a.start, a.length, 0, 0, 0, 0))
        r.gp_i32(0x1C, 0)
        r.gp_i32(0x10, a.cls)
        r.gp_i32(0x20, a.track)
        menu = H.u32(h, H.u32(h, 0x5E851C) + 4)
        n0 = init_count(log)
        r.call(R.START_RACE, ecx=menu)
        t0 = time.time()
        while init_count(log) == n0:
            if time.time() - t0 > 90 or p.poll() is not None:
                raise SystemExit("race did not load")
            time.sleep(0.5)
        cm = H.u32(h, 0x5E8520)
        car = H.u32(h, H.u32(h, cm + 0x10))
        rows = []
        last = None
        thr = False
        finished = None
        wall0 = time.time()
        while time.time() - wall0 < a.seconds + 60:
            raw = H.read(h, cm + 0x20, 4)
            state = H.u32(h, H.u32(h, 0x5E851C) + 4)
            phase = struct.unpack("<i", H.read(h, state + 0x118, 4))[0]
            if phase >= 4:
                finished = rows[-1][0] if rows else 0.0
                break
            if raw == last:
                continue
            last = raw
            rt = struct.unpack("<f", raw)[0]
            if rt > a.seconds:
                break
            if rt > 0.0 and not thr:
                r.write(INJECT, struct.pack("<3f", 0.0, 0.0, 1.0))
                thr = True
            c = H.read(h, car, 0x2D4)
            x, y, z = struct.unpack_from("<3f", c, 0x10)
            vx, vy, vz = struct.unpack_from("<3f", c, 0x2B4)
            prog = struct.unpack_from("<f", c, 0x224)[0]
            laps = struct.unpack_from("<i", c, 0x264)[0]
            done = struct.unpack("<f", H.read(h, P.CH_DONE, 4))[0]
            rows.append((rt, x, y, z, (vx * vx + vy * vy + vz * vz) ** 0.5, prog, done, laps, phase))
            if shots and rt >= shots[0]:
                H.shot(os.path.join(a.out, "shot_%g.png" % shots.pop(0)))
        r.write(INJECT, struct.pack("<3f", 0.0, 0.0, 0.0))
        gp = H.u32(h, P.GP_POINTER)
        print("ghost loaded (gp+54h):", H.read(h, gp + 0x54, 1)[0])
        if finished is not None:
            time.sleep(2.0)
            H.shot(os.path.join(a.out, "shot_end.png"))
            if a.weiter:
                print("result page after 'Weiter':", hex(result_weiter(h, r) or 0))
        with open(os.path.join(a.out, "run.csv"), "w") as f:
            f.write("t,x,y,z,speed,prog,done,laps,phase\n")
            for row in rows:
                f.write(",".join("%.5f" % v if isinstance(v, float) else str(v) for v in row) + "\n")
        first = rows[0] if rows else None
        print(f"{len(rows)} frames; start prog {first[5]:.4f} at ({first[1]:.1f}, {first[3]:.1f}); "
              f"last: prog {rows[-1][5]:.4f} done {rows[-1][6]:.4f} of {a.length}; "
              + (f"FINISHED at {finished:.2f} s" if finished is not None else "not finished"))
    finally:
        r.write(INJECT, struct.pack("<3f", 0.0, 0.0, 0.0))
        H.kernel32.TerminateProcess(h, 0)


if __name__ == "__main__":
    main()
