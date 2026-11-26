r"""Results of the preset candidates (ids "c-<name>-<n>-t<track>") per candidate.

usage: preset_report.py <out dir> [<out dir> ...]   (the default runs come from runs\sweep1)
Prints per candidate: races, mean badness, races with badness >= 1, the computer karts' speed
against the defaults, and the line the patcher shows for it; the current presets for comparison.
"""
import os
import sys
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
SANDBOX = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(SANDBOX)), "tools"))
import patch_200cc as P   # noqa: E402
import tune_sweep_fit as F   # noqa: E402


def main():
    dirs = [os.path.join(SANDBOX, "runs", d) for d in ("sweep1", "sweep2", "sweep3")] + sys.argv[1:]
    recs, _ = F.load(dirs)
    by = defaultdict(list)
    for r in recs:
        by[tuple(r["v"])].append(r)
    cand = defaultdict(set)
    for r in recs:
        if r["id"].startswith("c-"):
            cand[r["id"].rsplit("-", 2)[0][2:]].add(tuple(r["v"]))
    names = dict(P.TUNE_PRESETS)
    for name in sorted(cand):
        rows = []
        if name in names:
            rows.append(("now", names[name]))
        rows += [("cand", v) for v in sorted(cand[name])]
        print("== " + name)
        for tag, v in rows:
            g = by.get(tuple(v), [])
            if not g:
                print("   %-4s %-46s no races" % (tag, list(v)))
                continue
            lv, risk, push = P.tune_limit(list(v))
            print("   %-4s %-46s n %d badness %.2f bad %d speed %.2f | line %d risk %d push %d | %s" % (
                tag, list(v), len(g), sum(map(F.bad2, g)) / len(g), sum(1 for r in g if F.bad2(r) >= 1),
                sum(r["speed"] for r in g) / len(g), lv, risk, push, " ".join("%.1f" % F.bad2(r) for r in g)))


if __name__ == "__main__":
    main()
