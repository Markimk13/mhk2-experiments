"""Start a championship race WITHOUT keyboard input and record all karts frame by frame.

Needs one of the auto_*.exe test builds (no pause on focus loss, intro skipped, window not activated).
The race is started by setting the game parameters in memory and calling the game's own
"start race" routine (0x004122E0) on the menu object.

usage: ai_race.py <exe> <out.csv> [--seconds 45] [--cls 2] [--mode 1] [--track 0] [--tune a,b,c,d,e,f,g]
                  [--stop-above V] [--physics60] [--ai-flat F]
--tune sets the seven or eight values of the tuning class (class 5) before the race loads
(the eighth is the gravity in percent, patch 1.7; 100 if left out). A ninth value is "Tempo"
of the page "Gegner", as --tempo gives it.
--tempo N sets "Tempo" (percent, -100..200), in any class since patch 1.10; without it the
race has "Standard", the class's own pace. --improved N makes kart numbers 1..N drive the
learned way (0 without it). Both are written in every run, so no run inherits them from the
settings.dat of the one before.
--physics60 switches the patch's "60-FPS-Fahrphysik" on for this run (matters above 60 FPS).
--stop-above ends the recording one second after any kart got faster than V (a kart whose
speed runs away numerically; saves the rest of the race time).
--ai-flat sets every throttle factor of the computer karts' table (singleton at [0x5E852C], see
.claude/memory/mhk2-computer-kart-ai.md) to F: base, ahead and behind factors of all three classes and
every kart's strength. 1.0 = full throttle for all, no rubber band.
--ai-look F multiplies the computer karts' look-ahead (controller +ACh / +B0h = 200 / F),
--ai-corner F their corner speed constant (+B4h = 250000 * F; the speed goes with its root),
--ai-steer F their cars' largest steering angle (car+18Ch); all written once the race runs.
--geo-on 0,0,0,1,1,1 switches the geometric driver (geo_driver.asm, builds from patch 1.10 work)
per class, --geo k=v,... sets its values for every kart, --geo-kart N:k=v,... for kart number N
(car+304h; repeatable). Written before the race starts.
--watch off switches the watch off (geo_watch in geo_driver.asm: a kart without progress for WT
seconds goes back to the road), --watch WT[,WA] sets its times and switches it on in every class.
One row per kart per game frame; the last columns are the kart number, laps + progress
(car+220h), the driver's allowed speed (controller +88h) and the controller's throttle, brake
and steering.
"""
import argparse
import ctypes
import os
import struct
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H
import remote_test as R


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
    ap.add_argument("--seconds", type=float, default=45.0)
    ap.add_argument("--cls", type=int, default=2)
    ap.add_argument("--mode", type=int, default=1)       # 1 = championship (6 computer karts), 0 = time trial
    ap.add_argument("--track", type=int, default=0)
    ap.add_argument("--tune", default="")
    ap.add_argument("--improved", type=int, default=None)
    ap.add_argument("--tempo", type=int, default=None)
    ap.add_argument("--geo-tables", default="")
    ap.add_argument("--stop-above", type=float, default=0.0)
    ap.add_argument("--physics60", action="store_true")
    ap.add_argument("--ai-flat", type=float, default=None)
    ap.add_argument("--ai-look", type=float, default=None)
    ap.add_argument("--ai-corner", type=float, default=None)
    ap.add_argument("--ai-steer", type=float, default=None)
    ap.add_argument("--geo-on", default=None)
    ap.add_argument("--geo", default="")
    ap.add_argument("--geo-kart", action="append", default=[])
    ap.add_argument("--watch", default=None)
    a = ap.parse_args()
    exe = os.path.abspath(a.exe)
    log = os.path.join(os.path.dirname(exe), "log.txt")
    if os.path.exists(log):
        os.remove(log)
    import optest
    import ghostlib
    ghostlib.wait_free()              # never next to another instance of the game
    p = optest.launch(exe)
    t0 = time.time()
    while init_count(log) < 1:
        if time.time() - t0 > 60 or p.poll() is not None:
            raise SystemExit("game did not reach the menu")
        time.sleep(0.5)
    time.sleep(3.0)
    r = R.Remote()
    tempo = a.tempo
    if a.tune:
        values = [int(x) for x in a.tune.split(",")]
        assert len(values) in (7, 8, 9), "--tune takes seven to nine values (the gravity defaults to 100)"
        if len(values) == 9 and tempo is None:
            tempo = values[8]
        values = (values + [100])[:8]
        r.write(r.gp + 0x2E4C, struct.pack("<8i", *values))
        r.write(r.gp + 0x2E7C, b"TUNE")
        r.write(r.gp + 0x2D70, b"WELT")                # patch 1.7: else the race start converts them as a 1.6 save
        r.write(r.gp + 0x2D78, b"GEGN")                # patch 1.9: ... or as a 1.8 save
    # "Gegner" (any class since patch 1.10): "Tempo" (-125 = "Standard") and how many karts drive the learned way
    r.write(r.gp + 0x2E6C, struct.pack("<2i", -125 if tempo is None else tempo, a.improved or 0))
    r.write(r.gp + 0x2D94, b"NEWG")                    # their markers: else the game takes them as "Standard" and 0
    r.write(r.gp + 0x2D98, b"STDG")
    if a.geo_tables:                                   # a table per kart number for this race (7 * 512 bytes)
        import geo_params as G
        blob = open(a.geo_tables, "rb").read()
        assert len(blob) == 7 * 512, "--geo-tables: 7 tables of 512 bytes"
        va = G.var_va(exe)
        r.write(va + 4, blob)
        r.write(va, b"\1\0\0\0")
    if a.watch is not None:                            # the watch: "off", or WT[,WA] in seconds, for every class
        import geo_params as G
        va = G.watch_va(exe)
        if a.watch == "off":
            r.write(va, bytes(8))
        else:
            w = [float(x) for x in a.watch.split(",")]
            r.write(va, bytes([1, 1, 1, 1, 1, 1, 0, 0]) + struct.pack("<f", w[0]) + (struct.pack("<f", -w[1]) if len(w) > 1 else b""))
    # the switch's marker bytes; always written, because the game stores them in settings.dat
    # when a race starts and the next run would inherit them
    r.write(r.gp + 0x4D, b"60F" if a.physics60 else b"\0\0\0")
    if a.geo_on is not None or a.geo or a.geo_kart:
        import geo_params as G
        per = {}
        for spec in a.geo_kart:
            n, vals = spec.split(":", 1)
            per[int(n)] = G.parse(vals)
        on = [int(x) for x in a.geo_on.split(",")] if a.geo_on is not None else None
        G.apply(r.write, lambda ad, n: H.read(r.h, ad, n), exe, on, G.parse(a.geo), per)
        print("geometric driver: on %s, all %s, karts %s" % (on, a.geo or "-", per or "-"), flush=True)
    r.gp_i32(0x1C, a.mode)
    r.gp_i32(0x10, a.cls)
    # the track of the time trial menu: in a championship (mode 1) the race does not use it, so it
    # is set to another track here, as it is after a player's own menu path (the learned driver read
    # it up to 1.10-pre16 and drove the wrong track's table in real championships)
    r.gp_i32(0x20, (a.track + 3) % 8 if a.mode == 1 else a.track)
    r.gp_i32(0x24, 2)                                  # Meisterschaft 1
    for i, trk in enumerate((a.track, 1, 2, 3)):
        r.gp_i32(0x28 + 4 * i, trk)
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
    t0 = time.time()
    while f32(h, cm + 0x20) < 0.2:
        if time.time() - t0 > 40 or p.poll() is not None:
            raise SystemExit("race did not start")
        time.sleep(0.005)
    if a.ai_flat is not None:
        tab = H.u32(h, 0x5E852C)
        if not tab:
            raise SystemExit("AI table not created yet")
        f = struct.pack("<f", a.ai_flat)
        for off in (0x20, 0x2C, 0x44):                 # B (ahead), C (level), E (behind), per class
            r.write(tab + off, f * 3)
        r.write(tab + 0x54, f * 18)                    # strength [3 classes][6 karts]
        print("AI table at 0x%X set to %.2f" % (tab, a.ai_flat), flush=True)
    b, e = H.u32(h, cm + 0x10), H.u32(h, cm + 0x14)
    cars = [H.u32(h, b + 4 * i) for i in range((e - b) // 4)]
    for c in cars[1:]:
        ctl = H.u32(h, c + 0x1F4)                      # the computer kart's controller (fn 0x42C240)
        if not ctl or H.u32(h, ctl + 0x10) != c:
            continue
        if a.ai_look is not None:                      # look-ahead: speed / [+ACh] + 0.1, speed / [+B0h] + 0.5
            r.write(ctl + 0xAC, struct.pack("<2f", 200.0 / a.ai_look, 200.0 / a.ai_look))
        if a.ai_corner is not None:                    # corner speed sqrt([+B4h] / curvature)
            r.write(ctl + 0xB4, struct.pack("<f", 250000.0 * a.ai_corner))
        if a.ai_steer is not None:                     # the car's largest steering angle
            r.write(c + 0x18C, struct.pack("<f", f32(h, c + 0x18C) * a.ai_steer))
    if a.ai_look is not None or a.ai_corner is not None or a.ai_steer is not None:
        print("computer karts: look %s, corner %s, steer %s" % (a.ai_look, a.ai_corner, a.ai_steer), flush=True)
    phys = [H.u32(h, c + 0x44) for c in cars]
    frames = [H.u32(h, pc + 0x30) for pc in phys]
    mass = [f32(h, c + 0x60) for c in cars]
    knum = [H.u32(h, c + 0x304) for c in cars]
    ctls = [H.u32(h, c + 0x1F4) for c in cars]
    par = H.u32(h, phys[0] + 4)                        # the vehicle's parameter object
    print("kart 0: mass %.2f | drag: factor %.3f, coefficient %.3f | downforce: factor %.3f, coefficient %.3f" % (
        mass[0], f32(h, phys[0] + 0x260), f32(h, par + 0x1DC), f32(h, phys[0] + 0x264), f32(h, par + 0x1E0)), flush=True)
    rows = []
    last = None
    stop_at = None
    wall0 = time.time()
    while time.time() - wall0 < a.seconds + 30:
        rt_raw = H.read(h, cm + 0x20, 4)
        if rt_raw == last:
            continue
        last = rt_raw
        rt = struct.unpack("<f", rt_raw)[0]
        if rt > a.seconds or (stop_at is not None and rt > stop_at):
            break
        for i, (c, pc, fr) in enumerate(zip(cars, phys, frames)):
            x, y, z = struct.unpack("<3f", H.read(h, c + 0x10, 12))
            vx, vy, vz = struct.unpack("<3f", H.read(h, c + 0x2B4, 12))
            if a.stop_above and stop_at is None and not (vx * vx + vy * vy + vz * vz <= a.stop_above ** 2):
                stop_at = rt + 1.0
            m = struct.unpack("<12f", H.read(h, fr + 0x10, 48))
            w = H.read(h, pc + 0x34, 4 * 0x84)
            wheels = []
            for k in range(4):
                wheels += [struct.unpack_from("<i", w, k * 0x84 + 0x18)[0], struct.unpack_from("<f", w, k * 0x84 + 0x40)[0]]
            prog = f32(h, c + 0x220)
            cl = struct.unpack("<4f", H.read(h, ctls[i] + 0x14, 12) + H.read(h, ctls[i] + 0x88, 4)) if ctls[i] else (0, 0, 0, 0)
            rows.append((rt, i, mass[i], x, y, z, vx, vy, vz, m[0], m[1], m[2], m[8], m[9], m[10], *wheels,
                         knum[i], prog, cl[3], cl[0], cl[1], cl[2], f32(h, c + 0x22C), f32(h, c + 0x224)))
    else:
        raise SystemExit("race clock stopped (paused?)")
    with open(a.out, "w") as f:
        f.write("t,kart,mass,x,y,z,vx,vy,vz,fx,fy,fz,sx,sy,sz," + ",".join(f"c{k},load{k}" for k in range(4)) + ",knum,prog,allow,thr,brk,steer,lat,pathprog\n")
        for row in rows:
            f.write(",".join("%.5f" % v if isinstance(v, float) else str(v) for v in row) + "\n")
    print(f"{os.path.basename(exe)}: {len(rows)} rows, {len(cars)} karts, fps stat {f32(h, 0x0087B0CC):.1f}")
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
