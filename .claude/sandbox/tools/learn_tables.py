r"""Speed and line tables for the computer karts, learned from the player's recorded laps.

usage: learn_tables.py [recording.csv ...] [--show TRACK] [--no-adjust]

Recordings are race_recorder.py files of time trials; without arguments every
runs\user\*_c4_t<track>.csv (250 cc) is used. Writes geo_tables.inc next to geo_driver.asm:
per track 0..7 256 places along the lap (the game's progress, car+224h), two bytes each:
  speed  2 * whole units/s (2..254), + 1 where the learned speed overrules a speed limit box of
         the game (geo_free.json next to this file: per track the stretches [first place, last
         place]; geo_boxes.py finds the boxes and what they cost); 0 = no data here
  line   1 + 63.5 * (lateral + 1.5) (1..255; lateral 0..1 across the road as the path planner
         counts it, 0.5 = middle, -1.5..2.5 fit), 0 = no data
Per place the middle one of the clean passes by speed (of two the faster), then smoothed over
the neighbouring places (1 2 1). Left out: the first 6 s (standing start), 3 s
around a reset, the time from 0.5 s before a hit (speed loss > 12 units/s in 0.1 s, unless the
kart was falling faster than 12 units/s just before: a landing) until the
speed is back, and of every pass the places where it is off the road (a shortcut: more than EDGE
units beyond the edge) with MARGIN places before and after. Small skips within EDGE stay in the
line (the driver keeps it within -LC..1 + LC, inside the game's off-track limit); up to GAP places that no pass touched (a skip makes the progress jump) are filled in
between their neighbours. Several recordings of a track are merged, so laps that stay on the road fill the places
that shortcut laps leave empty. Places with speed data but no pass on the road keep 0.
The place is the recording's `pathprog` (car+224h); older recordings only have `prog`
(car+220h), which on Sumpf is half a lap ahead of it (SHIFT).
geo_adjust.json (written by table_repair.py, the search that races changes of the tables at the
places where the computer karts get into trouble) is applied on top, unless --no-adjust is given: per track and place a factor for the
speed and a shift for the line.
The lateral position is estimated from the centre line of track_line.py (a recording with a
`lat` column, the game's own car+22Ch, is used directly).
"""
import collections
import csv
import glob
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SANDBOX = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from track_line import Line  # noqa: E402

BINS = 256
TRACKS = 8
OUT = os.path.join(HERE, "geo_tables.inc")
ADJUST = os.path.join(HERE, "geo_adjust.json")
FREE = os.path.join(HERE, "geo_free.json")
SHIFT = {7: 0.5}                 # laps + progress (car+220h) minus the path progress (car+224h), measured 2026-11-24
EDGE = 16.0                      # units beyond the road edge that still count as on the road (small skips).
                                 # 22 took in the Bergwerk start cut (lateral 2.2..2.7): outside lateral -1..2 the
                                 # game sets a computer kart back on the track (car+24Ch), 13..16 times per race.
                                 # The lateral itself is no good as the rule: where the road edges pinch (Burg
                                 # 0.10..0.12, width under 2) it reaches 5 with the kart 1 unit from the centre.
GAP = 5                          # places without any pass between two with data are filled in up to this many
MARGIN = 8                       # a pass that leaves the road is left out this many places before and after
LAT_MIN, LAT_MAX = -1.5, 2.5     # what a line byte can hold (0..1 = edge to edge); the driver clamps (LC)


def passes(path, ln, track):
    """-> list of (bin, speed, lateral or None when off the road) of the clean frames"""
    rows = []
    with open(path) as f:
        for r in csv.DictReader(f):
            if r["kart"] == "0":
                rows.append(r)
    T = [float(r["t"]) for r in rows]
    X = [float(r["x"]) for r in rows]
    Z = [float(r["z"]) for r in rows]
    V = [math.sqrt(float(r["vx"]) ** 2 + float(r["vy"]) ** 2 + float(r["vz"]) ** 2) for r in rows]
    VY = [float(r["vy"]) for r in rows]
    bad = [t < 6.0 for t in T]

    def mark(t0, t1):
        for i, t in enumerate(T):
            if t0 <= t <= t1:
                bad[i] = True

    j = 0
    i = 1
    while i < len(rows):
        if math.hypot(X[i] - X[i - 1], Z[i] - Z[i - 1]) > 4:
            mark(T[i] - 3.0, T[i] + 3.0)
        while T[i] - T[j] > 0.1:
            j += 1
        if V[j] - V[i] > 12 and not bad[i] and min(VY[max(0, j - 30):i + 1]) > -12:   # not a landing after a drop
            before = V[j]
            k = i
            while k < len(rows) - 1 and V[k] < 0.9 * before and T[k] - T[i] < 6:
                k += 1
            mark(T[i] - 0.5, T[k])
        i += 1
    out = []
    has_lat = "lat" in rows[0]
    for i in range(0, len(rows), 4):
        if bad[i]:
            continue
        idx, d = ln.nearest(X[i], Z[i])
        w = max(ln.width[idx], 4.0)
        a, b = ln.pts[idx - 1], ln.pts[(idx + 1) % ln.n]
        ux, uz = b[0] - a[0], b[2] - a[2]
        off = ((X[i] - ln.pts[idx][0]) * -uz + (Z[i] - ln.pts[idx][2]) * ux) / math.hypot(ux, uz)
        lat = float(rows[i]["lat"]) if has_lat and rows[i]["lat"] else 0.5 - off / w
        on_road = d <= w / 2 + EDGE
        place = float(rows[i]["pathprog"]) if rows[i].get("pathprog") else float(rows[i]["prog"]) - SHIFT.get(track, 0.0)
        out.append((int((place % 1.0) * BINS) % BINS, V[i], lat if on_road else None, int(math.floor(float(rows[i]["prog"])))))
    return out


def table(track, paths):
    ln = Line(track)
    per = collections.defaultdict(lambda: collections.defaultdict(list))   # bin -> pass id -> frames
    for pi, path in enumerate(paths):
        for b, v, lat, lap in passes(path, ln, track):
            per[b][(pi, lap)].append((v, lat))
    speed, line, npass = [0.0] * BINS, [None] * BINS, [0] * BINS
    off = [False] * BINS
    left = collections.defaultdict(set)                     # pass -> places where it is off the road
    for b in range(BINS):
        for pid, frames in per[b].items():
            if any(l is None for _, l in frames):
                left[pid].add(b)
    for b in range(BINS):
        vs, ls, offs = [], [], 0
        for pid, frames in per[b].items():
            if any((b + k) % BINS in left[pid] for k in range(-MARGIN, MARGIN + 1)):
                offs += 1                                   # this pass takes a shortcut here or close by
                continue
            vs.append(sum(v for v, _ in frames) / len(frames))
            ls.append(sum(l for _, l in frames) / len(frames))
        npass[b] = len(vs)
        if vs:
            k = sorted(range(len(vs)), key=lambda i: vs[i])[len(vs) // 2]   # the middle pass, of two the faster
            speed[b], line[b] = vs[k], ls[k]
        elif offs:
            off[b] = True
    b = 0                                                   # short gaps (a skip makes the progress jump): filled in
    while b < BINS:
        if speed[b] or off[b]:
            b += 1
            continue
        e = b
        while e < BINS and not speed[e] and not off[e]:
            e += 1
        lo, hi = (b - 1) % BINS, e % BINS
        if e - b <= GAP and speed[lo] and speed[hi]:
            for k in range(b, e):
                f = (k - b + 1) / (e - b + 1)
                speed[k] = speed[lo] + (speed[hi] - speed[lo]) * f
                line[k] = line[lo] + (line[hi] - line[lo]) * f
        b = e
    for vals in (speed, line):                              # smoothed over the neighbours with data (1 2 1)
        src = list(vals)
        for b in range(BINS):
            if src[b] is None or (vals is speed and not src[b]):
                continue
            acc, wsum = 2.0 * src[b], 2.0
            for k in (-1, 1):
                o = src[(b + k) % BINS]
                if o is not None and (vals is line or o):
                    acc, wsum = acc + o, wsum + 1.0
            vals[b] = acc / wsum
    return speed, line, npass, off


def encode(speed, line, free=()):
    out = bytearray()
    for b, (v, l) in enumerate(zip(speed, line)):
        out.append(0 if not v else 2 * max(1, min(127, int(round(v)))) + (1 if b in free else 0))
        out.append(0 if l is None or not v else max(1, min(255, 1 + int(round(63.5 * (max(LAT_MIN, min(LAT_MAX, l)) + 1.5))))))
    return bytes(out)


def main():
    a = sys.argv[1:]
    show = int(a[a.index("--show") + 1]) if "--show" in a else None
    files = [x for i, x in enumerate(a) if not x.startswith("--") and (i == 0 or a[i - 1] != "--show")]
    if not files:
        files = sorted(glob.glob(os.path.join(SANDBOX, "runs", "user", "*_c4_t?.csv")))
    by_track = collections.defaultdict(list)
    for f in files:
        meta = json.load(open(f[:-4] + ".json"))
        if meta.get("mode") == 0 and meta.get("karts", 9) <= 2:
            by_track[meta["track"]].append(f)
    adjust = json.load(open(ADJUST)) if os.path.exists(ADJUST) and "--no-adjust" not in a else {}
    free_all = json.load(open(FREE)) if os.path.exists(FREE) else {}
    blobs = []
    for t in range(TRACKS):
        if not by_track.get(t):
            blobs.append(bytes(2 * BINS))
            continue
        speed, line, npass, off = table(t, by_track[t])
        changes = 0
        if str(t) in adjust:
            adj = adjust[str(t)]
            speed = [v * f for v, f in zip(speed, adj["speed"])]
            line = [None if l is None else l + d for l, d in zip(line, adj["line"])]
            changes = len(adj.get("changes", []))
        free = set(b % BINS for lo, hi in free_all.get(str(t), []) for b in range(lo, hi + 1))
        blobs.append(encode(speed, line, free))
        if free:
            print("track %d: %d places overrule a speed limit box" % (t, len(free)))
        have = [v for v in speed if v]
        runs_off = sum(1 for b in range(BINS) if off[b] and not off[b - 1])
        if changes:
            print("track %d: %d change(s) of geo_adjust.json applied" % (t, changes))
        print("track %d: %d recording(s), %d of %d places with data (speed %.0f..%.0f, mean %.1f), %d stretch(es) without a pass on the road, %d places with one pass only"
              % (t, len(by_track[t]), len(have), BINS, min(have), max(have), sum(have) / len(have), runs_off, sum(1 for n in npass if n == 1)))
        if show == t:
            for b in range(BINS):
                print("   %.3f  %s  %s  passes %d%s" % (b / BINS, "%5.1f" % speed[b] if speed[b] else "  -  ",
                                                      "%5.2f" % line[b] if line[b] is not None else "  -  ", npass[b], "  off road" if off[b] else ""))
    with open(OUT, "w", newline="\n") as f:
        f.write("; generated by learn_tables.py from the player's recorded laps; do not edit by hand\n")
        f.write("; %d tracks * %d places * (speed, line)\n" % (TRACKS, BINS))
        for t, blob in enumerate(blobs):
            f.write("; track %d\n" % t)
            for k in range(0, len(blob), 32):
                f.write("    db  " + ", ".join("%d" % x for x in blob[k:k + 32]) + "\n")
    print("wrote %s" % OUT)


if __name__ == "__main__":
    main()
