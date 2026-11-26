"""Moments where a computer kart drives visibly ahead of the player through a curve or a jump,
as scene candidates for cut_video.py ("Verbesserte Gegner" crossing a difficult part).

usage: opp_ahead.py [RUN PREFIX, default 20261126_21]   (races in runs\\user filmed with --video)

Per 0.1 s, the opponents 6..30 units ahead of the player (in the player's driving direction, at
most 0.35 rad off it); score = how hard that kart turns (heading change per second) + how much it
climbs/falls (|vy|). Prints the best 4 s windows per race at their video times. Found the bridge on
Insel for the clip of 2026-11-26; check every candidate on a video_scenes.py sheet.
"""
import csv, glob, json, math, os, sys
RUNS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runs", "user")
PREFIX = sys.argv[1] if len(sys.argv) > 1 else "20261126_21"
names = {0: "Moorhuhn X", 1: "Winter", 2: "Insel", 3: "Ägypten", 4: "Fabrik", 5: "Bergwerk", 6: "Burg", 7: "Sumpf"}
for js in sorted(glob.glob(os.path.join(RUNS, PREFIX + "*.json"))):
    m = json.load(open(js))
    if "video_t" not in m:
        continue
    rows = {}
    for r in csv.DictReader(open(js[:-5] + ".csv")):
        t = round(float(r["t"]), 1)
        rows.setdefault(t, {})[int(r["kart"])] = (float(r["x"]), float(r["y"]), float(r["z"]),
                                                    float(r["vx"]), float(r["vy"]), float(r["vz"]))
    ts = sorted(rows)
    score = {}
    prev_head = {}
    for t in ts:
        k = rows[t]
        if 0 not in k:
            continue
        px, py, pz, pvx, pvy, pvz = k[0]
        sp = math.hypot(pvx, pvz)
        if sp < 5:
            continue
        hx, hz = pvx / sp, pvz / sp
        best = 0.0
        for i, (x, y, z, vx, vy, vz) in k.items():
            if i == 0:
                continue
            dx, dz = x - px, z - pz
            ahead = dx * hx + dz * hz
            side = abs(-dx * hz + dz * hx)
            if not (6 < ahead < 30 and side < ahead * 0.35):
                continue
            head = math.atan2(vz, vx)
            turn = 0.0
            if (i, round(t - 0.1, 1)) in prev_head:
                d = head - prev_head[(i, round(t - 0.1, 1))]
                turn = abs((d + math.pi) % (2 * math.pi) - math.pi) / 0.1
            best = max(best, min(turn, 3.0) + min(abs(vy) / 10, 2.0))
        for i, (x, y, z, vx, vy, vz) in k.items():
            prev_head[(i, t)] = math.atan2(vz, vx)
        score[int(t * 10)] = best
    wins = []
    for s in score:
        w = [score.get(s + j, 0) for j in range(40)]
        if sum(1 for v in w if v > 0) >= 30:          # an opponent in view most of the 4 s
            wins.append((sum(w), s / 10))
    wins.sort(reverse=True)
    picked = []
    for sc, t in wins:
        if all(abs(t - p) > 6 for _, p in picked):
            picked.append((sc, t))
        if len(picked) == 3:
            break
    vt = m["video_t"]
    print(f"{names[m['track']]:10} class {m['class']}: " + ", ".join(
        f"race {t:.1f}s = video {int((vt + t) // 60)}:{(vt + t) % 60:04.1f} (score {sc:.0f})" for sc, t in picked))
