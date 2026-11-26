"""Build mhk2_manager.jar from the manager's sources, keeping the layout of the existing jar.

usage: build_manager_jar.py [manager repo] [out jar]

The manager (..\\mhk2_manager, the user's own tool) has no build file; its jar was exported from
Eclipse in 2020 for Java 8. This script compiles every .java with JDK 17's javac --release 8
(source encoding Cp1252, classpath source/lib/utils.jar) into .claude/sandbox/manager/classes,
then writes a new jar: the entries of the jar in the repo (manifest first, the crc classes from
utils.jar, the source phantoms, .project / .classpath) with every class under main/ replaced by
the fresh ones and the .properties files taken from the sources. Default output:
.claude/sandbox/manager/mhk2_manager.jar; copy it over source/mhk2_manager.jar when it is good.
"""
import os
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
WORK = os.path.join(os.path.dirname(HERE), "manager")
sys.path.insert(0, HERE)
import paths                                        # noqa: E402


def main():
    repo = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else
                           os.path.join(HERE, "..", "..", "..", "..", "mhk2_manager"))
    out = sys.argv[2] if len(sys.argv) > 2 else os.path.join(WORK, "mhk2_manager.jar")
    src = os.path.join(repo, "source", "src")
    base = os.path.join(repo, "source", "mhk2_manager.jar")
    classes = os.path.join(WORK, "classes")
    if os.path.isdir(classes):
        for r, ds, fs in os.walk(classes, topdown=False):
            for f in fs:
                os.remove(os.path.join(r, f))
            for d in ds:
                os.rmdir(os.path.join(r, d))
    os.makedirs(classes, exist_ok=True)
    sources = [os.path.join(r, f) for r, _, fs in os.walk(src) for f in fs if f.endswith(".java")]
    listing = os.path.join(WORK, "sources.txt")
    with open(listing, "w", encoding="utf-8") as f:
        f.write("\n".join('"%s"' % s.replace("\\", "/") for s in sources))
    javac = paths.javac()
    if not javac:
        raise SystemExit("needs javac of a JDK 9 or newer (JAVA_HOME, PATH or Program Files\\Java)")
    subprocess.run([javac, "--release", "8", "-encoding", "Cp1252", "-nowarn",
                    "-cp", os.path.join(repo, "source", "lib", "utils.jar"),
                    "-d", classes, "@" + listing], check=True)

    fresh = {}
    for r, _, fs in os.walk(classes):
        for f in fs:
            p = os.path.join(r, f)
            fresh[os.path.relpath(p, classes).replace(os.sep, "/")] = open(p, "rb").read()
    for r, _, fs in os.walk(src):
        for f in fs:
            if f.endswith(".properties"):
                p = os.path.join(r, f)
                fresh[os.path.relpath(p, src).replace(os.sep, "/")] = open(p, "rb").read()

    old = zipfile.ZipFile(base)
    written = set()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for info in old.infolist():
            n = info.filename
            if n.startswith("main/") and n.endswith(".class") and n not in fresh:
                print("dropped", n)
                continue
            data = fresh.get(n, old.read(n))
            z.writestr(n, data)
            written.add(n)
        for n in sorted(set(fresh) - written):
            z.writestr(n, fresh[n])
            print("added", n)
    print("wrote %s (%d entries, %d compiled classes)"
          % (out, len(zipfile.ZipFile(out).namelist()), sum(n.endswith(".class") for n in fresh)))


if __name__ == "__main__":
    main()
