r"""Many races of the tuning class over random value sets, three games side by side (sandbox).

usage: tune_sweep.py make <sets.json> <n> [--seed S] [--tracks 0-7]
       tune_sweep.py sparse <sets.json> <n> [--seed S] [--tracks 0-7]   (single rows, then 1..3 rows changed)
       tune_sweep.py run <sets.json> <out dir> [--build c5_new60.exe] [--folders game,game2,game3] [--physics60]
       tune_sweep.py show <out dir>

"make" writes n random sets (nine values each, see TUNE_ROWS in the patcher) plus the built-in
presets and the defaults on every track, each with a track. Every row keeps its default with
probability 0.35, else it takes a random value on its grid; "Gegner" is mostly 100.
"run" races every set that has no result yet in <out dir>\results.jsonl (so it can be stopped and
started again; a file "stop" in <out dir> ends it after the running races), one worker per game
folder, each a call of ai_race.py with the folder's test build. The CSV of a race is analysed and
deleted; one JSON line per race: values, track, the computer karts' mean speed, slowest kart,
seconds nearly still (all six added up, after 5 s), resets (jumps of more than 8 units in a frame),
share of frames with no wheel on the ground, top speed, runaway (as tune_races.py).
"show" prints the results sorted by stuck time.
"""
import csv
import json
import math
import os
import random
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SANDBOX = os.path.dirname(HERE)
ROOT = os.path.dirname(os.path.dirname(SANDBOX))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import patch_200cc as P   # noqa: E402

ROWS = P.TUNE_ROWS
DEFAULTS = [r[3] for r in ROWS]


def rev_limit_speed(gearing):
    return 6000.0 * (gearing / 100.0) / 143.27


def grid(row):
    lo, hi, step, _ = row
    return list(range(lo, hi + 1, step))


def make(path, n, seed, tracks):
    rnd = random.Random(seed)
    sets = []
    for t in tracks:
        for rep in range(2):
            sets.append({"id": "default-t%d-%d" % (t, rep), "v": DEFAULTS, "track": t})
    for name, vals in P.TUNE_PRESETS:
        for t in rnd.sample(tracks, 2):
            sets.append({"id": "preset-%s-t%d" % (name.replace(" ", ""), t), "v": list(vals), "track": t})
    for i in range(n):
        v = []
        for k, row in enumerate(ROWS):
            if k == 8:
                v.append(rnd.choice([100] * 5 + [0, 50, 150, 200]))
            elif rnd.random() < 0.35:
                v.append(row[3])
            else:
                v.append(rnd.choice(grid(row)))
        sets.append({"id": "r%04d" % i, "v": v, "track": rnd.choice(tracks)})
    json.dump(sets, open(path, "w"), indent=0)
    print("%d sets -> %s" % (len(sets), path))


def make_sparse(path, n, seed, tracks):
    """Single rows at several levels (two tracks each), then n sets with 1..3 rows changed,
    starting from the defaults (70 %) or a built-in preset."""
    rnd = random.Random(seed)
    sets = []
    for k, row in enumerate(ROWS):
        g = [x for x in grid(row) if x != row[3]]
        levels = sorted(set([g[0], g[-1]] + [g[int(i * (len(g) - 1) / 5)] for i in range(1, 5)]))
        for x in levels:
            v = list(DEFAULTS)
            v[k] = x
            for t in rnd.sample(tracks, 2):
                sets.append({"id": "s%d-%d-t%d" % (k, x, t), "v": v, "track": t})
    for i in range(n):
        base = list(DEFAULTS) if rnd.random() < 0.7 else list(rnd.choice(P.TUNE_PRESETS)[1])
        nch = rnd.choice([1, 2, 2, 2, 3, 3])
        for k in rnd.sample(range(9), nch):
            base[k] = rnd.choice([x for x in grid(ROWS[k]) if x != base[k]])
        sets.append({"id": "p%04d" % i, "v": base, "track": rnd.choice(tracks)})
    json.dump(sets, open(path, "w"), indent=0)
    print("%d sets -> %s" % (len(sets), path))


def analyse(path, limit):
    karts = {}
    with open(path) as f:
        for r in csv.DictReader(f):
            v = math.sqrt(float(r["vx"]) ** 2 + float(r["vy"]) ** 2 + float(r["vz"]) ** 2)
            air = all(int(r["c%d" % k]) == 0 for k in range(4))
            karts.setdefault(int(r["kart"]), []).append((float(r["t"]), float(r["x"]), float(r["y"]), float(r["z"]), v, air))
    res = {"mean": [], "stuck": 0.0, "resets": 0, "air": 0.0, "top": 0.0, "runaway": None, "ymax": -1e9}
    nair = nall = 0
    for k in sorted(karts):
        rows = karts[k]
        bad = next((q[0] for q in rows if not q[4] <= limit), None)
        if bad is not None and (res["runaway"] is None or bad < res["runaway"]):
            res["runaway"] = bad
        if not k:
            continue
        good = [q for q in rows if bad is None or q[0] < bad]
        if len(good) < 2:
            continue
        dist = 0.0
        for a, b in zip(good, good[1:]):
            d = math.sqrt((b[1] - a[1]) ** 2 + (b[2] - a[2]) ** 2 + (b[3] - a[3]) ** 2)
            if d > 8.0:
                res["resets"] += 1
            else:
                dist += math.hypot(b[1] - a[1], b[3] - a[3])
        dur = good[-1][0] - good[0][0]
        res["mean"].append(dist / dur if dur > 0 else 0.0)
        res["top"] = max(res["top"], max(q[4] for q in good))
        res["ymax"] = max(res["ymax"], max(q[2] for q in good))
        later = [q for q in good if q[0] > 5.0]
        res["stuck"] += sum(b[0] - a[0] for a, b in zip(later, later[1:]) if a[4] < 3.0)
        nair += sum(1 for q in good if q[0] > 3.0 and q[5])
        nall += sum(1 for q in good if q[0] > 3.0)
    m = res.pop("mean")
    res["mean"] = sum(m) / len(m) if m else 0.0
    res["slowest"] = min(m) if m else 0.0
    res["air"] = nair / nall if nall else 0.0
    res["dur"] = max(rows[-1][0] for rows in karts.values())
    return res


def run(sets_path, out, build, folders, physics60):
    sets = json.load(open(sets_path))
    os.makedirs(out, exist_ok=True)
    resfile = os.path.join(out, "results.jsonl")
    done = set()
    if os.path.exists(resfile):
        for line in open(resfile):
            done.add(json.loads(line)["id"])
    todo = [s for s in sets if s["id"] not in done]
    lock = threading.Lock()
    print("%d sets, %d to run, folders %s" % (len(sets), len(todo), ",".join(folders)), flush=True)
    t_start = time.time()
    count = [0]

    def worker(folder):
        env = dict(os.environ, MHK2_GAME=folder)
        exe = os.path.join(SANDBOX, folder, build)
        while True:
            with lock:
                if not todo or os.path.exists(os.path.join(out, "stop")):
                    return
                s = todo.pop(0)
            csvp = os.path.join(out, "race_%s.csv" % folder)
            if os.path.exists(csvp):
                os.remove(csvp)
            limit = max(100.0, 1.5 * rev_limit_speed(s["v"][0]))
            r = subprocess.run([sys.executable, os.path.join(HERE, "ai_race.py"), exe, csvp, "--seconds", "45",
                                "--cls", "5", "--track", str(s["track"]), "--tune", ",".join(map(str, s["v"])),
                                "--stop-above", "%.0f" % limit] + (["--physics60"] if physics60 else []),
                               cwd=SANDBOX, env=env, capture_output=True, text=True)
            rec = {"id": s["id"], "v": s["v"], "track": s["track"]}
            if os.path.exists(csvp):
                try:
                    rec.update(analyse(csvp, limit))
                except Exception as e:      # noqa: BLE001
                    rec["error"] = repr(e)
                os.remove(csvp)
            else:
                rec["error"] = (r.stdout + r.stderr).strip()[-200:]
            with lock:
                with open(resfile, "a") as f:
                    f.write(json.dumps(rec) + "\n")
                count[0] += 1
                el = time.time() - t_start
                left = len(todo)
                print("%s %-6s %-22s %s t%d: %s | %.0f min, ~%.0f min left" % (
                    time.strftime("%H:%M:%S"), folder, s["id"], s["v"], s["track"],
                    "ERROR" if "error" in rec else "mean %.1f still %.1f resets %d air %.2f" % (
                        rec["mean"], rec["stuck"], rec["resets"], rec["air"]),
                    el / 60, el / count[0] * left / len(folders) * len(folders) / 60 / 1), flush=True)

    threads = [threading.Thread(target=worker, args=(f,)) for f in folders]
    for th in threads:
        th.start()
        time.sleep(1.0)
    for th in threads:
        th.join()


def show(out):
    recs = [json.loads(line) for line in open(os.path.join(out, "results.jsonl"))]
    recs = [r for r in recs if "error" not in r]
    recs.sort(key=lambda r: r["stuck"])
    for r in recs:
        print("%-22s %-48s t%d mean %5.1f slow %5.1f still %5.1f resets %3d air %.2f top %5.1f%s" % (
            r["id"], r["v"], r["track"], r["mean"], r["slowest"], r["stuck"], r["resets"], r["air"], r["top"],
            " RUNAWAY" if r["runaway"] is not None else ""))


def main():
    a = sys.argv[1:]

    def opt(name, default):
        if name in a:
            i = a.index(name)
            v = a[i + 1]
            del a[i:i + 2]
            return v
        return default
    if a[0] == "make":
        seed = int(opt("--seed", "1"))
        lo, hi = map(int, opt("--tracks", "0-7").split("-"))
        make(a[1], int(a[2]), seed, list(range(lo, hi + 1)))
    elif a[0] == "sparse":
        seed = int(opt("--seed", "2"))
        lo, hi = map(int, opt("--tracks", "0-7").split("-"))
        make_sparse(a[1], int(a[2]), seed, list(range(lo, hi + 1)))
    elif a[0] == "run":
        build = opt("--build", "c5_new60.exe")
        folders = opt("--folders", "game,game2,game3").split(",")
        phys = "--physics60" in a
        run(a[1], a[2], build, folders, phys)
    elif a[0] == "show":
        show(a[1])


if __name__ == "__main__":
    main()
