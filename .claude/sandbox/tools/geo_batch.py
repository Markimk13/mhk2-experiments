r"""Race candidate value sets of the geometric driver against each other (sandbox, three games).

usage: geo_batch.py <out dir> <plan.json> [--games 3] [--report-only]

plan.json:
  {"exe": "geo60.exe", "cls": 4, "seconds": 60, "tracks": [0, 3], "rotations": 6,
   "common": {"kc": 1.6},                       # optional, for every candidate
   "candidates": {"stock": {"on": 0}, "base": {}, "kc14": {"kc": 1.4}, ...}}   # six at most

Each race has six computer karts (kart numbers 1..6); in rotation r kart n drives candidate
(n - 1 + r) mod 6, so over six rotations every candidate starts from every grid slot once.
With fewer than six candidates the list is repeated. Races go into <out>\t<track>_r<r>.csv
(skipped when present, so a batch can be resumed) with a .json of who drove which kart.
The report: per candidate and track the mean laps + progress at the end, resets, seconds
nearly still, braking share; the mean also gives the resets while moving, then the mean over the tracks and the gain against "stock" (the mean of the
per-track ratios, so every track counts the same).
"""
import json
import os
import queue
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
SANDBOX = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import geo_summary  # noqa: E402


def races(plan):
    names = list(plan["candidates"])
    slots = [names[i % len(names)] for i in range(6)]
    out = []
    for track in plan["tracks"]:
        for r in range(plan.get("rotations", 6)):
            who = {n: slots[(n - 1 + r) % 6] for n in range(1, 7)}
            out.append(("t%d_r%d" % (track, r), track, who))
    return out


def args_for(plan, track, who):
    a = ["--seconds", str(plan.get("seconds", 60)), "--cls", str(plan.get("cls", 4)), "--track", str(track),
         "--geo-on", ",".join(["1"] * 6)]
    if plan.get("tune"):
        a += ["--tune", plan["tune"]]
    if plan.get("physics60"):
        a.append("--physics60")
    common = dict(plan.get("common", {}))
    for n, name in who.items():
        vals = dict(common)
        vals.update(plan["candidates"][name])
        vals.setdefault("on", 1)
        a += ["--geo-kart", "%d:%s" % (n, ",".join("%s=%s" % kv for kv in vals.items()))]
    return a


def run(out, plan, games):
    q = queue.Queue()
    for name, track, who in races(plan):
        if not os.path.exists(os.path.join(out, name + ".csv")):
            q.put((name, track, who))
    total = q.qsize()
    lock = threading.Lock()
    done = [0]

    def worker(folder):
        exe = os.path.join(SANDBOX, folder, plan.get("exe", "geo60.exe"))
        while True:
            try:
                name, track, who = q.get_nowait()
            except queue.Empty:
                return
            csv_path = os.path.join(out, name + ".csv")
            for attempt in range(2):
                r = subprocess.run([sys.executable, os.path.join(HERE, "ai_race.py"), exe, csv_path + ".part"] + args_for(plan, track, who),
                                   capture_output=True, text=True)
                if r.returncode == 0 and os.path.exists(csv_path + ".part"):
                    os.replace(csv_path + ".part", csv_path)
                    json.dump(who, open(os.path.join(out, name + ".json"), "w"))
                    break
            with lock:
                done[0] += 1
                print("%d/%d %s %s" % (done[0], total, name, "ok" if os.path.exists(csv_path) else "FAILED: " + (r.stdout + r.stderr)[-300:]), flush=True)

    folders = ["game", "game2", "game3"][:games]
    th = [threading.Thread(target=worker, args=(f,)) for f in folders]
    for t in th:
        t.start()
    for t in th:
        t.join()


def report(out, plan):
    keys = ("prog", "resets", "moving", "still", "brk")
    per = {}                                   # (candidate, track) -> list of dicts
    for name, track, who in races(plan):
        path = os.path.join(out, name + ".csv")
        if not os.path.exists(path):
            continue
        s = geo_summary.summary(path)
        for n, cand in who.items():
            if n in s:
                per.setdefault((cand, track), []).append(s[n])
    tracks = plan["tracks"]
    print("%-14s" % "candidate" + "".join("   track %-18d" % t for t in tracks) + "   mean (laps, resets, moving, still)")
    rows = {}
    for cand in plan["candidates"]:
        line = "%-14s" % cand
        means = []
        for t in tracks:
            lst = per.get((cand, t), [])
            if not lst:
                line += "   %-24s" % "-"
                continue
            m = {k: sum(d[k] for d in lst) / len(lst) for k in keys}
            means.append(m)
            line += "   %.3f %4.1f %5.1f %3.0f%%  " % (m["prog"], m["resets"], m["still"], 100 * m["brk"])
        if means:
            mm = {k: sum(m[k] for m in means) / len(means) for k in keys}
            rows[cand] = mm
            line += "   %.3f %4.2f %4.2f %5.1f" % (mm["prog"], mm["resets"], mm["moving"], mm["still"])
        print(line)
    if "stock" in rows:                        # mean of the per-track ratios: every track counts the same
        def prog(c, t):
            lst = per.get((c, t), [])
            return sum(d["prog"] for d in lst) / len(lst) if lst else None
        gains = []
        for c in rows:
            if c == "stock":
                continue
            r = [prog(c, t) / prog("stock", t) for t in tracks if prog(c, t) and prog("stock", t)]
            gains.append("%s %+.1f %%" % (c, 100 * (sum(r) / len(r) - 1)))
        print("progress against stock (mean of the tracks' ratios): " + ", ".join(gains))


def main():
    a = sys.argv[1:]
    games = 3
    if "--games" in a:
        i = a.index("--games")
        games = int(a[i + 1])
        del a[i:i + 2]
    only = "--report-only" in a
    a = [x for x in a if x != "--report-only"]
    out, plan_path = a[0], a[1]
    plan = json.load(open(plan_path))
    os.makedirs(out, exist_ok=True)
    if not only:
        run(out, plan, games)
    report(out, plan)


if __name__ == "__main__":
    main()
