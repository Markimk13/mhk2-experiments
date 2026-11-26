r"""Rebuild the parts of the sandbox that git does not keep.

usage: py .claude\sandbox\tools\setup_sandbox.py [--no-disasm] [--no-builds]

The sandbox is .claude\sandbox in the repository. Git keeps tools\ (these scripts) and fixtures\
(the phantom folder and settings.dat every test scenario starts from). Everything else is
ignored by git; this script makes what the tools need:

  ..\..\output\                   MHK2-XXL.exe and data\MK2\text-20.csv, built by tools\patch_200cc.py
  work\MHK2-XXL.orig.exe          the original exe (original_exe in local.json), hash checked
  work\disasm.txt, disasm.pickle  dumpbin's listing and the index dis.py works on
                                  (needs Visual Studio's dumpbin.exe; skipped if it is not found)
  work\cfg\, work\txt\            karts.txt, config.txt, text.csv taken out of mhk2-00.dat
  game\data\mhk2-00.dat           the game's data file (144 MB; game_data in local.json)
  game\data\Phantom, settings.dat from fixtures\
  game\data\MK2\text-20.csv       from output\
  game\*.exe                      the unattended test builds, from output\MHK2-XXL.exe and the original
  builds\, runs\, shots\          empty folders for patcher builds to check, test results, pictures

The game files come from the paths in .claude\sandbox\local.json (see paths.py); they are only
read. Run it again after the patcher changed.
It first claims game\ and the extra game folders (game2, game3, ... which gameslot.py makes
when tests run side by side) and waits while a test uses one, because it replaces the test
builds; at the end it copies the new builds and data into the extra folders too.
"""
import glob
import hashlib
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import paths                                                  # noqa: E402

ROOT = paths.SANDBOX                                          # .claude\sandbox
REPO = paths.REPO
ORIGINAL = paths.original_exe()
DATA_SOURCE = paths.game_data()
OUTPUT = paths.OUTPUT
WORK, GAME, FIXTURES = (os.path.join(ROOT, n) for n in ("work", "game", "fixtures"))
DUMPBIN = r"C:\Program Files\Microsoft Visual Studio\*\*\VC\Tools\MSVC\*\bin\Hostx64\x86\dumpbin.exe"
# test builds: (name, source, extra arguments of prep_class5.py)
BUILDS = (("ghost_new.exe", "patched", []), ("ghost_mouse.exe", "patched", ["--mouse"]),
          ("c5_new60.exe", "patched", ["60"]), ("ghost_orig.exe", "original", []),
          ("fps200.exe", "patched", []))        # 200 FPS: the races at the game's own frame rate


def step(text):
    print("- " + text, flush=True)


def py(*args):
    r = subprocess.run([sys.executable] + list(args), capture_output=True, text=True)
    if r.returncode:
        raise SystemExit("failed: %s\n%s" % (" ".join(args), (r.stdout + r.stderr).strip()))
    return r.stdout.strip()


def output_folder():
    py(paths.PATCHER, ORIGINAL, OUTPUT)
    step("output\\ built by the patcher")


def work_folder(disasm):
    os.makedirs(WORK, exist_ok=True)
    data = open(ORIGINAL, "rb").read()
    if not hashlib.sha256(data).hexdigest().startswith("272bfad50336ec4c"):
        raise SystemExit("%s is not the original exe" % ORIGINAL)
    orig = os.path.join(WORK, "MHK2-XXL.orig.exe")
    with open(orig, "wb") as f:
        f.write(data)
    step("work\\MHK2-XXL.orig.exe")
    if disasm:
        found = sorted(glob.glob(DUMPBIN))
        if not found:
            step("no dumpbin.exe found: work\\disasm.txt not built (dis.py will not work)")
        else:
            with open(os.path.join(WORK, "disasm.txt"), "wb") as f:
                subprocess.run([found[-1], "/disasm", orig], stdout=f, check=True)
            py(os.path.join(HERE, "dis.py"), "index")
            step("work\\disasm.txt and its index")
    # the plain-text files of the game data
    import datlist
    import mhk2crypt
    wanted = {"data\\mk2\\settings\\karts\\karts.txt": ("cfg", "karts.txt"),
              "data\\config.txt": ("cfg", "config.txt"),
              "data\\mk2\\level01\\settings\\misc\\misc.txt": ("cfg", "misc01.txt"),
              "data\\mk2\\text.csv": (os.path.join("txt", "data", "mk2"), "text.csv")}
    magic, count, align, entries = datlist.read_index(DATA_SOURCE)
    got = []
    with open(DATA_SOURCE, "rb") as f:
        for name, off, size, rest in entries:
            if name.lower() in wanted:
                folder, out = wanted[name.lower()]
                os.makedirs(os.path.join(WORK, folder), exist_ok=True)
                f.seek(off)
                raw = f.read(size)
                if out.endswith(".txt"):
                    raw = mhk2crypt.decrypt(raw)
                with open(os.path.join(WORK, folder, out), "wb") as g:
                    g.write(raw)
                got.append(out)
    step("work\\cfg and work\\txt: %s" % ", ".join(sorted(got)))
    if len(got) != len(wanted):
        step("WARNING: %d of %d files were not found in mhk2-00.dat" % (len(wanted) - len(got), len(wanted)))


def game_folder(builds):
    os.makedirs(os.path.join(GAME, "data", "MK2"), exist_ok=True)
    big = os.path.join(GAME, "data", "mhk2-00.dat")
    if not os.path.exists(big) or os.path.getsize(big) != os.path.getsize(DATA_SOURCE):
        shutil.copyfile(DATA_SOURCE, big)
        step("game\\data\\mhk2-00.dat copied (%d MB)" % (os.path.getsize(big) >> 20))
    phantom = os.path.join(GAME, "data", "Phantom")
    if os.path.isdir(phantom):
        shutil.rmtree(phantom)
    shutil.copytree(os.path.join(FIXTURES, "Phantom"), phantom)
    shutil.copyfile(os.path.join(FIXTURES, "settings.dat"), os.path.join(GAME, "settings.dat"))
    shutil.copyfile(os.path.join(OUTPUT, "data", "MK2", "text-20.csv"), os.path.join(GAME, "data", "MK2", "text-20.csv"))
    step("game\\data\\Phantom and game\\settings.dat (fixtures), text-20.csv (output)")
    rebuilt = [os.path.join("data", "mhk2-00.dat"), os.path.join("data", "MK2", "text-20.csv")]
    if builds:
        sources = {"patched": os.path.join(OUTPUT, "MHK2-XXL.exe"), "original": ORIGINAL}
        prep = os.path.join(HERE, "prep_class5.py")
        for name, source, extra in BUILDS:
            py(prep, sources[source], os.path.join(GAME, name), *extra)
            rebuilt.append(name)
        step("game\\" + ", ".join(name for name, source, extra in BUILDS))
    return rebuilt


def main():
    import gameslot
    for folder in [GAME] + gameslot.slot_dirs():
        gameslot.claim_dir(folder)
    with gameslot.setup_lock():
        for folder in ("builds", "runs", "shots"):
            os.makedirs(os.path.join(ROOT, folder), exist_ok=True)
        output_folder()
        work_folder("--no-disasm" not in sys.argv)
        rebuilt = game_folder("--no-builds" not in sys.argv)
        for folder in gameslot.slot_dirs():
            gameslot.sync_from_game(folder, force=rebuilt, locked=True)
            step(os.path.basename(folder) + " brought up to date")
    print("sandbox ready in", ROOT)


if __name__ == "__main__":
    main()
