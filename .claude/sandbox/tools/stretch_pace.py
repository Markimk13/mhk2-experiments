"""Pace of the challenge tuning sets: when do computer karts pass each 1/64 of a lap? (sandbox)

usage: stretch_pace.py <out dir> [--seconds 75] [--folders game,game2,game3] [--sets 0-63]
                       [--tracks 0,1,..] [--keep-csv]
--seconds auto: 100 s per lap of track 0's length (at least 75 s), so long tracks get one
flying lap too.

For the medals of the challenges (issue #35). Each run is a championship race in the tuning
class with one set of challenge_sets() on one track: the six computer karts drive the learned
way (*Verbesserte Gegner* 6) at full throttle (*Tempo* 100 %), 60 FPS physics, no cans. The
player's kart stands on the grid with character (set + track) % 7, so every character drives
in 6 of 7 runs. ai_race.py records the race; this tool reduces each kart to
the race times at which its progress (car+224h, unwrapped, counted from the grid) first passes
each multiple of 1/64 lap, and deletes the big CSV.

Output: <out dir>/pace_s<set>_t<track>.json with
  {"set", "track", "values", "player_char",
   "karts": [{"kart", "char", "p0", "t_move", "cross": [[k, t], ...]}]}
k counts 1/64 laps over the lap's own grid (k = floor(p * 64) + 1 for the first point ahead of
the start p0); t is the race clock (car manager +20h). t_move is the first time the kart moves.
Runs that exist are skipped, so the tool can continue an interrupted batch.
"""
import csv
import json
import math
import os
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
SANDBOX = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(SANDBOX)), "tools"))
import patch_200cc as P

N = 64


def opt(args, name, default):
    if name in args:
        i = args.index(name)
        value = args[i + 1]
        del args[i:i + 2]
        return value
    return default


def parse_range(text):
    out = []
    for part in text.split(","):
        if "-" in part:
            a, b = part.split("-")
            out += list(range(int(a), int(b) + 1))
        else:
            out.append(int(part))
    return out


def reduce_csv(path):
    karts = {}
    with open(path) as f:
        for r in csv.DictReader(f):
            k = int(r["kart"])
            if not k:
                continue
            karts.setdefault(k, []).append((float(r["t"]), float(r["pathprog"]),
                                            math.sqrt(float(r["vx"]) ** 2 + float(r["vz"]) ** 2)))
    out = []
    for k in sorted(karts):
        rows = karts[k]
        p0 = rows[0][1]
        t_move = next((t for t, _, v in rows if v > 0.5), None)
        cum, last, best = 0.0, p0, 0.0
        nxt = math.floor(p0 * N) + 1           # the next grid point, in 1/64 laps from progress 0
        cross = []
        for t, p, _ in rows:
            d = p - last
            d -= round(d)                      # wrapped into -0.5..0.5
            cum += d
            last = p
            if cum > best:
                best = cum
                while p0 + best >= nxt / N:
                    cross.append([nxt, round(t, 4)])
                    nxt += 1
        out.append({"kart": k, "p0": round(p0, 6), "t_move": t_move, "cross": cross})
    return out


def run_one(exe, out, s, track, values, seconds, keep):
    name = os.path.join(out, "pace_s%02d_t%d" % (s, track))
    if os.path.exists(name + ".json"):
        return "s%02d t%d: exists" % (s, track)
    csv_path = name + ".csv"
    r = subprocess.run([sys.executable, os.path.join(HERE, "ai_race.py"), exe, csv_path, "--seconds", str(seconds),
                        "--mode", "1", "--cls", "5", "--track", str(track),
                        "--tune", ",".join(str(v) for v in values), "--tempo", "100", "--improved", "6",
                        "--physics60", "--char", str((s + track) % 7)], capture_output=True, text=True)
    if not os.path.exists(csv_path):
        return "s%02d t%d: NO DATA %s" % (s, track, (r.stdout + r.stderr).strip()[-200:])
    karts = reduce_csv(csv_path)
    chars = next((l.split(":")[1].split() for l in r.stdout.splitlines() if l.startswith("characters:")), None)
    for k in karts:
        k["char"] = int(chars[k["kart"]]) if chars else None
    json.dump({"set": s, "track": track, "values": list(values), "player_char": int(chars[0]) if chars else None,
               "karts": karts}, open(name + ".json", "w"))
    if not keep:
        os.remove(csv_path)
    laps = [(k["cross"][-1][0] - k["cross"][0][0]) / N if k["cross"] else 0 for k in karts]
    return "s%02d t%d: laps %s" % (s, track, " ".join("%.2f" % x for x in laps))


def main():
    args = sys.argv[1:]
    seconds = opt(args, "--seconds", "75")
    folders = opt(args, "--folders", "game,game2,game3").split(",")
    sets = parse_range(opt(args, "--sets", "0-63"))
    tracks = parse_range(opt(args, "--tracks", "0-7"))
    keep = "--keep-csv" in args
    if keep:
        args.remove("--keep-csv")
    out = os.path.abspath(args[0])
    os.makedirs(out, exist_ok=True)
    all_sets = P.challenge_sets()
    queue = [(s, t) for t in tracks for s in sets]
    lock = threading.Lock()
    log = open(os.path.join(out, "pace.log"), "a", encoding="utf-8")

    def worker(folder):
        exe = os.path.join(SANDBOX, folder, "c5_new60.exe")
        while True:
            with lock:
                if not queue:
                    return
                s, t = queue.pop(0)
            sec = max(75, round(P.CH_PATHS[t] / P.CH_PATHS[0] * 100)) if seconds == "auto" else float(seconds)
            line = run_one(exe, out, s, t, all_sets[s], sec, keep)
            with lock:
                print(line, flush=True)
                log.write(line + "\n")
                log.flush()

    threads = [threading.Thread(target=worker, args=(f,)) for f in folders]
    for th in threads:
        th.start()
    for th in threads:
        th.join()


if __name__ == "__main__":
    main()
