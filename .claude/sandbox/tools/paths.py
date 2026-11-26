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
"""
import json
import os

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
