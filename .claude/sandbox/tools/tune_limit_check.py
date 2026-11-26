r"""Checks the "Am Limit" computation against races (tune_sweep.py results).

usage: tune_limit_check.py <out dir> [<out dir> ...]   (one of them with the default runs, e.g. runssweep1)

Groups the races by the patcher's risk points (tune_limit) for sets with enough "push", and prints
per group the mean badness (tune_sweep_fit.bad2), the share of clearly bad races (badness >= 1) and
the mean speed of the computer karts against the defaults on the same track; then the same per level
of the line and per named preset.
"""
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(HERE))), "tools"))
import patch_200cc as P   # noqa: E402
import tune_sweep_fit as F   # noqa: E402


def main():
    recs, _ = F.load(sys.argv[1:])
    recs = [r for r in recs if not r["id"].startswith("default")]
    band = defaultdict(list)
    level = defaultdict(list)
    for r in recs:
        lv, risk, push = P.tune_limit(r["v"])
        r["lv"], r["risk"], r["push"] = lv, risk, push
        key = "near/easy" if push < P.LIMIT_PUSH_MIN else "too risky" if risk >= P.LIMIT_RISK_MAX else "level %d" % lv
        level[key].append(r)
        if push >= P.LIMIT_PUSH_MIN:
            band[min(risk // 4, 12)].append(r)

    def line(name, g):
        print("%-14s n %3d  badness %.2f  bad %3.0f %%  speed %.2f" % (
            name, len(g), sum(map(F.bad2, g)) / len(g), 100.0 * sum(1 for r in g if F.bad2(r) >= 1) / len(g),
            sum(r["speed"] for r in g) / len(g)))
    print("push >= %d, by risk points (4 per band):" % P.LIMIT_PUSH_MIN)
    for b in sorted(band):
        line("risk %d..%d" % (4 * b, 4 * b + 3) if b < 12 else "risk 48+", band[b])
    print("by what the line shows:")
    for k in sorted(level):
        line(k, level[k])
    print("presets:")
    for name, vals in P.TUNE_PRESETS:
        g = [r for r in recs if tuple(r["v"]) == tuple(vals)]
        if g:
            line(name[:14], g)


if __name__ == "__main__":
    main()
