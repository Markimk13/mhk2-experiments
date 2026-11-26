"""Cornering response of scripted drives.  usage: corner.py <t_turn> <csv> [csv...]

Prints, in 0.25 s windows after the steering input starts: speed, how fast the direction of travel
turns (lateral acceleration = v * turn rate), slip angle, and what share of the load is not on the wheels.
"""
import csv
import math
import os
import sys

G = 19.62
MASS = 20.0


def main():
    t_turn = float(sys.argv[1])
    for p in sys.argv[2:]:
        rows = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(open(p))]
        print(f"== {os.path.basename(p)}")
        print("   window        speed   lat.accel   turn radius   slip angle   steer in   load off wheels   wheels down")
        w = 0.25
        t = t_turn - 0.25
        while t < rows[-1]["t"] - w:
            sel = [r for r in rows if t <= r["t"] < t + w]
            if len(sel) < 3:
                break
            a, b = sel[0], sel[-1]
            dt = b["t"] - a["t"]
            sp = sum(math.hypot(r["vx"], r["vz"]) for r in sel) / len(sel)
            dh = (math.atan2(b["vz"], b["vx"]) - math.atan2(a["vz"], a["vx"]) + math.pi) % (2 * math.pi) - math.pi
            alat = sp * dh / dt
            radius = sp / abs(dh / dt) if abs(dh) > 1e-4 else float("inf")
            slips = []
            for r in sel:
                v_long = r["vx"] * r["fx"] + r["vy"] * r["fy"] + r["vz"] * r["fz"]
                v_lat = r["vx"] * r["sx"] + r["vy"] * r["sy"] + r["vz"] * r["sz"]
                slips.append(math.degrees(math.atan2(v_lat, abs(v_long))))
            slip = sum(slips) / len(slips)
            down = [r for r in sel if all(r[f"c{i}"] for i in range(4))]
            if down:
                need = sum(MASS * G + 0.5 * (r["vx"] ** 2 + r["vz"] ** 2) for r in down)
                have = sum(sum(r[f"load{i}"] for i in range(4)) for r in down)
                off = (1 - have / need) * 100
            else:
                off = float("nan")
            steer = sum(r["steer"] for r in sel) / len(sel)
            print(f"   {t - t_turn:+5.2f}..{t - t_turn + w:+5.2f}s  {sp:6.2f}   {alat:8.2f}   {radius:10.1f}   {slip:9.2f}   {steer:7.2f}   {off:13.1f}%   {len(down)/len(sel)*100:8.0f}%")
            t += w


if __name__ == "__main__":
    main()
