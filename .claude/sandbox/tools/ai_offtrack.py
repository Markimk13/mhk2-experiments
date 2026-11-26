"""Where do the computer karts get put back onto the track? From an ai_race.py or race_recorder.py recording.

usage: ai_offtrack.py <race.csv> [...]

A reset is a jump of more than 4 units between two frames (the game sets a kart that left the
track back onto it). Per kart: distance driven (without the jumps), resets and where they were;
then all resets of the race grouped by place (10-unit grid), so a corner that throws several
karts off shows up as one line.
"""
import collections
import csv
import math
import sys


def main():
    for path in sys.argv[1:]:
        karts = collections.defaultdict(list)
        with open(path) as f:
            for r in csv.DictReader(f):
                karts[int(r["kart"])].append((float(r["t"]), float(r["x"]), float(r["z"])))
        print(path)
        places = collections.Counter()
        total = 0
        for k in sorted(karts):
            rows = karts[k]
            dist, resets = 0.0, []
            for a, b in zip(rows, rows[1:]):
                d = math.hypot(b[1] - a[1], b[2] - a[2])
                if d > 4.0:
                    resets.append((a[0], a[1], a[2]))
                    places[(round(a[1] / 10) * 10, round(a[2] / 10) * 10)] += 1
                else:
                    dist += d
            total += len(resets) if k else 0
            print("   kart %d: %6.0f units, %d resets %s" % (k, dist, len(resets),
                  " ".join("%.0fs@(%.0f,%.0f)" % r for r in resets[:8])))
        print("   computer karts: %d resets; places: %s" % (total, ", ".join(
            "(%d,%d) x%d" % (p[0], p[1], n) for p, n in places.most_common(6))))


if __name__ == "__main__":
    main()
