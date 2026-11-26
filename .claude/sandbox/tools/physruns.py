"""Run the scripted drives for the "60 FPS physics" switch and print one comparison table.

usage: physruns.py <patcher> <gamedir> <outdir> [variant ...]
variants: new200_off new200_on new60_off new60_on orig200
Each variant is driven twice: a full-lock turn and a straight launch.
"""
import csv
import math
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PLANS = {"turn": "0.5:1:0:0,2.3:1:1:0,3.2", "straight": "0.5:1:0:0,3.6"}
VARIANTS = {
    "new200_off": ("opt_new.exe", "off"),
    "new200_on": ("opt_new.exe", "on"),
    "new60_off": ("opt_new60.exe", "off"),
    "new60_on": ("opt_new60.exe", "on"),
    "orig200": ("opt_orig.exe", None),
}
G, MASS = 19.62, 20.0


def flag_in_file(path):
    d = open(path, "rb").read()
    return d[0x49:0x4C]


def run(patcher, game, out, name):
    exe, flag = VARIANTS[name]
    settings = os.path.join(game, "settings.dat")
    if flag:
        subprocess.run([sys.executable, patcher, "--physics60", flag, settings], check=True, stdout=subprocess.DEVNULL)
    else:
        subprocess.run([sys.executable, patcher, "--physics60", "off", settings], check=True, stdout=subprocess.DEVNULL)
    for plan_name, plan in PLANS.items():
        before = flag_in_file(settings)
        dst = os.path.join(out, f"{name}_{plan_name}.csv")
        r = subprocess.run([sys.executable, os.path.join(HERE, "drive.py"), os.path.join(game, exe), dst, "--plan", plan],
                           capture_output=True, text=True, timeout=240)
        after = flag_in_file(settings)
        print(f"  {name:11s} {plan_name:8s} {r.stdout.strip() or r.stderr.strip()[-200:]} | flag bytes in settings.dat {before.hex()} -> {after.hex()}")


def load(path):
    return [{k: float(v) for k, v in r.items()} for r in csv.DictReader(open(path))]


def at(rows, t, f):
    for a, b in zip(rows, rows[1:]):
        if a["t"] <= t <= b["t"]:
            w = (t - a["t"]) / max(b["t"] - a["t"], 1e-9)
            return f(a) + w * (f(b) - f(a))
    return float("nan")


def speed(r):
    return math.hypot(r["vx"], r["vz"])


def summarize(out, name):
    s = load(os.path.join(out, f"{name}_straight.csv"))
    t = load(os.path.join(out, f"{name}_turn.csv"))
    steps = sorted(b["t"] - a["t"] for a, b in zip(s, s[1:]))
    rest = [r["y"] for r in s if 0.2 <= r["t"] <= 0.45]
    off = []
    for r in s:
        if r["t"] >= 2.0 and all(r[f"c{i}"] for i in range(4)):
            need = MASS * G + 0.5 * (r["vx"] ** 2 + r["vz"] ** 2)
            off.append(1 - sum(r[f"load{i}"] for i in range(4)) / need)
    # turn: 0.25..0.75 s after the steering input
    sel = [r for r in t if 2.55 <= r["t"] <= 3.05]
    a, b = sel[0], sel[-1]
    dh = (math.atan2(b["vz"], b["vx"]) - math.atan2(a["vz"], a["vx"]) + math.pi) % (2 * math.pi) - math.pi
    sp = sum(speed(r) for r in sel) / len(sel)
    alat = abs(sp * dh / (b["t"] - a["t"]))
    slips = []
    for r in sel:
        vl = r["vx"] * r["fx"] + r["vy"] * r["fy"] + r["vz"] * r["fz"]
        vs = r["vx"] * r["sx"] + r["vy"] * r["sy"] + r["vz"] * r["sz"]
        slips.append(abs(math.degrees(math.atan2(vs, abs(vl)))))
    return (name, steps[len(steps) // 2] * 1000, sum(rest) / len(rest), at(s, 2.0, speed), at(s, 3.0, speed),
            at(s, 3.5, speed), 100 * sum(off) / max(len(off), 1), alat, sum(slips) / len(slips))


def main():
    patcher, game, out = sys.argv[1:4]
    names = sys.argv[4:] or list(VARIANTS)
    os.makedirs(out, exist_ok=True)
    if "--table-only" not in names:
        for n in names:
            run(patcher, game, out, n)
    names = [n for n in names if n != "--table-only"] or list(VARIANTS)
    print("variant       step ms  rest height  v(2.0s)  v(3.0s)  v(3.5s)  load off wheels  turn lat.acc  slip deg")
    for n in names:
        try:
            r = summarize(out, n)
        except (OSError, IndexError) as e:
            print(f"{n:11s}  no data ({e})")
            continue
        print("%-11s  %7.2f  %11.4f  %7.2f  %7.2f  %7.2f  %14.1f%%  %12.1f  %8.1f" % r)


if __name__ == "__main__":
    main()
