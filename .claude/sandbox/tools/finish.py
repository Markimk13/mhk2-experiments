import sys, os, struct, ctypes
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import harness as H
h = H.open_proc()
cm = H.u32(h, 0x5E8520)
begin = H.u32(h, cm + 0x10)
car = H.u32(h, begin)
raw = H.read(h, car + 0x258, 16)
print("before: laps", struct.unpack("<3f", raw[:12]), "lap counter", struct.unpack("<i", raw[12:])[0], "state", H.u32(h, car + 0x2D0))
laps = [float(x) for x in sys.argv[1:4]]
n = ctypes.c_size_t()
data = struct.pack("<3fi", *laps, 3)
H.kernel32.WriteProcessMemory(h, ctypes.c_void_p(car + 0x258), data, len(data), ctypes.byref(n))
print("forced finish with laps", laps)
