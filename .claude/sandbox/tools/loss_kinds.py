"""Sudden speed losses sorted by kind and by the ground under the wheels (issue #32).

usage: loss_kinds.py <recording.csv> [...] [--kart N] [--min 45] [--drop 0.25] [--window 0.15] [--list]

Reads race_recorder.py recordings (the player's own races; needs the surf / c columns, recorder
of 2026-11-27 or later) and ai_race.py recordings (with cstate). Default: kart 0 for a
race_recorder.py file (the player), the computer karts (1..6) for an ai_race.py file.

A loss: the speed falls by --drop (share) or more within --window seconds, from above --min
units/s, without the brake (only computer karts have a brake column). Each loss gets
"<event>/<where>": the event is the first of the game's own reaction animations (car+29Ch) within
0.3 s: crash, scratch, drop, respawn, landing, anim22, anim23, or "-" for none; where is "air" (no
wheel down right before), "edge" (lat below 0.2 or above 0.8) or "middle".
"middle" is where an invisible obstacle would show. Ground: wood if a wheel stood on the track's
wood material in the window, else the material of the wheels (names known for Insel; other
tracks print the index and the resistance from the race's .json).
"""
import argparse
import collections
import csv
import json
import math
import os

# car+29Ch is the character's animation (fn 0x42D6C0 picks it): 12 / 13 steering, 15 drop (wheels on
# the drop geometry, CAL_drop), 16..19 crash in direction 0..3 and 21 scratch (the collision message
# at 0x4322A5: velocity change in the kart's frame above 10 / 5 / 7 / 5 units/s, scratch above 75 %
# of it; CAL_crash / CAL_scratch), 20 respawn, 7 jump landing, 22 / 23 chosen in a loop over the other
# karts (not traced). Which animation a power-up hit plays was not traced.
EVENT = {15: "drop", 16: "crash", 17: "crash", 18: "crash", 19: "crash", 20: "respawn", 21: "scratch",
         22: "anim22", 23: "anim23", 7: "landing"}
NAMES = {2: ["beton", "sand", "sandstrasse", "gras", "holz", "sandstrasse grip", "seite"]}   # track index 2 = Insel


def ground_name(track, surfs, table):
    names = NAMES.get(track)
    s = sorted(x for x in surfs if x >= 0)
    if not s:
        return "none"
    if names:
        if names.index("holz") in s:
            return "holz"
        return "+".join(names[x] if x < len(names) else str(x) for x in s)
    return "+".join("%d(r%.2f)" % (x, table[x][2]) if table and x < len(table) and table[x] else str(x) for x in s)


def speed(r):
    return math.sqrt(r["vx"] ** 2 + r["vy"] ** 2 + r["vz"] ** 2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--kart", type=int, default=None)
    ap.add_argument("--min", type=float, default=45)
    ap.add_argument("--drop", type=float, default=0.25)
    ap.add_argument("--window", type=float, default=0.15)
    ap.add_argument("--list", action="store_true", help="print every loss")
    a = ap.parse_args()
    tim = collections.Counter()
    kinds = collections.defaultdict(collections.Counter)
    events = []
    for path in a.files:
        meta = {}
        js = os.path.splitext(path)[0] + ".json"
        if os.path.exists(js):
            meta = json.load(open(js))
        track = meta.get("track", 2 if "i32" in path else None)
        table = meta.get("surfaces")
        karts = collections.defaultdict(list)
        with open(path) as f:
            rd = csv.DictReader(f)
            recorder = "item" in rd.fieldnames
            if "surf0" not in rd.fieldnames:
                print("%s: no surf columns (recorded before 2026-11-27), skipped" % path)
                continue
            for r in rd:
                row = {}
                for k, v in r.items():
                    try:
                        row[k] = float(v) if v != "" else 0.0
                    except ValueError:
                        row[k] = 0.0
                karts[int(row["kart"])].append(row)
        want = [a.kart] if a.kart is not None else ([0] if recorder else [k for k in karts if k != 0])
        for kn in want:
            rows = karts.get(kn, [])
            sp = [speed(r) for r in rows]
            for i in range(1, len(rows)):
                if sp[i] > a.min and rows[i]["t"] > rows[i - 1]["t"]:
                    tim[ground_name(track, {int(rows[i]["surf%d" % k]) for k in range(4)}, table)] += rows[i]["t"] - rows[i - 1]["t"]
            i = 0
            while i < len(rows):
                hit = None
                if sp[i] > a.min:
                    j = i + 1
                    while j < len(rows) and rows[j]["t"] - rows[i]["t"] <= a.window:
                        if sp[j] < (1 - a.drop) * sp[i] and max(r.get("brk", 0) for r in rows[i:j + 1]) < 0.1:
                            hit = j
                            break
                        j += 1
                if hit is None:
                    i += 1
                    continue
                r = rows[i]
                t_end = rows[hit]["t"] + 0.3
                anims = [int(x["cstate"]) for x in rows[i:] if x["t"] <= t_end and int(x["cstate"]) in EVENT]
                surfs = {int(rows[k]["surf%d" % w]) for k in range(max(0, i - 3), hit + 1) for w in range(4)}
                g = ground_name(track, surfs, table)
                event = EVENT[anims[0]] if anims else "-"
                if not any(r["c%d" % k] for k in range(4)):
                    where = "air"
                elif not 0.2 < r["lat"] < 0.8:
                    where = "edge"
                else:
                    where = "middle"
                kind = "%s/%s" % (event, where)
                kinds[g][kind] += 1
                events.append((os.path.basename(path), kn, r["t"], sp[i], sp[hit], r["x"], r["y"], r["z"], r["lat"], g, kind))
                while i < len(rows) and rows[i]["t"] <= t_end:
                    i += 1
    print("ground: seconds above %g units/s, losses by kind, per 10 s" % a.min)
    for g in sorted(set(tim) | set(kinds), key=lambda g: -tim[g]):
        k = kinds[g]
        print("  %-22s %7.1f s  %s" % (g, tim[g], "  ".join("%s %d (%.2f)" % (n, k[n], 10 * k[n] / tim[g] if tim[g] else 0)
                                                           for n in sorted(k))))
    if a.list:
        print("file                          kart       t   from ->   to      x      y      z   lat  ground      kind")
        for e in events:
            print("%-28s %4d %7.2f %6.1f -> %5.1f %6.1f %6.1f %6.1f %5.2f  %-11s %s" % e)


if __name__ == "__main__":
    main()
