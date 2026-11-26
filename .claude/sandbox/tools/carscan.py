"""Snapshot helpers for finding live kart state in the running sandbox game.

  carscan.py frame            print the player's render-frame matrix (via car+0x44 -> +0x30)
  carscan.py diff <seconds>   dump car[0] floats that changed between two snapshots
"""
import os
import struct
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H


def cars(h):
    cm = H.u32(h, 0x5E8520)
    b, e = H.u32(h, cm + 0x10), H.u32(h, cm + 0x14)
    return cm, [H.u32(h, b + 4 * i) for i in range((e - b) // 4)]


def frame_ptr(h, car):
    obj = H.u32(h, car + 0x44)
    return H.u32(h, obj + 0x30)


def main():
    h = H.open_proc(0x0410)
    cm, cs = cars(h)
    car = cs[0]
    if sys.argv[1] == "frame":
        f = frame_ptr(h, car)
        m = struct.unpack("<16f", H.read(h, f + 0x10, 64))
        print(f"car={car:#x} frame={f:#x} race time={struct.unpack('<f', H.read(h, cm + 0x20, 4))[0]:.3f}")
        for r in range(4):
            print("   ", ["%10.4f" % v for v in m[4 * r:4 * r + 4]])
    elif sys.argv[1] == "diff":
        size = 0x360
        a = H.read(h, car, size)
        time.sleep(float(sys.argv[2]))
        b = H.read(h, car, size)
        for o in range(0, size, 4):
            if a[o:o + 4] != b[o:o + 4]:
                fa, fb = struct.unpack_from("<f", a, o)[0], struct.unpack_from("<f", b, o)[0]
                ia, ib = struct.unpack_from("<i", a, o)[0], struct.unpack_from("<i", b, o)[0]
                print(f"  +{o:#05x}: {fa:14.6g} -> {fb:14.6g}   ({ia} -> {ib})")


if __name__ == "__main__":
    main()
