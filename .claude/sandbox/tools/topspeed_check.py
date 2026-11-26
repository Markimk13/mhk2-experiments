r"""Does the top speed the tuning pages show match the kart on the endless straight? (sandbox)

usage: topspeed_check.py <exe> <name>=<v1,..,v9> [--char N] [--tolerance 5]

Drives the values with topspeed.py (25 s on the endless straight) and compares the measured top
speed (top_model, see topspeed.py) with the patcher's top_speed(), which the game shows. Prints
"N checks ok, M failed" like the other test scripts (jobs.py group "topspeed").
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "tools"))
import patch_200cc as P  # noqa: E402
import topspeed as TS    # noqa: E402

# (preset, character): the defaults, the ones far from them, and two other characters
CASES = (("250 cc", 0), ("Mondrakete", 0), ("Jupiter", 0), ("Wahnsinn", 0), ("Federgewicht", 0),
         ("250 cc", 5), ("Rakete", 4))


def cases():
    """(job name, values, character) of every case."""
    names = [n for n, _ in P.TUNE_PRESETS]
    return [("%s c%d" % (name, char), list(P.TUNE_PRESETS[names.index(name)][1]), char) for name, char in CASES]


def main():
    a = sys.argv[1:]

    def opt(name, default):
        if name in a:
            i = a.index(name)
            v = a[i + 1]
            del a[i:i + 2]
            return v
        return default
    char = int(opt("--char", "0"))
    tol = float(opt("--tolerance", "5")) / 100
    exe, spec = a[0], a[1]
    name, vals = spec.split("=")
    values = [int(x) for x in vals.split(",")]
    want = P.top_speed(values, char)
    ok = bad = 0
    for attempt in range(3):          # the kart sometimes drifts off the straight (the rig, not the game)
        res = TS.one(exe, values, 25, cls=5, char=char)
        if "left the straight" not in res.get("error", ""):
            break
        print("   attempt %d left the straight, again" % (attempt + 1), flush=True)
    got = res.get("top_model") or (res.get("top", 0) * 1.02 if "top" in res else None)
    if got is None:
        print("  FAIL %s: no measurement (%s)" % (name, res.get("error")))
        bad += 1
    else:
        err = got / want - 1
        good = abs(err) <= tol
        print("  %s %s, character %d: driven %.1f units/s (%.0f km/h), shown %.0f km/h, %+.1f %% (allowed %.0f %%)"
              % ("ok  " if good else "FAIL", name, char, got, got * 3.6, P.top_kmh(values, char), 100 * err, 100 * tol))
        ok, bad = ok + good, bad + (not good)
    print("%d checks ok, %d failed" % (ok, bad), flush=True)


if __name__ == "__main__":
    main()
