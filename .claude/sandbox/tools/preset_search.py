r"""Looks for preset values that keep a preset's idea and stay "am Limit" (sandbox).

usage: preset_search.py [name ...] [--sets out.json --tracks 8]

For every preset idea below: a box of allowed values per row and an aim (fast, slippery, heavy,
...). Coordinate ascent from many random starts on the grid, scored by the aim, with the
patcher's tune_limit (risk below the preset's limit, push at least LIMIT_PUSH_MIN) and the speed
model of tune_sweep_fit (fitted on the races in runs\sweep1..3). Prints the best few sets per
idea. With --sets it writes them (the best three per idea) as a tune_sweep.py set file, each set on
the given number of tracks.
"""
import json
import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SANDBOX = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(SANDBOX)), "tools"))
import patch_200cc as P   # noqa: E402
import tune_sweep_fit as F   # noqa: E402

ROWS = P.TUNE_ROWS
FULL = [(lo, hi) for lo, hi, _, _ in ROWS]


def box(**kw):
    """Allowed (lo, hi) per row; rows not named stay at their default."""
    names = ("gear", "power", "grip", "weight", "brakes", "steer", "down", "gravity", "opp")
    out = []
    for k, n in enumerate(names):
        d = ROWS[k][3]
        out.append(kw.get(n, (d, d)))
    return out


# name: (box, aim(values, speed, risk, push), risk limit[, push needed (default yes)])
IDEAS = {
    "Rakete": (box(gear=(200, 400), power=(300, 1000), grip=(100, 400), weight=(50, 150), brakes=(100, 400),
                   steer=(100, 200), down=(100, 800)),
               lambda v, s, r, p: math.log2(s), 12),
    "Formel 1": (box(gear=(180, 400), power=(300, 1000), grip=(200, 400), weight=(75, 100), brakes=(200, 400),
                     steer=(100, 200), down=(300, 800)),
                 lambda v, s, r, p: math.log2(s), 12),
    "Rallye": (box(gear=(155, 250), power=(200, 500), grip=(50, 90), steer=(125, 200), down=(25, 100), weight=(75, 125)),
               lambda v, s, r, p: p / 32.0 + math.log2(s), 12),
    "Glatteis": (box(grip=(25, 60), down=(25, 100), steer=(100, 200), brakes=(25, 100)),
                 lambda v, s, r, p: -math.log2(v[2] / 100.0) + 0.5 * -math.log2((v[6] + 25) / 125.0), 12),
    "Schwergewicht": (box(weight=(150, 400), power=(200, 600), brakes=(100, 400), down=(100, 400), grip=(100, 200)),
                      lambda v, s, r, p: math.log2(v[3] / 100.0) + 0.5 * math.log2(s), 24, False),
    "Dragster": (box(gear=(300, 400), power=(300, 1000), grip=(100, 400), weight=(50, 150), steer=(50, 100),
                     down=(50, 800)),
                 lambda v, s, r, p: math.log2(s) + 0.5 * math.log2(v[1] / 200.0) - 0.3 * math.log2(v[5] / 100.0), 24),
    # ideas for new presets (2026-11-23)
    "Mondrakete": (box(gear=(155, 400), power=(200, 1000), gravity=(25, 75), down=(100, 800), grip=(100, 400),
                       steer=(100, 200)),
                   lambda v, s, r, p: math.log2(s) - 0.5 * math.log2(v[7] / 100.0), 12),
    "Kurvenkünstler": (box(gear=(155, 300), power=(200, 600), grip=(150, 400), steer=(150, 200), down=(200, 800),
                           brakes=(100, 400)),
                       lambda v, s, r, p: math.log2(s) + 0.5 * math.log2(v[5] / 100.0), 12),
    "Bremsversagen": (box(gear=(155, 350), power=(200, 600), brakes=(25, 25), grip=(75, 200), down=(50, 400)),
                      lambda v, s, r, p: math.log2(s), 12),
    "Hetzjagd": (box(gear=(155, 250), power=(200, 400), opp=(150, 200), grip=(100, 300), down=(100, 400)),
                 lambda v, s, r, p: v[8] / 100.0 + math.log2(s), 24),
    "Federleicht": (box(weight=(25, 50), power=(100, 400), gear=(155, 300), grip=(75, 200), down=(50, 400),
                        gravity=(50, 150)),
                    lambda v, s, r, p: -math.log2(v[3] / 100.0) + math.log2(s), 12),
    "Achterbahn": (box(gravity=(200, 300), gear=(155, 400), power=(200, 600), down=(100, 800), grip=(100, 300)),
                   lambda v, s, r, p: math.log2(v[7] / 100.0) + math.log2(s), 12),
    "Wahnsinn": (FULL, lambda v, s, r, p: p / 32.0 + 4 * math.log2(s), 24),
}


def grid(k, lo, hi):
    lo_, hi_, step, _ = ROWS[k]
    return [x for x in range(lo_, hi_ + 1, step) if lo <= x <= hi]


def search(name, sw, starts=40, seed=1):
    bx, aim, rmax = IDEAS[name][:3]
    need_push = IDEAS[name][3] if len(IDEAS[name]) > 3 else True
    rnd = random.Random(seed)
    grids = [grid(k, lo, hi) for k, (lo, hi) in enumerate(bx)]

    def score(v):
        lv, risk, push = P.tune_limit(v)
        if risk >= rmax or (need_push and push < P.LIMIT_PUSH_MIN):
            return -1e9 + push - risk
        s = F.speed_pred(sw, v)
        return aim(v, s, risk, push) - 0.01 * risk

    found = {}
    for _ in range(starts):
        v = [rnd.choice(g) for g in grids]
        best = score(v)
        improved = True
        while improved:
            improved = False
            for k in rnd.sample(range(9), 9):
                for x in grids[k]:
                    if x == v[k]:
                        continue
                    w = list(v)
                    w[k] = x
                    sc = score(w)
                    if sc > best + 1e-9:
                        v, best, improved = w, sc, True
        if best > -1e8:
            found[tuple(v)] = best
    return sorted(found.items(), key=lambda kv: -kv[1])


def main():
    a = sys.argv[1:]
    out, tracks = None, 8
    if "--sets" in a:
        i = a.index("--sets")
        out = a[i + 1]
        del a[i:i + 2]
    if "--tracks" in a:
        i = a.index("--tracks")
        tracks = int(a[i + 1])
        del a[i:i + 2]
    names = a or list(IDEAS)
    recs, _ = F.load([os.path.join(SANDBOX, "runs", d) for d in sorted(os.listdir(os.path.join(SANDBOX, "runs"))) if d.startswith("sweep") and os.path.exists(os.path.join(SANDBOX, "runs", d, "results.jsonl"))])
    sw, _ = F.speed_fit([r for r in recs if not r["id"].startswith("default")])
    sets = []
    rnd = random.Random(9)
    for name in names:
        res = search(name, sw)
        now = dict(P.TUNE_PRESETS).get(name)
        print("== %s (now %s)" % (name, "%s: %s" % (list(now), P.tune_limit(list(now))) if now else "new"))
        picked = []
        for v, sc in res:
            # the best three that differ in more than one row from each other
            if all(sum(1 for x, y in zip(v, q) if x != y) > 1 for q in picked):
                picked.append(v)
            if len(picked) == 3:
                break
        for v in picked:
            print("   %s  %s  speed %.2f" % (list(v), P.tune_limit(list(v)), F.speed_pred(sw, list(v))))
        for n, v in enumerate(picked):
            for t in rnd.sample(range(8), tracks):
                sets.append({"id": "c-%s-%d-t%d" % (name.replace(" ", ""), n, t), "v": list(v), "track": t})
    if out:
        json.dump(sets, open(out, "w"), indent=0)
        print("%d sets -> %s" % (len(sets), out))


if __name__ == "__main__":
    main()
