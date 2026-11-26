import sys, os, struct
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H
h = H.open_proc(0x0410)
gp = H.u32(h, 0x5E84EC)
cls = struct.unpack("<i", H.read(h, gp + 0x10, 4))[0]
cm = H.u32(h, 0x5E8520)
begin, end = H.u32(h, cm + 0x10), H.u32(h, cm + 0x14)
n = (end - begin) // 4 if begin else 0
print(f"class={cls} CarManager={cm:#x} cars={n}")
for i in range(n):
    car = H.u32(h, begin + 4 * i)
    raw = H.read(h, car, 0x340)
    f = lambda o: struct.unpack_from("<f", raw, o)[0]
    gears = [round(f(0x128 + 4 * k), 3) for k in range(5)]
    torque = [round(f(0x154 + 4 * k), 4) for k in range(4)]
    rpm = [round(f(0x144 + 4 * k), 1) for k in range(4)]
    print(f"  car[{i}] @ {car:#x}: mass={f(0x60):.1f} diff ratio={f(0x13C):.4f} gears={gears} rpm={rpm} torque={torque}")
    print(f"       -> class factor = {6.0 / f(0x13C):.4f} (stock diff ratio 6.0), torque1/1.4 = {f(0x154)/1.4:.4f}")
