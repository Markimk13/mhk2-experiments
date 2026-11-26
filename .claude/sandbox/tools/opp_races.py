r"""Races with the two values of the page "Gegner" in any class: how far the computer karts get.

usage: opp_races.py <out folder> [--cls 0,2] [--tracks 0,3,4,7] [--races 2] [--seconds 90]
                    [--improved 3] [--tempo T1,T2,..] [--exe geo200.exe] [--more "<ai_race.py arguments>"] [--report]

Runs --races races per class, track and tempo (three at a time, one per game folder; a race that
cannot start is tried again every minute) with ai_race.py: the shipped driver settings, the 60 FPS
switch on, kart numbers 1..--improved the learned way, the others the game's. --tempo lists the
"Tempo" values to race ("std" = "Standard", the default). Recordings: c<class>_t<track>_<tempo>_r<n>.csv.

Prints per class and tempo the laps (car+220h, last minus first row) of the improved karts and
of the game's karts in the same races, their difference with a z value (pooled variance), and
how often a kart was set back (a jump of more than 4 units between two frames).
--more hands further arguments to ai_race.py, for example driver values per kart number
(--geo-kart 2:pf=1.05). --report only prints, from the recordings that are there.
"""
import csv
import math
import os
import queue
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SANDBOX = os.path.dirname(HERE)


def load(path):
    """-> {kart number: (laps driven, times set back)} of the computer karts"""
    first, last, pos, resets = {}, {}, {}, {}
    with open(path) as f:
        for r in csv.DictReader(f):
            if r["kart"] == "0":
                continue
            k = int(r["knum"])
            p = (float(r["x"]), float(r["y"]), float(r["z"]))
            first.setdefault(k, float(r["prog"]))
            last[k] = float(r["prog"])
            if k in pos and math.dist(pos[k], p) > 4.0:
                resets[k] = resets.get(k, 0) + 1
            pos[k] = p
    return {k: (last[k] - first[k], resets.get(k, 0)) for k in first}


def mean(v):
    return sum(v) / len(v) if v else 0.0


def z_of(a, b):
    if len(a) < 2 or len(b) < 2:
        return 0.0
    ma, mb = mean(a), mean(b)
    var = (sum((x - ma) ** 2 for x in a) + sum((x - mb) ** 2 for x in b)) / (len(a) + len(b) - 2)
    return (mb - ma) / math.sqrt(var * (1.0 / len(a) + 1.0 / len(b))) if var else 0.0


def main():
    a = sys.argv[1:]

    def opt(name, default):
        return a[a.index(name) + 1] if name in a else default

    out = a[0]
    classes = [int(x) for x in opt("--cls", "0,2").split(",")]
    tracks = [int(x) for x in opt("--tracks", "0,3,4,7").split(",")]
    races, seconds = int(opt("--races", "2")), float(opt("--seconds", "90"))
    improved = int(opt("--improved", "3"))
    tempos = opt("--tempo", "std").split(",")
    exe_name = opt("--exe", "geo200.exe")
    extra = opt("--more", "").split()
    os.makedirs(out, exist_ok=True)
    jobs = [(c, t, tp, n) for c in classes for tp in tempos for t in tracks for n in range(races)]

    def name(c, t, tp, n):
        return os.path.join(out, "c%d_t%d_%s_r%d.csv" % (c, t, tp, n))

    if "--report" not in a:
        q = queue.Queue()
        for j in jobs:
            if not os.path.exists(name(*j)):
                q.put(j)

        def worker(folder):
            exe = os.path.join(SANDBOX, folder, exe_name)
            while True:
                try:
                    c, t, tp, n = q.get_nowait()
                except queue.Empty:
                    return
                path = name(c, t, tp, n)
                more = ([] if tp == "std" else ["--tempo", tp]) + extra
                for attempt in range(30):
                    r = subprocess.run([sys.executable, os.path.join(HERE, "ai_race.py"), exe, path + ".part", "--track", str(t),
                                        "--seconds", str(seconds), "--cls", str(c), "--physics60", "--improved", str(improved)] + more,
                                       capture_output=True, text=True)
                    if r.returncode == 0 and os.path.exists(path + ".part"):
                        os.replace(path + ".part", path)
                        print("done %s" % os.path.basename(path), flush=True)
                        break
                    print("   %s attempt %d failed: %s" % (os.path.basename(path), attempt + 1, (r.stdout + r.stderr)[-200:].replace("\n", " ")), flush=True)
                    time.sleep(60)

        th = [threading.Thread(target=worker, args=(f,)) for f in ("game", "game2", "game3")]
        for t in th:
            t.start()
        for t in th:
            t.join()

    print("class tempo   races   laps improved (1..%d)   laps the game's   difference      set back improved / game's" % improved)
    for c in classes:
        for tp in tempos:
            new, old, rn, ro, n = [], [], [], [], 0
            per_track = []
            for t in tracks:
                tn, to = [], []
                for k in range(races):
                    p = name(c, t, tp, k)
                    if not os.path.exists(p):
                        continue
                    n += 1
                    for kn, (laps, resets) in load(p).items():
                        (tn if kn <= improved else to).append(laps)
                        (rn if kn <= improved else ro).append(resets)
                new += tn
                old += to
                if tn and to:
                    per_track.append("t%d %+.0f %%" % (t, 100 * (mean(tn) / mean(to) - 1)))
            if not new or not old:
                continue
            print("%4d  %5s   %4d    %.3f                  %.3f             %+5.1f %% (z %.1f)   %.2f / %.2f    %s"
                  % (c, tp, n, mean(new), mean(old), 100 * (mean(new) / mean(old) - 1), z_of(old, new), mean(rn), mean(ro),
                     ", ".join(per_track)))


if __name__ == "__main__":
    main()
