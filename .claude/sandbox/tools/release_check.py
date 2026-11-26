r"""Builds the release zips with tools\make_release.py and checks them (sandbox; no game needed).

usage: release_check.py <out dir>

Copies tools\make_release.py and tools\patch_200cc.py into <out dir>\tools, runs it on the
original exe (original_exe in .claude\sandbox\local.json, see paths.py) into <out dir>\dist and
checks both zips: the files, the same exe in both (= the patcher's own build with the release
number), the version in the exe and on the main menu, the patcher copy, the texts (cp1252, each
id once, the language), then a CHANGELOG section for the release. Prints "N checks ok, M failed"
(jobs.py group "release").
"""
import os
import shutil
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(os.path.dirname(HERE)))
sys.path.insert(0, os.path.join(REPO, "tools"))
sys.path.insert(0, HERE)
import paths  # noqa: E402
import patch_200cc as P  # noqa: E402

OK = [0, 0]


def check(label, got, want=True):
    good = got == want
    OK[0 if good else 1] += 1
    print("  %s %s: %r%s" % ("ok  " if good else "FAIL", label, got, "" if good else "   (expected %r)" % (want,)), flush=True)


def main():
    out = os.path.abspath(sys.argv[1])
    tools, dist = os.path.join(out, "tools"), os.path.join(out, "dist")
    shutil.rmtree(out, ignore_errors=True)
    os.makedirs(tools)
    shutil.copy(os.path.join(REPO, "tools", "make_release.py"), tools)
    shutil.copy(os.path.join(REPO, "tools", "patch_200cc.py"), tools)
    with open(os.path.join(REPO, "CHANGELOG.md"), encoding="utf-8") as f:       # make_release.py wants a
        changelog = f.read()                                                   # section for the release;
    section = "\n## %s\n" % P.patch_version(release=True)                     # a missing one is reported
    with open(os.path.join(out, "CHANGELOG.md"), "w", encoding="utf-8") as f:  # at the end
        f.write(changelog if section in changelog else changelog + section)
    orig = paths.original_exe()
    r = subprocess.run([sys.executable, os.path.join(tools, "make_release.py"), orig, dist], cwd=out,
                       capture_output=True, text=True)
    print(r.stdout + r.stderr)
    check("make_release.py ran", r.returncode, 0)
    version = P.patch_version(release=True)
    check("the release number has two digits", version.count("."), 1)
    want_exe = P.patch_exe(orig, (P.FACTOR_200, P.FACTOR_250), (P.PULL_200, P.PULL_250), version)[0]
    exes = {}
    for lang in P.TEXTS:
        path = os.path.join(dist, "mhk2-patch-%s-%s.zip" % (version, lang))
        check("%s zip exists" % lang, os.path.exists(path))
        if not os.path.exists(path):
            continue
        z = zipfile.ZipFile(path)
        names = set(z.namelist())
        for f in ("MHK2-XXL.exe", "data/MK2/text-20.csv", "tools/patch_200cc.py"):
            check("%s zip has %s" % (lang, f), f in names)
        check("%s zip has an install note" % lang, any(n.endswith(".txt") for n in names))
        exes[lang] = z.read("MHK2-XXL.exe")
        check("%s: the exe is the patcher's release build" % lang, exes[lang] == want_exe)
        check("%s: the exe carries version %s" % (lang, version),
              (P.SIGNATURE_PREFIX + b" " + version.encode() + b"\0") in exes[lang])
        check("%s: the patcher copy is this repo's" % lang,
              z.read("tools/patch_200cc.py") == open(os.path.join(REPO, "tools", "patch_200cc.py"), "rb").read())
        raw = z.read("data/MK2/text-20.csv")
        try:
            text = raw.decode("cp1252")
            check("%s: texts are cp1252" % lang, True)
        except UnicodeDecodeError as e:
            check("%s: texts are cp1252" % lang, str(e), "")
            continue
        ids = [int(line.split(";", 1)[0]) for line in text.split("\r\n") if line and not line.startswith("#")]
        check("%s: every text id once" % lang, len(ids), len(set(ids)))
        lines = dict((int(k), v) for k, v in (line.split(";", 1) for line in text.split("\r\n") if line and not line.startswith("#")))
        check("%s: main menu shows patch %s" % (lang, version), ("Patch %s<" % version) in lines.get(P.TXT_VERSION, ""), True)
        check("%s: the texts are the patcher's" % lang, text == P.text_overrides(lang, version))
        check("%s: top speed line in the language" % lang,
              lines.get(P.TXT_TOP, "").endswith(("ca. %d km/h</scale>" if lang == "de" else "about %d km/h</scale>")), True)
        check("%s: speed in the race" % lang, lines.get(P.TXT_SPEED), "<scale 0.75>%d km/h</scale>")
    if len(exes) == 2:
        check("both zips have the same exe", exes["de"] == exes["en"])
    check("CHANGELOG.md has a section for %s" % version, section in changelog)
    print("%d checks ok, %d failed" % tuple(OK))


if __name__ == "__main__":
    main()
