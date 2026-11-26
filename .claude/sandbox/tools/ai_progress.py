"""How far each kart gets in an ai_race.py recording.

usage: ai_progress.py <race.csv> [<race.csv> ...]

Per kart: distance driven, mean and top speed (game units, seconds of race time), and how long it
stood nearly still after the start phase (a kart stuck on a wall shows up there). Kart 0 is the
player's kart, which gets no input in these recordings.
"""
import csv
import math
import sys


def main():
    for path in sys.argv[1:]:
        karts = {}
        with open(path) as f:
            for r in csv.DictReader(f):
                karts.setdefault(int(r["kart"]), []).append((float(r["t"]), float(r["x"]), float(r["z"]),
                                                             math.sqrt(float(r["vx"]) ** 2 + float(r["vy"]) ** 2 + float(r["vz"]) ** 2)))
        print(path)
        tot = []
        for k in sorted(karts):
            rows = karts[k]
            dist = sum(math.hypot(b[1] - a[1], b[2] - a[2]) for a, b in zip(rows, rows[1:]))
            dur = rows[-1][0] - rows[0][0]
            later = [q for q in rows if q[0] > 5.0]
            stuck = sum(b[0] - a[0] for a, b in zip(later, later[1:]) if a[3] < 3.0)
            top = max(q[3] for q in rows)
            print("   kart %d: %7.0f units in %.0f s, mean %.1f, top %.1f, nearly still for %.1f s"
                  % (k, dist, dur, dist / dur, top, stuck))
            if k:
                tot.append((dist / dur, top, stuck))
        if tot:
            print("   computer karts: mean speed %.1f (%.1f .. %.1f), top %.1f, nearly still %.1f s in total"
                  % (sum(q[0] for q in tot) / len(tot), min(q[0] for q in tot), max(q[0] for q in tot),
                     max(q[1] for q in tot), sum(q[2] for q in tot)))


if __name__ == "__main__":
    main()
