r"""The game's speed limit boxes and what they do to the learned driver, from a geo_duel.py batch.

usage: geo_boxes.py <geo_duel dir> --with off --without bx,bxse [--tables geo_tables.inc] [--json boxes.json]

A speed limit box sets car+33Ch while a kart is inside it (14 to 25 units/s; made for the stock
driver). The learned driver takes the lower of the box and its learned speed unless its value BX
overrules the box. In the recordings a box shows as an allowed speed that is a whole number far
below the learned speed of the place.

Prints per track the boxes (places of the lap in 256ths, value, learned speed there) found in
the karts named by --with, and for every box the time the karts need from 12 places ahead of
it to 16 places behind it: with the box (--with) and with the box overruled (--without, karts
that drove bx=1). --json writes the boxes for other tools.
"""
import collections
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import geo_duel as D
import geo_incidents as INC

BINS = 256
AHEAD, BEHIND = 12, 16


def region_times(rows, lo, hi):
    """seconds of every pass from place lo to place hi (hi may be above 255); None for a pass that did not end"""
    shift = round(((rows[50][8] - rows[50][7]) % 1.0) * 2) / 2.0
    cross = {}
    reached = math.floor((rows[0][8] - shift) * BINS)
    first = reached
    for r in rows:
        m = math.floor((r[8] - shift) * BINS)
        while reached < m:
            reached += 1
            cross[reached] = r[0]
    out = []
    for lap in range(first // BINS - 1, reached // BINS + 2):
        a, b = lap * BINS + lo, lap * BINS + hi
        if a in cross and cross[a] >= 8.0:
            out.append(cross[b] - cross[a] if b in cross else None)
    return out


def main():
    a = sys.argv[1:]
    if not a:
        raise SystemExit(__doc__)
    out = a[0]

    def opt(name, default):
        return a[a.index(name) + 1] if name in a else default

    with_ = opt("--with", "off").split(",")
    without = opt("--without", "bx").split(",")
    tabs = D.read_inc(opt("--tables", os.path.join(HERE, "geo_tables.inc")))
    who_all = json.load(open(os.path.join(out, "who.json")))
    found = {}
    for t in range(8):
        speed = tabs[t][0]
        recs = []
        r = 0
        while os.path.exists(os.path.join(out, "t%d_r%d.csv" % (t, r))):
            recs.append((who_all["t%d_r%d" % (t, r)], INC.load(os.path.join(out, "t%d_r%d.csv" % (t, r)))))
            r += 1
        if not recs:
            continue
        box = collections.defaultdict(collections.Counter)
        n = collections.Counter()
        for who, karts in recs:
            for kn, rows in karts.items():
                if kn == 0 or who[str(kn)] not in with_:
                    continue
                for row in rows:
                    if row[0] < 8:
                        continue
                    b = int(row[7] * BINS) % BINS
                    n[b] += 1
                    al = row[5]
                    if abs(al - round(al)) < 1e-3 and al < 45 and al < 0.9 * 1.1 * speed[b]:
                        box[b][int(round(al))] += 1
        zones = []
        for b in range(BINS):
            if box[b] and sum(box[b].values()) > 0.3 * n[b]:
                v = box[b].most_common(1)[0][0]
                if zones and zones[-1][1] >= b - 2 and zones[-1][2] == v:
                    zones[-1][1] = b
                else:
                    zones.append([b, b, v])
        found[t] = zones
        print("track %d: %d box(es)" % (t, len(zones)))
        for lo, hi, v in zones:
            cells = []
            for names in (with_, without):
                times, open_ = [], 0
                for who, karts in recs:
                    for kn, rows in karts.items():
                        if kn and who[str(kn)] in names:
                            for s in region_times(rows, lo - AHEAD, hi + BEHIND):
                                if s is None:
                                    open_ += 1
                                else:
                                    times.append(s)
                times.sort()
                if times:
                    cap = 2.5 * times[len(times) // 2]
                    m, se = D.mean_se([min(x, cap) for x in times])
                    cells.append((m, se, times[len(times) // 2], len(times), open_))
                else:
                    cells.append((0, 0, 0, 0, open_))
            (m1, s1, med1, n1, o1), (m2, s2, med2, n2, o2) = cells
            z = (m1 - m2) / math.sqrt(s1 * s1 + s2 * s2) if s1 or s2 else 0.0
            print("   places %3d..%3d: box %2d, learned %2.0f..%2.0f | with the box %.2f s (median %.2f, %d passes) | overruled %.2f s (median %.2f, %d passes) | gain %+.0f %%, z %.1f"
                  % (lo, hi, v, min(speed[lo:hi + 1]), max(speed[lo:hi + 1]), m1, med1, n1, m2, med2, n2, 100 * (1 - m2 / m1) if m1 else 0, z))
    if "--json" in a:
        json.dump({str(t): z for t, z in found.items()}, open(opt("--json", ""), "w"))


if __name__ == "__main__":
    main()
