"""Sudden speed losses and the ground below the wheels, from ai_race.py recordings (issue #32).

usage: surf_loss.py <recording.csv> [...] [--drop 0.25] [--window 0.15] [--resist r0,r1,...]

Needs the columns surf0..surf3 (wheel+14h, the index into the track's materials; ai_race.py
prints the table at the start of a race) and ux, uy, uz (the kart's up axis).

A loss: the speed falls by at least --drop (share) within --window seconds while the brake
is below 0.1. For each loss it prints where it starts, the surfaces under the four wheels
(-1 = no ground), the wheel contacts, and the "chassis load": the downforce plus the weight
along the up axis minus what the four wheels carry, in weights of the kart (an estimate: it
leaves out the vertical acceleration). A large chassis load means the body lies on the road.

Then, per surface, the frames on it: share of the time, mean speed, and the losses that
start on it.
"""
import csv
import math
import sys
from collections import defaultdict

G = 19.62


def load(path):
    karts = defaultdict(list)
    with open(path) as f:
        for r in csv.DictReader(f):
            karts[int(r["kart"])].append({k: float(v) for k, v in r.items()})
    return karts


def downforce(r, coef, cap_ground, cap_air):
    vf = r["vx"] * r["fx"] + r["vy"] * r["fy"] + r["vz"] * r["fz"]
    on = any(int(r[f"c{k}"]) for k in range(4))
    cap = cap_ground if on else cap_air
    s = min(abs(vf), cap)
    if r["uy"] < 0.5:
        return 0.0
    return coef * s * s


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--drop", type=float, default=0.25)
    ap.add_argument("--window", type=float, default=0.15)
    ap.add_argument("--anpress", type=float, default=350, help="Anpressdruck in percent")
    ap.add_argument("--gewicht", type=float, default=100)
    ap.add_argument("--min", type=float, default=45, help="losses only from this speed up; per-surface time above it")
    a = ap.parse_args()
    drop, win = a.drop, a.window
    coef = 0.5 * a.anpress / 100
    cap_g = 120 * math.sqrt(a.gewicht / a.anpress) if a.anpress else 1e9
    cap_a = 75 * math.sqrt(a.gewicht / a.anpress) if a.anpress else 1e9
    for path in a.files:
        karts = load(path)
        print(f"== {path}")
        per_surf = defaultdict(lambda: [0, 0.0, 0])      # frames, speed sum, losses
        events = []
        for kart, rows in karts.items():
            sp = [math.sqrt(r["vx"] ** 2 + r["vy"] ** 2 + r["vz"] ** 2) for r in rows]
            for r, s in zip(rows, sp):
                if s < a.min:
                    continue
                m = r["mass"]
                ch = (downforce(r, coef, cap_g, cap_a) + m * G * max(r["uy"], 0) - sum(r[f"load{k}"] for k in range(4))) / (m * G)
                for sidx in {int(r[f"surf{k}"]) for k in range(4)}:
                    per_surf[sidx][0] += 1
                    per_surf[sidx][1] += ch
            i = 0
            n = len(rows)
            while i < n:
                j = i
                best = None
                while j < n and rows[j]["t"] - rows[i]["t"] <= win:
                    if sp[i] > a.min and sp[j] < sp[i] * (1 - drop) and max(rows[k]["brk"] for k in range(i, j + 1)) < 0.1:
                        best = j
                        break
                    j += 1
                if best is None:
                    i += 1
                    continue
                r = rows[i]
                m = r["mass"]
                df = downforce(r, coef, cap_g, cap_a)
                wl = sum(r[f"load{k}"] for k in range(4))
                chassis = (df + m * G * max(r["uy"], 0) - wl) / (m * G)
                # surfaces and contacts over the window before the loss (5 frames)
                surfs = sorted({int(rows[k][f"surf{w}"]) for k in range(max(0, i - 5), best + 1) for w in range(4)})
                events.append((kart, r["t"], sp[i], sp[best], r["x"], r["y"], r["z"], surfs,
                               "".join(str(int(r[f"c{k}"])) for k in range(4)), df / (m * G), wl / (m * G), chassis))
                for sidx in surfs:
                    per_surf[sidx][2] += 1
                i = best + 1
        events.sort(key=lambda e: (e[0], e[1]))
        print(f"{len(events)} losses (>= {drop:.0%} in {win} s, no brake)")
        print("kart     t   from ->   to      x      y      z  surfaces        contact  DF   wheels chassis (weights)")
        for e in events:
            print("%4d %6.2f %6.1f -> %5.1f %6.1f %6.1f %6.1f  %-15s %s  %5.1f %5.1f %6.1f" % (
                e[0], e[1], e[2], e[3], e[4], e[5], e[6], ",".join(map(str, e[7])), e[8], e[9], e[10], e[11]))
        tot = sum(v[0] for v in per_surf.values())
        dts = sorted(b["t"] - a_["t"] for a_, b in zip(karts[0], karts[0][1:]) if b["t"] > a_["t"])
        fps = 1 / dts[len(dts) // 2]                    # the median frame time (a 200 FPS build may run slower)
        print(f"per surface, kart frames above {a.min} units/s with a wheel on it (fps {fps:.0f}):")
        print("surface  seconds  mean chassis load  losses  losses per 10 s")
        for sidx in sorted(per_surf):
            fr, ss, lo = per_surf[sidx]
            sec = fr / fps
            print("%7d %8.1f %10.1f %14d %8.2f" % (sidx, sec, ss / fr, lo, 10 * lo / sec))


if __name__ == "__main__":
    main()
