r"""Repair the learned tables at the places where the computer karts get into trouble (sandbox, three games).

usage: table_repair.py <state dir> [--until HH:MM] [--tracks 0,1,..] [--games 3] [--start geo_adjust.json]
                       [--driver k=v,..] [--scout <geo_duel dir> --scout-sets A+B,A,..] [--report]

The computer karts with the learned tables lose 10 to 25 % of a race to incidents (resets, hits),
and most of that at a few places of each track. This tool looks for those places and tries
changes of the table around them; a change is kept when the karts pass the place faster with it.

A generation, per track:
- The spots: up to MAXSPOTS places with the highest cost of the champion's incidents
  (geo_incidents.py: resets and hits, by the place the kart was at before the trouble began),
  MINCOST seconds per kart and race or more. A spot's region runs from BEFORE places ahead of it
  to AFTER places behind it; regions do not overlap.
- Four challenger tables. Each is the champion with one recipe at every spot: less speed ahead of
  the spot ("slow"), over a longer way ("early"), more speed ("fast": a jump that needs it, a
  corner the karts brake too hard for), the line moved back towards the road on the side the
  karts leave it ("shift"), both, or the line nearer to the middle ("mid").
- A round is six races in which the six computer karts drive the champion (two karts) and the
  four challengers (the test build's table per kart number, ai_race.py --geo-tables), rotated
  over the kart numbers. Every pass of a kart through a region gives a time; times are capped at
  CAP times the champion's median.
- After the first round a generation ends if nothing looks promising. A recipe is adopted when
  its mean time is GAIN lower than the champion's with Z2 standard errors (pooled variance; Z1
  after one round). At most ROUNDS_MAX rounds.
A track without spots is not raced. Without incidents on record a track starts with a round in
which all six karts drive the champion (or --scout: recordings of geo_duel.py, with the names
of the karts that drove the champion, joined by "+", per track or one for all; several --scout
with their --scout-sets add up).
--driver: values of the driver for all karts on top of geo_duel.py's (kept in the state).

The state (<state dir>\state.json) is saved after every round; start the tool again to go on.
--until: no new round after this time of day. --start: the first champion is the base tables
(<state dir>\base_tables.inc, a copy of geo_tables.inc) with this file's changes on top. After
every round, and with --report, the champions are written as geo_adjust.json next to
geo_driver.asm (factors and shifts against the base tables); learn_tables.py applies it.
"""
import json
import math
import os
import random
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import geo_duel as D
import geo_incidents as INC

BINS = 256
SECONDS = {3: 170}                       # race length per track; the laps of track 3 take the computer karts 85 s
SECONDS_DEFAULT = 120
CHALLENGERS = 4
ROUNDS_MAX = 3
GAIN, Z1, Z2, CAP = 0.03, 3.3, 2.8, 2.5
MAXSPOTS, MINCOST = 5, 0.4
BEFORE, AFTER = 16, 20
ADJUST = os.path.join(HERE, "geo_adjust.json")
# (kind, less speed, line shift towards the road) in the order they are tried
WITH_SIDE = (("slow", 0.12, 0), ("both", 0.12, 0.3), ("shift", 0, 0.3), ("fast", 0.12, 0),
             ("slow", 0.25, 0), ("early", 0.15, 0), ("shift", 0, 0.6), ("both", 0.25, 0.3),
             ("slow", 0.4, 0), ("fast", 0.25, 0), ("mid", 0.5, 0), ("early", 0.3, 0))
NO_SIDE = (("slow", 0.12, 0), ("fast", 0.12, 0), ("shift", 0, 0.3), ("shift", 0, -0.3),
           ("slow", 0.25, 0), ("early", 0.15, 0), ("mid", 0.5, 0), ("fast", 0.25, 0),
           ("slow", 0.4, 0), ("shift", 0, 0.6), ("shift", 0, -0.6), ("early", 0.3, 0))


def window(center, before, after):
    """place -> weight 0..1: 1 at the centre, falling to 0 `before` places ahead and `after` behind"""
    w = {}
    for k in range(-before, after + 1):
        span = before if k < 0 else after
        w[(center + k) % BINS] = 0.5 * (1 + math.cos(math.pi * k / (span + 1)))
    return w


def vary(tab, recipe, place):
    kind, amount, shift = recipe
    speed, line = list(tab[0]), list(tab[1])
    if kind in ("slow", "both", "early", "fast"):
        for b, w in window(place, 28 if kind == "early" else 14, 4).items():
            speed[b] *= 1 + amount * w if kind == "fast" else 1 - amount * w
    if kind in ("shift", "both"):
        for b, w in window(place, 12, 8).items():
            if line[b] is not None:
                line[b] += shift * w
    if kind == "mid":
        for b, w in window(place, 12, 8).items():
            if line[b] is not None:
                line[b] += (0.5 - line[b]) * amount * w
    return speed, line, tab[2]


def near_places(a, b):
    """the same spot from one generation to the next (its place moves by a few)"""
    return min((a - b) % BINS, (b - a) % BINS) <= 8


def in_region(place, spot):
    return (place - (spot - BEFORE)) % BINS <= BEFORE + AFTER


def kart_data(rows, spots):
    """-> region passes [(spot index, seconds, still inside at the end)], incidents [(place, cost, lateral)]"""
    shift = round(((rows[50][8] - rows[50][7]) % 1.0) * 2) / 2.0          # laps + progress is half a lap ahead on Sumpf
    cross = {}                                                            # place counted from the start of the race -> first time there
    reached = math.floor((rows[0][8] - shift) * BINS)
    first = reached
    for r in rows:
        m = math.floor((r[8] - shift) * BINS)
        while reached < m:
            reached += 1
            cross[reached] = r[0]
    passes = []
    for i, s in enumerate(spots):
        for lap in range(first // BINS - 1, reached // BINS + 2):
            lo, hi = lap * BINS + s["place"] - BEFORE, lap * BINS + s["place"] + AFTER
            if lo not in cross or cross[lo] < 8.0:                        # not there, or the standing start
                continue
            if hi in cross:
                passes.append((i, cross[hi] - cross[lo], False))
            else:
                passes.append((i, rows[-1][0] - cross[lo], True))
    inc = [(o["place"], round(o["cost"], 2), round(rows[o["first"]][6], 2)) for o in INC.incidents(rows) if rows[o["first"]][0] > 10.0]
    return passes, inc


def find_spots(inc, kart_races, tried):
    """the spots of a generation from the champion's incidents, with the recipes of the four challengers"""
    cost = [0.0] * BINS
    lat = [0.0] * BINS
    for place, c, l in inc:
        cost[place] += c
        lat[place] += c * max(-1.0, min(2.0, l))
    around = [sum(cost[(b + k) % BINS] for k in range(-4, 5)) for b in range(BINS)]
    spots = []
    for b in sorted(range(BINS), key=lambda b: -around[b]):
        if around[b] / max(1, kart_races) < MINCOST or len(spots) == MAXSPOTS:
            break
        near = [(b + k) % BINS for k in range(-4, 5)]
        place = int(round(b + sum(k * cost[(b + k) % BINS] for k in range(-4, 5)) / around[b])) % BINS
        if any(min((place - s["place"]) % BINS, (s["place"] - place) % BINS) < BEFORE + AFTER + 2 for s in spots):
            continue
        side = sum(lat[p] for p in near) / around[b]
        menu = WITH_SIDE if side > 1.15 or side < -0.15 else NO_SIDE
        sign = -1.0 if side > 1.15 else 1.0                             # the line goes back towards the road
        done = set(tuple(x[1:]) for x in tried if near_places(x[0], place))
        picks = [[k, a, round(sign * s, 2)] for k, a, s in menu if (k, a, round(sign * s, 2)) not in done][:CHALLENGERS]
        if not picks:
            continue                                                    # everything was tried here
        picks += [["none", 0, 0]] * (CHALLENGERS - len(picks))
        spots.append({"place": place, "cost": round(around[b] / max(1, kart_races), 2), "side": round(side, 2), "recipes": picks})
    return spots


def tables_for(st):
    champ = tuple(st["champion"])
    out = {"champion": champ}
    for j in range(CHALLENGERS):
        tab = champ
        for s in st["spots"]:
            tab = vary(tab, s["recipes"][j], s["place"])
        out["c%d" % j] = tab
    return out


def capped(times, cap):
    return [min(s, cap) for s, o in times if not o or s >= cap]


def decide(st, z_min):
    """-> adopted [(spot index, challenger, gain, z)], spots that deserve another round, log lines"""
    adopted, maybe, lines = [], [], []
    for i, s in enumerate(st["spots"]):
        champ = [(x[1], x[2]) for x in st["passes"].get("champion", []) if x[0] == i]
        done = sorted(x for x, o in champ if not o)
        if len(done) < 8:
            lines.append("      spot %d: only %d passes of the champion" % (s["place"], len(done)))
            continue
        cap = CAP * done[len(done) // 2]
        c = capped(champ, cap)
        mc = sum(c) / len(c)
        best = None
        cells = []
        for j in range(CHALLENGERS):
            if s["recipes"][j][0] == "none":
                continue
            t = capped([(x[1], x[2]) for x in st["passes"].get("c%d" % j, []) if x[0] == i], cap)
            if len(t) < 5:
                cells.append("-")
                continue
            mt = sum(t) / len(t)
            var = (sum((x - mc) ** 2 for x in c) + sum((x - mt) ** 2 for x in t)) / (len(c) + len(t) - 2)
            z = (mc - mt) / math.sqrt(var * (1.0 / len(c) + 1.0 / len(t))) if var else 0.0
            gain = 1 - mt / mc
            k, a, sh = s["recipes"][j]
            cells.append("%s %.2f %+.1f: %+.1f%% z%.1f" % (k, a, sh, 100 * gain, z))
            if gain >= GAIN and z >= z_min and (best is None or z > best[3]):
                best = (i, j, gain, z)
            elif gain >= GAIN / 2 and z >= (1.0 if z_min == Z1 else 2.0) and i not in maybe:
                maybe.append(i)
        lines.append("      spot %d (cost %.1f s, side %.1f, champion %.2f s, median %.2f): %s"
                     % (s["place"], s["cost"], s["side"], mc, done[len(done) // 2], " | ".join(cells)))
        if best:
            adopted.append(best)
            if i in maybe:
                maybe.remove(i)
    return adopted, maybe, lines


def write_adjust(state, base):
    adj = {}
    for t, st in state["tracks"].items():
        speed, line = st["champion"][:2]
        bs, bl = base[int(t)][:2]
        f = [round(v / b, 4) if b else 1.0 for v, b in zip(speed, bs)]
        d = [round(l - b, 4) if l is not None and b is not None else 0.0 for l, b in zip(line, bl)]
        if any(x != 1.0 for x in f) or any(x != 0.0 for x in d):
            adj[t] = {"speed": f, "line": d, "changes": st.get("adopted", [])}
    with open(ADJUST, "w") as f:
        json.dump(adj, f)
    return adj


def main():
    a = sys.argv[1:]
    if not a:
        raise SystemExit(__doc__)
    out = a[0]

    def opt(name, default):
        return a[a.index(name) + 1] if name in a else default

    tracks = [int(x) for x in opt("--tracks", "0,1,2,3,4,5,6,7").split(",")]
    games = int(opt("--games", "3"))
    until = opt("--until", "")
    os.makedirs(out, exist_ok=True)
    sp = os.path.join(out, "state.json")
    bp = os.path.join(out, "base_tables.inc")
    if not os.path.exists(bp):
        shutil.copyfile(os.path.join(HERE, "geo_tables.inc"), bp)
    base = D.read_inc(bp)
    state = json.load(open(sp)) if os.path.exists(sp) else {"round": 0, "tracks": {}}
    first = D.adjusted(base, opt("--start", "")) if "--start" in a else base
    start_changes = json.load(open(opt("--start", ""))) if "--start" in a else {}
    for t in tracks:
        if str(t) not in state["tracks"]:
            state["tracks"][str(t)] = {"champion": [list(x) for x in first[t]], "spots": None, "rounds": 0, "passes": {},
                                       "inc": {}, "kart_races": 0, "tried": [], "gens": 0,
                                       "adopted": list(start_changes.get(str(t), {}).get("changes", []))}
    logf = open(os.path.join(out, "log.txt"), "a")

    def log(msg):
        print(msg, flush=True)
        logf.write(msg + "\n")
        logf.flush()

    if "--report" in a:
        adj = write_adjust(state, base)
        for t, st in sorted(state["tracks"].items()):
            print("track %s: %d generations, changes: %s" % (t, st["gens"], "; ".join(
                "%s %.2f %+.1f at %d (%+.1f %%)" % (x["kind"], x["amount"], x.get("shift", 0), x["place"], 100 * x["gain"]) for x in st["adopted"]) or "-"))
        print("wrote %s (%d tracks changed)" % (ADJUST, len(adj)))
        return
    if "--driver" in a:
        state["driver"] = opt("--driver", "")
    driver = D.DRIVER + ("," + state["driver"] if state.get("driver") else "")
    if "--scout" in a and state["round"] == 0:
        for k in [i for i, x in enumerate(a) if x == "--scout"]:
            sdir = a[k + 1]
            sets = a[a.index("--scout-sets", k) + 1].split(",")
            who_all = json.load(open(os.path.join(sdir, "who.json")))
            for t in tracks:
                st = state["tracks"][str(t)]
                mine = sets[t if len(sets) > 1 else 0].split("+")
                r = 0
                while os.path.exists(os.path.join(sdir, "t%d_r%d.csv" % (t, r))):
                    who = who_all["t%d_r%d" % (t, r)]
                    for kn, rows in INC.load(os.path.join(sdir, "t%d_r%d.csv" % (t, r))).items():
                        if kn and len(rows) > 100 and who[str(kn)] in mine:
                            st["inc"].setdefault("champion", []).extend(kart_data(rows, [])[1])
                            st["kart_races"] += 1
                    r += 1
        for t in tracks:
            st = state["tracks"][str(t)]
            log("track %d: %d kart races scouted, %d incidents" % (t, st["kart_races"], len(st["inc"].get("champion", []))))
    while not until or time.strftime("%H:%M") < until:
        rnd = state["round"]
        rdir = os.path.join(out, "r%03d" % rnd)
        os.makedirs(rdir, exist_ok=True)
        jobs, plan = [], {}
        for t in tracks:
            st = state["tracks"][str(t)]
            if st["spots"] is None:                                   # a new generation
                if st["kart_races"]:
                    st["spots"] = find_spots(st["inc"].get("champion", []), st["kart_races"], st["tried"])
                    st["scouting"] = False
                else:
                    st["spots"], st["scouting"] = [], True
                st["rounds"], st["passes"], st["inc"], st["kart_races"] = 0, {}, {}, 0
            if not st["spots"] and not st["scouting"]:
                continue
            tabs = tables_for(st)
            slots = ["champion"] * 6 if st["scouting"] else ["champion", "champion"] + ["c%d" % j for j in range(CHALLENGERS)]
            plan[t] = []
            for r in range(6):
                who = {n: slots[(n - 1 + r) % 6] for n in range(1, 7)}
                blob = bytearray(D.encode(*tabs["champion"]))
                for n in range(1, 7):
                    blob += D.encode(*tabs[who[n]])
                tf = os.path.join(rdir, "t%d_r%d.tab" % (t, r))
                open(tf, "wb").write(bytes(blob))
                path = os.path.join(rdir, "t%d_r%d.csv" % (t, r))
                plan[t].append((path, who))
                if not os.path.exists(path):
                    jobs.append((path, t, tf, SECONDS.get(t, SECONDS_DEFAULT)))
        if not plan:
            log("no track has a spot left")
            break
        random.Random(rnd).shuffle(jobs)                              # the tracks mixed over the three games
        log("round %d: %d races (%s)" % (rnd, len(jobs), time.strftime("%H:%M")))
        D.run_races(jobs, games, log, driver)
        for t in sorted(plan):
            st = state["tracks"][str(t)]
            for path, who in plan[t]:
                if not os.path.exists(path):
                    continue
                for kn, rows in INC.load(path).items():
                    if kn == 0 or len(rows) < 100:
                        continue
                    passes, inc = kart_data(rows, st["spots"])
                    st["passes"].setdefault(who[kn], []).extend(passes)
                    st["inc"].setdefault(who[kn], []).extend(inc)
                    if who[kn] == "champion":
                        st["kart_races"] += 1
                os.remove(path)                                       # the recordings are large
            st["rounds"] += 1
            if st["scouting"]:
                log("   track %d: scouted, %d kart races, %d incidents" % (t, st["kart_races"], len(st["inc"].get("champion", []))))
                st["spots"] = None
                continue
            last = st["rounds"] >= ROUNDS_MAX
            adopted, maybe, lines = decide(st, Z1 if st["rounds"] == 1 else Z2)
            if maybe and not last:
                log("   track %d: generation %d goes on for the spots %s" % (t, st["gens"], [st["spots"][i]["place"] for i in maybe]))
                for ln in lines:
                    log(ln)
                continue
            log("   track %d: generation %d after %d round(s)" % (t, st["gens"], st["rounds"]))
            for ln in lines:
                log(ln)
            champ = tuple(st["champion"])
            inc = list(st["inc"].get("champion", []))
            for i, j, gain, z in adopted:
                s = st["spots"][i]
                k, am, sh = s["recipes"][j]
                champ = vary(champ, s["recipes"][j], s["place"])
                st["adopted"].append({"gen": st["gens"], "kind": k, "amount": am, "shift": sh, "place": s["place"],
                                      "gain": round(gain, 4), "z": round(z, 2)})
                log("      ADOPTED at %d: %s %.2f %+.1f (%+.1f %%, z %.1f)" % (s["place"], k, am, sh, 100 * gain, z))
                # the incidents of the new champion in this region are the challenger's (one kart for the champion's two)
                inc = [x for x in inc if not in_region(x[0], s["place"])]
                inc += [(p, 2 * c, l) for p, c, l in st["inc"].get("c%d" % j, []) if in_region(p, s["place"])]
            st["champion"] = [list(x) for x in champ]
            took = set(i for i, _, _, _ in adopted)
            for i, s in enumerate(st["spots"]):                   # what was tried without success is not tried again there
                if i in took:
                    st["tried"] = [x for x in st["tried"] if not near_places(x[0], s["place"])]
                else:
                    st["tried"] += [[s["place"]] + list(r) for r in s["recipes"] if r[0] != "none"]
            st["inc"] = {"champion": inc}
            st["spots"] = None
            st["gens"] += 1
        shutil.rmtree(rdir, ignore_errors=True)
        state["round"] = rnd + 1
        with open(sp + ".tmp", "w") as f:
            json.dump(state, f)
        os.replace(sp + ".tmp", sp)
        write_adjust(state, base)
    log("stopped after round %d (%s)" % (state["round"] - 1, time.strftime("%H:%M")))


if __name__ == "__main__":
    main()
