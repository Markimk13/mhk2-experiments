"""The 64 tuning sets of the challenges with power cans: does any set blow up the physics? (sandbox)

usage: ch_can_check.py <out dir> [--seconds 45] [--folders game,game2,game3] [--tracks 0,1,..]

Challenges give the player one power can ("Powerdose"). Its accel factor 5.0 stacks with the pull
of the drawn tuning set. Each set races once with the six computer karts on the track
set_index % 8, with the 60 FPS switch on; the computer karts get a new can whenever they hold none
(tune_races.py --cans). The tracks are spread over the game folders, one tune_races.py per folder
at a time. Every line of <out dir>\\races.log says "no runaway" or "RUNAWAY".
"""
import os
import subprocess
import sys
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
SANDBOX = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(SANDBOX)), "tools"))
import patch_200cc as P


def opt(args, name, default):
    if name in args:
        i = args.index(name)
        value = args[i + 1]
        del args[i:i + 2]
        return value
    return default


def main():
    args = sys.argv[1:]
    seconds = opt(args, "--seconds", "45")
    folders = opt(args, "--folders", "game,game2,game3").split(",")
    tracks = [int(t) for t in opt(args, "--tracks", "0,1,2,3,4,5,6,7").split(",")]
    out = os.path.abspath(args[0])
    os.makedirs(out, exist_ok=True)
    sets = P.challenge_sets()
    queue = list(tracks)
    lock = threading.Lock()

    def worker(folder):
        exe = os.path.join(SANDBOX, folder, "c5_new60.exe")
        while True:
            with lock:
                if not queue:
                    return
                track = queue.pop(0)
            named = ["set%02d=%s" % (k, ",".join(str(v) for v in sets[k])) for k in range(track, len(sets), 8)]
            subprocess.run([sys.executable, os.path.join(HERE, "tune_races.py"), exe, out, "--seconds", seconds,
                            "--track", str(track), "--physics60", "--cans", "--tag", "t%d" % track] + named)

    threads = [threading.Thread(target=worker, args=(f,)) for f in folders]
    for th in threads:
        th.start()
    for th in threads:
        th.join()
    lines = open(os.path.join(out, "races.log"), encoding="utf-8").read().splitlines()
    print("%d races, %d with a runaway, %d without data" % (
        len(lines), sum("RUNAWAY" in l for l in lines), sum("NO DATA" in l for l in lines)))


if __name__ == "__main__":
    main()
