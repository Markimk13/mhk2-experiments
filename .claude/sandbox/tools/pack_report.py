r"""How the computer karts of a race get in each other's way: stops, pile-ups, how close they drive.

usage: pack_report.py <recording.csv | folder> [...] [--seconds 120] [--list] [--against folder[,folder..]]

Reads recordings of ai_race.py (opp_races.py, geo_duel.py) and of race_recorder.py. Per set of
recordings (a folder counts as one set) it prints, per kart race:
- laps driven in the first --seconds (laps + progress, car+220h),
- stops: the kart is slower than 10 units/s after it was faster than 40 within the second
  before (later than 8 s into the race); time lost = until it is faster than 40 again,
- pile-ups: stops of three or more karts within 2.5 s and 4 places (256ths of the lap) of each
  other, and the share of all stops that belong to one,
- the gap to the next kart ahead, in seconds (median over the race, from the progress and the
  karts' mean lap time), and the share of the time a kart has another within 0.5 s ahead.
--list prints every pile-up. --against compares every set with the kart races of the given
folders taken together: laps, stops and time lost, each with a z value (pooled variance).
"""
import collections
import csv
import glob
import math
import os
import sys


def load(path, tmax):
    """-> {kart: [(t, speed, place, progress)]} of the computer karts"""
    K = collections.defaultdict(list)
    with open(path) as f:
        for r in csv.DictReader(f):
            if r["kart"] == "0":
                continue
            t = float(r["t"])
            if t > tmax:
                break
            k = r.get("knum") or r["kart"]
            K[k].append((t, math.hypot(float(r["vx"]), float(r["vz"])), (float(r["pathprog"]) * 256) % 256, float(r["prog"])))
    return K


def stops(rows):
    out, i, n, fast_t = [], 0, len(rows), -9.0
    while i < n:
        t, v, pl, _ = rows[i]
        if v > 40:
            fast_t = t
        if v < 10 and t - fast_t < 1.0 and t > 8:
            j = i
            while j < n and rows[j][1] <= 40:
                j += 1
            out.append((t, pl, (rows[j][0] if j < n else rows[-1][0]) - t))
            fast_t = -9.0
            i = j
        i += 1
    return out


def pileups(ev):
    """ev: [(t, place, lost, kart)] of one race -> groups of three or more karts"""
    ev = sorted(ev)
    groups, used = [], set()
    for a in range(len(ev)):
        if a in used:
            continue
        g = [a]
        for b in range(a + 1, len(ev)):
            if b in used:
                continue
            if ev[b][0] - ev[g[-1]][0] <= 2.5 and min(abs(ev[b][1] - ev[a][1]), 256 - abs(ev[b][1] - ev[a][1])) <= 4 \
                    and ev[b][3] not in [ev[x][3] for x in g]:
                g.append(b)
        if len(g) >= 3:
            used.update(g)
            groups.append([ev[x] for x in g])
    return groups


def gaps(K):
    """-> (median gap to the kart ahead in s, share of the samples with a kart within 0.5 s ahead)"""
    ks = sorted(K)
    n = min(len(K[k]) for k in ks)
    laps = sum(K[k][n - 1][3] - K[k][0][3] for k in ks) / len(ks)
    t_end = K[ks[0]][n - 1][0]
    lap_time = t_end / laps if laps > 0 else 60.0
    out, close, total = [], 0, 0
    for i in range(0, n, 40):                    # every 0.2 s at 200 rows per second
        if K[ks[0]][i][0] < 10:
            continue
        p = sorted(K[k][i][3] for k in ks)
        for a, b in zip(p, p[1:]):
            g = (b - a) * lap_time
            out.append(g)
            total += 1
            close += g < 0.5
    out.sort()
    return (out[len(out) // 2] if out else 0.0), (close / total if total else 0.0)


def per_kart(files, tmax):
    """-> (laps, stops, seconds lost) per kart race"""
    laps, n, lost = [], [], []
    for p in files:
        for k, rows in load(p, tmax).items():
            s = stops(rows)
            laps.append(rows[-1][3] - rows[0][3])
            n.append(len(s))
            lost.append(sum(x[2] for x in s))
    return laps, n, lost


def z_of(a, b):
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    var = (sum((x - ma) ** 2 for x in a) + sum((x - mb) ** 2 for x in b)) / (len(a) + len(b) - 2)
    return (mb - ma) / math.sqrt(var * (1.0 / len(a) + 1.0 / len(b))) if var else 0.0


def main():
    a = sys.argv[1:]
    if not a:
        raise SystemExit(__doc__)
    tmax = float(a[a.index("--seconds") + 1]) if "--seconds" in a else 120.0
    against = a[a.index("--against") + 1].split(",") if "--against" in a else []
    sets, skip = [], False
    for x in a:
        if skip or x.startswith("--"):
            skip = x in ("--seconds", "--against")
            continue
        sets.append((x, sorted(glob.glob(os.path.join(x, "*.csv"))) if os.path.isdir(x) else [x]))
    print("set                        races  laps   stops  lost s  in pile-ups  pile-ups per race  gap s  within 0.5 s")
    for name, files in sets:
        laps, nstops, lost, inpile, npile, gap, close, karts = [], 0, 0.0, 0, 0, [], [], 0
        listing = []
        for p in files:
            K = load(p, tmax)
            if not K:
                continue
            karts += len(K)
            ev = []
            for k, rows in K.items():
                laps.append(rows[-1][3] - rows[0][3])
                for t, pl, l in stops(rows):
                    ev.append((t, pl, l, k))
            nstops += len(ev)
            lost += sum(e[2] for e in ev)
            groups = pileups(ev)
            npile += len(groups)
            inpile += sum(len(g) for g in groups)
            for g in groups:
                listing.append("   %s t %.1f place %.0f: karts %s, lost %s s" % (os.path.basename(p), g[0][0], g[0][1], " ".join(str(e[3]) for e in g),
                                                                               " ".join("%.1f" % e[2] for e in g)))
            m, c = gaps(K)
            gap.append(m)
            close.append(c)
        if not karts:
            continue
        print("%-26s %4d   %.3f  %.2f   %5.1f   %3.0f %%        %.2f               %.2f   %3.0f %%"
              % (os.path.basename(name.rstrip("/\\")), len(files), sum(laps) / len(laps), nstops / karts, lost / karts,
                 100.0 * inpile / max(1, nstops), npile / len(files), sum(gap) / len(gap), 100 * sum(close) / len(close)))
        if "--list" in a:
            print("\n".join(listing))
    if against:
        base = per_kart([p for d in against for p in sorted(glob.glob(os.path.join(d, "*.csv")))], tmax)
        m = [sum(v) / len(v) for v in base]
        print("against %s (%d kart races: laps %.3f, stops %.2f, lost %.1f s):" % (", ".join(against), len(base[0]), m[0], m[1], m[2]))
        for name, files in sets:
            s = per_kart(files, tmax)
            if not s[0]:
                continue
            print("   %-22s laps %+5.1f %% (z %4.1f)   stops %+5.2f (z %4.1f)   lost %+5.1f s (z %4.1f)   n %d"
                  % (os.path.basename(os.path.normpath(name)), 100 * (sum(s[0]) / len(s[0]) / m[0] - 1), z_of(base[0], s[0]),
                     sum(s[1]) / len(s[1]) - m[1], z_of(base[1], s[1]), sum(s[2]) / len(s[2]) - m[2], z_of(base[2], s[2]), len(s[0])))


if __name__ == "__main__":
    main()
