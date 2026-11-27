"""Issue #32: the frames around a hit of one kart: position, step length, speed, velocity, wheel
contacts, ground under each wheel, up axis, driver animation, lat.
usage: py tools/hit_frames.py <recording.csv> <kart> <t> [--before 0.08] [--after 0.08]
"""
import csv
import math
import sys

path, kart, t0 = sys.argv[1], int(sys.argv[2]), float(sys.argv[3])
before = float(sys.argv[sys.argv.index("--before") + 1]) if "--before" in sys.argv else 0.08
after = float(sys.argv[sys.argv.index("--after") + 1]) if "--after" in sys.argv else 0.08
prev = None
for r in csv.DictReader(open(path)):
    if int(float(r["kart"])) != kart:
        continue
    t = float(r["t"])
    if t < t0 - before - 0.05:
        prev = r
        continue
    if t > t0 + after:
        break
    f = {k: float(v) if v not in ("",) else 0.0 for k, v in r.items() if k not in ()}
    sp = math.sqrt(f["vx"] ** 2 + f["vy"] ** 2 + f["vz"] ** 2)
    step = math.dist((f["x"], f["y"], f["z"]), (float(prev["x"]), float(prev["y"]), float(prev["z"]))) if prev else 0
    if t >= t0 - before:
        print("t %.3f pos %8.2f %6.2f %8.2f step %5.2f v %5.1f (%6.1f %5.1f %6.1f) c %d%d%d%d surf %d %d %d %d up (%.2f %.2f %.2f) anim %d lat %.2f"
              % (t, f["x"], f["y"], f["z"], step, sp, f["vx"], f["vy"], f["vz"], f["c0"], f["c1"], f["c2"], f["c3"],
                 f["surf0"], f["surf1"], f["surf2"], f["surf3"], f["ux"], f["uy"], f["uz"], f["cstate"], f["lat"]))
    prev = r
