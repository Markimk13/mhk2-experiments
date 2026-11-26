r"""The player's laps in race_recorder.py recordings: lap times, resets, hits, how far off the road.

usage: user_laps.py <recording.csv> [...]

Per recording the player's kart (index 0): per lap the time, top and mean speed, resets (the kart
jumps more than 4 units between two frames), hits (speed loss of more than 12 units/s within
0.1 s without a reset) and the places where the kart was farther from the centre line than half
the road width + 3 units (track_line.py), each with lap share, position and what happened.
"""
import csv
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from track_line import Line  # noqa: E402


def load(path, kart="0"):
    rows = []
    for r in csv.DictReader(open(path)):
        if r["kart"] == kart:
            rows.append((float(r["t"]), float(r["x"]), float(r["y"]), float(r["z"]),
                         math.hypot(float(r["vx"]), float(r["vz"])), float(r["vy"]), float(r["prog"])))
    return rows


def events(rows, ln):
    """list of (kind, t, lap share, x, z, text)"""
    ev = []
    j = 0
    off_since = None
    for i in range(1, len(rows)):
        t, x, y, z, v, vy, prog = rows[i]
        pt, px, py, pz, pv, pvy, pprog = rows[i - 1]
        if math.hypot(x - px, z - pz) > 4:
            ev.append(("reset", pt, pprog % 1, px, pz, "jump of %.0f units, speed before %.0f" % (math.hypot(x - px, z - pz), pv)))
            off_since = None
            continue
        while t - rows[j][0] > 0.1:
            j += 1
        if rows[j][4] - v > 12 and not (ev and ev[-1][0] in ("hit", "reset") and t - ev[-1][1] < 1.0):
            ev.append(("hit", t, prog % 1, x, z, "speed %.0f -> %.0f" % (rows[j][4], v)))
        if i % 10 == 0:
            idx, d = ln.nearest(x, z)
            out = d > ln.width[idx] / 2 + 3
            if out and off_since is None:
                off_since = (t, prog % 1, x, z, d)
            elif out and d > off_since[4]:
                off_since = off_since[:4] + (d,)
            elif not out and off_since is not None:
                ev.append(("off", off_since[0], off_since[1], off_since[2], off_since[3],
                           "%.1f s, up to %.0f units from the centre" % (t - off_since[0], off_since[4])))
                off_since = None
    return ev


def main():
    for path in sys.argv[1:]:
        name = os.path.basename(path)
        track = int(name[name.index("_t") + 2:name.index(".")])
        rows = load(path)
        ln = Line(track)
        print("%s: %d frames, %.1f s" % (name, len(rows), rows[-1][0]))
        lap0, k0 = None, 0
        base = math.floor(rows[0][6])
        for i in range(1, len(rows)):
            if math.floor(rows[i][6]) > math.floor(rows[i - 1][6]) and rows[i][6] - rows[i - 1][6] < 0.5:
                if lap0 is not None:
                    seg = rows[k0:i]
                    print("   lap %d: %.2f s, top %.1f, mean %.1f" % (math.floor(rows[i][6]) - base - 1, rows[i][0] - lap0,
                                                                     max(e[4] for e in seg), sum(e[4] for e in seg) / len(seg)))
                lap0, k0 = rows[i][0], i
        for kind, t, share, x, z, text in events(rows, ln):
            print("   %-5s t %6.1f  lap %.3f  (%5.0f, %5.0f)  %s" % (kind, t, share, x, z, text))


if __name__ == "__main__":
    main()
