"""Wheel contact / drivetrain statistics for recorded runs.  usage: contact.py <csv> [csv...] [--until T]"""
import csv
import math
import os
import sys


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    until = 2.5
    for a in sys.argv[1:]:
        if a.startswith("--until="):
            until = float(a.split("=")[1])
    for p in args:
        rows = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(open(p))]
        t0 = rows[0]["race_time"]
        print(f"== {os.path.basename(p)}  (first {until} s)")
        print("    window      speed  rpm   gear thr | wheel contact share FL FR RL RR | all4  none | mean load (in contact) FL FR RL RR | load when free")
        w = 0.5
        t = 0.0
        while t < until - 1e-9:
            sel = [r for r in rows if t <= r["race_time"] - t0 < t + w]
            if not sel:
                break
            n = len(sel)
            share = [sum(1 for r in sel if r[f"c{i}"] != 0) / n for i in range(4)]
            all4 = sum(1 for r in sel if all(r[f"c{i}"] != 0 for i in range(4))) / n
            none = sum(1 for r in sel if all(r[f"c{i}"] == 0 for i in range(4))) / n
            loads = []
            for i in range(4):
                v = [r[f"load{i}"] for r in sel if r[f"c{i}"] != 0]
                loads.append(sum(v) / len(v) if v else 0.0)
            sp = sum(math.hypot(r["vx"], r["vz"]) for r in sel) / n
            rpm = sum(r["rpm"] for r in sel) / n
            gear = sorted(r["gear"] for r in sel)[n // 2]
            thr = sum(r["throttle"] for r in sel) / n
            print(f"   {t:4.1f}-{t+w:4.1f}s  {sp:6.2f} {rpm:6.0f}  {gear:3.0f} {thr:4.2f} |   "
                  + " ".join(f"{s*100:5.1f}%" for s in share) + f" | {all4*100:5.1f}% {none*100:5.1f}% |  "
                  + " ".join(f"{l:8.1f}" for l in loads))
            t += w


if __name__ == "__main__":
    main()
