r"""How long the computer karts go without progress: the stretches in which a kart does not get
beyond the farthest place it has reached (laps + progress, car+220h).

usage: no_progress.py <recording.csv | folder> [...] [--track N] [--min 2.0]

Reads recordings of ai_race.py (also a geo_duel.py folder, --track picks the track) and of
race_recorder.py. Prints how many stretches of --min seconds or more there are, by length, and
how much time per kart race lies beyond 3, 4, 5, 6 and 8 s without progress: the time a rule
"set the kart back after N seconds without progress" could save at most.
"""
import collections
import csv
import glob
import os
import sys


def load(path):
    karts = collections.defaultdict(list)
    with open(path) as f:
        rd = csv.DictReader(f)
        rec = "knum" not in rd.fieldnames
        for r in rd:
            if r["kart"] != "0":
                karts[int(r["kart"] if rec else r["knum"])].append((float(r["t"]), float(r["prog"])))
    return karts


def stretches(rows, least):
    out = []
    best, since = rows[0][1], rows[0][0]
    for t, p in rows:
        if t < 6.0 or p > best + 1e-5:
            if t - since >= least:
                out.append((since, t - since, best))
            best, since = max(best, p), t
    if rows[-1][0] - since >= least:
        out.append((since, rows[-1][0] - since, best))
    return out


def main():
    a = sys.argv[1:]
    if not a:
        raise SystemExit(__doc__)

    def opt(name, default):
        return a[a.index(name) + 1] if name in a else default

    least = float(opt("--min", "2.0"))
    track = opt("--track", "*")
    files, skip = [], False
    for x in a:
        if skip or x.startswith("--"):
            skip = x in ("--track", "--min")
            continue
        files += sorted(glob.glob(os.path.join(x, "t%s_r*.csv" % track))) if os.path.isdir(x) else [x]
    all_, kart_races, seconds = [], 0, 0.0
    for f in files:
        for k, rows in load(f).items():
            kart_races += 1
            seconds += rows[-1][0] - rows[0][0]
            all_ += [(d, f, k, t, b) for t, d, b in stretches(rows, least)]
    print("%d file(s), %d kart races, %.0f s driven" % (len(files), kart_races, seconds))
    for lo, hi in ((2, 3), (3, 4), (4, 5), (5, 6), (6, 8), (8, 12), (12, 999)):
        n = [d for d, *_ in all_ if lo <= d < hi]
        print("   %3d..%3s s: %4d stretches, %5.2f per kart race" % (lo, hi if hi < 999 else "", len(n), len(n) / max(1, kart_races)))
    for lim in (3, 4, 5, 6, 8):
        over = [d - lim for d, *_ in all_ if d > lim]
        print("   beyond %d s: %4d stretches (%.2f per kart race), %.2f s per kart race" % (lim, len(over), len(over) / max(1, kart_races), sum(over) / max(1, kart_races)))
    for d, f, k, t, b in sorted(all_, reverse=True)[:8]:
        print("   longest: %5.1f s  %s kart %d from t %.1f at place %d" % (d, os.path.basename(f), k, t, int(b * 256) % 256))


if __name__ == "__main__":
    main()
