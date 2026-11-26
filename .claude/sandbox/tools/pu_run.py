"""Straight-line run from the start line with an optional speed power-up (needs a prep_fps/prep_opt/prep_ghost build).

usage: pu_run.py <exe> <out.csv> [--track N] [--cls C] [--tend S]
                 [--boost 2|7] [--boost-from V] [--cut V] [--then 2|7] [--tune a,b,c,d,e,f,g[,h[,i]]] [--lift V]
  --boost 2      blue light ("Sirene"), --boost 7 turbo can ("Powerdose"): activated with the game's own
                 routine once the kart is faster than --boost-from, then kept alive (timer pinned)
  --cut V        end the power-up once the kart is faster than V; the rest of the run is plain full throttle
  --then T       after the cut, as soon as the first power-up is gone, switch on power-up T and keep it
                 alive (push with the power can, then watch where the siren settles)
  --tune ...     the seven values of the tuning class (class 5): gearing in hundredths, then pull,
                 grip, mass, brakes, steering and downforce in percent; written before the race loads
  --lift V       let go of the throttle once the kart is faster than V and coast for the rest of the run
                 (how hard the engine brakes; lift_check.py reads the result)
Full throttle from 0.5 s, no steering. One row per game frame; the last two columns are the number
of wheels on the ground and the summed wheel load divided by the kart's weight (1.0 = standing).
"""
import argparse
import math
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H
import remote_test as R
import ghostlib

INJECT = 0x00884F00     # steer, brake, throttle
ACTIVATE = 0x0042D320   # Car::ActivatePowerUp(type), thiscall


def init_count(log):
    try:
        return open(log, "r", encoding="latin-1").read().count("GameMK2::Init done")
    except OSError:
        return 0


def f32(h, a):
    return struct.unpack("<f", H.read(h, a, 4))[0]


def activate(r, car, kind):
    """Switch a power-up on with the game's own routine and pin its timer."""
    r.call(ACTIVATE, ecx=car, args=(kind,))
    r.write(car + 0x278, struct.pack("<f", 1.0e6))     # keep it alive


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exe")
    ap.add_argument("out")
    ap.add_argument("--track", type=int, default=0)
    ap.add_argument("--cls", type=int, default=2)
    ap.add_argument("--tend", type=float, default=8.0)
    ap.add_argument("--boost", type=int, default=0)
    ap.add_argument("--boost-from", type=float, default=16.0)
    ap.add_argument("--cut", type=float, default=0.0)
    ap.add_argument("--then", type=int, default=0)
    ap.add_argument("--tune", default="")
    ap.add_argument("--lift", type=float, default=0.0)
    a = ap.parse_args()

    ghostlib.wait_free()          # never next to another instance of the game
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
    if a.tune:
        values = [int(x) for x in a.tune.split(",")]
        assert len(values) in (7, 8, 9), "--tune takes seven to nine values (gravity and 'Gegner' default to 100)"
        values += [100] * (9 - len(values))
        r.write(r.gp + 0x2E4C, struct.pack("<9i", *values))
        r.write(r.gp + 0x2E7C, b"TUNE")
        r.write(r.gp + 0x2D70, b"WELT")                # patch 1.7: else the race start converts them as a 1.6 save
        r.write(r.gp + 0x2D78, b"GEGN")                # patch 1.9: ... or as a 1.8 save
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
    weight = f32(h, car + 0x60) * 20.4          # mass * gravity (from the wheel loads of a standing kart)
    rows = []
    last = None
    thr_on = False
    state = "plain"                   # plain -> boost -> cut -> then
    wall0 = time.time()
    while time.time() - wall0 < a.tend + 30:
        rt_raw = H.read(h, cm + 0x20, 4)
        if rt_raw == last:
            continue
        last = rt_raw
        rt = struct.unpack("<f", rt_raw)[0]
        if rt > a.tend:
            break
        if rt >= 0.5 and not thr_on:
            r.write(INJECT, struct.pack("<3f", 0.0, 0.0, 1.0))
            thr_on = True
        x, y, z = struct.unpack("<3f", H.read(h, car + 0x10, 12))
        vx, vy, vz = struct.unpack("<3f", H.read(h, car + 0x2B4, 12))
        v = math.sqrt(vx * vx + vy * vy + vz * vz)
        put, ptimer = struct.unpack("<if", H.read(h, car + 0x274, 8))
        raw = H.read(h, pc + 0x244, 0x2C)
        rpm, thr = struct.unpack_from("<ff", raw, 0)
        gear = struct.unpack_from("<i", raw, 0x0C)[0]
        accf, spdf = struct.unpack_from("<ff", raw, 0x24)
        if a.lift and thr_on and state != "lift" and v >= a.lift:
            r.write(INJECT, struct.pack("<3f", 0.0, 0.0, 0.0))
            state = "lift"
        elif a.boost and state == "plain" and v >= a.boost_from:
            activate(r, car, a.boost)
            state = "boost"
        elif state == "boost" and a.cut and v >= a.cut:
            r.write(car + 0x278, struct.pack("<f", 0.001))     # the game ends it on its next frame
            state = "cut"
        elif state == "cut" and a.then and put == -1:
            activate(r, car, a.then)
            state = "then"
        w = H.read(h, pc + 0x34, 4 * 0x84)
        ground = sum(1 for k in range(4) if struct.unpack_from("<i", w, k * 0x84 + 0x18)[0])
        load = sum(struct.unpack_from("<f", w, k * 0x84 + 0x40)[0] for k in range(4)) / weight
        rows.append((rt, x, y, z, v, rpm, gear, thr, put, ptimer, accf, spdf, state, ground, load))
    else:
        raise SystemExit("race clock stopped")
    r.write(INJECT, struct.pack("<3f", 0.0, 0.0, 0.0))
    with open(a.out, "w") as f:
        f.write("t,x,y,z,v,rpm,gear,throttle,pu,putimer,accf,spdf,state,ground,load\n")
        for row in rows:
            f.write(",".join("%.5f" % q if isinstance(q, float) else str(q) for q in row) + "\n")
    print(f"{os.path.basename(exe)}: {len(rows)} frames, fps stat {f32(h, 0x0087B0CC):.1f}, final state {state}")
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
        if isinstance(e, SystemExit) and e.code not in (None, 0):
            print("STOPPED:", e.code)
