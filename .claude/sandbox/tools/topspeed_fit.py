r"""Fits the top speed model of the tuning class (patch_200cc.py, TOP_*) to runs of topspeed.py.

usage: py topspeed_fit.py [iterations] [results.jsonl ...]     (from .claude\sandbox; default:
       runs	op1..3esults.jsonl, the runs of 2026-11-23: 330 value sets, 72 with the other
       characters and light karts, 13 on grip and brakes)

Target of a run: its top_model when the free stretches were nearly settled (|a| < 1), else
the mean of its last seconds plus 2 % (the jumps cost a little speed) when that was flat.
Model (forces, mass in the game's units): drive = min(Motorkraft * min(2.2548 * k * T(rpm), 444),
tmax), rpm = k * v / Übersetzung, k = 47.75 * top gear * diff ratio; resistance = c0 * v^2 +
(F0 + fw / Gewicht + fg * mass * Schwerkraft + f1 * over if over > 0), over = 0.5 * Anpressdruck
* min(v, 120 * sqrt(Gewicht / Anpressdruck))^2 + mass * 19.62 * (ga * Schwerkraft - cap).
The top speed is where drive = resistance (bisection). Nelder-Mead on the log error, each run's
error capped at 15 % (runs where the kart flipped). Prints the parameters, every run and the
median / 80 % / 90 % error. The 2026-11-23 result: median 1.8 %, 90 % within 6.6 %.
"""
import json, sys, math
CHARS = [(20, 0.5 * 6.0), (20, 0.5 * 6.0), (17, 0.55 * 6.0), (18, 0.45 * 7.0), (23, 0.55 * 5.5), (17, 0.52 * 6.7), (21, 0.5 * 6.2)]
FILES = [a for a in sys.argv[1:] if a.endswith('.jsonl')] or ['runs/top1/results.jsonl', 'runs/top2/results.jsonl', 'runs/top3/results.jsonl']
rows = []
for f in FILES:
    try:
        rows += [json.loads(l) for l in open(f)]
    except OSError:
        pass
data = [r for r in rows if 'v_free' in r and 'error' not in r]
for r in data:
    r.setdefault('char', 0)
    if 'top_model' in r and abs(r['a_free']) < 1.0:
        r['tgt'] = r['top_model']
    elif abs(r['slope']) < 0.15:
        r['tgt'] = r['top'] * 1.02
    else:
        r['tgt'] = None
pts = [r for r in data if r['tgt']]
NAMES = "c0 F0 fw fg f1 cap ga tmax".split()

def torque(rpm):
    if rpm < 4000: return 1.4 - 0.0002 * rpm
    return max(0.0, 1.8 - 0.0003 * rpm)

def force(p, vals, char, v):
    c0, F0, fw, fg, f1, cap, ga, tmax = p
    mass, gd = CHARS[char]
    k = 47.75 * gd
    s, pull, w, d, G = vals[0] / 100, vals[1] / 100, vals[3] / 100, vals[6] / 100, vals[7] / 100
    m = mass * w
    th = min(pull * min(2.2548 * k * torque(k * v / s), 444.0), tmax)
    vd = v if d <= 0 else min(v, 120 * math.sqrt(w / d))
    over = 0.5 * d * vd * vd + m * 19.62 * (ga * G - cap)
    res = c0 * v * v + ((F0 + fw / w + fg * m * G + f1 * over) if over > 0 else 0.0)
    return th - res

def top(p, vals, char=0):
    mass, gd = CHARS[char]
    lo, hi = 0.0, 6000 * vals[0] / 100 / (47.75 * gd)
    for _ in range(30):
        mid = (lo + hi) / 2
        if force(p, vals, char, mid) > 0: lo = mid
        else: hi = mid
    return lo

def err(p, show=False, cap=0.15):
    e = 0
    for r in pts:
        q = math.log(max(top(p, r['v'], r['char']), 1.0) / r['tgt'])
        e += min(q * q, cap * cap)
        if show: print('%-44s c%d tgt %6.2f pred %6.2f %+5.1f%% %s' % (r['v'][:8], r['char'], r['tgt'], top(p, r['v'], r['char']), 100 * q, r['id']))
    return math.sqrt(e / len(pts))

def nm(f, x0, steps, iters=600):
    n = len(x0)
    simplex = [list(x0)] + [[x + (s if i == j else 0) for j, (x, s) in enumerate(zip(x0, steps))] for i in range(n)]
    vals = [f(x) for x in simplex]
    for it in range(iters):
        order = sorted(range(n + 1), key=lambda i: vals[i])
        simplex = [simplex[i] for i in order]; vals = [vals[i] for i in order]
        c = [sum(x[j] for x in simplex[:-1]) / n for j in range(n)]
        xr = [c[j] + (c[j] - simplex[-1][j]) for j in range(n)]; fr = f(xr)
        if fr < vals[0]:
            xe = [c[j] + 2 * (c[j] - simplex[-1][j]) for j in range(n)]; fe = f(xe)
            simplex[-1], vals[-1] = (xe, fe) if fe < fr else (xr, fr)
        elif fr < vals[-2]:
            simplex[-1], vals[-1] = xr, fr
        else:
            xc = [c[j] + 0.5 * (simplex[-1][j] - c[j]) for j in range(n)]; fc = f(xc)
            if fc < vals[-1]: simplex[-1], vals[-1] = xc, fc
            else:
                simplex = [simplex[0]] + [[simplex[0][j] + 0.5 * (x[j] - simplex[0][j]) for j in range(n)] for x in simplex[1:]]
                vals = [vals[0]] + [f(x) for x in simplex[1:]]
    return simplex[0], vals[0]

if __name__ == '__main__':
    P0 = [0.01862, 413.2, 63.8, -0.1994, 0.01078, 6.039, 1.0249, 1048.0]   # the shipped numbers (TOP_*); 0 iterations checks them
    print(len(pts), 'targets, start', err(P0), flush=True)
    p, e = nm(lambda p: 9 if p[0] < 0 else err(p), P0, [0.003, 50, 20, 0.2, 0.003, 0.3, 0.1, 100], next((int(a) for a in sys.argv[1:] if a.isdigit()), 800))
    print('BEST', dict(zip(NAMES, p)), e, flush=True)
    print('P =', p)
    err(p, True)
    q = sorted(abs(math.log(max(top(p, r['v'], r['char']), 1) / r['tgt'])) for r in pts)
    print('median %.3f  p80 %.3f  p90 %.3f' % (q[len(q) // 2], q[int(len(q) * .8)], q[int(len(q) * .9)]))
