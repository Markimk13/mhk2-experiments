"""Wait for a race to load, skip the intro, wait for the green light, then force the player's finish."""
import sys, os, struct, time, ctypes
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H

def cars(h):
    cm = H.u32(h, 0x5E8520)
    if not cm:
        return []
    b, e = H.u32(h, cm + 0x10), H.u32(h, cm + 0x14)
    return [H.u32(h, b + 4 * i) for i in range((e - b) // 4)] if b else []

h = H.open_proc()
laps = [float(x) for x in sys.argv[1:4]]
t0 = time.time()
while time.time() - t0 < 60:
    try:
        cs = cars(h)
        if cs and H.u32(h, cs[0] + 0x264) == 0:
            break
    except OSError:
        pass
    time.sleep(0.5)
else:
    raise SystemExit("no race loaded")
print(f"race loaded after {time.time()-t0:.1f}s, cars={len(cs)}")
time.sleep(4.0)
H.keys(["enter"])                       # skip the intro camera
t0 = time.time()
while time.time() - t0 < 30:
    if H.u32(h, cars(h)[0] + 0x2D0) == 2:
        break
    time.sleep(0.2)
else:
    raise SystemExit("race did not start")
print(f"green light after {time.time()-t0:.1f}s")
time.sleep(1.5)
car = cars(h)[0]
n = ctypes.c_size_t()
data = struct.pack("<3fi", *laps, 3)
H.kernel32.WriteProcessMemory(h, ctypes.c_void_p(car + 0x258), data, len(data), ctypes.byref(n))
print("forced finish, laps", laps)
