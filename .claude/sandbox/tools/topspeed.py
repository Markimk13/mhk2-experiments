r"""Top speed of the tuning class on an endless straight (sandbox, 60 FPS test build).

usage: topspeed.py run <out.jsonl> <values> [<values> ...] [--seconds 40] [--trace dir] [--cls 5] [--char N]
       topspeed.py sets <sets.json> <out dir> [--folders game,game2,game3] [--seconds 40]

The start straight of "Ägypten" (track 3) runs from x 150.7 down to about 52, with a dip at
x 95..103. The kart gets full throttle and no steering (the injected steering acts like a key:
even 0.02 makes it weave). Whenever it is past x = X_LOW, its physics body (and the frames that
show it) move back by X_JUMP along x, all in one frame, by the test build's add routine on the
game's own thread; the sideways position goes back to the start line's, and the body's matrix
and velocity are turned about the vertical so that it heads along -x again (speed, height,
pitch, roll and spin stay as they were).
Every jump costs the kart about 1 unit/s (it sinks a little and bounces; the reason was not
found), so it never quite settles at its top speed. The top speed is found instead from the free
stretches between the jumps: on each (x below X_FLAT, SKIP frames after the landing, race time
from FIT_FROM s) the mean speed and the acceleration; a line through acceleration against speed
crosses zero at the top speed ("top_fit"). Checked on the defaults: 61.35..61.38 in three runs,
the stock measurement (decay on the straight) 61.21. At high speed the free stretches are short
and the kart hops a little (its speed drops by 0.4 every few frames), so that line is noisy;
"top_model" takes the mean speed v and acceleration a of all free stretches and the slope k of
acceleration against speed from the engine model (class_model.py: thrust slope minus twice the
resistance over v, the resistance being thrust minus a): top = v - a / k. On the defaults k is
-0.99 (the line: -1.0). "top" is the plain mean of the last TAIL s.
Values: nine numbers as on the tuning pages (gearing in hundredths), comma separated.
"sets" runs a set file ([{"id", "v"}]) on up to three game folders side by side, resumable
(results.jsonl in the out dir).
"""
import json
import math
import os
import struct
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SANDBOX = os.path.dirname(HERE)
sys.path.insert(0, HERE)

INJECT = 0x00884F00        # steer, brake, throttle
SCRATCH = 0x00884FA0       # the new x for the copy routine (free, zero-initialised .data)
ADD_VA = 0x00593AA0        # add(list) in the test builds (prep_fps.py): floats += deltas in one frame
X_LOW, X_JUMP = 53.0, 39.0     # land at x 92, behind the dip
X_FLAT = 80.0                  # x 80..53 is flat: only these frames go into the fit
SKIP = 8                       # frames after a landing that are left out (the kart settles)
TAIL = 4.0
FIT_FROM = 6.0


def f32(h, a):
    import harness as H
    return struct.unpack("<f", H.read(h, a, 4))[0]


def find_pos(h, body, pos):
    """Address of the x of the body's position in the physics engine's matrix pool."""
    import harness as H
    pool = H.u32(h, body)
    raw = b""
    for k in range(0, 0x2000, 0x100):                    # as far as the memory goes
        try:
            raw += H.read(h, pool + k, 0x100)
        except OSError:
            break
    fl = struct.unpack("<%df" % (len(raw) // 4), raw)
    for i in range(len(fl) - 2):
        if abs(fl[i] - pos[0]) < 1.0 and abs(fl[i + 1] - pos[1]) < 0.5 and abs(fl[i + 2] - pos[2]) < 1.0:
            return pool + 4 * i
    raise SystemExit("body position not found")


def find_vel(h, pos_addr, vel):
    """Address of the body's linear velocity (same pool, further on)."""
    import harness as H
    raw = b""
    for k in range(0, 0x3000, 0x100):
        try:
            raw += H.read(h, pos_addr + k, 0x100)
        except OSError:
            break
    fl = struct.unpack("<%df" % (len(raw) // 4), raw)
    sp = math.sqrt(sum(c * c for c in vel))
    for i in range(len(fl) - 2):
        if abs(fl[i] - vel[0]) < 0.03 * sp + 0.05 and abs(fl[i + 1] - vel[1]) < 0.03 * sp + 0.05                 and abs(fl[i + 2] - vel[2]) < 0.03 * sp + 0.05:
            return pos_addr + 4 * i
    return None


def one(exe, values, seconds, trace=None, cls=5, char=None):
    import harness as H
    import remote_test as R
    import ghostlib
    import optest
    ghostlib.wait_free()
    log = os.path.join(os.path.dirname(exe), "log.txt")
    if os.path.exists(log):
        os.remove(log)
    p = optest.launch(exe)
    try:
        t0 = time.time()
        while ghostlib.O.init_count(log) < 1:
            if time.time() - t0 > 60 or p.poll() is not None:
                raise SystemExit("game did not reach the menu")
            time.sleep(0.5)
        time.sleep(2.0)
        r = R.Remote()
        h = r.h
        r.write(INJECT, struct.pack("<3f", 0.0, 0.0, 0.0))
        v9 = list(values) + [100] * (9 - len(values))
        r.write(r.gp + 0x2E4C, struct.pack("<9i", *v9))
        r.write(r.gp + 0x2E7C, b"TUNE")
        r.write(r.gp + 0x2D70, b"WELT")
        r.write(r.gp + 0x2D78, b"GEGN")
        r.gp_i32(0x1C, 0)
        r.gp_i32(0x10, cls)
        r.gp_i32(0x20, 3)
        if char is not None:
            r.gp_i32(0x58, char)                         # player 1's character (settings.dat 84)
        n0 = ghostlib.O.init_count(log)
        r.call(R.START_RACE, ecx=r.menu())
        t0 = time.time()
        while ghostlib.O.init_count(log) == n0:
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
        o10 = H.u32(h, H.u32(h, car + 0x44) + 0x10)
        body, frame = H.u32(h, o10 + 4), H.u32(h, o10 + 8)
        veh = H.u32(h, car + 0x44)
        frame2 = H.u32(h, veh + 0x30)
        pos_addr = find_pos(h, body, struct.unpack("<3f", H.read(h, car + 0x10, 12)))
        # every copy of the kart's position found in memory (2026-11-23): the physics body, the
        # frames' modelling and world matrices, the vehicle's own copy, the car's two
        moved = [pos_addr, frame + 0x30, frame + 0x70, frame2 + 0x40, frame2 + 0x80, car + 0x10]
        extra = os.environ.get("TOPSPEED_EXTRA")              # probing: more offsets "car+350,o10+108"
        if extra:
            for e in extra.split(","):
                k, off = e.split("+")
                moved.append({"car": car, "o10": o10, "veh": veh}[k] + int(off, 16))
        vel_addr = None
        rows, last, thr, jumps = [], None, False, 0
        z0 = None
        wall0 = time.time()
        while time.time() - wall0 < seconds + 30:
            raw = H.read(h, cm + 0x20, 4)
            if raw == last:
                continue
            last = raw
            rt = struct.unpack("<f", raw)[0]
            if rt > seconds:
                break
            if rt >= 0.5 and not thr:
                r.write(INJECT, struct.pack("<3f", 0.0, 0.0, 1.0))
                thr = True
            x, y, z = struct.unpack("<3f", H.read(h, car + 0x10, 12))
            vx, vy, vz = struct.unpack("<3f", H.read(h, car + 0x2B4, 12))
            v = math.sqrt(vx * vx + vy * vy + vz * vz)
            rows.append((rt, x, y, z, v))
            if vel_addr is None and v > 10.0:
                vel_addr = find_vel(h, pos_addr, (vx, vy, vz))
            if z0 is None:
                z0 = z
            if x < X_LOW and thr:
                dz = z0 - z                              # x and z of the body and of the frame's two
                pairs = []                               # matrices move; the height is left alone
                for base in moved:
                    pairs += [(base, X_JUMP), (base + 8, dz)]
                if vel_addr is not None:                 # turn heading and velocity back to -x
                    bvx, _, bvz = struct.unpack("<3f", H.read(h, vel_addr, 12))
                    phi = math.atan2(bvz, -bvx)
                    if abs(phi) > 0.001:
                        c, s_ = math.cos(phi), math.sin(phi)
                        rot = struct.unpack("<12f", H.read(h, pos_addr - 0x30, 0x30))
                        for row in range(3):
                            ax, az = rot[4 * row], rot[4 * row + 2]
                            pairs += [(pos_addr - 0x30 + 0x10 * row, ax * c - az * s_ - ax),
                                      (pos_addr - 0x30 + 0x10 * row + 8, ax * s_ + az * c - az)]
                        pairs += [(vel_addr, bvx * c - bvz * s_ - bvx), (vel_addr + 8, bvx * s_ + bvz * c - bvz)]
                r.write(SCRATCH, struct.pack("<I", len(pairs)) + b"".join(struct.pack("<If", a_, d_) for a_, d_ in pairs))
                r.call(ADD_VA, args=(SCRATCH,))
                jumps += 1
            if not (-20.0 < y < 20.0) or abs(z + 33.0) > 12.0:
                break                                    # off the straight: no top speed from this run
        r.write(INJECT, struct.pack("<3f", 0.0, 0.0, 0.0))
    finally:
        try:
            H.kernel32.TerminateProcess(H.open_proc(0x0001), 0)
        except Exception:
            pass
        time.sleep(1.0)
    if trace:
        with open(trace, "w") as f:
            f.write("t,x,y,z,v\n")
            for row in rows:
                f.write(",".join("%.4f" % q for q in row) + "\n")
    return summarize(values, rows, seconds, jumps)


def summarize(values, rows, seconds, jumps):
    res = {"v": list(values), "jumps": jumps, "frames": len(rows)}
    if not rows:
        res["error"] = "no frames"
        return res
    t_end = rows[-1][0]
    res["t_end"] = round(t_end, 2)
    res["max"] = round(max(q[4] for q in rows), 3)
    tail = [q for q in rows if q[0] >= t_end - TAIL]
    if t_end < seconds - 0.5 or len(tail) < 10:
        res["error"] = "left the straight at %.1f s (x %.1f y %.1f z %.1f)" % (t_end, rows[-1][1], rows[-1][2], rows[-1][3])
        return res
    n = len(tail)
    mt = sum(q[0] for q in tail) / n
    mv = sum(q[4] for q in tail) / n
    slope = sum((q[0] - mt) * (q[4] - mv) for q in tail) / sum((q[0] - mt) ** 2 for q in tail)
    res["top"] = round(mv, 3)
    res["slope"] = round(slope, 4)
    res["spread"] = round(max(q[4] for q in tail) - min(q[4] for q in tail), 3)
    for s in (5, 10, 20):
        near = min(rows, key=lambda q: abs(q[0] - s))
        res["v%d" % s] = round(near[4], 2)
    fit = fit_top(rows)
    if fit:
        res.update(fit)
        res.update(model_top(values, fit["v_free"], fit["a_free"]))
    else:
        res["error"] = "too few free stretches for the fit"
    return res


def thrust(values, v):
    """Engine thrust as an acceleration (units/s2) in top gear, from class_model (at top speed the
    kart is in top gear; above 6000 rpm the torque is 0)."""
    import class_model as M
    s, pull, mass = values[0] / 100.0, values[1] / 100.0, values[3] / 100.0
    return pull * min(M.C * M.torque(143.27 * v / s), M.TRACTION) / mass


def model_top(values, v, a):
    dv = 0.05
    th = thrust(values, v)
    slope = (thrust(values, v + dv) - thrust(values, v - dv)) / (2 * dv)
    res_ = th - a
    k = slope - 2.0 * res_ / v
    if k >= -1e-3:
        return {"k_model": round(k, 3)}
    return {"k_model": round(k, 3), "top_model": round(v - a / k, 3)}


def fit_top(rows):
    """Top speed from the free stretches between jumps: line through (mean speed, acceleration)."""
    jumps = [i for i in range(1, len(rows)) if rows[i][1] > rows[i - 1][1] + 5.0]
    pts = []
    for a, b in zip(jumps, jumps[1:]):
        seg = [q for q in rows[a + SKIP:b] if q[1] < X_FLAT and q[0] >= FIT_FROM]
        if len(seg) < 5:
            continue
        n = len(seg)
        mt = sum(q[0] for q in seg) / n
        mv = sum(q[4] for q in seg) / n
        den = sum((q[0] - mt) ** 2 for q in seg)
        if den <= 0:
            continue
        pts.append((mv, sum((q[0] - mt) * (q[4] - mv) for q in seg) / den))
    if len(pts) < 8:
        return None
    n = len(pts)
    mx = sum(p[0] for p in pts) / n
    my = sum(p[1] for p in pts) / n
    sxx = sum((p[0] - mx) ** 2 for p in pts)
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pts)
    frames = [q for a, b in zip(jumps, jumps[1:]) for q in rows[a + SKIP:b] if q[1] < X_FLAT and q[0] >= FIT_FROM]
    out = {"fit_n": n, "v_mean": round(mx, 3), "a_mean": round(my, 3),
           "v_free": sum(q[4] for q in frames) / len(frames), "a_free": my}
    if sxx <= 1e-6 or sxy >= 0:
        out["fit_bad"] = True
        return out
    k = sxy / sxx
    out.update({"k": round(k, 3), "top_fit": round(mx - my / k, 3)})
    return out


def run_sets(sets_path, out, folders, seconds):
    sets = json.load(open(sets_path))
    os.makedirs(out, exist_ok=True)
    resfile = os.path.join(out, "results.jsonl")
    done = set()
    if os.path.exists(resfile):
        done = {json.loads(line)["id"] for line in open(resfile)}
    todo = [s for s in sets if s["id"] not in done]
    lock = threading.Lock()
    print("%d sets, %d to run" % (len(sets), len(todo)), flush=True)

    def worker(folder):
        while True:
            with lock:
                if not todo or os.path.exists(os.path.join(out, "stop")):
                    return
                s = todo.pop(0)
            env = dict(os.environ, MHK2_GAME=folder)
            cmd = [sys.executable, os.path.abspath(__file__), "run", os.path.join(out, "one_%s.jsonl" % folder),
                   ",".join(map(str, s["v"])), "--seconds", str(seconds), "--folder", folder]
            if "char" in s:
                cmd += ["--char", str(s["char"])]
            subprocess.run(cmd, cwd=SANDBOX, env=env, capture_output=True, text=True)
            tmp = os.path.join(out, "one_%s.jsonl" % folder)
            rec = json.loads(open(tmp).read().strip().splitlines()[-1]) if os.path.exists(tmp) else {"error": "no result"}
            if os.path.exists(tmp):
                os.remove(tmp)
            rec["id"] = s["id"]
            rec.setdefault("v", s["v"])
            if "char" in s:
                rec["char"] = s["char"]
            with lock:
                with open(resfile, "a") as f:
                    f.write(json.dumps(rec) + "\n")
                print("%s %-6s %-14s %s -> %s" % (time.strftime("%H:%M:%S"), folder, s["id"], s["v"],
                                                  rec.get("error") or "top %.2f slope %.3f" % (rec["top"], rec["slope"])),
                      flush=True)

    threads = [threading.Thread(target=worker, args=(f,)) for f in folders]
    for th in threads:
        th.start()
        time.sleep(1.0)
    for th in threads:
        th.join()


def main():
    a = sys.argv[1:]

    def opt(name, default):
        if name in a:
            i = a.index(name)
            v = a[i + 1]
            del a[i:i + 2]
            return v
        return default
    seconds = float(opt("--seconds", "40"))
    if a[0] == "sets":
        run_sets(a[1], a[2], opt("--folders", "game,game2,game3").split(","), seconds)
        return
    trace = opt("--trace", None)
    folder = opt("--folder", os.environ.get("MHK2_GAME", "game"))
    cls = int(opt("--cls", "5"))
    char = opt("--char", None)
    exe = os.path.join(SANDBOX, folder, "c5_new60.exe")
    for k, vs in enumerate(a[2:]):
        values = [int(x) for x in vs.split(",")]
        tr = os.path.join(trace, "trace_%d.csv" % k) if trace else None
        if trace:
            os.makedirs(trace, exist_ok=True)
        res = one(exe, values, seconds, tr, cls, None if char is None else int(char))
        print(json.dumps(res), flush=True)
        with open(a[1], "a") as f:
            f.write(json.dumps(res) + "\n")


if __name__ == "__main__":
    main()
