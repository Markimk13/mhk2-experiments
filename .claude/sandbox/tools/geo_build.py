r"""Rebuild the geometric driver into the patcher and the sandbox test builds.

usage: geo_build.py

geo_driver.asm -> asm2py.py -> tools\patch_200cc.py (table GEO_DRIVER) -> builds\geo\MHK2-XXL.exe,
dumpbin check (verify_listing.py, must be 0 mismatches), then geo60.exe (60 FPS cap) and
geo200.exe (the game's 200 FPS) in game, game2 and game3, with the build's text file (it carries
the version shown in the menu). Refuses while a test game runs.
"""
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SANDBOX = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(SANDBOX))
OUT = os.path.join(SANDBOX, "builds", "geo")


def run(*args, **kw):
    r = subprocess.run(list(args), capture_output=True, text=True, **kw)
    if r.returncode:
        raise SystemExit("failed: %s\n%s" % (" ".join(args), r.stdout + r.stderr))
    return r.stdout


def main():
    sys.path.insert(0, HERE)
    import gameslot
    import paths
    if any(not g["real"] for g in gameslot.games()):
        raise SystemExit("a test game runs (its exe may be one of the builds)")
    dumpbin = paths.msvc_tool("dumpbin.exe")
    if not dumpbin:
        raise SystemExit("needs dumpbin.exe: Visual Studio with the C++ tools (MSVC x86)")
    print(run(sys.executable, os.path.join(HERE, "asm2py.py"), os.path.join(HERE, "geo_driver.asm"), "GEO_DRIVER",
              os.path.join(REPO, "tools", "patch_200cc.py")).strip())
    os.makedirs(OUT, exist_ok=True)
    listing = os.path.join(OUT, "listing.txt")
    print(run(sys.executable, os.path.join(REPO, "tools", "patch_200cc.py"), paths.original_exe(),
              OUT, "--listing", listing).strip().splitlines()[0])
    dis = os.path.join(OUT, "mod200.dis.txt")
    with open(dis, "w") as f:
        subprocess.run([dumpbin, "/disasm", "/section:.mod200", os.path.join(OUT, "MHK2-XXL.exe")], stdout=f, check=True)
    check = run(sys.executable, os.path.join(HERE, "verify_listing.py"), listing, dis).strip().splitlines()
    print(check[-1].split(", data")[0])
    if " 0 mismatches" not in check[-1]:
        print("\n".join(check[:-1]))
        raise SystemExit("listing mismatches")
    for g in ("game", "game2", "game3"):
        shutil.copyfile(os.path.join(OUT, "data", "MK2", "text-20.csv"), os.path.join(SANDBOX, g, "data", "MK2", "text-20.csv"))
        for name, extra in (("geo60.exe", ["60"]), ("geo200.exe", [])):
            run(sys.executable, os.path.join(HERE, "prep_class5.py"), os.path.join(OUT, "MHK2-XXL.exe"), os.path.join(SANDBOX, g, name), *extra)
    print("test builds geo60.exe / geo200.exe in game, game2, game3")


if __name__ == "__main__":
    main()
