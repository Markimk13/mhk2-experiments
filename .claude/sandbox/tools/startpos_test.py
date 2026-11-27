"""Time trial from a moved start: where the kart stands and how its path progress runs.

usage: startpos_test.py <game folder> <out.csv> [--dat archive.dat] [--track 0] [--cls 2]
                        [--seconds 8] [--exe c5_new60.exe]

--dat is copied into <game folder>\\data\\mhk2-02.dat for the run and removed afterwards (an
archive from datpack.py, e.g. one track's objects.txt with another "start spline offset").
The kart gets full throttle, no steering. One row per frame: race time, position, speed, path
progress car+224h, wrap counter car+230h, expected value car+234h, laps car+264h, car state
car+2D0h. The race-start grid (fn 0x4061E0, 0x40647C..0x406607) puts kart i at path progress
offset - 3 * i / path length, so the player (i = 0) should start at the offset itself.
"""
import argparse
import os
import shutil
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H
import remote_test as R
from drive import INJECT, f32, init_count


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("folder")
    ap.add_argument("out")
    ap.add_argument("--dat")
    ap.add_argument("--track", type=int, default=0)
    ap.add_argument("--cls", type=int, default=2)
    ap.add_argument("--seconds", type=float, default=8.0)
    ap.add_argument("--exe", default="c5_new60.exe")
    a = ap.parse_args()
    folder = os.path.abspath(a.folder)
    extra = os.path.join(folder, "data", "mhk2-02.dat")
    if os.path.exists(extra):
        raise SystemExit(f"{extra} exists already; remove it first")
    if a.dat:
        shutil.copyfile(a.dat, extra)
    try:
        run(a, os.path.join(folder, a.exe))
    finally:
        for _ in range(100):           # the game keeps the archive open until it has exited
            try:
                if os.path.exists(extra):
                    os.remove(extra)
                break
            except PermissionError:
                time.sleep(0.2)


def run(a, exe):
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
        wall0 = time.time()
        while time.time() - wall0 < a.seconds + 60:
            raw = H.read(h, cm + 0x20, 4)
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
            prog, prev = struct.unpack_from("<2f", c, 0x224)
            wraps, expect = struct.unpack_from("<2i", c, 0x230)
            laps = struct.unpack_from("<i", c, 0x264)[0]
            state = struct.unpack_from("<i", c, 0x2D0)[0]
            rows.append((rt, x, y, z, (vx * vx + vy * vy + vz * vz) ** 0.5, prog, prev, wraps, expect, laps, state))
        with open(a.out, "w") as f:
            f.write("t,x,y,z,speed,prog,prev,wraps,expect,laps,state\n")
            for row in rows:
                f.write(",".join("%.5f" % v if isinstance(v, float) else str(v) for v in row) + "\n")
        if rows:
            first = next((row for row in rows if row[0] >= 0.0), rows[0])
            print(f"{len(rows)} frames; first: t {first[0]:.2f} pos ({first[1]:.2f}, {first[2]:.2f}, {first[3]:.2f}) "
                  f"prog {first[5]:.4f}; last: prog {rows[-1][5]:.4f} speed {rows[-1][4]:.1f} wraps {rows[-1][7]}")
    finally:
        r.write(INJECT, struct.pack("<3f", 0.0, 0.0, 0.0))
        H.kernel32.TerminateProcess(h, 0)


if __name__ == "__main__":
    main()
