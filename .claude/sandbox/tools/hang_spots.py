r"""Where the computer karts hang: the places of a track where a kart stands or crawls for a second or more.

usage: hang_spots.py <recording.csv | folder> [...] [--track N] [--slow 5] [--min 1.0] [--list]

Reads recordings of ai_race.py (also the t<N>_r<M>.csv of a geo_duel.py folder; --track picks
the track there) and of race_recorder.py (the user's own races). A hang starts when a computer
kart is slower than --slow units/s for --min seconds or more, later than 6 s into the race, and
ends when it is faster than 15 units/s again or the game sets it back on the track (a jump of
more than 4 units between two frames).

Prints the hangs joined by where the kart stood (within 4 units): the middle of the spot, the
place of the lap in 256ths (car+224h) and across the road (car+22Ch), how many hangs, how long
they took (mean, longest, sum per kart race) and how they ended: "reset" = the game set the
kart back, "free" = the kart drove off by itself. For the recorder's files also the car states
(car+29Ch) and the stuck states (controller +9Ch) seen during the hangs.
--list prints every hang.
"""
import collections
import csv
import glob
import math
import os
import sys


def load(path):
    """-> {kart: [(t, x, y, z, v, lat, pathprog, cstate, stuck, thr, brk, steer)]}, computer karts only"""
    karts = collections.defaultdict(list)
    with open(path) as f:
        rd = csv.DictReader(f)
        rec = "knum" not in rd.fieldnames                     # race_recorder.py: kart index, 0 = the player
        for r in rd:
            if r["kart"] == "0":
                continue
            k = int(r["kart"] if rec else r["knum"])

            def num(name, default=0.0):
                v = r.get(name, "")
                return float(v) if v not in ("", None) else default

            karts[k].append((float(r["t"]), float(r["x"]), float(r["y"]), float(r["z"]),
                             math.hypot(float(r["vx"]), float(r["vz"])), num("lat"), num("pathprog"),
                             int(num("cstate", -1)), int(num("stuck", -1)), num("thr"), num("brk"), num("steer")))
    return karts


def hangs(rows, slow, least):
    out = []
    i, n = 0, len(rows)
    while i < n:
        if rows[i][0] < 6.0 or rows[i][4] >= slow:
            i += 1
            continue
        j = i
        end = "open"
        while j + 1 < n:
            a, b = rows[j], rows[j + 1]
            if math.dist(a[1:4], b[1:4]) > 4.0:
                end = "reset"
                break
            if b[4] > 15.0:
                end = "free"
                break
            j += 1
        k = i                                                 # the frames it really stood (below slow)
        while k < j and rows[k][4] < slow:
            k += 1
        if rows[k][0] - rows[i][0] >= least:
            seg = rows[i:j + 1]
            out.append({"t": rows[i][0], "dur": rows[j][0] - rows[i][0], "pos": rows[i][1:4], "lat": rows[i][5],
                        "place": int(rows[i][6] * 256) % 256, "end": end,
                        "cstates": collections.Counter(r[7] for r in seg), "stuck": collections.Counter(r[8] for r in seg),
                        "thr": sum(r[9] for r in seg) / len(seg), "brk": sum(r[10] for r in seg) / len(seg),
                        "moved": sum(math.dist(seg[m][1:4], seg[m + 1][1:4]) for m in range(len(seg) - 1))})
        i = j + 1
    return out


def main():
    a = sys.argv[1:]
    if not a:
        raise SystemExit(__doc__)

    def opt(name, default):
        return a[a.index(name) + 1] if name in a else default

    slow, least = float(opt("--slow", "5")), float(opt("--min", "1.0"))
    track = opt("--track", None)
    files = []
    skip = False
    for x in a:
        if skip or x.startswith("--"):
            skip = x in ("--track", "--slow", "--min")
            continue
        if os.path.isdir(x):
            files += sorted(glob.glob(os.path.join(x, "t%s_r*.csv" % (track if track is not None else "*"))))
        else:
            files.append(x)
    all_ = []
    kart_races = 0
    seconds = 0.0
    for f in files:
        for k, rows in load(f).items():
            kart_races += 1
            seconds += rows[-1][0] - rows[0][0]
            for h in hangs(rows, slow, least):
                h["file"], h["kart"] = os.path.basename(f), k
                all_.append(h)
    spots = []
    for h in sorted(all_, key=lambda h: -h["dur"]):
        for s in spots:
            if math.dist(s["pos"], h["pos"]) <= 4.0:
                s["hangs"].append(h)
                break
        else:
            spots.append({"pos": h["pos"], "hangs": [h]})
    total = sum(h["dur"] for h in all_)
    print("%d file(s), %d kart races, %.0f s driven; %d hangs, %.1f s per kart race (%.0f %% of the time)"
          % (len(files), kart_races, seconds, len(all_), total / max(1, kart_races), 100 * total / max(1.0, seconds)))
    print("spot (x, y, z)             place  across   hangs  mean s  longest  s per kart race   reset / free / open   moved   throttle")
    for s in sorted(spots, key=lambda s: -sum(h["dur"] for h in s["hangs"])):
        hs = s["hangs"]
        d = [h["dur"] for h in hs]
        x, y, z = (sum(h["pos"][i] for h in hs) / len(hs) for i in range(3))
        ends = collections.Counter(h["end"] for h in hs)
        places = sorted(h["place"] for h in hs)
        line = ("(%7.1f, %5.1f, %7.1f)   %3d    %5.2f   %4d   %5.1f   %5.1f   %6.2f            %3d / %3d / %3d   %5.1f   %4.2f"
                % (x, y, z, places[len(places) // 2], sum(h["lat"] for h in hs) / len(hs), len(hs), sum(d) / len(d), max(d),
                   sum(d) / max(1, kart_races), ends["reset"], ends["free"], ends["open"],
                   sum(h["moved"] for h in hs) / len(hs), sum(h["thr"] for h in hs) / len(hs)))
        cs = sum((h["cstates"] for h in hs), collections.Counter())
        if -1 not in cs:
            st = sum((h["stuck"] for h in hs), collections.Counter())
            n = sum(cs.values())
            line += "   car states " + " ".join("%d:%.0f%%" % (k, 100.0 * v / n) for k, v in cs.most_common(4))
            line += "   stuck " + " ".join("%d:%.0f%%" % (k, 100.0 * v / n) for k, v in sorted(st.items()))
        print(line)
    if "--list" in a:
        for h in sorted(all_, key=lambda h: (h["file"], h["kart"], h["t"])):
            print("%s kart %d t %6.1f  %5.1f s  place %3d across %5.2f  (%.1f, %.1f, %.1f)  %s  moved %.1f"
                  % (h["file"], h["kart"], h["t"], h["dur"], h["place"], h["lat"], h["pos"][0], h["pos"][1], h["pos"][2], h["end"], h["moved"]))


if __name__ == "__main__":
    main()
