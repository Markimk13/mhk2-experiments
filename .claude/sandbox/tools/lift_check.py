r"""How hard a kart slows down after the throttle is lifted, from pu_run.py --lift recordings.

usage: lift_check.py <run.csv> [<run.csv> ...]

Per run: speed, gear and engine speed at the lift, and the mean deceleration from 0.1 s to 0.6 s
after it (game units per second squared). Engine braking and rolling resistance together; runs
with the same gearing lifted at the same speed differ only by the engine braking.
"""
import csv
import sys


def main():
    for path in sys.argv[1:]:
        rows = list(csv.DictReader(open(path)))
        i = next((k for k, r in enumerate(rows) if r["state"] == "lift"), None)
        if i is None:
            print("%s: the throttle was never lifted (top %.1f)" % (path, max(float(r["v"]) for r in rows)))
            continue
        t0 = float(rows[i]["t"])
        at = lambda d: min(rows[i:], key=lambda r: abs(float(r["t"]) - (t0 + d)))
        a, b = at(0.1), at(0.6)
        dec = (float(a["v"]) - float(b["v"])) / (float(b["t"]) - float(a["t"]))
        print("%s: lifted at v %.1f (gear %s, %.0f rpm) | 0.1 s later v %.1f at %.0f rpm, 0.6 s later v %.1f | deceleration %.1f"
              % (path, float(rows[i]["v"]), rows[i]["gear"], float(rows[i]["rpm"]), float(a["v"]), float(a["rpm"]), float(b["v"]), dec))


if __name__ == "__main__":
    main()
