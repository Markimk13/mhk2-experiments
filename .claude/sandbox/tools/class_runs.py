r"""Standing start and top speed of engine classes, measured in the sandbox (track 3, 60 FPS build).

usage: class_runs.py <60 FPS test exe> <out dir> <class>:<cut>[,<cut>...] [...]
       e.g. class_runs.py game\c5_new60.exe runs 2:46.5,48.5 3:s52,s55 4:s56,s59

Per class: one plain standing start (speeds after 0.5 / 1 / 2 / 3 s, time to 30 / 40 / 50) and
one pushed run per cut speed: a power-up until the cut, then plain. What the kart does behind the
dip tells its top speed. A cut written as s52 pushes with the siren instead of the power can:
that is the one to use for classes with a pull above 1, where the power can overshoots by far.
Uses pu_run.py and hold_speed.py; waits for other game instances.
"""
import csv
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hold_speed as HS


def run(exe, out, cls, extra):
    if os.path.exists(out):
        os.remove(out)
    r = subprocess.run([sys.executable, os.path.join(HERE, "pu_run.py"), exe, out, "--track", "3", "--cls", str(cls)] + extra,
                       capture_output=True, text=True)
    if not os.path.exists(out):
        print("   run failed:", (r.stdout + r.stderr).strip()[-200:], flush=True)
        return False
    return True


def standing(path):
    rows = [(float(r["t"]), float(r["v"]), float(r["throttle"])) for r in csv.DictReader(open(path))]
    t_on = next(t for t, v, thr in rows if thr > 0.5)
    at = lambda d: min(rows, key=lambda q: abs(q[0] - (t_on + d)))[1]
    def to(v):
        for t, vv, thr in rows:
            if vv >= v:
                return "%.2f" % (t - t_on)
        return "-"
    return "after 0.5/1/2/3 s: %.1f %.1f %.1f %.1f | time to 30/40/50: %s %s %s" % (at(0.5), at(1.0), at(2.0), at(3.0), to(30), to(40), to(50))


def held(path):
    rows, seg = HS.segment(path)
    if len(seg) < 5:
        return "no frames behind the dip"
    t = [float(r["t"]) for r in seg]
    v = [float(r["v"]) for r in seg]
    n = len(seg)
    tm, vm = sum(t) / n, sum(v) / n
    slope = sum((a - tm) * (b - vm) for a, b in zip(t, v)) / sum((a - tm) ** 2 for a in t)
    text = "v %.2f -> %.2f over %.2f s (slope %+.2f per s)" % (v[0], v[-1], t[-1] - t[0], slope)
    if abs(v[-1] - v[0]) > 0.15:
        k, veq, rms = HS.approach(t, v)
        text += ", heading for %.2f (rms %.3f)" % (veq, rms)
    return text


def main():
    exe, outdir = sys.argv[1], sys.argv[2]
    os.makedirs(outdir, exist_ok=True)
    for spec in sys.argv[3:]:
        cls, _, cuts = spec.partition(":")
        cls = int(cls)
        p = os.path.join(outdir, "c%d_plain.csv" % cls)
        if run(exe, p, cls, ["--tend", "4.2"]):
            print("class %d standing start: %s" % (cls, standing(p)), flush=True)
        for cut in [c for c in cuts.split(",") if c]:
            boost, speed = ("2", cut[1:]) if cut.startswith("s") else ("7", cut)
            p = os.path.join(outdir, "c%d_cut%s.csv" % (cls, cut.replace(".", "")))
            if run(exe, p, cls, ["--tend", "3.6", "--boost", boost, "--cut", speed]):
                print("class %d pushed with the %s, cut at %s: %s" % (cls, "siren" if boost == "2" else "power can", speed, held(p)), flush=True)


if __name__ == "__main__":
    main()
