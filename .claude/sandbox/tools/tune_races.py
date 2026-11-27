r"""Races of the tuning class with computer karts, for sets of tuning values (sandbox, 60 FPS build).

usage: tune_races.py <test exe> <out dir> [--seconds 45] [--track 0] [--physics60] [--tag T] name=a,b,c,d,e,f,g ...

The seven or eight values are Übersetzung (hundredths), Motorkraft, Haftung, Gewicht, Bremsen, Lenkung,
Anpressdruck and Schwerkraft (percent; Schwerkraft 100 if left out). The player's kart gets no input; the six computer karts drive. Per set:
their mean speed, the top speed seen, how long they stood nearly still, and whether a kart "ran
away": faster than 1.5 times what its gearing allows at the engine's limit (6000 rpm), which only
happens when the physics blows up. A run ends one second after the first runaway.
--cans gives the computer karts a power can again and again (ai_race.py --cans); the line then
ends with the number of cans fired.
--physics60 switches "60-FPS-Fahrphysik" on (for builds that run faster than 60 FPS); --tag is put
in front of the names in the log and in the file names (for example the frame rate of the build).
Uses ai_race.py (one game at a time, waits for other instances). Results also go to <out dir>\races.log.
"""
import csv
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def rev_limit_speed(gearing):
    return 6000.0 * (gearing / 100.0) / 143.27


def report(path, limit):
    karts = {}
    with open(path) as f:
        for r in csv.DictReader(f):
            v = math.sqrt(float(r["vx"]) ** 2 + float(r["vy"]) ** 2 + float(r["vz"]) ** 2)
            karts.setdefault(int(r["kart"]), []).append((float(r["t"]), float(r["x"]), float(r["z"]), v))
    mean, tops, stuck, away = [], [], 0.0, []
    for k in sorted(karts):
        rows = karts[k]
        bad = next((q[0] for q in rows if not q[3] <= limit), None)
        if bad is not None:
            away.append((bad, k))
        if not k:
            continue
        good = [q for q in rows if bad is None or q[0] < bad]
        if len(good) < 2:
            continue
        dur = good[-1][0] - good[0][0]
        dist = sum(math.hypot(b[1] - a[1], b[2] - a[2]) for a, b in zip(good, good[1:]))
        mean.append(dist / dur if dur > 0 else 0.0)
        tops.append(max(q[3] for q in good))
        later = [q for q in good if q[0] > 5.0]
        stuck += sum(b[0] - a[0] for a, b in zip(later, later[1:]) if a[3] < 3.0)
    dur = max(rows[-1][0] for rows in karts.values())
    text = "%.0f s | computer karts mean %.1f (%.1f .. %.1f), top %.1f, nearly still %.1f s" % (
        dur, sum(mean) / len(mean), min(mean), max(mean), max(tops), stuck)
    if away:
        away.sort()
        text += " | RUNAWAY: %d kart(s), first kart %d at %.1f s" % (len(away), away[0][1], away[0][0])
    else:
        text += " | no runaway"
    return text


def main():
    args = sys.argv[1:]
    seconds, track = "45", "0"
    for opt in ("--seconds", "--track"):
        if opt in args:
            i = args.index(opt)
            value = args[i + 1]
            del args[i:i + 2]
            if opt == "--seconds":
                seconds = value
            else:
                track = value
    physics60 = "--physics60" in args
    if physics60:
        args.remove("--physics60")
    cans = "--cans" in args
    if cans:
        args.remove("--cans")
    tag = ""
    if "--tag" in args:
        i = args.index("--tag")
        tag = args[i + 1] + " "
        del args[i:i + 2]
    exe, outdir = args[0], args[1]
    os.makedirs(outdir, exist_ok=True)
    log = open(os.path.join(outdir, "races.log"), "a", encoding="utf-8")
    for a in args[2:]:
        name, vals = tag + a.split("=")[0], [int(x) for x in a.split("=")[1].split(",")]
        out = os.path.join(outdir, "race_%s.csv" % name.replace(" ", "_"))
        if os.path.exists(out):
            os.remove(out)
        limit = max(100.0, 1.5 * rev_limit_speed(vals[0]))
        r = subprocess.run([sys.executable, os.path.join(HERE, "ai_race.py"), exe, out, "--seconds", seconds, "--cls", "5",
                            "--track", track, "--tune", ",".join(str(v) for v in vals), "--stop-above", "%.0f" % limit]
                           + (["--physics60"] if physics60 else []) + (["--cans"] if cans else []),
                           capture_output=True, text=True)
        if not os.path.exists(out):
            line = "%-24s %s: NO DATA (%s)" % (name, vals, (r.stdout + r.stderr).strip()[-160:])
        else:
            line = "%-24s %s: %s" % (name, vals, report(out, limit))
            fired = [l for l in r.stdout.splitlines() if l.startswith("cans fired")]
            if fired:
                line += " | " + fired[0]
        print(line, flush=True)
        log.write(line + "\n")
        log.flush()


if __name__ == "__main__":
    main()
