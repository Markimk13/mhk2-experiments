"""The player's challenge runs in race_recorder.py recordings against their medal times (sandbox).

usage: challenge_runs.py [recording dir, default runs\\user] [--since YYYYMMDD_HHMMSS]

Per recording with a "challenge" block (race_recorder.py since 2026-11-28): the draw (track, metres,
set, character), the player's time over the stretch (kart 0's path progress, unwrapped, until it
covers the challenge's length; the race clock t starts at "go"), whether the power can was fired
(held power-up 7 -> -1), the medal times and what the run won, and the average speed as a share of
the top speed the page shows (top_kmh of the set and the driver). A run that did not reach the
finish (restart, abort) shows its covered share instead of a time.
Then per seed the best run, and the ratios best / gold, best / computer karts' time, and the medal
times of the patcher as it is now.
"""
import csv
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "tools"))
import patch_200cc as P

SETS = P.challenge_sets()
P.challenge_sets = lambda: SETS          # challenge_medals draws the sets again on every call


def run_of(csv_path, length):
    """(time or None, covered share, can fired, max speed in units/s) of kart 0."""
    last = cum = None
    t_end, fired, held, vmax = None, False, None, 0.0
    tail = []                    # (t, cum) of the last frames
    with open(csv_path, newline="") as f:
        for r in csv.DictReader(f):
            if r["kart"] != "0":
                continue
            p, t = float(r["pathprog"]), float(r["t"])
            item = int(r["item"]) if r["item"] not in ("", None) else None
            if held == 7 and item == -1:
                fired = True
            held = item
            v = (float(r["vx"]) ** 2 + float(r["vz"]) ** 2) ** 0.5
            vmax = max(vmax, v)
            if last is None:
                last, cum = p, 0.0
                continue
            d = p - last
            d -= round(d)
            cum += d
            last = p
            tail = (tail + [(t, cum)])[-10:]
            if t_end is None and cum >= length:
                t_end = t
    # the recorder stops with the race: the last frame is often a hair short of the finish
    if t_end is None and cum >= length * 0.99 and len(tail) >= 2 and tail[-1][1] > tail[0][1]:
        (t0, c0), (t1, c1) = tail[0], tail[-1]
        t_end = t1 + (length - c1) * (t1 - t0) / (c1 - c0)
    return t_end, cum, fired, vmax


def main():
    args = sys.argv[1:]
    since = None
    if "--since" in args:
        i = args.index("--since"); since = args[i + 1]; del args[i:i + 2]
    folder = args[0] if args else os.path.join(HERE, "..", "runs", "user")
    rows = []
    for js in sorted(glob.glob(os.path.join(folder, "2*.json"))):
        name = os.path.basename(js)[:15]
        if since and name < since:
            continue
        m = json.load(open(js, encoding="utf-8"))
        ch = m.get("challenge")
        if not ch:
            continue
        seed = ch["seed"]
        track, start, share, char, values = P.challenge_draw(seed)
        s = P._draw_set(seed)
        metres = share * P.CH_PATHS[track]
        top = P.top_kmh(values, char)
        t, cov, fired, vmax = run_of(js[:-5] + ".csv", ch["length"])
        medals = ch["medals"]
        won = None if t is None else next((n for n, x in zip(("gold", "silver", "bronze"), medals) if t <= x), "none")
        rows.append((name, seed, track, metres, s, char, top, t, cov / ch["length"], fired, vmax * 3.6, medals, won))
    print("%-15s %10s %2s %5s %3s %2s %4s %7s %4s %5s %5s  %-23s %s" % (
        "recording", "seed", "tr", "m", "set", "ch", "top", "time", "can", "avg%", "vmax", "gold / silver / bronze", "won"))
    best = {}
    for name, seed, track, metres, s, char, top, t, cov, fired, vmax, medals, won in rows:
        if t is None:
            tt, avg = "%5.0f%%" % (100 * cov), ""
        else:
            tt, avg = "%7.2f" % t, "%4.0f%%" % (100 * metres / t / (top / 3.6))
            if seed not in best or t < best[seed][0]:
                best[seed] = (t, fired, track, metres, s, top, medals)
        print("%-15s %10d %2d %5.0f %3d %2d %4d %7s %4s %5s %5.0f  %-23s %s" % (
            name, seed, track, metres, s, char, top, tt, "yes" if fired else "", avg, vmax,
            " / ".join("%.2f" % x for x in medals), won or ""))
    # the computer karts' time: the silver time without its factors (the recording's medals may
    # be of an older build; this uses the patcher's tables now)
    ai_ref = {}
    for seed in best:
        ai_ref[seed] = P.challenge_medals(seed)[1] / (P.CH_MEDAL_FACTORS[1])
    print()
    print("best per seed: time / gold, time / silver, avg speed / top speed, the computer karts' share")
    for seed, (t, fired, track, metres, s, top, medals) in best.items():
        print("%10d track %d %5.0f m set %2d top %3d: %6.2f s (%s) gold x%.2f silver x%.2f avg %3.0f km/h = %3.0f %% "
              "of top, computer karts %5.2f s (you x%.2f), now gold / silver / bronze %s" % (
            seed, track, metres, s, top, t, "can" if fired else "no can", t / medals[0], t / medals[1],
            metres / t * 3.6, 100 * metres / t / (top / 3.6), ai_ref[seed], t / ai_ref[seed],
            " / ".join("%.2f" % x for x in P.challenge_medals(seed))))


if __name__ == "__main__":
    main()
