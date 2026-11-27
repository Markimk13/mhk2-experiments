"""Issue #32: per loss of kart 0 (loss_kinds.py) the velocity change split into forward / side / up,
the nearest other kart and the item held. usage (from .claude/sandbox): py tools/loss_crash_look.py <recording.csv> [...]
"""
import sys, math, csv, subprocess, collections
files=[a for a in sys.argv[1:] if not a.startswith("-")]
out=subprocess.run([sys.executable,"tools/loss_kinds.py",*files,"--list","--min","25"],capture_output=True,text=True).stdout
loss=collections.defaultdict(list)
for line in out.splitlines():
    w=line.split()
    try: t=float(w[2]); x=float(w[6])
    except (ValueError, IndexError): continue
    loss[w[0]].append((t,w[-1],float(w[3]),float(w[5])))
for f in files:
    import os
    rows=collections.defaultdict(list)
    for r in csv.DictReader(open(f)):
        rows[int(r["kart"])].append({k:(float(v) if v not in ("",) else 0.0) for k,v in r.items()})
    me=rows[0]; ts=[r["t"] for r in me]
    import bisect
    for t,kind,v0,v1 in loss[os.path.basename(f)]:
        i=bisect.bisect_left(ts,t)
        j=i
        while j<len(me)-1 and me[j]["t"]<t+0.15 and math.sqrt(me[j]["vx"]**2+me[j]["vy"]**2+me[j]["vz"]**2)>v1+0.5: j+=1
        a,b=me[i],me[j]
        # kart frame: forward = horizontal velocity direction before; up = (ux,uy,uz)
        fx,fz=a["vx"],a["vz"]; L=math.hypot(fx,fz) or 1; fx/=L; fz/=L
        dv=(b["vx"]-a["vx"],b["vy"]-a["vy"],b["vz"]-a["vz"])
        fwd=dv[0]*fx+dv[2]*fz; side=-dv[0]*fz+dv[2]*fx; up=dv[1]
        dk=min((math.dist((a["x"],a["y"],a["z"]),(r2["x"],r2["y"],r2["z"])),k) for k in rows if k!=0 for r2 in [rows[k][min(i,len(rows[k])-1)]])
        print("%s t %7.2f %5.1f->%5.1f %-14s dv fwd %6.1f side %6.1f up %6.1f  next kart %5.1f (#%d)  item %d->%d  y %.1f" %
              (os.path.basename(f)[:15], t, v0, v1, kind, fwd, side, up, dk[0], dk[1], a["item"], b["item"], a["y"]))
