r"""The sandbox checks as small jobs, run by up to three workers at once (each in its own game folder).

usage: py jobs.py <name> [selector ...] [--workers N] [--no-setup]
       py jobs.py --list [selector ...]

  <name>        results go to runs\<name>: one log per job in jobs\, the joined logs
                (classtest.log, ghosttest.log, corners.log, singles.log, tune.log, classes.log,
                lift.log, ai.log), progress.log, summary.txt
  selector      what to run (default: all). A group (classtest, ghosttest, races, corners,
                singles, straight, tune, classes, lift, ai), a job (classtest:tt250,
                "tune:pull max", corners:200off m50, ...) or a prefix of job names (classtest:tune).
                Several selectors add up.
  --workers N   game folders used at once (default 3: game, game2, game3; MHK2_GAMES="game4
                game5" picks others). gameslot.py still keeps the PC-wide limit.
  --no-setup    skip setup_sandbox.py (test builds from output\) when the builds are current
  --list        show the jobs and their expected times, run nothing

Every job is one scenario, one race set or one straight run, independent of the others (each
scenario puts the fixtures back first). Each worker takes the longest job left; the times of
the last runs (runs\jobtimes.json) decide what is long. "touch runs\<name>\stop" lets the
workers finish their current job and stop. At the end every game folder gets its fixtures back.
"""
import json
import os
import re
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
SANDBOX = os.path.dirname(HERE)
sys.path.insert(0, HERE)

PY = sys.executable
C50 = "corner m50 d800=400,1000,400,50,400,200,800"
C25 = "corner m25 d800=400,1000,400,25,400,200,800"
ALL = "all max=400,1000,400,400,400,200,800"
SINGLES = ["gearing max=400,200,100,100,100,100,100", "pull max=155,1000,100,100,100,100,100",
           "grip max=155,200,400,100,100,100,100", "grip min=155,200,25,100,100,100,100",
           "downforce 0=155,200,100,100,100,100,0", "downforce max=155,200,100,100,100,100,800",
           "mass max=155,200,100,400,100,100,100", "mass min=155,200,100,25,100,100,100"]
CLASSTEST = "hud tuning gegner tunelimit save16 save18 pause tunemouse tuneown ownmouse tunekart tttune menu tt250 tt200 champ oldsave unlockall browser".split()
GHOSTTEST = "main cc200 options".split()
# group -> joined log file
JOINED = {"classtest": "classtest.log", "ghosttest": "ghosttest.log", "corners": "corners.log", "singles": "singles.log",
          "tune": "tune.log", "classes": "classes.log", "lift": "lift.log", "ai": "ai.log",
          "topspeed": "topspeed.log", "release": "release.log"}
SUPER = {"races": ("corners", "singles"), "straight": ("tune", "classes", "lift", "ai", "topspeed")}
GUESS = {"classtest": 60, "ghosttest": 40, "corners": 60, "singles": 55, "tune": 16, "classes": 30, "lift": 40, "ai": 95, "topspeed": 45, "release": 30}


class Job:
    def __init__(self, group, name, cmds):
        self.group, self.name, self.cmds = group, "%s:%s" % (group, name), cmds   # cmds(folder, out) -> [argv, ...]


def all_jobs():
    t = lambda *a: [PY, os.path.join(HERE, a[0])] + list(a[1:])
    exe = lambda g, name: os.path.join(SANDBOX, g, name)
    jobs = []
    for s in CLASSTEST:
        jobs.append(Job("classtest", s, lambda g, out, s=s: [t("classtest.py", s)]))
    for s in GHOSTTEST:
        jobs.append(Job("ghosttest", s, lambda g, out, s=s: [t("ghosttest.py", s)]))
    for tag, build, extra, sets in (("60", "c5_new60.exe", [], (C50, C25, ALL)),
                                    ("200off", "fps200.exe", [], (C50, C25, ALL)),
                                    ("200on", "fps200.exe", ["--physics60"], (C50,))):
        for st in sets:
            jobs.append(Job("corners", "%s %s" % (tag, st.split("=")[0]),
                            lambda g, out, b=build, tag=tag, extra=extra, st=st: [t("tune_races.py", exe(g, b), out, "--tag", tag, *extra, st)]))
    for st in SINGLES:
        jobs.append(Job("singles", st.split("=")[0], lambda g, out, st=st: [t("tune_races.py", exe(g, "c5_new60.exe"), out, "--tag", "60", st)]))
    import tune_runs
    for name, vals in tune_runs.cases():
        arg = "%s=%s" % (name, ",".join(str(v) for v in vals))
        jobs.append(Job("tune", name, lambda g, out, arg=arg: [t("tune_runs.py", exe(g, "c5_new60.exe"), out, arg)]))
    for spec in ("3:s55", "4:s56"):
        jobs.append(Job("classes", spec, lambda g, out, spec=spec: [t("class_runs.py", exe(g, "c5_new60.exe"), out, spec)]))
    jobs.append(Job("lift", "150cc 250cc", lambda g, out: [
        t("pu_run.py", exe(g, "c5_new60.exe"), os.path.join(out, "lift_150cc.csv"), "--track", "3", "--cls", "2", "--tend", "5", "--lift", "40"),
        t("pu_run.py", exe(g, "c5_new60.exe"), os.path.join(out, "lift_250cc.csv"), "--track", "3", "--cls", "4", "--tend", "5", "--lift", "48"),
        t("lift_check.py", os.path.join(out, "lift_150cc.csv"), os.path.join(out, "lift_250cc.csv"))]))
    import topspeed_check
    for name, vals, char in topspeed_check.cases():
        arg = "%s=%s" % (name, ",".join(str(v) for v in vals))
        jobs.append(Job("topspeed", name, lambda g, out, arg=arg, char=char: [
            t("topspeed_check.py", exe(g, "c5_new60.exe"), arg, "--char", str(char))]))
    jobs.append(Job("release", "zips", lambda g, out: [t("release_check.py", os.path.join(out, "release"))]))
    jobs.append(Job("ai", "250cc race", lambda g, out: [
        t("ai_race.py", exe(g, "c5_new60.exe"), os.path.join(out, "ai_250cc.csv"), "--seconds", "75", "--cls", "4", "--track", "0"),
        t("ai_progress.py", os.path.join(out, "ai_250cc.csv"))]))
    return jobs


def select(jobs, sels):
    if not sels or "all" in sels:
        return jobs
    groups = set()
    for s in sels:
        groups.update(SUPER.get(s, (s,)))
    picked = [j for j in jobs if j.group in groups or any(j.name == s or j.name.startswith(s) for s in sels if ":" in s)]
    unknown = [s for s in sels if s not in SUPER and s not in JOINED and not any(j.name.startswith(s) for j in jobs)]
    if unknown:
        raise SystemExit("unknown selector(s): %s (see --list)" % ", ".join(unknown))
    return picked


def safe(name):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", name)


class Runner:
    def __init__(self, out, jobs, folders, times):
        self.out, self.folders, self.times = out, folders, times
        self.todo = sorted(jobs, key=lambda j: -self.expect(j))
        self.lock = threading.Lock()
        self.results = []                           # (job, folder, seconds, returncode)
        os.makedirs(os.path.join(out, "jobs"), exist_ok=True)

    def expect(self, j):
        return self.times.get(j.name, GUESS[j.group])

    def log(self, text):
        with self.lock:
            with open(os.path.join(self.out, "progress.log"), "a", encoding="utf-8") as f:
                f.write("%s %s\n" % (time.strftime("%H:%M:%S"), text))
            print(text, flush=True)

    def worker(self, folder):
        env = dict(os.environ, MHK2_GAME=folder)
        while True:
            with self.lock:
                if not self.todo or os.path.exists(os.path.join(self.out, "stop")):
                    return
                job = self.todo.pop(0)
            self.log("%-6s start %s" % (folder, job.name))
            t0 = time.time()
            rc = 0
            with open(os.path.join(self.out, "jobs", safe(job.name) + ".log"), "w", encoding="utf-8") as f:
                for argv in job.cmds(folder, self.out):
                    r = subprocess.run(argv, cwd=SANDBOX, env=env, stdout=f, stderr=subprocess.STDOUT)
                    rc = rc or r.returncode
            dt = time.time() - t0
            with self.lock:
                self.results.append((job, folder, dt, rc))
                if rc == 0:
                    self.times[job.name] = round(dt, 1)
            self.log("%-6s done  %s (%.0f s%s)" % (folder, job.name, dt, "" if rc == 0 else ", exit code %d" % rc))

    def run(self):
        threads = [threading.Thread(target=self.worker, args=(f,)) for f in self.folders]
        for th in threads:
            th.start()
            time.sleep(0.5)
        for th in threads:
            th.join()


def joined_logs(out, jobs):
    for group, fname in JOINED.items():
        parts = [j for j in jobs if j.group == group]
        if not parts:
            continue
        with open(os.path.join(out, fname), "w", encoding="utf-8") as f:
            for j in parts:
                p = os.path.join(out, "jobs", safe(j.name) + ".log")
                if os.path.exists(p):
                    f.write("### %s\n" % j.name)
                    f.write(open(p, encoding="utf-8", errors="replace").read())


def summary(out, runner, jobs, minutes):
    lines = []
    for group in ("classtest", "ghosttest"):
        ok = bad = 0
        for j in jobs:
            if j.group != group:
                continue
            p = os.path.join(out, "jobs", safe(j.name) + ".log")
            m = re.findall(r"(\d+) checks ok, (\d+) failed", open(p, encoding="utf-8", errors="replace").read()) if os.path.exists(p) else []
            if m:
                ok += int(m[-1][0])
                bad += int(m[-1][1])
            else:
                bad += 1
                lines.append("%s: no result line (see jobs\\%s.log)" % (j.name, safe(j.name)))
        if any(j.group == group for j in jobs):
            lines.append("%s: %d checks ok, %d failed" % (group, ok, bad))
    races = [j for j in jobs if j.group in ("corners", "singles")]
    if races:
        text = "".join(open(os.path.join(out, "jobs", safe(j.name) + ".log"), encoding="utf-8", errors="replace").read()
                       for j in races if os.path.exists(os.path.join(out, "jobs", safe(j.name) + ".log")))
        lines.append("runaways: %d in %d race sets" % (text.count("RUNAWAY"), len(races)))
    failed = [(j, rc) for j, f, dt, rc in runner.results if rc]
    for j, rc in failed:
        lines.append("job %s ended with exit code %d" % (j.name, rc))
    missing = len(jobs) - len(runner.results)
    if missing:
        lines.append("%d job(s) not run (stopped)" % missing)
    try:
        n = sum(1 for _ in open(os.path.join(SANDBOX, "focusguard.log")))
    except OSError:
        n = 0
    lines.append("focus guard log lines: %d" % n)
    lines.append("%d jobs in %.1f minutes with %d game folders" % (len(runner.results), minutes, len(runner.folders)))
    open(os.path.join(out, "summary.txt"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n" + "\n".join(lines))
    return not failed and not missing and all("0 failed" in l for l in lines if "checks ok" in l)


def main():
    args = sys.argv[1:]
    workers = 3
    if "--workers" in args:
        i = args.index("--workers")
        workers = int(args[i + 1])
        del args[i:i + 2]
    flags = {a for a in args if a.startswith("--")}
    args = [a for a in args if not a.startswith("--")]
    jobs = all_jobs()
    times_path = os.path.join(SANDBOX, "runs", "jobtimes.json")
    try:
        times = json.load(open(times_path))
    except (OSError, ValueError):
        times = {}
    if "--list" in flags:
        sel = select(jobs, args)                    # no run name with --list
        for j in sel:
            print("%-40s %5.0f s" % (j.name, times.get(j.name, GUESS[j.group])))
        total = sum(times.get(j.name, GUESS[j.group]) for j in sel)
        print("%d jobs, about %.0f min in a row, %.0f min with %d workers" % (len(sel), total / 60, total / 60 / workers, workers))
        return
    if not args:
        raise SystemExit(__doc__)
    out = os.path.join(SANDBOX, "runs", args[0])
    sel = select(jobs, args[1:])
    os.makedirs(out, exist_ok=True)
    for name in ("progress.log", "summary.txt", "stop"):
        if os.path.exists(os.path.join(out, name)):
            os.remove(os.path.join(out, name))
    folders = (os.environ.get("MHK2_GAMES") or " ".join(["game"] + ["game%d" % i for i in range(2, 10)])).split()[:workers]
    t0 = time.time()
    with open(os.path.join(out, "build.log"), "a", encoding="utf-8") as b:
        if "--no-setup" not in flags:
            print("test builds from output\\ ...", flush=True)
            if subprocess.run([PY, os.path.join(HERE, "setup_sandbox.py"), "--no-disasm"], cwd=SANDBOX, stdout=b, stderr=subprocess.STDOUT).returncode:
                raise SystemExit("setup failed, see %s" % os.path.join(out, "build.log"))
        for g in folders:
            if subprocess.run([PY, os.path.join(HERE, "gameslot.py"), "make", g], cwd=SANDBOX, stdout=b, stderr=subprocess.STDOUT).returncode:
                raise SystemExit("game folder %s failed, see build.log" % g)
    runner = Runner(out, sel, folders, times)
    runner.log("%d jobs, %d workers: %s" % (len(sel), len(folders), " ".join(folders)))
    t1 = time.time()
    runner.run()
    minutes = (time.time() - t1) / 60
    for g in folders:                               # every folder gets its fixtures back
        subprocess.run([PY, "-c", "import sys; sys.path.insert(0, r'%s'); import ghosttest; ghosttest.restore()" % HERE],
                       cwd=SANDBOX, env=dict(os.environ, MHK2_GAME=g), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    os.makedirs(os.path.dirname(times_path), exist_ok=True)
    json.dump(runner.times, open(times_path, "w"), indent=1, sort_keys=True)
    joined_logs(out, sel)
    runner.log("end: %.1f minutes of jobs, %.1f with the builds" % (minutes, (time.time() - t0) / 60))
    sys.exit(0 if summary(out, runner, sel, minutes) else 1)


if __name__ == "__main__":
    main()
