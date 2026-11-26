"""Put the sound of `race_recorder.py --audio` under the video of `--video`: one file with both.

usage:
    merge_av.py VIDEO.mkv [VIDEO2.mkv ...] [--mp4] [-o OUT]
        For each video, takes the .m4a and the offset its .json names ("audio", "audio_offset")
        and writes "<video name> mit Ton.mkv" next to it (--mp4: .mp4, plays in more places,
        e.g. a browser). Nothing is encoded again (stream copy): fast and without any loss.
        The sound is cut to the length of the video. -o names the output (one video only).
    merge_av.py --all [FOLDER]
        Every video in FOLDER (default: runs\\user\\video) that has sound and no merged file yet.
    merge_av.py --fix FILE.m4a|FILE.mkv [...]
        Repairs a file the recorder could not finish (recorder or ffmpeg killed): an .m4a left
        fragmented, an .mkv without its end. Afterwards players show the total time and can jump
        in it. Stream copy, same data, no loss. Merging repairs such files by itself first.

Needs ffmpeg (winget install Gyan.FFmpeg).
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from procaudio import find_ffmpeg, finish_m4a  # noqa: E402
from race_recorder import finish_mkv  # noqa: E402


def unfinished(ffmpeg, path):
    """True if the file has no duration: ffmpeg was killed before it could close it."""
    ffprobe = str(Path(ffmpeg).with_name("ffprobe" + Path(ffmpeg).suffix))
    r = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)],
                       capture_output=True, text=True)
    return r.stdout.strip() in ("", "N/A")

DEFAULT_DIR = Path(__file__).resolve().parent.parent / "runs" / "user" / "video"
SUFFIX = " mit Ton"


def merge(ffmpeg, video, out=None, mp4=False):
    video = Path(video)
    side = video.with_suffix(".json")
    if not side.exists():
        print(f"{video.name}: no .json next to it (not a recorder video?)")
        return False
    meta = json.loads(side.read_text(encoding="utf-8"))
    if not meta.get("audio"):
        print(f"{video.name}: recorded without --audio")
        return False
    audio = video.with_name(meta["audio"])
    if not audio.exists():
        print(f"{video.name}: sound file {audio.name} is missing")
        return False
    for f, fix in ((video, finish_mkv), (audio, finish_m4a)):
        if unfinished(ffmpeg, f):
            print(f"{f.name}: not finished by the recorder, repairing first: {'ok' if fix(str(f), ffmpeg) else 'FAILED'}")
    offset = float(meta.get("audio_offset", 0.0))
    out = Path(out) if out else video.with_name(video.stem + SUFFIX + (".mp4" if mp4 else ".mkv"))
    # offset > 0: the sound started before the video, skip its beginning; < 0: delay it
    audio_in = ["-ss", f"{offset:.3f}", "-i", str(audio)] if offset >= 0 else \
               ["-itsoffset", f"{-offset:.3f}", "-i", str(audio)]
    cmd = [ffmpeg, "-v", "error", "-stats", "-y", "-i", str(video), *audio_in,
           "-map", "0:v", "-map", "1:a", "-c", "copy", "-shortest"]
    if mp4 or out.suffix.lower() == ".mp4":
        cmd += ["-movflags", "+faststart"]
    r = subprocess.run(cmd + [str(out)])
    if r.returncode != 0:
        print(f"{video.name}: ffmpeg failed")
        return False
    print(f"wrote {out} (sound from {offset:.3f} s of {audio.name})")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*")
    ap.add_argument("-o", "--out")
    ap.add_argument("--mp4", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--fix", action="store_true")
    a = ap.parse_args()
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        sys.exit("needs ffmpeg: winget install Gyan.FFmpeg")

    if a.fix:
        for f in a.files:
            fix = finish_mkv if f.lower().endswith(".mkv") else finish_m4a
            print(("fixed " if fix(f, ffmpeg) else "could not fix ") + f)
        return
    if a.all:
        folder = Path(a.files[0]) if a.files else DEFAULT_DIR
        videos = [v for v in sorted(folder.glob("*.mkv")) if not v.stem.endswith(SUFFIX)
                  and not v.with_name(v.stem + SUFFIX + (".mp4" if a.mp4 else ".mkv")).exists()]
        if not videos:
            print(f"nothing to merge in {folder}")
        for v in videos:
            merge(ffmpeg, v, mp4=a.mp4)
        return
    if not a.files:
        ap.error("name a video, or use --all or --fix")
    if a.out and len(a.files) > 1:
        ap.error("-o works with one video only")
    ok = all([merge(ffmpeg, v, a.out, a.mp4) for v in a.files])
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
