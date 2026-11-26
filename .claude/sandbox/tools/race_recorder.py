"""Record the user's own races: every kart, every frame (read-only, next to the running game).

usage: race_recorder.py [out dir] [--exe MHK2-XXL.exe] [--once] [--video [--quality normal]] [--audio]

Waits for the game (process name --exe), then for each race writes
  <out dir>\\<date>_<time>_c<class>_t<track>.csv   one row per kart per game frame
  <out dir>\\<date>_<time>_c<class>_t<track>.json  class, track, mode, championship, tuning values, characters
Default out dir: ..\\runs\\user (ignored by git).

It only reads the game's memory (OpenProcess with read rights): no input, no focus, no writes,
so it can run while the user plays. The race object lives on between races, so a race ends
when its clock jumps back or its list of cars changes; a pause or the menu just stops the
clock. Columns:
  t        race time (s)              kart     index in the race (0 = player 1)
  x y z    position                   vx vy vz velocity
  prog     the kart's progress along the track (laps, fractional), the value the AI compares
  thr brk steer   the computer kart's controller outputs (empty for human karts)
  item     the power-up the kart holds (car+270h, -1 = none; the AI decides from it when to use one)
  stuck    a computer kart's stuck check (controller +9Ch): 0 driving, 1 backing out, 2 trying again
  moved    the distance it has summed up in the current check (controller +90h)
  cstate ctimer   the car's state (car+29Ch; 0 normal, other values for crashes, power-ups, ...)
           and the timer at car+2D4h
  lat      the kart's place across the road as the path planner counts it (car+22Ch; 0.5 = middle)
  pathprog the kart's place along the track path (car+224h, 0..1; on Sumpf half a lap behind prog)
--once stops after the first race.

--video also films the game window with ffmpeg (on PATH or from winget) while the game runs,
menus included, at the game's own resolution:
  <out dir>\\video\\<YYYY-MM-DD HH-MM-SS>.mkv   (OBS-style name: video_scenes.py and cut_video.py take it)
  <out dir>\\video\\<YYYY-MM-DD HH-MM-SS>.json  the capture's start time to the millisecond
and every race's .json gets "video" (the file) and "video_t" (second of the video at race time 0).
It uses Windows' window capture (ffmpeg's gfxcapture, as OBS's window capture): only the game
window, also while other windows cover it, no mouse cursor, no input, no focus. H.264 by the first
encoder that works: NVIDIA NVENC, AMD AMF, Intel Quick Sync, else libx264 on the CPU (on the
user's laptop 2026-11-25: AMF; NVENC of ffmpeg 9.1 needs NVIDIA driver 610 or newer).
--quality high|normal|small or a base value (lower = better, bigger; default normal). Each encoder
gets its own setting from the base value: AMF qp_i/qp_p/qp_b = q/q+2/q+4, NVENC cq q+1, QSV q+2,
libx264 crf q. The real game at 800x600, AMF, 30 s re-encoded from a "high" recording (2026-11-25):
  high   20   ~70-80 MB per minute   no visible loss
  normal 24   ~50 MB                 looks the same as high side by side
  small  28   ~35 MB                 sand and grass textures a bit smoother
  (26: 43 MB, 29: 32 MB, 32: 23 MB and clearly soft) If the game makes a new window (resolution change), a new file starts. MKV,
so a file stays playable if the recorder is killed. Sync: at "video_t" the game's clock shows
0:00:00 to 0:00:03 (sandbox race and the user's fullscreen races).

--audio records the game's sound, and only the game's (Windows' process loopback, procaudio.py;
no chat, no notifications), from attaching to the game until it ends, as a separate file:
  <out dir>\\video\\<YYYY-MM-DD HH-MM-SS>.m4a         AAC 192 kbit/s, 48 kHz stereo (fragmented while
                                                     recording, made seekable at the end)
  <out dir>\\video\\<YYYY-MM-DD HH-MM-SS>.audio.json  its start time to the millisecond
The file runs on the wall clock (silence where the game plays nothing). Every video's .json gets
"audio" and "audio_offset" (second of the audio at second 0 of the video), every race "audio" and
"audio_t"; cut_video.py takes the sound from the .m4a by itself. One file with picture and sound:
merge_av.py VIDEO.mkv (or --all), no re-encoding.
"""
import ctypes
import ctypes.wintypes as W
import datetime
import json
import os
import shutil
import struct
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
k32 = ctypes.WinDLL("kernel32", use_last_error=True)
u32 = ctypes.WinDLL("user32", use_last_error=True)
READ_ACCESS = 0x0010 | 0x0400        # PROCESS_VM_READ | PROCESS_QUERY_INFORMATION

RACE = 0x005E8520                    # race object: +10h/+14h vector of the cars, +20h race time
GP = 0x005E84EC                      # GameParameters
AI_VTABLE = 0x00598C94               # the computer karts' controller class (constructor 0x43ABE0)


class PE32(ctypes.Structure):
    _fields_ = [("dwSize", W.DWORD), ("cntUsage", W.DWORD), ("th32ProcessID", W.DWORD),
                ("th32DefaultHeapID", ctypes.c_void_p), ("th32ModuleID", W.DWORD), ("cntThreads", W.DWORD),
                ("th32ParentProcessID", W.DWORD), ("pcPriClassBase", ctypes.c_long), ("dwFlags", W.DWORD),
                ("szExeFile", ctypes.c_char * 260)]


def find_pid(name):
    snap = k32.CreateToolhelp32Snapshot(2, 0)
    e = PE32()
    e.dwSize = ctypes.sizeof(PE32)
    ok = k32.Process32First(snap, ctypes.byref(e))
    pid = None
    while ok:
        if e.szExeFile.decode("latin-1").lower() == name.lower():
            pid = e.th32ProcessID
        ok = k32.Process32Next(snap, ctypes.byref(e))
    k32.CloseHandle(snap)
    return pid


class Proc:
    def __init__(self, pid):
        self.h = k32.OpenProcess(READ_ACCESS, False, pid)
        if not self.h:
            raise OSError("cannot open process %d" % pid)
        self.buf = {}

    def read(self, addr, n):
        b = ctypes.create_string_buffer(n)
        got = ctypes.c_size_t()
        if not addr or not k32.ReadProcessMemory(self.h, ctypes.c_void_p(addr), b, n, ctypes.byref(got)):
            return None
        return b.raw

    def u32(self, addr):
        r = self.read(addr, 4)
        return struct.unpack("<I", r)[0] if r else 0

    def i32(self, addr):
        r = self.read(addr, 4)
        return struct.unpack("<i", r)[0] if r else 0

    def f32(self, addr):
        r = self.read(addr, 4)
        return struct.unpack("<f", r)[0] if r else 0.0

    def alive(self):
        code = W.DWORD()
        return k32.GetExitCodeProcess(self.h, ctypes.byref(code)) and code.value == 259


def game_window(pid):
    """The game's main window: its largest visible top-level window (the developer dialogs are hidden)."""
    best = [0, 0]
    proc = ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)

    def cb(hwnd, _):
        owner = W.DWORD()
        u32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and u32.IsWindowVisible(hwnd):
            r = W.RECT()
            u32.GetClientRect(hwnd, ctypes.byref(r))
            area = (r.right - r.left) * (r.bottom - r.top)
            if area > best[1]:
                best[:] = [hwnd, area]
        return True

    u32.EnumWindows(proc(cb), 0)
    return best[0] if best[1] >= 320 * 240 else 0


def finish_mkv(path, ffmpeg):
    """Give an .mkv that ffmpeg could not close (killed) its end and index: stream copy into a new
    file, which replaces the old one only if ffmpeg succeeded. Same frames, no re-encoding."""
    tmp = path[:-4] + ".repair.mkv"
    subprocess.run([ffmpeg, "-v", "error", "-y", "-i", path, "-map", "0", "-c", "copy", tmp],
                   capture_output=True, creationflags=NO_WINDOW)
    if os.path.exists(tmp) and os.path.getsize(tmp) > 0.9 * os.path.getsize(path):
        os.replace(tmp, path)               # "File ended prematurely" makes the return code 0 or not; size decides
        return True
    if os.path.exists(tmp):
        os.remove(tmp)
    return False


def free_base(folder, stamp, exts):
    """folder\\stamp, or folder\\stamp (2), (3), ... if a file with one of `exts` exists already:
    a recorder never writes into another one's file."""
    base, n = os.path.join(folder, stamp), 1
    while any(os.path.exists(base + e) for e in exts):
        n += 1
        base = os.path.join(folder, "%s (%d)" % (stamp, n))
    return base


def one_recorder_only():
    """Two recorders on one game film it twice and record every race twice (seen 2026-11-25: an old
    recorder still ran in another terminal). A named mutex lets only one run; returns its handle."""
    k32.CreateMutexW.restype = ctypes.c_void_p
    h = k32.CreateMutexW(None, False, "Local\\mhk2-race-recorder")
    if ctypes.get_last_error() == 183:                 # ERROR_ALREADY_EXISTS
        sys.exit("another race_recorder.py is running already (look in your other terminals); end it with Ctrl+C first")
    return h


def find_ffmpeg():
    path = shutil.which("ffmpeg")
    winget = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Links", "ffmpeg.exe")
    return path or (winget if os.path.exists(winget) else None)


# --quality: a base value q, lower = better and bigger (constant quality; the clip is compressed
# again by cut_video.py anyway). Sizes and how they look: see the module doc.
QUALITY = {"high": 20, "normal": 24, "small": 28}
DEFAULT_QUALITY = "normal"
NO_WINDOW = 0x08000000                 # CREATE_NO_WINDOW: ffmpeg gets no console, so it can never take the focus


def encoders(q):
    """H.264 encoders in the order they are tried, each with its settings for base value q."""
    return [
        ("h264_nvenc", ["-preset", "p5", "-tune", "hq", "-rc", "vbr", "-cq", str(q + 1), "-b:v", "0"]),
        ("h264_amf", ["-quality", "quality", "-rc", "cqp", "-qp_i", str(q), "-qp_p", str(q + 2), "-qp_b", str(q + 4)]),
        ("h264_qsv", ["-preset", "medium", "-global_quality", str(q + 2)]),
        ("libx264", ["-preset", "veryfast", "-crf", str(q)]),
    ]


def parse_quality(text):
    """'high', 'normal', 'small' or a base value 0..51."""
    if text in QUALITY:
        return QUALITY[text]
    if text.isdigit() and 0 <= int(text) <= 47:
        return int(text)
    sys.exit("--quality: high, normal, small or a number 0..47 (lower = better, bigger)")


def pick_encoder(ffmpeg, q=QUALITY[DEFAULT_QUALITY]):
    for name, opts in encoders(q):
        r = subprocess.run([ffmpeg, "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=640x480:r=60:d=0.2",
                            "-pix_fmt", "yuv420p", "-c:v", name, *opts, "-f", "null", "-"],
                           capture_output=True, creationflags=NO_WINDOW)
        if r.returncode == 0:
            return name, opts
    return None


class VideoCapture(threading.Thread):
    """Films the game window with ffmpeg as long as the game runs; a new file per game window."""

    def __init__(self, ffmpeg, encoder, pid, out_dir, audio=None):
        super().__init__(daemon=True)
        self.ffmpeg, self.encoder, self.pid, self.out_dir = ffmpeg, encoder, pid, out_dir
        self.audio = audio           # a running procaudio.ProcessAudio of the same game, or None
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.proc = None
        self.file = None
        self.started = None          # time.time() when ffmpeg delivered its first frame (about)

    def position(self, wall):
        """(file name, second in that file) of the wall clock time `wall`, or None."""
        with self.lock:
            if self.file and self.started and wall >= self.started:
                return os.path.basename(self.file), round(wall - self.started, 3)
        return None

    def run(self):
        os.makedirs(self.out_dir, exist_ok=True)
        fails = 0
        while not self.stop_event.is_set():
            hwnd = game_window(self.pid)
            if not hwnd:
                if self.stop_event.wait(0.5):
                    break
                continue
            ok = self.film(hwnd)
            fails = 0 if ok else fails + 1
            if fails >= 5:
                print("   video: ffmpeg failed 5 times in a row, filming stopped (see the .log)", flush=True)
                return
            self.stop_event.wait(1.0 if ok else 3.0)

    def film(self, hwnd):
        now = time.time()
        stamp = datetime.datetime.fromtimestamp(now).strftime("%Y-%m-%d %H-%M-%S")
        base = free_base(self.out_dir, stamp, (".mkv", ".json", ".log"))
        name, opts = self.encoder
        cmd = [self.ffmpeg, "-hide_banner", "-nostats", "-loglevel", "info", "-y",
               "-progress", "pipe:1", "-stats_period", "0.2",
               "-filter_complex", f"gfxcapture=hwnd={hwnd}:capture_cursor=0:max_framerate=60:resize_mode=scale_aspect,"
                                  "hwdownload,format=bgra,format=yuv420p",
               "-c:v", name, *opts, "-r", "60", "-fps_mode", "cfr",
               "-colorspace", "bt709", "-color_primaries", "bt709", "-color_trc", "bt709", "-color_range", "tv",
               base + ".mkv"]
        log = open(base + ".log", "w", encoding="utf-8")
        log.write(" ".join(cmd) + "\n")
        log.flush()
        proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log,
                                creationflags=NO_WINDOW)
        with self.lock:
            self.proc, self.file, self.started = proc, base + ".mkv", None
        if self.stop_event.is_set():
            self.end_proc(proc)
        # Sync: every 0.2 s ffmpeg reports how much video it has written (out_time_us). Wall clock now
        # minus that is the start of the video plus the delay of the pipeline, so the smallest value
        # seen is the start to within a frame or two. (The time the file appears is ~2 s late: the
        # encoder buffers first.)
        best = None

        def save():
            info = {"video": os.path.basename(base + ".mkv"), "hwnd": hwnd, "encoder": name,
                    "start": datetime.datetime.fromtimestamp(best).isoformat(timespec="milliseconds")}
            if self.audio and self.audio.start_wall:
                # second of the audio file at second 0 of this video (cut_video.py takes the sound from there)
                info["audio"] = os.path.basename(self.audio.path)
                info["audio_offset"] = round(best - self.audio.start_wall, 3)
            json.dump(info, open(base + ".json", "w"), indent=1)

        for line in proc.stdout:
            now = time.time()
            m = line.strip().split(b"=", 1)
            if len(m) == 2 and m[0] == b"out_time_us" and m[1].strip().isdigit() and int(m[1]) > 0:
                start = now - int(m[1]) / 1e6
                if best is None or start < best:
                    first = best is None
                    best = start
                    with self.lock:
                        self.started = best
                    if first:
                        save()
                        print("   video: filming -> %s.mkv (%s)" % (base, name), flush=True)
            if not u32.IsWindow(hwnd) or self.stop_event.is_set():
                self.end_proc(proc)
        self.end_proc(proc)
        proc.wait()
        if best is not None:
            save()
        if proc.returncode != 0 and os.path.exists(base + ".mkv"):
            # killed (2026-11-26: after the game closed in fullscreen, gfxcapture got no "closed" event and
            # ffmpeg ignored 'q'): the file has no end. A stream copy gives it one, nothing lost.
            ok = finish_mkv(base + ".mkv", self.ffmpeg)
            log.write("\n[race_recorder] ffmpeg ended with %s; file repaired by stream copy: %s\n" % (proc.returncode, ok))
            print("   video: ffmpeg had to be stopped hard; file %s" % ("repaired" if ok else "NOT repaired"), flush=True)
        log.close()
        with self.lock:
            self.proc = None
        return best is not None

    @staticmethod
    def end_proc(proc):
        """Ask ffmpeg to finish the file ('q'); kill it if it has not ended 10 s later."""
        if proc.poll() is None and not proc.stdin.closed:
            try:
                proc.stdin.write(b"q")
                proc.stdin.close()
            except OSError:
                pass
            threading.Timer(10, lambda: proc.poll() is None and proc.kill()).start()

    def stop(self):
        self.stop_event.set()
        with self.lock:
            proc = self.proc
        if proc:
            self.end_proc(proc)
        self.join(15)


def meta(p, cars):
    gp = p.u32(GP)
    mode, menu_track = p.i32(gp + 0x1C), p.i32(gp + 0x20)
    tracks = struct.unpack("<4i", p.read(gp + 0x28, 16) or bytes(16))
    # the track of this race, as the game takes it (race setup 0x4087C6): in a championship (modes 1
    # and 3) entry gp+48h of the list at gp+28h; gp+20h is the track of the time trial menu
    track = tracks[p.i32(gp + 0x48) & 3] if mode in (1, 3) else menu_track
    m = {"class": p.i32(gp + 0x10), "mode": mode, "track": track, "menu_track": menu_track,
         "championship_race": p.i32(gp + 0x48),
         "championship": p.i32(gp + 0x24), "karts": len(cars),
         "championship_tracks": list(struct.unpack("<4i", p.read(gp + 0x28, 16) or b"\0" * 16)),
         "start_position": list(struct.unpack("<3f", p.read(cars[0] + 0x10, 12) or b"\0" * 12)) if cars else None}
    if m["class"] == 5:
        m["tuning"] = list(struct.unpack("<9i", p.read(gp + 0x2E4C, 36) or b"\0" * 36))
    # "Gegner" (any class since patch 1.10): "Tempo" in percent (-125 = "Standard") and how many karts drive
    # the learned way; both count only with the marker "STDG"
    m["gegner"] = list(struct.unpack("<2i", p.read(gp + 0x2E6C, 8) or b"\0" * 8))
    m["gegner_valid"] = (p.read(gp + 0x2D98, 4) or b"") == b"STDG"
    m["kart_index"] = [p.i32(c + 0x304) for c in cars]
    m["human_flag_308"] = [(p.read(c + 0x308, 1) or b"\0")[0] for c in cars]
    return m


def controller(p, car):
    """The computer kart's AI controller, if this car has one ([car+1F4h], set in fn 0x42C240; its +10h is the car)."""
    c = p.u32(car + 0x1F4)
    return c if c and p.u32(c + 0x10) == car else 0


def record(p, out_dir, once, video=None, audio=None):
    while p.alive():
        race = p.u32(RACE)
        t0 = p.f32(race + 0x20) if race else 0.0
        time.sleep(0.05)
        t1 = p.f32(race + 0x20) if race else 0.0
        race_zero = time.time() - t1                       # wall clock time of race time 0
        if not race or not (0.0 < t1 < 3.0) or t1 == t0:   # only a race that has just started and runs
            time.sleep(0.1)
            continue
        b, e = p.u32(race + 0x10), p.u32(race + 0x14)
        if not b or e <= b or (e - b) // 4 > 16:
            time.sleep(0.2)
            continue
        cars = [p.u32(b + 4 * i) for i in range((e - b) // 4)]
        ctrls = [controller(p, c) for c in cars]
        m = meta(p, cars)
        m["controllers"] = [bool(c) for c in ctrls]
        at = video.position(race_zero) if video else None
        if at:
            m["video"], m["video_t"] = at
        if audio and audio.start_wall and race_zero >= audio.start_wall:
            m["audio"], m["audio_t"] = os.path.basename(audio.path), round(race_zero - audio.start_wall, 3)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        base = os.path.join(out_dir, "%s_c%d_t%d" % (stamp, m["class"], m["track"]))
        json.dump(m, open(base + ".json", "w"), indent=1)
        print("race: class %d, track %d, mode %d, %d karts -> %s.csv" % (m["class"], m["track"], m["mode"], len(cars), base),
              flush=True)
        rows = 0
        last = None
        with open(base + ".csv", "w") as f:
            f.write("t,kart,x,y,z,vx,vy,vz,prog,thr,brk,steer,item,stuck,moved,cstate,ctimer,lat,pathprog\n")
            t_last = 0.0
            while p.alive() and p.u32(RACE) == race and (p.u32(race + 0x10), p.u32(race + 0x14)) == (b, e):
                raw = p.read(race + 0x20, 4)
                if raw is None:
                    break
                if raw == last:
                    time.sleep(0.001)
                    continue
                last = raw
                t = struct.unpack("<f", raw)[0]
                if t < t_last - 0.5:
                    break                                  # the clock started again: a new race
                t_last = t
                for i, (c, ct) in enumerate(zip(cars, ctrls)):
                    pos = p.read(c + 0x10, 12)
                    vel = p.read(c + 0x2B4, 12)
                    if pos is None or vel is None:
                        continue
                    x, y, z = struct.unpack("<3f", pos)
                    vx, vy, vz = struct.unpack("<3f", vel)
                    prog = p.f32(c + 0x220)
                    extra = ","
                    if ct:
                        thr, brk, steer = struct.unpack("<3f", p.read(ct + 0x14, 12) or b"\0" * 12)
                        ctl = "%.3f,%.3f,%.3f" % (thr, brk, steer)
                        if p.u32(ct) == AI_VTABLE:             # a computer kart: its stuck check too
                            _, moved, _, _, state = struct.unpack("<4fi", p.read(ct + 0x8C, 0x14) or b"\0" * 0x14)
                            extra = "%d,%.3f" % (state, moved)
                    else:
                        ctl = ",,"
                    item = p.i32(c + 0x270)
                    extra += ",%d,%.3f,%.4f,%.4f" % (p.i32(c + 0x29C), p.f32(c + 0x2D4), p.f32(c + 0x22C), p.f32(c + 0x224))
                    f.write("%.4f,%d,%.3f,%.3f,%.3f,%.3f,%.3f,%.3f,%.4f,%s,%d,%s\n"
                            % (t, i, x, y, z, vx, vy, vz, prog, ctl, item, extra))
                    rows += 1
        print("   race over: %d rows" % rows, flush=True)
        if once:
            return


def main():
    takes_value = ("--exe", "--quality")
    args = [a for i, a in enumerate(sys.argv[1:], 1) if not a.startswith("--") and sys.argv[i - 1] not in takes_value]
    out_dir = args[0] if args else os.path.join(os.path.dirname(HERE), "runs", "user")
    exe = sys.argv[sys.argv.index("--exe") + 1] if "--exe" in sys.argv else "MHK2-XXL.exe"
    _lock = one_recorder_only()                        # noqa: F841 - held until the process ends
    os.makedirs(out_dir, exist_ok=True)
    encoder = ffmpeg = None
    if "--video" in sys.argv:
        ffmpeg = find_ffmpeg()
        if not ffmpeg:
            sys.exit("--video needs ffmpeg: winget install Gyan.FFmpeg")
        q_text = sys.argv[sys.argv.index("--quality") + 1] if "--quality" in sys.argv else DEFAULT_QUALITY
        encoder = pick_encoder(ffmpeg, parse_quality(q_text))
        if not encoder:
            sys.exit("--video: no H.264 encoder of ffmpeg works")
        print("video: %s, quality %s (%s), files go to %s" % (encoder[0], q_text, " ".join(encoder[1]),
                                                               os.path.join(out_dir, "video")), flush=True)
    want_audio = "--audio" in sys.argv
    if want_audio:
        ffmpeg = ffmpeg or find_ffmpeg()
        if not ffmpeg:
            sys.exit("--audio needs ffmpeg: winget install Gyan.FFmpeg")
        from procaudio import ProcessAudio
        print("audio: the game's sound only, files go to %s" % os.path.join(out_dir, "video"), flush=True)
    print("waiting for %s; recordings go to %s (Ctrl+C ends)" % (exe, out_dir), flush=True)
    video = audio = None
    try:
        while True:
            pid = find_pid(exe)
            if pid:
                p = Proc(pid)
                print("attached to pid %d (read only)" % pid, flush=True)
                media = os.path.join(out_dir, "video")
                if want_audio:
                    os.makedirs(media, exist_ok=True)
                    stamp = os.path.basename(free_base(media, datetime.datetime.now().strftime("%Y-%m-%d %H-%M-%S"),
                                                       (".m4a", ".audio.json", ".audio.log")))
                    audio = ProcessAudio(pid, os.path.join(media, stamp + ".m4a"), ffmpeg)
                    audio.start()
                    audio.ready.wait(15)
                    if audio.error or not audio.start_wall:
                        print("   audio: not recording (%s)" % (audio.error or "no answer"), flush=True)
                        audio = None
                    else:
                        json.dump({"audio": stamp + ".m4a", "pid": pid, "start": datetime.datetime.fromtimestamp(
                            audio.start_wall).isoformat(timespec="milliseconds")},
                            open(os.path.join(media, stamp + ".audio.json"), "w"), indent=1)
                        print("   audio: recording -> %s.m4a" % os.path.join(media, stamp), flush=True)
                if encoder:
                    video = VideoCapture(ffmpeg, encoder, pid, media, audio)
                    video.start()
                record(p, out_dir, "--once" in sys.argv, video, audio)
                for m in (video, audio):
                    if m:
                        m.stop()
                video = audio = None
                if "--once" in sys.argv:
                    return
                print("game ended; waiting for the next start", flush=True)
            time.sleep(2.0)
    finally:
        for m in (video, audio):
            if m:
                m.stop()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
