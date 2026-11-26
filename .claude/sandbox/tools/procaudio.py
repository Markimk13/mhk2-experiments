"""Capture the sound of one process (and its children), nothing else: Windows' process loopback.

usage (alone, for a test): procaudio.py PID OUT.m4a [--seconds N]

Windows 10 2004 or newer: ActivateAudioInterfaceAsync on the virtual device
"VAD\\Process_Loopback" with AUDIOCLIENT_ACTIVATION_TYPE_PROCESS_LOOPBACK gives an IAudioClient
that hears only the target process tree, before the master volume of the speakers, so other
programs (chat, notifications) are not in the file. ffmpeg cannot do this itself, so this module
reads the PCM (48 kHz, 16 bit, stereo) and pipes it into ffmpeg, which writes AAC in a fragmented
.m4a (stays playable if the process is killed). At the end the file is rewritten as a plain .m4a
(finish_m4a, no re-encoding), because a fragmented one has no index: players show no total time and
cannot jump in it. A file left fragmented by a kill: `merge_av.py --fix FILE.m4a`.

The file runs on the wall clock: where the game plays nothing, Windows delivers no packets, and
the gaps are filled with silence from the packets' QPC time stamps (time.perf_counter() is the
same clock), so second N of the file is N seconds after `start` (time.time()).

Pure ctypes, no packages. Only reads sound; no input, no focus.
"""
import ctypes
import ctypes.wintypes as W
import os
import shutil
import subprocess
import sys
import threading
import time

ole32 = ctypes.WinDLL("ole32")
mmdev = ctypes.WinDLL("Mmdevapi")
k32 = ctypes.WinDLL("kernel32")
HRESULT = ctypes.c_long

RATE, CHANNELS, BITS = 48000, 2, 16
FRAME = CHANNELS * BITS // 8
NO_WINDOW = 0x08000000


class GUID(ctypes.Structure):
    _fields_ = [("d1", ctypes.c_uint32), ("d2", ctypes.c_uint16), ("d3", ctypes.c_uint16), ("d4", ctypes.c_ubyte * 8)]

    def __init__(self, s):
        super().__init__()
        h = s.replace("-", "")
        self.d1, self.d2, self.d3 = int(h[:8], 16), int(h[8:12], 16), int(h[12:16], 16)
        for i in range(8):
            self.d4[i] = int(h[16 + 2 * i:18 + 2 * i], 16)

    def __eq__(self, o):
        return bytes(self) == bytes(o)


IID_IUnknown = GUID("00000000-0000-0000-C000-000000000046")
IID_IAgileObject = GUID("94ea2b94-e9cc-49e0-c0ff-ee64ca8f5b90")
IID_Handler = GUID("41D949AB-9862-444A-80F6-C261334DA5EB")       # IActivateAudioInterfaceCompletionHandler
IID_IAudioClient = GUID("1CB9AD4C-DBFA-4c32-B178-C2F568A703B2")
IID_IAudioCaptureClient = GUID("C8ADBD64-E71E-48A0-A4DE-185C395CD317")


class WAVEFORMATEX(ctypes.Structure):
    _fields_ = [("wFormatTag", W.WORD), ("nChannels", W.WORD), ("nSamplesPerSec", W.DWORD),
                ("nAvgBytesPerSec", W.DWORD), ("nBlockAlign", W.WORD), ("wBitsPerSample", W.WORD), ("cbSize", W.WORD)]


class ACTIVATION_PARAMS(ctypes.Structure):          # AUDIOCLIENT_ACTIVATION_PARAMS, process loopback
    _fields_ = [("ActivationType", ctypes.c_int), ("TargetProcessId", W.DWORD), ("ProcessLoopbackMode", ctypes.c_int)]


class BLOB(ctypes.Structure):
    _fields_ = [("cbSize", W.ULONG), ("pBlobData", ctypes.c_void_p)]


class PROPVARIANT(ctypes.Structure):
    _fields_ = [("vt", W.USHORT), ("r1", W.WORD), ("r2", W.WORD), ("r3", W.WORD), ("blob", BLOB)]


def vcall(obj, index, restype, *args):
    """Call method `index` of the COM interface pointer `obj` (a c_void_p)."""
    vtbl = ctypes.cast(obj, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p)))[0]
    byref_type = type(ctypes.byref(ctypes.c_int()))
    proto = ctypes.WINFUNCTYPE(restype, ctypes.c_void_p,
                               *[ctypes.c_void_p if isinstance(a, byref_type) else type(a) for a in args])
    return proto(vtbl[index])(obj, *args)


def check(hr, what):
    if hr < 0:
        raise OSError("%s failed: HRESULT 0x%08X" % (what, hr & 0xFFFFFFFF))


# --- the completion handler: a minimal free-threaded COM object made of ctypes callbacks ---
QI = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.POINTER(GUID), ctypes.POINTER(ctypes.c_void_p))
REF = ctypes.WINFUNCTYPE(W.ULONG, ctypes.c_void_p)
DONE = ctypes.WINFUNCTYPE(HRESULT, ctypes.c_void_p, ctypes.c_void_p)


class Handler:
    def __init__(self):
        self.event = threading.Event()
        self.op = None
        self._qi = QI(self.query)
        self._ref = REF(lambda this: 1)
        self._done = DONE(self.completed)
        self.vtbl = (ctypes.c_void_p * 4)(*[ctypes.cast(f, ctypes.c_void_p) for f in
                                            (self._qi, self._ref, self._ref, self._done)])
        self.obj = (ctypes.c_void_p * 1)(ctypes.addressof(self.vtbl))

    @property
    def ptr(self):
        return ctypes.c_void_p(ctypes.addressof(self.obj))

    def query(self, this, riid, out):
        if riid[0] in (IID_IUnknown, IID_Handler, IID_IAgileObject):
            out[0] = this
            return 0
        out[0] = None
        return -2147467262                              # E_NOINTERFACE

    def completed(self, this, op):
        self.op = op
        self.event.set()
        return 0


class ProcessAudio(threading.Thread):
    """Records process `pid` (with its children) into `path` (.m4a) until stop()."""

    def __init__(self, pid, path, ffmpeg, log=None):
        super().__init__(daemon=True)
        self.pid, self.path, self.ffmpeg = pid, path, ffmpeg
        self.log = log or os.path.splitext(path)[0] + ".audio.log"
        self.stop_event = threading.Event()
        self.ready = threading.Event()
        self.start_wall = None          # time.time() of the file's first sample
        self.error = None
        self.frames = 0                 # frames written (captured + filled silence)

    def run(self):
        try:
            self.capture()
        except Exception as e:          # noqa: BLE001 - reported to the caller
            self.error = e
            self.ready.set()

    def activate(self):
        params = ACTIVATION_PARAMS(1, self.pid, 0)       # PROCESS_LOOPBACK, include the process tree
        pv = PROPVARIANT()
        pv.vt = 65                                       # VT_BLOB
        pv.blob.cbSize = ctypes.sizeof(params)
        pv.blob.pBlobData = ctypes.addressof(params)
        handler = Handler()
        op = ctypes.c_void_p()
        fn = mmdev.ActivateAudioInterfaceAsync
        fn.argtypes = [W.LPCWSTR, ctypes.POINTER(GUID), ctypes.POINTER(PROPVARIANT), ctypes.c_void_p,
                       ctypes.POINTER(ctypes.c_void_p)]
        fn.restype = HRESULT
        check(fn("VAD\\Process_Loopback", ctypes.byref(IID_IAudioClient), ctypes.byref(pv), handler.ptr,
                 ctypes.byref(op)), "ActivateAudioInterfaceAsync")
        if not handler.event.wait(10):
            raise OSError("process loopback: no answer from Windows")
        hr, client = HRESULT(), ctypes.c_void_p()
        check(vcall(op, 3, HRESULT, ctypes.byref(hr), ctypes.byref(client)), "GetActivateResult")
        check(hr.value, "activating process loopback")
        vcall(op, 2, W.ULONG)                            # Release the operation
        return client

    def capture(self):
        ole32.CoInitializeEx(None, 0)                    # COINIT_MULTITHREADED
        client = self.activate()
        fmt = WAVEFORMATEX(1, CHANNELS, RATE, RATE * FRAME, FRAME, BITS, 0)
        flags = 0x00020000 | 0x00040000 | 0x80000000 | 0x08000000   # LOOPBACK, EVENTCALLBACK, AUTOCONVERTPCM, SRC_DEFAULT_QUALITY
        check(vcall(client, 3, HRESULT, ctypes.c_int(0), W.DWORD(flags), ctypes.c_longlong(200 * 10000),
                    ctypes.c_longlong(0), ctypes.byref(fmt), ctypes.c_void_p()), "IAudioClient::Initialize")
        event = k32.CreateEventW(None, False, False, None)
        check(vcall(client, 13, HRESULT, ctypes.c_void_p(event)), "SetEventHandle")
        cap = ctypes.c_void_p()
        check(vcall(client, 14, HRESULT, ctypes.byref(IID_IAudioCaptureClient), ctypes.byref(cap)), "GetService")

        logf = open(self.log, "w", encoding="utf-8")
        enc = subprocess.Popen([self.ffmpeg, "-hide_banner", "-loglevel", "warning", "-y",
                                "-f", "s16le", "-ar", str(RATE), "-ac", str(CHANNELS), "-i", "pipe:0",
                                "-c:a", "aac", "-b:a", "192k",
                                "-movflags", "+frag_keyframe+empty_moov+default_base_moof", self.path],
                               stdin=subprocess.PIPE, stdout=logf, stderr=logf, creationflags=NO_WINDOW)
        check(vcall(client, 10, HRESULT), "IAudioClient::Start")
        t_perf = time.perf_counter()
        self.start_wall = time.time() - (time.perf_counter() - t_perf)
        start_qpc = t_perf * 1e7                         # perf_counter is QPC; packets stamp QPC in 100 ns
        self.ready.set()
        data, n, fl = ctypes.c_void_p(), W.UINT(), W.DWORD()
        devpos, qpc = ctypes.c_uint64(), ctypes.c_uint64()
        size = W.UINT()
        silence = bytes(FRAME * RATE // 10)
        try:
            while not self.stop_event.is_set():
                k32.WaitForSingleObject(event, 100)
                while True:
                    check(vcall(cap, 5, HRESULT, ctypes.byref(size)), "GetNextPacketSize")
                    if size.value == 0:
                        break
                    check(vcall(cap, 3, HRESULT, ctypes.byref(data), ctypes.byref(n), ctypes.byref(fl),
                                ctypes.byref(devpos), ctypes.byref(qpc)), "GetBuffer")
                    frames = n.value
                    # where this packet belongs on the wall clock; fill a gap of more than 10 ms with silence
                    due = int((qpc.value - start_qpc) / 1e7 * RATE) if qpc.value else self.frames
                    gap = due - self.frames
                    while gap > RATE // 100:
                        k = min(gap, len(silence) // FRAME)
                        enc.stdin.write(silence[:k * FRAME])
                        self.frames += k
                        gap -= k
                    if fl.value & 0x2 or not data.value:   # AUDCLNT_BUFFERFLAGS_SILENT
                        enc.stdin.write(bytes(frames * FRAME))
                    else:
                        enc.stdin.write(ctypes.string_at(data.value, frames * FRAME))
                    self.frames += frames
                    check(vcall(cap, 4, HRESULT, W.UINT(frames)), "ReleaseBuffer")
                # nothing playing: keep the file running on the wall clock
                due = int((time.perf_counter() - t_perf) * RATE)
                if due - self.frames > RATE // 5:             # more than 200 ms behind: silence up to 100 ms ago
                    k = due - RATE // 10 - self.frames
                    while k > 0:
                        m = min(k, len(silence) // FRAME)
                        enc.stdin.write(silence[:m * FRAME])
                        self.frames += m
                        k -= m
        finally:
            vcall(client, 11, HRESULT)                   # Stop
            vcall(cap, 2, W.ULONG)
            vcall(client, 2, W.ULONG)
            k32.CloseHandle(event)
            try:
                enc.stdin.close()
            except OSError:
                pass
            try:
                enc.wait(15)
            except subprocess.TimeoutExpired:
                enc.kill()
            logf.close()
            finish_m4a(self.path, self.ffmpeg)

    def stop(self):
        self.stop_event.set()
        self.join(20)


def finish_m4a(path, ffmpeg):
    """Rewrite a fragmented .m4a as a plain one (same AAC data, no re-encoding).

    The fragmented file has no index, so players show no total time and cannot jump in it. The
    plain file is written next to it and replaces it only when ffmpeg succeeded; returns True then.
    """
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return False
    tmp = path + ".tmp.m4a"
    r = subprocess.run([ffmpeg, "-v", "error", "-y", "-i", path, "-map", "0:a", "-c", "copy",
                        "-movflags", "+faststart", tmp], capture_output=True, creationflags=NO_WINDOW)
    if r.returncode != 0 or not os.path.exists(tmp) or os.path.getsize(tmp) == 0:
        if os.path.exists(tmp):
            os.remove(tmp)
        return False
    os.replace(tmp, path)
    return True


def find_ffmpeg():
    path = shutil.which("ffmpeg")
    winget = os.path.join(os.environ.get("LOCALAPPDATA", ""), "Microsoft", "WinGet", "Links", "ffmpeg.exe")
    return path or (winget if os.path.exists(winget) else None)


if __name__ == "__main__":
    pid, out = int(sys.argv[1]), sys.argv[2]
    secs = float(sys.argv[sys.argv.index("--seconds") + 1]) if "--seconds" in sys.argv else 10.0
    a = ProcessAudio(pid, out, find_ffmpeg())
    a.start()
    a.ready.wait(15)
    if a.error:
        sys.exit("error: %s" % a.error)
    print("recording pid %d -> %s for %.0f s" % (pid, out, secs))
    time.sleep(secs)
    a.stop()
    print("frames %d = %.2f s" % (a.frames, a.frames / RATE))
    if a.error:
        sys.exit("error: %s" % a.error)
