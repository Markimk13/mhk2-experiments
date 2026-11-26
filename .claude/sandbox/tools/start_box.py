r"""Where a kart passes the start box of a track, from a race_recorder.py recording.

usage: start_box.py <recording.csv> [--kart K] [--track T] [--dat game\data\mhk2-00.dat]

A lap counts only when the kart enters the track's start box (a RotatedBoxArea with the
message "start" in level<T+1>\settings\objects\objects.txt), see the lap counting part of
.claude/memory/mhk2-tracks-and-championships.md. This script reads that box from the game
archive (read-only) and prints every time the kart crosses the plane of the box: the place
across the box and the height above its centre, in box units. "inside" means both are within
half the box size. A pass far outside the box (beside or above it) does not count the lap.

--track defaults to the "track" value of the recording's .json. --kart defaults to 0 (player 1).
"""
import argparse
import csv
import json
import math
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import datlist      # noqa: E402
import mhk2crypt    # noqa: E402


def start_boxes(dat, track):
    """[(position, rotation w x y z, size)] of the boxes with message "start" of track index `track`"""
    want = f"data\\mk2\\level{track + 1:02d}\\settings\\objects\\objects.txt"
    _, _, _, entries = datlist.read_index(dat)
    for name, off, size, _ in entries:
        if name.lower() == want:
            with open(dat, "rb") as f:
                f.seek(off)
                text = mhk2crypt.decrypt(f.read(size)).decode("cp1252")
            break
    else:
        sys.exit(f"{want} not in {dat}")
    boxes = []
    for block in text.split("DYNAMIC OBJECT START"):
        if '"class RotatedBoxArea"' in block and re.search(r'"message"\s+"start"', block):
            nums = {k: [float(v) for v in re.search(rf'"{k}"\s+([-\d. ]+)', block).group(1).split()]
                    for k in ("position", "rotation", "size")}
            boxes.append((nums["position"], nums["rotation"], nums["size"]))
    return boxes


def to_local(pos, rot):
    """world -> box frame; objects.txt stores the rotation as w x y z (a kart's yaw is (w, 0, y, 0))"""
    w, x, y, z = rot
    n = math.sqrt(w * w + x * x + y * y + z * z)
    w, x, y, z = w / n, x / n, y / n, z / n
    r = [[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
         [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
         [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]]
    return lambda p: [sum(r[i][j] * (p[i] - pos[i]) for i in range(3)) for j in range(3)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("csv")
    ap.add_argument("--kart", default="0")
    ap.add_argument("--track", type=int)
    ap.add_argument("--dat", default=os.path.join(HERE, "..", "game", "data", "mhk2-00.dat"))
    a = ap.parse_args()
    track = a.track
    if track is None:
        with open(os.path.splitext(a.csv)[0] + ".json") as f:
            track = json.load(f)["track"]
    for pos, rot, size in start_boxes(a.dat, track):
        print(f"start box of track {track}: centre {pos}, size {size} (across, height, along)")
        loc = to_local(pos, rot)
        prev = None
        with open(a.csv) as f:
            for row in csv.DictReader(f):
                if row["kart"] != a.kart:
                    continue
                p = (float(row["x"]), float(row["y"]), float(row["z"]))
                q = loc(p)
                if prev is not None and prev[2] * q[2] < 0:
                    inside = abs(q[0]) <= size[0] / 2 and abs(q[1]) <= size[1] / 2
                    print(f"  {float(row['t']):8.3f} s  across {q[0]:8.2f}  height {q[1]:7.2f}  "
                          f"{'inside' if inside else 'OUTSIDE'}  pathprog {row['pathprog']}  cstate {row['cstate']}")
                prev = q


if __name__ == "__main__":
    main()
