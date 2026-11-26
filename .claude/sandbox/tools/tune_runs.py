r"""Straight-line runs of the tuning class with different values (sandbox, track 3, 60 FPS build).

usage: tune_runs.py <60 FPS test exe> <out dir> [name=a,b,c,d,e,f,g ...]

Without names it runs a fixed set: the defaults, single values pushed to their limits, everything
at once and two sets that reach the downforce limit of the class. Per run: did the game survive,
speeds after 0.5 / 1 / 2 / 3 s (the straight ends after about 100 units, so fast karts are past
it before 3 s), the top speed seen, the wheel load at 30 / 45 / 60 units/s as a multiple of the
kart's weight (shows the downforce; "-" = no frame near that speed with four wheels on the
ground) and where the kart was at the end. Uses pu_run.py; waits for other game instances.
"""
import csv
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = [155, 200, 100, 100, 100, 100, 100]
NAMES = ["gearing", "pull", "grip", "mass", "brakes", "steering", "downforce"]
LIMITS = [(50, 400), (25, 1000), (25, 400), (25, 400), (25, 400), (25, 200), (0, 800)]


def cases():
    out = [("defaults", DEFAULT)]
    for i, (lo, hi) in enumerate(LIMITS):
        if i in (4, 5):
            continue                      # brakes and steering do nothing on a straight at full throttle
        for tag, v in (("min", lo), ("max", hi)):
            vals = list(DEFAULT)
            vals[i] = v
            out.append(("%s %s" % (NAMES[i], tag), vals))
    out.append(("all max", [hi for lo, hi in LIMITS]))
    out.append(("fast and light", [400, 1000, 400, 25, 100, 100, 800]))
    # downforce limit: with 800 % it sets in at 120 * sqrt(100 / 800) = 42 units/s
    out.append(("pull max down max", [155, 1000, 100, 100, 100, 100, 800]))
    out.append(("pull max down 400", [155, 1000, 100, 100, 100, 100, 400]))
    return out


def load_at(rows, speed):
    near = sorted(q[6] for q in rows if q[5] == 4 and abs(q[4] - speed) <= 3.0)
    return "%.1f" % near[len(near) // 2] if len(near) >= 3 else "-"


def main():
    exe, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    todo = [(a.split("=")[0], [int(x) for x in a.split("=")[1].split(",")]) for a in sys.argv[3:]] or cases()
    for name, vals in todo:
        out = os.path.join(outdir, "tune_%s.csv" % name.replace(" ", "_"))
        if os.path.exists(out):
            os.remove(out)
        r = subprocess.run([sys.executable, os.path.join(HERE, "pu_run.py"), exe, out, "--track", "3", "--cls", "5",
                            "--tend", "4.0", "--tune", ",".join(str(v) for v in vals)], capture_output=True, text=True)
        if not os.path.exists(out):
            print("%-18s %s: NO DATA (%s)" % (name, vals, (r.stdout + r.stderr).strip()[-160:]), flush=True)
            continue
        rows = [(float(q["t"]), float(q["x"]), float(q["y"]), float(q["z"]), float(q["v"]), int(q["ground"]), float(q["load"]),
                 float(q["throttle"])) for q in csv.DictReader(open(out))]
        t_on = next((q[0] for q in rows if q[7] > 0.5), rows[0][0])
        at = lambda d: min(rows, key=lambda q: abs(q[0] - (t_on + d)))[4]
        bad = any(math.isnan(q[4]) or math.isinf(q[4]) or abs(q[2]) > 500 for q in rows)
        top = max(q[4] for q in rows)
        print("%-18s %s: %d frames%s | v after 0.5/1/2/3 s: %.1f %.1f %.1f %.1f | top %.1f | load at 30/45/60: %s %s %s | end x %.0f y %.1f"
              % (name, vals, len(rows), " BAD VALUES" if bad else "", at(0.5), at(1.0), at(2.0), at(3.0), top,
                 load_at(rows, 30), load_at(rows, 45), load_at(rows, 60), rows[-1][1], rows[-1][2]), flush=True)


if __name__ == "__main__":
    main()
