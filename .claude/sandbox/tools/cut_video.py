"""Cut a long gameplay recording into a short showcase clip with ffmpeg.

Usage:
    py .claude\\sandbox\\tools\\cut_video.py RECORDING CUTS.txt [-o OUT.mp4]
        [--crop auto|W:H:X:Y] [--height N] [--fps N] [--target-mb 9.5]
        [--no-audio] [--no-labels]

CUTS.txt, one scene per line ('#' starts a comment):
    MM:SS-MM:SS  Label shown at the bottom of the scene
    1:02:05.5-1:02:12  Another scene (H:MM:SS and fractions work too)
    + 27:06-27:11  A leading '+': the picture cuts, the sound does not

A scene with '+' takes its sound from where the previous scene's sound ended, without a
fade, so a run of menu scenes has one continuous soundtrack (the user's rule, 2026-11-26:
in the menus the clicks don't matter, but music that jumps every few seconds disturbs).
Mark every menu scene after the first with '+'.

The scenes are joined in file order, every scene gets its label (if any), and the
result is encoded with two-pass H.264 so it lands just under --target-mb (GitHub
takes videos of up to 10 MB in issues, PRs, release notes and the README).

--crop auto finds the game picture with ffmpeg's cropdetect (the 2026-11-25
recording had the game only in a 300x225 corner of a 960x540 canvas). --height
scales the result (default: keep the cropped size; even numbers only). --sharpen
(default 0.7) runs ffmpeg's CAS sharpening after the scaling; it helps the small
game picture a little, 0 turns it off.

Needs ffmpeg and ffprobe on PATH (winget install Gyan.FFmpeg). Work files go into
.claude/sandbox/video/ (ignored by git).
"""
import argparse
import collections
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

SANDBOX = Path(__file__).resolve().parent.parent
WORK = SANDBOX / "video"
FONT = "C\\:/Windows/Fonts/arialbd.ttf"
WINGET_LINKS = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Links"


def find_tool(name):
    path = shutil.which(name) or (str(WINGET_LINKS / f"{name}.exe") if (WINGET_LINKS / f"{name}.exe").exists() else None)
    if not path:
        sys.exit(f"{name} not found; install it with: winget install Gyan.FFmpeg")
    return path


def parse_time(text):
    parts = [float(p) for p in text.strip().split(":")]
    seconds = 0.0
    for p in parts:
        seconds = seconds * 60 + p
    return seconds


def read_cuts(path):
    cuts = []
    for n, line in enumerate(Path(path).read_text(encoding="utf-8-sig").splitlines(), 1):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        m = re.match(r"^(\+?)\s*([\d:.]+)\s*-\s*([\d:.]+)\s*(.*)$", line)
        if not m:
            sys.exit(f"{path}:{n}: expected '[+] MM:SS-MM:SS label', got: {line}")
        start, end = parse_time(m.group(2)), parse_time(m.group(3))
        if end <= start:
            sys.exit(f"{path}:{n}: end is not after start")
        if m.group(1) and not cuts:
            sys.exit(f"{path}:{n}: '+' needs a scene before it")
        cuts.append((start, end, m.group(4).strip(), bool(m.group(1))))
    if not cuts:
        sys.exit(f"{path}: no scenes")
    return cuts


def probe(ffprobe, video):
    out = subprocess.run(
        [ffprobe, "-v", "error", "-show_entries", "stream=codec_type,width,height:format=duration",
         "-of", "default=nw=1", video], capture_output=True, text=True, check=True).stdout
    info = {"audio": "codec_type=audio" in out}
    for key in ("width", "height", "duration"):
        m = re.search(rf"^{key}=([\d.]+)", out, re.M)
        info[key] = float(m.group(1)) if m else 0.0
    return info


def detect_crop(ffmpeg, video, cuts):
    """Most frequent cropdetect result over a few frames of every scene."""
    votes = collections.Counter()
    for start, end, *_ in cuts:
        r = subprocess.run(
            [ffmpeg, "-hide_banner", "-ss", f"{start:.3f}", "-t", f"{min(end - start, 5):.3f}", "-i", video,
             "-vf", "fps=2,cropdetect=limit=24:round=2:reset=1", "-f", "null", "-"],
            capture_output=True, text=True)
        votes.update(m for m in re.findall(r"crop=(\d+:\d+:\d+:\d+)", r.stderr))
    if not votes:
        return None
    crop = votes.most_common(1)[0][0]
    w, h, x, y = map(int, crop.split(":"))
    return f"{w - w % 2}:{h - h % 2}:{x}:{y}"


def drawtext_escape(text):
    return text.replace("\\", "\\\\").replace("'", "’").replace(":", "\\:").replace("%", "\\%")


def build_filter(cuts, crop, height, fps, audio, labels, sharpen=0.0, audio_in="0:a", audio_offset=0.0):
    chains, inputs = [], []
    a_end = None
    for i, (start, end, label, joined) in enumerate(cuts):
        v = f"[0:v]trim=start={start:.3f}:end={end:.3f},setpts=PTS-STARTPTS"
        if crop:
            v += f",crop={crop}"
        if height:
            v += f",scale=-2:{height}:flags=lanczos"
        if sharpen:
            v += f",cas=strength={sharpen}"
        if fps:
            v += f",fps={fps}"
        if labels and label:
            v += (f",drawtext=fontfile='{FONT}':text='{drawtext_escape(label)}'"
                  # shrink long labels so they fit the width (Arial bold: about 0.6 em per letter)
                  f":fontcolor=white:fontsize='min(h/14,w*0.9/{0.6 * len(label):.2f})'"
                  f":box=1:boxcolor=black@0.55:boxborderw=6"
                  f":x=(w-tw)/2:y=h-th-h/20"
                  f":alpha='min(1,min(t/0.3,({end - start:.3f}-t)/0.3))'")
        chains.append(v + f",setsar=1[v{i}]")
        inputs.append(f"[v{i}]")
        if audio:
            # '+': the sound runs on from the previous scene's end (same length as this scene's picture)
            a0 = a_end if joined else start + audio_offset
            a1 = a0 + (end - start)
            a_end = a1
            nxt_joined = i + 1 < len(cuts) and cuts[i + 1][3]
            fades = ([] if joined else ["afade=t=in:d=0.15"]) + \
                    ([] if nxt_joined else [f"afade=t=out:st={max(0, end - start - 0.15):.3f}:d=0.15"])
            chains.append(f"[{audio_in}]atrim=start={a0:.3f}:end={a1:.3f},asetpts=PTS-STARTPTS"
                          + "".join("," + f for f in fades) + f"[a{i}]")
            inputs.append(f"[a{i}]")
    chains.append("".join(inputs) + f"concat=n={len(cuts)}:v=1:a={1 if audio else 0}" + ("[v][a]" if audio else "[v]"))
    return ";".join(chains)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("video")
    ap.add_argument("cuts")
    ap.add_argument("-o", "--out", default=str(WORK / "showcase.mp4"))
    ap.add_argument("--crop", default="auto", help="auto, none, or W:H:X:Y")
    ap.add_argument("--height", type=int, default=0, help="output height (0 = cropped size)")
    ap.add_argument("--fps", type=int, default=0, help="output frame rate (0 = like the recording)")
    ap.add_argument("--sharpen", type=float, default=0.7,
                    help="CAS sharpening after scaling, 0..1 (0 = off; labels stay unsharpened)")
    ap.add_argument("--target-mb", type=float, default=9.5)
    ap.add_argument("--audio-kbps", type=int, default=96)
    ap.add_argument("--no-audio", action="store_true")
    ap.add_argument("--no-labels", action="store_true")
    args = ap.parse_args()

    ffmpeg, ffprobe = find_tool("ffmpeg"), find_tool("ffprobe")
    WORK.mkdir(parents=True, exist_ok=True)
    video = str(Path(args.video).resolve())
    cuts = read_cuts(args.cuts)
    info = probe(ffprobe, video)
    for start, end, *_ in cuts:
        if end > info["duration"] + 0.5:
            sys.exit(f"scene {start:.1f}-{end:.1f} s goes past the end ({info['duration']:.1f} s)")
    # race_recorder.py --audio: the sound is a separate .m4a; the video's .json says where it lines up
    extra_inputs, audio_in, audio_offset = [], "0:a", 0.0
    side = Path(video).with_suffix(".json")
    if not info["audio"] and side.exists():
        meta = json.loads(side.read_text(encoding="utf-8"))
        sound = Path(video).with_name(meta.get("audio", "")) if meta.get("audio") else None
        if sound and sound.exists():
            extra_inputs, audio_in, audio_offset = ["-i", str(sound)], "1:a", float(meta.get("audio_offset", 0.0))
            info["audio"] = True
            print(f"sound: {sound.name} from {audio_offset:.3f} s")
    audio = info["audio"] and not args.no_audio

    crop = None
    if args.crop == "auto":
        crop = detect_crop(ffmpeg, video, cuts)
        if crop and crop == f"{int(info['width'])}:{int(info['height'])}:0:0":
            crop = None
        print(f"crop: {crop or 'none needed'}")
    elif args.crop != "none":
        crop = args.crop

    total = sum(end - start for start, end, *_ in cuts)
    budget_kbit = args.target_mb * 8 * 1000 * 0.97  # MB as GitHub counts them, 3 % container overhead
    video_kbps = int(budget_kbit / total - (args.audio_kbps if audio else 0))
    if video_kbps < 200:
        sys.exit(f"{total:.0f} s do not fit in {args.target_mb} MB; cut shorter or raise --target-mb")
    print(f"{len(cuts)} scenes, {total:.1f} s, video {video_kbps} kbit/s")

    graph = build_filter(cuts, crop, args.height, args.fps, audio, not args.no_labels, args.sharpen,
                         audio_in, audio_offset)
    maps = ["-map", "[v]"] + (["-map", "[a]"] if audio else [])
    common = [ffmpeg, "-hide_banner", "-v", "error", "-stats", "-y", "-i", video, *(extra_inputs if audio else []),
              "-filter_complex", graph, *maps,
              "-c:v", "libx264", "-preset", "slow", "-b:v", f"{video_kbps}k", "-pix_fmt", "yuv420p",
              "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
              "-passlogfile", str(WORK / "x264pass")]
    subprocess.run(common + ["-pass", "1", "-an", "-f", "null", "-"], check=True)
    audio_opts = ["-c:a", "aac", "-b:a", f"{args.audio_kbps}k"] if audio else []
    subprocess.run(common + ["-pass", "2", *audio_opts, "-movflags", "+faststart", args.out], check=True)
    size = Path(args.out).stat().st_size
    print(f"wrote {args.out}: {size / 1e6:.2f} MB")
    if size > 10e6:
        print("warning: over GitHub's 10 MB limit; lower --target-mb")


if __name__ == "__main__":
    main()
