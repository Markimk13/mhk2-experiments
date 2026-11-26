r"""Where the computer karts lose time: incidents in recordings of ai_race.py, by place of the lap.

usage: geo_incidents.py <recording.csv ...> [--top 8] [--trace 3] [--karts 1,2,3]

An incident of a kart is
- a reset: the kart's position jumps by more than 4 units between two frames (the game puts it
  back on the track), together with the slow seconds around it, or
- a hit: the kart is slower than 15 units/s for 0.3 s or longer without a reset (a wall, another
  kart, a power-up).
Its place is where the kart was ORIGIN seconds before the trouble began, in 256ths of the lap by
the path progress (car+224h, the key of the learned tables). Its cost is the time from there
until the kart is faster than 30 units/s again.

Prints per recording set the incidents per kart and race, then the places with the highest cost
(neighbouring places together) and, with --trace N, for N incidents of each place the kart's
values in the seconds before: place, lateral position (0..1 is the road), speed, allowed speed,
height, and the distance to the nearest other kart.
--karts counts only these kart numbers (the others still count as neighbours).
"""
import collections
import csv
import math
import sys

BINS = 256
ORIGIN = 1.0
TRACE_AT = (4.0, 3.0, 2.0, 1.5, 1.0, 0.5, 0.1)


def load(path):
    karts = collections.defaultdict(list)
    with open(path) as f:
        for r in csv.DictReader(f):
            karts[int(r["knum"]) if r["kart"] != "0" else 0].append((
                float(r["t"]), float(r["x"]), float(r["y"]), float(r["z"]),
                math.hypot(float(r["vx"]), float(r["vz"])), float(r["allow"]), float(r["lat"]),
                float(r["pathprog"]), float(r["prog"])))
    return karts


def at(rows, i, back):
    """index of the row `back` seconds before row i"""
    t = rows[i][0] - back
    j = i
    while j > 0 and rows[j][0] > t:
        j -= 1
    return j


def incidents(rows):
    """-> list of dicts: kind, i0 (row where the trouble began), i1 (row where it was over)"""
    n = len(rows)
    resets = [i for i in range(1, n) if math.dist(rows[i][1:4], rows[i - 1][1:4]) > 4]
    slow = []                                    # (first row, last row) of the slow stretches
    i = 0
    while i < n:
        if rows[i][0] > 8 and rows[i][4] < 15:
            j = i
            while j + 1 < n and rows[j + 1][4] < 15:
                j += 1
            if rows[j][0] - rows[i][0] >= 0.3:
                slow.append((i, j))
            i = j + 1
        else:
            i += 1
    spans = [(at(rows, i, 0.0) - 1, i, "reset") for i in resets if rows[i][0] > 5] + [(a, b, "hit") for a, b in slow]
    spans.sort()
    out = []
    for a, b, kind in spans:                     # join what belongs together: slow before a reset, standing after it
        if out and rows[a][0] - rows[out[-1]["last"]][0] < 3.0:
            o = out[-1]
            o["last"] = max(o["last"], b)
            if kind == "reset":
                o["kind"] = "reset"
                o["resets"] += 1
        else:
            out.append({"kind": kind, "first": a, "last": b, "resets": 1 if kind == "reset" else 0})
    for o in out:
        o["i0"] = at(rows, o["first"], ORIGIN)
        j = o["last"]
        while j + 1 < n and rows[j][4] < 30:
            j += 1
        o["i1"] = j
        o["cost"] = rows[j][0] - rows[o["i0"]][0]
        o["place"] = int(rows[o["i0"]][7] * BINS) % BINS
    return out


def nearest(karts, kn, t):
    """distance of kart kn to the nearest other kart at time t"""
    me = None
    best = 1e9
    pos = {}
    for k, rows in karts.items():
        lo, hi = 0, len(rows) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if rows[mid][0] < t:
                lo = mid + 1
            else:
                hi = mid
        pos[k] = rows[lo][1:4]
    me = pos[kn]
    for k, p in pos.items():
        if k != kn:
            best = min(best, math.dist(me, p))
    return best


def main():
    a = sys.argv[1:]
    top = int(a[a.index("--top") + 1]) if "--top" in a else 8
    trace = int(a[a.index("--trace") + 1]) if "--trace" in a else 0
    only = set(int(x) for x in a[a.index("--karts") + 1].split(",")) if "--karts" in a else None
    skip = set()
    for o in ("--top", "--trace", "--karts"):
        if o in a:
            skip |= {a.index(o), a.index(o) + 1}
    files = [x for i, x in enumerate(a) if i not in skip]
    if not files:
        raise SystemExit(__doc__)
    found = []                                   # (place, cost, kind, file, kart, rows, incident, karts)
    kart_races = 0
    seconds = 0.0
    for path in files:
        karts = load(path)
        for kn, rows in karts.items():
            if kn == 0 or len(rows) < 100 or (only and kn not in only):
                continue
            kart_races += 1
            seconds += rows[-1][0] - rows[0][0]
            for o in incidents(rows):
                found.append((o["place"], o["cost"], o["kind"], path, kn, rows, o, karts))
    if not kart_races:
        raise SystemExit("no karts")
    total = sum(f[1] for f in found)
    nres = sum(1 for f in found if f[2] == "reset")
    print("%d recordings, %d kart races of %.0f s: %.2f resets and %.2f hits per kart race, %.1f s lost (%.1f %% of the time)"
          % (len(files), kart_races, seconds / kart_races, nres / kart_races, (len(found) - nres) / kart_races,
             total / kart_races, 100 * total / seconds))
    cost = [0.0] * BINS
    for f in found:
        cost[f[0]] += f[1]
    groups = []                                  # neighbouring places together: (cost, first, last)
    used = [False] * BINS
    for b in sorted(range(BINS), key=lambda b: -cost[b]):
        if used[b] or cost[b] == 0:
            continue
        lo = hi = b
        while cost[(lo - 1) % BINS] > 0 and not used[(lo - 1) % BINS] and b - lo < 4:
            lo -= 1
        while cost[(hi + 1) % BINS] > 0 and not used[(hi + 1) % BINS] and hi - b < 4:
            hi += 1
        for k in range(lo, hi + 1):
            used[k % BINS] = True
        groups.append((sum(cost[k % BINS] for k in range(lo, hi + 1)), lo, hi))
    groups.sort(reverse=True)
    for c, lo, hi in groups[:top]:
        inc = [f for f in found if lo <= f[0] <= hi or lo <= f[0] - BINS <= hi or lo <= f[0] + BINS <= hi]
        nr = sum(1 for f in inc if f[2] == "reset")
        print("places %3d..%3d: %5.2f s per kart race, %d resets, %d hits" % (lo % BINS, hi % BINS, c / kart_races, nr, len(inc) - nr))
        for place, cst, kind, path, kn, rows, o, karts in inc[:trace]:
            print("    %s kart %d at %.1f s, cost %.1f s (%s)" % (kind, kn, rows[o["first"]][0], cst, path[-28:]))
            for back in TRACE_AT:
                r = rows[at(rows, o["first"], back)]
                print("      -%.1f s: place %5.1f lat %5.2f speed %5.1f allowed %5.1f height %6.2f next kart %5.1f"
                      % (back, r[7] * BINS, r[6], r[4], r[5], r[2], nearest(karts, kn, r[0])))
            r = rows[min(o["last"] + 1, len(rows) - 1)]
            print("      after:  place %5.1f lat %5.2f speed %5.1f" % (r[7] * BINS, r[6], r[4]))


if __name__ == "__main__":
    main()
