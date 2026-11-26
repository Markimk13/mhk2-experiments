"""Find the longest start straight: full throttle, no steering, on every track.

usage: pu_survey.py <exe> <outdir> [track ...]
Prints for each track how far the kart gets before it first slows down sharply.
Waits while any other instance of the game runs (the real one included).
"""
import csv
import math
import os
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ghostlib

HERE = os.path.dirname(os.path.abspath(__file__))


def analyse(path):
    rows = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(open(path))]
    go = [r for r in rows if r["throttle"] > 0.99]
    if not go:
        return None
    x0, z0 = go[0]["x"], go[0]["z"]
    best_v, dist, end = 0.0, 0.0, None
    prev = go[0]
    for r in go[1:]:
        v = math.sqrt(r["vx"] ** 2 + r["vy"] ** 2 + r["vz"] ** 2)
        dist += math.hypot(r["x"] - prev["x"], r["z"] - prev["z"])
        prev = r
        if v > best_v:
            best_v = v
        elif v < best_v - 1.5:            # lost 1.5 units/s against the best so far: hit something / left the road
            end = r
            break
    last = end or go[-1]
    return {"t_end": last["t"], "dist": dist, "vmax": best_v, "y0": go[0]["y"], "y1": last["y"],
            "straight": math.hypot(last["x"] - x0, last["z"] - z0), "ran_out": end is None}


def main():
    exe, out = sys.argv[1], sys.argv[2]
    tracks = [int(t) for t in sys.argv[3:]] or list(range(8))
    os.makedirs(out, exist_ok=True)
    for t in tracks:
        ghostlib.wait_free()          # never next to another instance of the game
        dst = os.path.join(out, "survey_t%d.csv" % t)
        r = subprocess.run([sys.executable, os.path.join(HERE, "drive.py"), exe, dst, "--plan", "0.5:1:0:0,12", "--track", str(t), "--cls", "2"],
                           capture_output=True, text=True, timeout=300)
        msg = (r.stdout.strip() or r.stderr.strip())[-120:]
        if not os.path.exists(dst):
            print("track %d: no data (%s)" % (t, msg), flush=True)
            continue
        a = analyse(dst)
        if not a:
            print("track %d: no throttle rows (%s)" % (t, msg), flush=True)
            continue
        print("track %d: straight for %.0f units (%.1f s), top %.1f units/s, height %.1f -> %.1f%s | %s"
              % (t, a["straight"], a["t_end"] - 0.5, a["vmax"], a["y0"], a["y1"], "  (still going at the end)" if a["ran_out"] else "", msg), flush=True)


if __name__ == "__main__":
    main()
