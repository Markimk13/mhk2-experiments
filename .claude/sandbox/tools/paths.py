r"""Where the game files are on this PC.

The repository holds no game files. The sandbox tools find them through .claude\sandbox\local.json
(ignored by git, like the rest of the sandbox outside tools\ and fixtures\):

    {
      "original_exe": "D:\\Games\\Moorhuhn Kart 2\\MHK2-XXL.exe",
      "game_data":    "D:\\Games\\Moorhuhn Kart 2\\data\\mhk2-00.dat",
      "v11_data":     "D:\\Games\\Moorhuhn Kart 2\\data\\source\\mhk2-01.dat"
    }

original_exe  the unpatched German V1.0 exe (SHA-256 272bfad50336ec4c...); required
game_data     the game's data file, 144 MB; default: data\mhk2-00.dat next to original_exe
v11_data      the V1.1 data file; optional, only ghosttest.py's "version" scenario needs it

Relative paths count from the repository. The files are only read, never changed.

msvc_tool() and javac() find the build tools some scripts need (ml.exe / dumpbin.exe of Visual
Studio's C++ tools, a JDK 9 or newer) wherever they are installed, without a fixed version.
"""
import glob
import json
import os
import re
import shutil
import subprocess

TOOLS = os.path.dirname(os.path.abspath(__file__))
SANDBOX = os.path.dirname(TOOLS)
REPO = os.path.dirname(os.path.dirname(SANDBOX))
CONFIG = os.path.join(SANDBOX, "local.json")
OUTPUT = os.path.join(REPO, "output")           # what setup_sandbox.py builds with the patcher
PATCHER = os.path.join(REPO, "tools", "patch_200cc.py")


def _config():
    if not os.path.exists(CONFIG):
        raise SystemExit("missing %s - it names the game files on this PC:\n%s" % (CONFIG, __doc__))
    with open(CONFIG, encoding="utf-8") as f:
        return json.load(f)


def _path(value):
    return os.path.normpath(os.path.join(REPO, value)) if value else None


def original_exe():
    return _path(_config()["original_exe"])


def game_data():
    c = _config()
    return _path(c.get("game_data")) or os.path.join(os.path.dirname(original_exe()), "data", "mhk2-00.dat")


def v11_data():
    """The V1.1 data file, or None when local.json names none."""
    return _path(_config().get("v11_data"))


def _version_key(path):
    return [int(n) for n in re.findall(r"\d+", path)]


def msvc_tool(name):
    r"""Full path of an x86 tool of Visual Studio's C++ tools (ml.exe, dumpbin.exe): the newest
    MSVC version of any edition or year, or None. Order: PATH (a developer prompt), the installs
    vswhere knows, the default folders under Program Files and Program Files (x86)."""
    found = shutil.which(name)
    if found:
        return found
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    roots = set()
    vswhere = os.path.join(pf86, "Microsoft Visual Studio", "Installer", "vswhere.exe")
    if os.path.exists(vswhere):
        r = subprocess.run([vswhere, "-all", "-products", "*", "-property", "installationPath"],
                           capture_output=True, text=True)
        roots.update(line.strip() for line in r.stdout.splitlines() if line.strip())
    for pf in (os.environ.get("ProgramFiles", r"C:\Program Files"), pf86):
        roots.update(glob.glob(os.path.join(pf, "Microsoft Visual Studio", "*", "*")))
    hits = [h for root in roots
            for h in glob.glob(os.path.join(root, "VC", "Tools", "MSVC", "*", "bin", "Hostx64", "x86", name))]
    return max(hits, key=_version_key) if hits else None


def javac():
    """Full path of javac.exe (JDK 9 or newer, for --release 8), or None. Order: JAVA_HOME, PATH,
    the usual JDK folders (Oracle, Adoptium, Microsoft, Zulu), the newest first."""
    home = os.environ.get("JAVA_HOME")
    if home and os.path.exists(os.path.join(home, "bin", "javac.exe")):
        return os.path.join(home, "bin", "javac.exe")
    found = shutil.which("javac")
    if found:
        return found
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    hits = [h for vendor in ("Java", "Eclipse Adoptium", "Microsoft", "Zulu")
            for h in glob.glob(os.path.join(pf, vendor, "*", "bin", "javac.exe"))]
    return max(hits, key=_version_key) if hits else None
