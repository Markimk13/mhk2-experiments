"""Scripted, keyboard-free drive of the player's kart in a time trial (needs an auto_*.exe build).

usage: drive.py <exe> <out.csv> --plan "t0:throttle:steer:brake,t1:...,tEnd" [--track 0] [--cls 2]
  e.g. --plan "0.5:1:0:0,2.5:1:0.5:0,4.5"   full throttle from 0.5 s, add half steering at 2.5 s, stop at 4.5 s
Records one row per game frame for the player's kart.
"""
import argparse
import os
import struct
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H
import remote_test as R

INJECT = 0x00884F00     # steer, brake, throttle (floats) read by the patched player controller


def init_count(log):
    try:
        return open(log, "r", encoding="latin-1").read().count("GameMK2::Init done")
    except OSError:
        return 0


def f32(h, a):
    return struct.unpack("<f", H.read(h, a, 4))[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exe")
    ap.add_argument("out")
    ap.add_argument("--plan", required=True)
    ap.add_argument("--track", type=int, default=0)
    ap.add_argument("--cls", type=int, default=2)
    a = ap.parse_args()
    steps = []
    parts = a.plan.split(",")
    for s in parts[:-1]:
        t, thr, st, br = (float(x) for x in s.split(":"))
        steps.append((t, thr, st, br))
    t_end = float(parts[-1])

    exe = os.path.abspath(a.exe)
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
    r.write(INJECT, struct.pack("<3f", 0.0, 0.0, 0.0))
    r.gp_i32(0x1C, 0)                 # time trial
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
    t0 = time.time()
    while f32(h, cm + 0x20) <= 0.0:
        if time.time() - t0 > 40 or p.poll() is not None:
            raise SystemExit("race did not start")
        time.sleep(0.002)
    car = H.u32(h, H.u32(h, cm + 0x10))
    pc = H.u32(h, car + 0x44)
    fr = H.u32(h, pc + 0x30)
    rows = []
    last = None
    cur = None
    wall0 = time.time()
    while time.time() - wall0 < t_end + 30:
        rt_raw = H.read(h, cm + 0x20, 4)
        if rt_raw == last:
            continue
        last = rt_raw
        rt = struct.unpack("<f", rt_raw)[0]
        if rt > t_end:
            break
        want = (0.0, 0.0, 0.0)
        for t, thr, st, br in steps:
            if rt >= t:
                want = (st, br, thr)
        if want != cur:
            r.write(INJECT, struct.pack("<3f", *want))
            cur = want
        x, y, z = struct.unpack("<3f", H.read(h, car + 0x10, 12))
        vx, vy, vz = struct.unpack("<3f", H.read(h, car + 0x2B4, 12))
        m = struct.unpack("<12f", H.read(h, fr + 0x10, 48))
        raw = H.read(h, pc, 0x2C0)
        wheels = []
        for k in range(4):
            o = 0x34 + k * 0x84
            wheels += [struct.unpack_from("<i", raw, o + 0x18)[0], struct.unpack_from("<f", raw, o + 0x40)[0]]
        rows.append((rt, x, y, z, vx, vy, vz, m[0], m[1], m[2], m[8], m[9], m[10],
                     struct.unpack_from("<f", raw, 0x244)[0], struct.unpack_from("<i", raw, 0x250)[0],
                     struct.unpack_from("<f", raw, 0x248)[0], struct.unpack_from("<f", raw, 0x274)[0], *wheels))
    else:
        raise SystemExit("race clock stopped")
    r.write(INJECT, struct.pack("<3f", 0.0, 0.0, 0.0))
    with open(a.out, "w") as f:
        f.write("t,x,y,z,vx,vy,vz,fx,fy,fz,sx,sy,sz,rpm,gear,throttle,steer," + ",".join(f"c{k},load{k}" for k in range(4)) + "\n")
        for row in rows:
            f.write(",".join("%.5f" % v if isinstance(v, float) else str(v) for v in row) + "\n")
    print(f"{os.path.basename(exe)}: {len(rows)} frames, fps stat {f32(h, 0x0087B0CC):.1f}")
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
