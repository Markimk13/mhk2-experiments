r"""The result of a recorded race (race_recorder.py): who finished when.

usage: race_result.py <recording.csv> [...]

The recorder stops when the player finishes. The finish line is the progress (laps + progress,
car+220h) the player's kart has in its last row. A kart that finished before the player is found
by the first row in which its progress reaches that line: after the finish its progress stops
or jumps back, so the distance at the end of the recording does not rank such a kart. Karts
that had not finished are ranked by their progress at the end, with the gap in laps.
"""
import csv
import os
import sys


def result(path):
    """-> (player's time, [(kart, finish time or None, laps behind or 0.0)] in finishing order, player first if equal)"""
    P = {}
    with open(path) as f:
        for r in csv.DictReader(f):
            P.setdefault(int(r["kart"]), []).append((float(r["t"]), float(r["prog"])))
    line = P[0][-1][1]
    t_me = P[0][-1][0]
    out = []
    for k, rows in P.items():
        tf = next((t for t, p in rows if p >= line - 0.002), None)
        if k == 0:
            tf = t_me
        out.append((k, tf, 0.0 if tf is not None else line - max(p for t, p in rows[-200:])))
    out.sort(key=lambda e: (e[1] is None, e[1] if e[1] is not None else e[2], e[0] != 0))
    return t_me, out


def main():
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    for path in sys.argv[1:]:
        t_me, res = result(path)
        place = 1 + [k for k, _, _ in res].index(0)
        parts = []
        for k, tf, behind in res:
            name = "you" if k == 0 else "kart %d" % k
            parts.append("%s %.1f s" % (name, tf) if tf is not None else "%s -%.2f laps" % (name, behind))
        print("%s: your place %d, %.1f s | %s" % (os.path.basename(path), place, t_me, ", ".join(parts)))


if __name__ == "__main__":
    main()
