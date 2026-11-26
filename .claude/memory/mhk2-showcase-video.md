---
name: mhk2-showcase-video
description: How the ~1 min showcase clip of the patch is made: filming with race_recorder.py --video (or OBS), scene times from the race recorder, cut_video.py, GitHub's 10 MB limit; what was wrong with the 2026-11-25 OBS recording
metadata:
  type: project
---

The user wants a clip of about 1 minute that shows what the patch adds (for the public repo's
README or a release). Plan (2026-11-25): the user re-records later; the processing is ready.

**Recording without OBS (since 2026-11-25):** `py .claude\sandbox\tools\race_recorder.py --video`
films the game window with ffmpeg's `gfxcapture` (Windows' window capture, as OBS's window capture:
only the game window, even when covered, no cursor, no focus) into `runs\user\video\<date time>.mkv`,
at the game's own size, and writes each race's `video_t` (second of the video at race time 0) into
the race's .json. Sync from ffmpeg's `-progress` (wall clock minus written video time, smallest
value); the time the file appears is ~2 s late because the encoder buffers. Tested on a sandbox
race (windowed test build, 1032x792): at `video_t` the game's clock shows 0:00:01; ~44 MB/min.
The real game in fullscreen works too (user's test 2026-11-25: 800x600, 60 fps, clean picture,
sync within ~30 ms, ~70 MB/min with AMF cqp 20/22). Since then `--quality high|normal|small`
(base value 20/24/28, default normal; any number works): measured on 30 s of that recording,
re-encoded with AMF: 20 → 79, 23 → 59, 26 → 43, 29 → 32, 32 → 23 MB/min (re-encoding a lossy
source inflates these by ~10 %). 20 and 23 look the same side by side; from 26 the sand gets
smoother, 29 is clearly softer in the background. The user asked for few levels and a default.
**The user's rules for a clip (2026-11-26):** at most ~20 s of settings, only the most important
ones; no track names in the labels ("we all know them"); few race clips (5), each 7-8 s rather
than many short ones; "Verbesserte Gegner" shows an opponent crossing a difficult part
(`tools/opp_ahead.py` finds opponents ahead of the player in curves/jumps; the Insel bridge in the
2026-11-26 clip); no scene where a computer kart shows a bug; **menus get one continuous
soundtrack** (mark every menu scene after the first with `+` in the scene list: the picture cuts,
the sound runs on; the clicks don't matter, but music jumping every few seconds disturbs).

Trap (2026-11-26): when the game closed in fullscreen, gfxcapture got no "capture item closed"
event, ffmpeg ignored 'q' and was killed after 10 s; the .mkv had no end (no duration, players
cannot jump). A stream copy repairs it without loss (`finish_mkv`); since then the recorder does it
by itself after a hard stop, and `merge_av.py` repairs unfinished .mkv/.m4a before merging (`--fix`
too). The 28-min recording of that day: picture and sound both stayed on the race clock (countdown
sound at all 9 starts within 20 ms; HUD clock = video time - video_t to 0.05 s through a 3:46 race).
Clip of that day: `video/cuts_2026-11-26.txt` (copied to `tools/cut_video_example.txt`), 15 scenes,
80 s at 800x600 30 fps (`--fps 30`), 9.3 MB. Track 5 is Bergwerk.

Trap (2026-11-25 23:31): an old recorder still ran in another terminal; both attached to the game
and both named their video by the same second, so two ffmpeg wrote one .mkv (timestamps jump). Since
then a named mutex (`Local\mhk2-race-recorder`) lets only one recorder run, and file names that
exist get " (2)".
Encoder: first that works of NVENC, AMF, QSV, libx264; on the user's laptop AMF (Radeon 610M runs
the display; NVENC of ffmpeg 9.1 needs NVIDIA driver ≥ 610, the laptop has 555.97).

**Sound:** `--audio` (separate file, the user's wish 2026-11-25: merge later if wanted) records only
the game's sound through Windows' process loopback (`procaudio.py`, ctypes COM: ActivateAudioInterfaceAsync
on "VAD\Process_Loopback"; ffmpeg cannot do it) into `<date time>.m4a` (AAC 192k, fragmented so it
survives a kill), on the wall clock with silence filled in from the packets' QPC stamps. The video's
.json gets `audio_offset`, races `audio_t`; `cut_video.py` takes the .m4a by itself. Tested in the
sandbox: sync of video and audio within ~10 ms, length right, cutting works; the content was silence,
because test games run with volume 0 (never play sound on the user's speakers in a test). The user
confirmed the real game's sound (2026-11-25), but the player showed no total time and could not
jump: a fragmented MP4 has no index. Since then the recorder rewrites the .m4a as a plain one at the
end (stream copy, audio packets bit-identical); `merge_av.py --fix` does it for a file of a killed
recorder. `merge_av.py VIDEO.mkv [--mp4]` / `--all` writes "<name> mit Ton.mkv" with picture and
sound (stream copy, sound cut to the video's length).

**Recording with OBS.** OBS, with `race_recorder.py` running next to the game so the races can be found
in the video. The 2026-11-25 recording (24 min, 637 MB, 960x540, 60 fps, colour range correct)
had the game only in a **300x224 corner** of the canvas: the canvas was much larger than the
game window and OBS scaled the whole canvas down. For the re-recording: Settings → Video, base and
output resolution = the game's window size; right-click the game source → Transform → Fit to
screen. Only the clip's scenes are needed: a few race moments and the menus (about 1½ min).
The recording lies untracked in the repository; it is never committed.

**Processing (no AI needed, deterministic: the same scene list gives a byte-identical file).**
1. `py .claude\sandbox\tools\video_scenes.py races RECORDING` lists the recorder's races at their
   video times (a `--video` file: from `video_t`; an OBS file: from its name's start time and
   the CSV file times, about ±1 s) and where karts were closest to the player.
2. `video_scenes.py sheet RECORDING FROM TO` makes a 1-second contact sheet; pick menu scenes
   from it with about 0.5 s slack (a tile shows the frame at its time; scenes cut on 3-second
   sheets came out wrong).
3. Write the scene list (`MM:SS-MM:SS label`), see `.claude/sandbox/tools/cut_video_example.txt`
   (the 2026-11-25 cut: 10 scenes, German labels).
4. `py .claude\sandbox\tools\cut_video.py RECORDING SCENES.txt --height 448` (height: twice the
   game picture there; for a full-size recording leave it out). Crops to the game picture,
   CAS sharpening 0.7, labels, two-pass H.264 to 9.5 MB.

**Why 10 MB:** GitHub takes videos of up to 10 MB in issues, PRs, release notes and the README
(free account). No video goes into git, the finished clip neither: the user keeps it locally as
`docs\showcase.mp4`, ignored through the checkout's `.git/info/exclude`
(not `.gitignore`, so nothing is committed). A commit of it (2026-11-26) was taken back before a
push, because every update would add ~9 MB to the history for good. Replace the file when a new
clip is made.

Tested on 2026-11-25: sharpening helps a little; AI upscaling (Real-ESRGAN) was not tried. It would
need a download and can invent letters in the small menu text. Related: [[mhk2-public-release]].
