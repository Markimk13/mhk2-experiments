r"""Race two sets of learned tables against each other in the same races (sandbox, three games).

usage: geo_duel.py <out dir> [--a tables.inc] [--b tables.inc] [--b-adjust geo_adjust.json]
                   [--drivers "off=;lift=ls=1,le=0.3" [--slots off,off,lift,lift,lift,lift]]
                   [--driver k=v,..] [--tracks 0,1,..] [--races 6] [--seconds 120[,track:seconds..]] [--games 3] [--odd "--watch off"] [--read]

In every race three of the six computer karts drive set A and three set B (the test build's
table per kart number, ai_race.py --geo-tables); the kart numbers alternate and swap from race
to race. A is geo_tables.inc unless --a names another file; B is --b, or A with the factors
and shifts of --b-adjust (the file table_evolve.py writes) on top. The recordings stay in
<out dir> (40 MB per race of 120 s) for geo_incidents.py; races that are there are not driven
again, --read only prints the result.
--drivers races settings of the driver in place of tables: every name has values on top of the
common ones (geo_params.py; ai_race.py --geo-kart), all karts drive set A. --slots says which
name each of the six karts drives in the first race (default: the names in turn); the order
moves on by one kart from race to race. The first name is the reference of the result.
<out dir>\who.json keeps which kart drove what. --driver: values of the driver for all karts.

Prints per track for A and B: the distance per kart race in laps, the time lost to incidents
(geo_incidents.py) and the resets per kart race, and the time per sixth of the lap (capped at
2.5 times the median, as in table_evolve.py).
"""
import json
import math
import os
import queue
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SANDBOX = os.path.dirname(HERE)
sys.path.insert(0, HERE)
import geo_incidents as INC

BINS = 256
SECTIONS = 6
EXE = "geo200.exe"
DRIVER = "pf=1.1,pt=0.2,pl=0.5,lc=0.75,on=1"
CAP = 2.5


def read_inc(path):
    """geo_tables.inc -> per track (speed[256] in units/s or 0, line[256] lateral or None, free[256]: the
    place overrules a speed limit box)"""
    tabs, cur = [], None
    for ln in open(path):
        if ln.startswith("; track"):
            cur = []
            tabs.append(cur)
        elif ln.strip().startswith("db"):
            cur += [int(x) for x in ln.split("db")[1].split(",")]
    out = []
    for t in tabs:
        speed = [float(t[2 * i] >> 1) for i in range(BINS)]
        line = [(t[2 * i + 1] - 1) / 63.5 - 1.5 if t[2 * i + 1] else None for i in range(BINS)]
        out.append((speed, line, [t[2 * i] & 1 for i in range(BINS)]))
    return out


def encode(speed, line, free=None):
    b = bytearray()
    for i, (v, l) in enumerate(zip(speed, line)):
        b.append(0 if not v else 2 * max(1, min(127, int(round(v)))) + (1 if free and free[i] else 0))
        b.append(0 if l is None or not v else max(1, min(255, 1 + int(round(63.5 * (max(-1.5, min(2.5, l)) + 1.5))))))
    return bytes(b)


def write_inc(path, tabs):
    """tables -> a file like geo_tables.inc (for --a / --b)"""
    with open(path, "w", newline="\n") as f:
        f.write("; written by geo_duel.write_inc\n")
        for t, tab in enumerate(tabs):
            blob = encode(*tab)
            f.write("; track %d\n" % t)
            for k in range(0, len(blob), 32):
                f.write("    db  " + ", ".join("%d" % x for x in blob[k:k + 32]) + "\n")


def adjusted(tabs, path):
    """the tables with the speed factors and line shifts of a geo_adjust.json on top"""
    adj = json.load(open(path))
    out = []
    for t, (speed, line, free) in enumerate(tabs):
        if str(t) in adj:
            a = adj[str(t)]
            speed = [v * f for v, f in zip(speed, a["speed"])]
            line = [None if l is None else l + d for l, d in zip(line, a["line"])]
        out.append((speed, line, free))
    return out


def run_races(jobs, games, log, driver=DRIVER):
    """jobs: (recording path, track, tables file, seconds[, more arguments for ai_race.py]); a race that cannot
    start is tried again every minute"""
    q = queue.Queue()
    for j in jobs:
        q.put(j)

    def worker(folder):
        exe = os.path.join(SANDBOX, folder, EXE)
        while True:
            try:
                job = q.get_nowait()
            except queue.Empty:
                return
            path, track, tables, seconds = job[:4]
            more = list(job[4]) if len(job) > 4 else []
            for attempt in range(60):
                r = subprocess.run([sys.executable, os.path.join(HERE, "ai_race.py"), exe, path + ".part", "--track", str(track),
                                    "--geo-tables", tables, "--seconds", str(seconds), "--cls", "4", "--physics60",
                                    "--geo-on", "1,1,1,1,1,1", "--geo", driver] + more, capture_output=True, text=True)
                if r.returncode == 0 and os.path.exists(path + ".part"):
                    os.replace(path + ".part", path)
                    break
                tail = (r.stdout + r.stderr)[-200:].replace("\n", " ")
                log("   %s attempt %d failed: %s" % (os.path.basename(path), attempt + 1, tail))
                time.sleep(60)

    th = [threading.Thread(target=worker, args=(f,)) for f in ["game", "game2", "game3"][:games]]
    for t in th:
        t.start()
    for t in th:
        t.join()


def section_passes(rows):
    """-> list of (section, seconds, still inside at the end) of one kart (rows of geo_incidents.load)"""
    shift = round(((rows[50][8] - rows[50][7]) % 1.0) * 2) / 2.0          # laps + progress is half a lap ahead on Sumpf
    cross = {}
    reached = math.floor((rows[0][8] - shift) * SECTIONS)
    for r in rows:
        m = math.floor((r[8] - shift) * SECTIONS)
        while reached < m:
            reached += 1
            cross[reached] = r[0]
    out = []
    for m in sorted(cross):
        if cross[m] < 5.0:                                                # the standing start
            continue
        if m + 1 in cross:
            out.append((m % SECTIONS, cross[m + 1] - cross[m], False))
        else:
            out.append((m % SECTIONS, rows[-1][0] - cross[m], True))
    return out


def capped(times, cap):
    out = []
    for sec, s, open_end in times:
        if open_end:
            if s >= cap:
                out.append(cap)
        else:
            out.append(min(s, cap))
    return out


def mean_se(v):
    n = len(v)
    if not n:
        return 0.0, 0.0
    m = sum(v) / n
    var = sum((x - m) ** 2 for x in v) / (n - 1) if n > 1 else 0.0
    return m, math.sqrt(var / n)


def who_of(r):
    """kart number -> "A" / "B" in race r: three karts each, another order from race to race"""
    order = ("ABABAB", "BABABA", "ABBABA", "BAABAB")[r % 4]
    return {n: order[n - 1] for n in range(1, 7)}


def report_names(out, tracks, races, names):
    """more than two sets (driver settings): laps, lost seconds and resets per name, per track and over all"""
    who_all = json.load(open(os.path.join(out, "who.json")))
    total = {n: [] for n in names}                # per kart race: laps as a share of the track's mean
    lost = {n: [] for n in names}
    resets = {n: [] for n in names}
    for t in tracks:
        dist = {n: [] for n in names}
        cost = {n: [] for n in names}
        res = {n: [] for n in names}
        for r in range(races):
            key = "t%d_r%d" % (t, r)
            path = os.path.join(out, key + ".csv")
            if not os.path.exists(path) or key not in who_all:
                continue
            for kn, rows in INC.load(path).items():
                if kn == 0 or len(rows) < 100:
                    continue
                w = who_all[key][str(kn)]
                inc = INC.incidents(rows)
                dist[w].append(rows[-1][8] - rows[0][8])
                cost[w].append(sum(o["cost"] for o in inc))
                res[w].append(sum(o["resets"] for o in inc))
        every = [x for n in names for x in dist[n]]
        if not every:
            continue
        mean = sum(every) / len(every)
        print("track %d: " % t + " | ".join("%s laps %.3f lost %.1f s resets %.2f" % (
            n, mean_se(dist[n])[0], mean_se(cost[n])[0], mean_se(res[n])[0]) for n in names))
        for n in names:
            total[n] += [x / mean for x in dist[n]]
            lost[n] += cost[n]
            resets[n] += res[n]
    m0, s0 = mean_se(total[names[0]])
    for n in names:
        m, s = mean_se(total[n])
        z = (m - m0) / math.sqrt(s * s + s0 * s0) if n != names[0] and (s or s0) else 0.0
        print("all tracks %-8s %3d kart races: distance %+.1f %% against %s (z %.1f), lost %.1f s, resets %.2f per kart race"
              % (n, len(total[n]), 100 * (m / m0 - 1) if m0 else 0, names[0], z, mean_se(lost[n])[0], mean_se(resets[n])[0]))


def report(out, tracks, races):
    for t in tracks:
        dist = {"A": [], "B": []}
        cost = {"A": [], "B": []}
        resets = {"A": 0, "B": 0}
        passes = {"A": [], "B": []}
        n = 0
        for r in range(races):
            path = os.path.join(out, "t%d_r%d.csv" % (t, r))
            if not os.path.exists(path):
                continue
            n += 1
            who = who_of(r)
            for kn, rows in INC.load(path).items():
                if kn == 0 or len(rows) < 100:
                    continue
                w = who[kn]
                dist[w].append(rows[-1][8] - rows[0][8])
                inc = INC.incidents(rows)
                cost[w].append(sum(o["cost"] for o in inc))
                resets[w] += sum(o["resets"] for o in inc)
                passes[w] += section_passes(rows)
        if not n:
            continue
        (da, sa), (db, sb) = mean_se(dist["A"]), mean_se(dist["B"])
        z = (db - da) / math.sqrt(sa * sa + sb * sb) if sa or sb else 0.0
        print("track %d, %d races: laps A %.3f B %.3f (%+.1f %%, z %.1f) | lost s A %.1f B %.1f | resets per kart race A %.2f B %.2f"
              % (t, n, da, db, 100 * (db / da - 1) if da else 0, z, mean_se(cost["A"])[0], mean_se(cost["B"])[0],
                 resets["A"] / max(1, len(dist["A"])), resets["B"] / max(1, len(dist["B"]))))
        cells = []
        for sec in range(SECTIONS):
            both = sorted(s for w in "AB" for q, s, o in passes[w] if q == sec and not o)
            if len(both) < 6:
                cells.append("s%d -" % sec)
                continue
            cap = CAP * both[len(both) // 2]
            (ma, ea), (mb, eb) = (mean_se(capped([p for p in passes[w] if p[0] == sec], cap)) for w in "AB")
            z = (ma - mb) / math.sqrt(ea * ea + eb * eb) if ea or eb else 0.0
            cells.append("s%d %.1f %.1f (%+.0f %%, z %.1f)" % (sec, ma, mb, 100 * (1 - mb / ma) if ma else 0, z))
        print("   sixths, seconds A B (gain of B): " + " | ".join(cells))


def main():
    a = sys.argv[1:]
    if not a:
        raise SystemExit(__doc__)
    out = a[0]

    def opt(name, default):
        return a[a.index(name) + 1] if name in a else default

    tracks = [int(x) for x in opt("--tracks", "0,1,2,3,4,5,6,7").split(",")]
    races = int(opt("--races", "6"))
    sec = opt("--seconds", "120").split(",")           # 120 or 120,3:170 (track 3 races 170 s)
    sec_of = dict(x.split(":") for x in sec[1:])
    games = int(opt("--games", "3"))
    odd = opt("--odd", "").split()                 # more ai_race.py arguments for the races 1, 3, 5, ..
    drivers = [x.split("=", 1) for x in opt("--drivers", "").split(";")] if "--drivers" in a else []
    names = [n for n, _ in drivers]
    slots = opt("--slots", "").split(",") if "--slots" in a else [names[i % len(names)] for i in range(6)] if names else []
    if "--read" not in a:
        os.makedirs(out, exist_ok=True)
        ta = read_inc(opt("--a", os.path.join(HERE, "geo_tables.inc")))
        tb = read_inc(opt("--b", "")) if "--b" in a else ta
        if "--b-adjust" in a:
            tb = adjusted(tb, opt("--b-adjust", ""))
        jobs = []
        wp = os.path.join(out, "who.json")
        who_all = json.load(open(wp)) if os.path.exists(wp) else {}
        for r in range(races):                   # race by race over the tracks, so a part of the batch is a result too
            for t in tracks:
                who = {n: slots[(n - 1 + r) % 6] for n in range(1, 7)} if drivers else who_of(r)
                who_all["t%d_r%d" % (t, r)] = {str(n): w for n, w in who.items()}
                more = list(odd) if r % 2 else []
                for n in range(1, 7):
                    spec = dict(drivers).get(who[n], "") if drivers else ""
                    if spec:
                        more += ["--geo-kart", "%d:%s" % (n, spec)]
                blob = bytearray(encode(*ta[t]))
                for n in range(1, 7):
                    blob += encode(*(tb[t] if who[n] == "B" and not drivers else ta[t]))
                tf = os.path.join(out, "t%d_r%d.tab" % (t, r))
                open(tf, "wb").write(bytes(blob))
                path = os.path.join(out, "t%d_r%d.csv" % (t, r))
                if not os.path.exists(path):
                    jobs.append((path, t, tf, sec_of.get(str(t), sec[0]), more))
        json.dump(who_all, open(wp, "w"))
        print("%d races (%s)" % (len(jobs), time.strftime("%H:%M")), flush=True)
        run_races(jobs, games, lambda m: print(m, flush=True), DRIVER + ("," + opt("--driver", "") if "--driver" in a else ""))
        print("done (%s)" % time.strftime("%H:%M"), flush=True)
    if drivers:
        report_names(out, tracks, races, names)
    else:
        report(out, tracks, races)


if __name__ == "__main__":
    main()
