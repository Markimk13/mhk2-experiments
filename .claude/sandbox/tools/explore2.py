"""Trace race phase / car state around a forced time trial finish (exploration, sandbox only).

usage: explore2.py <exe> <class> <track0> <lap1> <lap2> <lap3> [seconds to watch after the finish]
"""
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H
import optest as O
import ghostlib as G


def snap(g, newp, t_before):
    try:
        st = O.menu_ptr(g.h)
        cm = g.u32(0x5E8520)
        car = g.u32(g.u32(cm + 0x10)) if cm and g.u32(cm + 0x10) else 0
        laps = struct.unpack("<3fi", g.read(car + 0x258, 16)) if car else None
        cstate = g.u32(car + 0x2D0) if car else None
        phase = g.u32(st + 0x118)
        rt = G.f32(g.h, cm + 0x20) if cm else -1
    except OSError as e:
        return ("err", str(e)[:40])
    mt = os.path.getmtime(newp) if os.path.exists(newp) else None
    return (g.init_count(), phase, cstate, laps[3] if laps else None, round(rt, 1) if rt < 1e6 else rt, mt != t_before)


def main():
    exe, cls, trk = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
    laps = [float(x) for x in sys.argv[4:7]]
    watch = float(sys.argv[7]) if len(sys.argv) > 7 else 40
    g = G.Game(exe)
    try:
        newp = os.path.join(g.dir, "data", "Phantom", "new-phantom.mhk2")
        t_before = os.path.getmtime(newp) if os.path.exists(newp) else None
        g.start_time_trial(cls, trk)
        t0 = time.time()
        last = None
        forced = None
        racing_since = None
        print("columns: init count, race phase [state+118h], car state [car+2D0h], lap counter, race time, new-phantom written")
        while True:
            now = time.time() - t0
            if not H.alive():
                print("GAME DIED")
                break
            s = snap(g, newp, t_before)
            key = s[:4] + s[5:]
            if key != last:
                print("  t+%5.1fs %s" % (now, s), flush=True)
                last = key
            if forced is None and len(s) > 2 and s[2] == 2:
                racing_since = racing_since or now
                if now - racing_since > 1.5:
                    g.force_finish(laps)
                    forced = now
                    print("  t+%5.1fs forced finish, laps %s" % (now, laps), flush=True)
            if forced is not None and now - forced > watch:
                break
            if forced is None and now > 60:
                print("car never reached state 2")
                break
            time.sleep(0.1)
        print("after: gp+74h=%.4f laps gp+90h=%s" % (G.f32(g.h, g.gp + 0x74), struct.unpack("<3f", g.read(g.gp + 0x90, 12))))
        hdr = g.header()
        print("header:", hdr[:0x20], hdr[0x28:0x48], struct.unpack_from("<3i4f", hdr, 0x4C))
        print("gp+74h raw", g.read(g.gp + 0x74, 4).hex(), "hdr+58h raw", hdr[0x58:0x5C].hex())
        try:
            print("state object: state [+140h] =", g.menu_state(), "items:", g.menu_items())
        except OSError as e:
            print("no menu:", e)
        if os.path.exists(newp):
            print("new-phantom.mhk2:", G.phantom_info(newp))
        g.shot(os.path.join(os.path.dirname(g.dir), "shots", "explore2.png"))
    finally:
        g.kill()


if __name__ == "__main__":
    main()
