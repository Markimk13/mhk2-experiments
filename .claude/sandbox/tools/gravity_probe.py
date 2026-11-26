"""Check that the physics world's gravity can be changed during a race.

usage: gravity_probe.py <60 FPS test build> [--factor 0.25] [--at 3] [--seconds 6] [--track 3]

Starts a time trial (the player's kart gets no input and stands at the start), prints the gravity
vector of the physics world ([[[0x5E84FC]+4]+4]+0x4C, set by RwPhysics::Init 0x468E30 through
0x4CF270), multiplies its y by --factor at race time --at, and prints kart 0's height and vertical
speed every 0.25 s. A lighter world should lift the kart on its springs.
"""
import argparse
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H
import remote_test as R
import optest
import ghostlib
from ai_race import init_count, f32


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exe")
    ap.add_argument("--factor", type=float, default=0.25)
    ap.add_argument("--at", type=float, default=3.0)
    ap.add_argument("--seconds", type=float, default=6.0)
    ap.add_argument("--track", type=int, default=3)
    a = ap.parse_args()
    exe = os.path.abspath(a.exe)
    log = os.path.join(os.path.dirname(exe), "log.txt")
    if os.path.exists(log):
        os.remove(log)
    ghostlib.wait_free()
    p = optest.launch(exe)
    t0 = time.time()
    while init_count(log) < 1:
        if time.time() - t0 > 60 or p.poll() is not None:
            raise SystemExit("game did not reach the menu")
        time.sleep(0.5)
    time.sleep(3.0)
    r = R.Remote()
    r.write(r.gp + 0x4D, b"\0\0\0")
    r.gp_i32(0x1C, 0)
    r.gp_i32(0x10, 2)
    r.gp_i32(0x20, a.track)
    main_prog = H.u32(r.h, 0x5E851C)
    menu = H.u32(r.h, main_prog + 4)
    n0 = init_count(log)
    r.call(R.START_RACE, ecx=menu)
    t0 = time.time()
    while init_count(log) == n0:
        if time.time() - t0 > 90 or p.poll() is not None:
            raise SystemExit("race did not load")
        time.sleep(0.5)
    h = r.h
    cm = H.u32(h, 0x5E8520)
    while f32(h, cm + 0x20) < 0.2:
        time.sleep(0.005)
    car = H.u32(h, H.u32(h, cm + 0x10))
    inner = H.u32(h, H.u32(h, H.u32(h, 0x5E84FC) + 4) + 4)
    g = struct.unpack("<3f", H.read(h, inner + 0x4C, 12))
    print("physics world 0x%X, gravity %.3f %.3f %.3f" % (inner, *g), flush=True)
    done = False
    nxt = 0.0
    while True:
        rt = f32(h, cm + 0x20)
        if rt > a.seconds:
            break
        if not done and rt >= a.at:
            r.write(inner + 0x50, struct.pack("<f", g[1] * a.factor))
            print("t %.2f: gravity y set to %.3f" % (rt, g[1] * a.factor), flush=True)
            done = True
        if rt >= nxt:
            y = f32(h, car + 0x14)
            vy = f32(h, car + 0x2B8)
            print("t %.2f  y %.4f  vy %+.4f" % (rt, y, vy), flush=True)
            nxt += 0.25
        time.sleep(0.002)
    H.kernel32.TerminateProcess(h, 0)


if __name__ == "__main__":
    try:
        main()
    except BaseException as e:
        try:
            if H.alive():
                H.kernel32.TerminateProcess(H.open_proc(0x0001), 0)
        except Exception:
            pass
        if not isinstance(e, SystemExit) or e.code not in (None, 0):
            print("FAILED:", repr(e))
            sys.exit(1)
