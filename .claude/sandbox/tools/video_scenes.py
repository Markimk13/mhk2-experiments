"""Find scene times in an OBS recording, as input for cut_video.py.

usage:
    video_scenes.py races RECORDING [--runs DIR]
        Lists the races that race_recorder.py recorded while the video ran, at their
        video times. A video filmed by `race_recorder.py --video`: from each race's
        "video_t" (the green light, to the millisecond) to its last race time; --runs is
        then the recorder's out dir (the video's parent folder by default). An OBS video
        (named after its start, "YYYY-MM-DD HH-MM-SS.mkv"): a race starts at the time its
        CSV was created minus about 1 s and ends when the CSV was last written. Also prints where the karts were
        closest to the player, a hint for scenes with opponents in the picture.
    video_scenes.py sheet RECORDING FROM TO [--step 1] [--out PNG]
        A contact sheet of the game picture from FROM to TO (MM:SS), one tile per
        --step seconds, each tile stamped with its video time. Use it to pick exact
        scene limits; sheets go to .claude/sandbox/video/.

The video is cropped to the game picture with the same cropdetect as cut_video.py.
"""
import argparse
import csv
import datetime
import glob
import json
import math
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cut_video import WORK, find_tool, parse_time, detect_crop  # noqa: E402

SANDBOX = Path(__file__).resolve().parent.parent
RUNS = SANDBOX / "runs" / "user"
CLASSES = ["50 cc", "100 cc", "150 cc", "200 cc", "250 cc", "Tuning"]
# track numbers as the recorder stores them (5 = Bergwerk: 250 cc championship 2 of 2026-11-26)
TRACKS = {0: "Moorhuhn X", 1: "Winter", 2: "Insel", 3: "Ägypten", 4: "Fabrik", 5: "Bergwerk", 6: "Burg", 7: "Sumpf"}


def mmss(s):
    tenths = round(max(0.0, s) * 10)
    return f"{tenths // 600}:{tenths % 600 / 10:04.1f}"


def video_start(path):
    m = re.search(r"(\d{4})-(\d\d)-(\d\d)[ _](\d\d)-(\d\d)-(\d\d)", Path(path).name)
    if not m:
        sys.exit("cannot read the start time from the file name (expected 'YYYY-MM-DD HH-MM-SS')")
    return datetime.datetime(*map(int, m.groups()))


def duration(ffprobe, video):
    out = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video],
                         capture_output=True, text=True, check=True).stdout
    return float(out.strip())


def busiest(csv_path, window=8):
    """Second of the race with the most karts within 12 units of the player over `window` s."""
    per_t = {}
    with open(csv_path, newline="") as f:
        for r in csv.DictReader(f):
            per_t.setdefault(round(float(r["t"]), 1), {})[int(r["kart"])] = (float(r["x"]), float(r["z"]))
    per_s = {}
    for t, karts in per_t.items():
        if 0 in karts:
            px, pz = karts[0]
            n = sum(1 for k, (x, z) in karts.items() if k and math.hypot(x - px, z - pz) < 12)
            per_s.setdefault(int(t), []).append(n)
    avg = {s: sum(v) / len(v) for s, v in per_s.items()}
    best = max(((sum(avg.get(s + j, 0) for j in range(window)), s) for s in avg if s > 8), default=(0, 0))
    return best[1], best[0] / window


def cmd_races(args):
    ffprobe = find_tool("ffprobe")
    if args.runs is None:
        folder = Path(args.video).resolve().parent
        args.runs = str(folder.parent if folder.name == "video" and (Path(str(folder / Path(args.video).stem) + ".json")).exists()
                        else RUNS)
    start = video_start(args.video)
    length = duration(ffprobe, args.video)
    end = start + datetime.timedelta(seconds=length)
    print(f"video {start:%H:%M:%S} - {end:%H:%M:%S} ({mmss(length)})")
    found = 0
    for js in sorted(glob.glob(str(Path(args.runs) / "*.json"))):
        csv_path = js[:-5] + ".csv"
        if not os.path.exists(csv_path):
            continue
        created = datetime.datetime.fromtimestamp(os.path.getctime(csv_path))
        written = datetime.datetime.fromtimestamp(os.path.getmtime(csv_path))
        if written < start or created > end:
            continue
        meta = json.load(open(js, encoding="utf-8"))
        if meta.get("video") == Path(args.video).name and "video_t" in meta:
            # filmed by race_recorder.py --video: race time 0 (the green light) to the millisecond
            v0 = meta["video_t"]
            with open(csv_path, "rb") as f:
                f.seek(max(0, os.path.getsize(csv_path) - 400))
                v1 = v0 + float(f.read().splitlines()[-1].split(b",")[0])
        else:
            v0 = (created - start).total_seconds() - 1
            v1 = (written - start).total_seconds()
        busy_s, busy_n = busiest(csv_path)
        cls = CLASSES[meta["class"]] if 0 <= meta.get("class", -1) < len(CLASSES) else f"class {meta.get('class')}"
        track = TRACKS.get(meta.get("track"), f"track {meta.get('track')}")
        champ = f" championship {meta['championship'] + 1} race {meta['championship_race'] + 1}" if meta.get("mode") == 1 else ""
        print(f"{mmss(v0):>7} - {mmss(v1):>7}  {cls:7} {track:11}{champ}  closest karts {mmss(v0 + busy_s)} ({busy_n:.1f} within 12)")
        found += 1
    if not found:
        print(f"no recorder runs in {args.runs} during the video")
    else:
        print(f"menus after the last race: {mmss(v1)} - {mmss(length)}")


def cmd_sheet(args):
    ffmpeg = find_tool("ffmpeg")
    t0, t1 = parse_time(args.start), parse_time(args.end)
    crop = detect_crop(ffmpeg, args.video, [(t0, t1, "")])
    n = int((t1 - t0) / args.step) + 1
    cols = 10
    rows = math.ceil(n / cols)
    out = args.out or str(WORK / f"sheet_{int(t0)}_{int(t1)}.png")
    WORK.mkdir(parents=True, exist_ok=True)
    vf = (f"fps=1/{args.step}:start_time=0,"
          + (f"crop={crop}," if crop else "")
          + "scale=200:-2,"
          + f"drawtext=fontfile='C\\:/Windows/Fonts/arialbd.ttf':text='%{{eif\\:(t+{t0})/60\\:d}}\\:%{{eif\\:mod(t+{t0}\\,60)\\:d\\:2}}'"
          + ":fontcolor=yellow:fontsize=14:x=2:y=2:box=1:boxcolor=black,"
          + f"tile={cols}x{rows}")
    subprocess.run([ffmpeg, "-v", "error", "-y", "-ss", f"{t0:.3f}", "-t", f"{t1 - t0 + 0.01:.3f}", "-i", args.video,
                    "-vf", vf, "-frames:v", "1", out], check=True)
    print(f"wrote {out} ({n} tiles; a tile shows the frame at its time, so give scene limits ~0.5 s of slack)")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("races")
    r.add_argument("video")
    r.add_argument("--runs", default=None, help="recorder out dir (default: the video's parent folder if "
                                                 "the video is in a recorder's video folder, else runs\\user)")
    s = sub.add_parser("sheet")
    s.add_argument("video")
    s.add_argument("start")
    s.add_argument("end")
    s.add_argument("--step", type=float, default=1.0)
    s.add_argument("--out")
    args = ap.parse_args()
    {"races": cmd_races, "sheet": cmd_sheet}[args.cmd](args)


if __name__ == "__main__":
    main()
