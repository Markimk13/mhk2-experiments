#!/usr/bin/env python3
"""Build the release zips of the Moorhuhn Kart 2 patch.

usage: make_release.py <original MHK2-XXL.exe> [dist dir]

Runs patch_200cc.py once per language and writes dist/mhk2-patch-<version>-<lang>.zip, each with
MHK2-XXL.exe, data/MK2/text-20.csv, tools/patch_200cc.py (for --unlock and the other commands) and
a short install note. The exe is the same in all of them.
"""
import os
import sys
import tempfile
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import patch_200cc as P

NOTES = {
    "de": "Moorhuhn Kart 2 XXL - Patch %s (200 cc, 250 cc, Tuning, 60-FPS-Fahrphysik, eigene Phantome)\r\n"
          "\r\n"
          "Installation: den Inhalt des ZIPs in den Spielordner entpacken\r\n"
          "(vorher die originale MHK2-XXL.exe sichern). exe und data sind noetig.\r\n"
          "\r\n"
          "Klassen freischalten (Python 3 noetig; im Spielordner, das Spiel vorher beenden):\r\n"
          "  py tools\\patch_200cc.py --unlock settings.dat          50 bis 250 cc, je beide Meisterschaften\r\n"
          "  py tools\\patch_200cc.py --unlock-tuning settings.dat   dasselbe und die Tuning-Klasse\r\n"
          "Die exe selbst aus der originalen bauen:\r\n"
          "  py tools\\patch_200cc.py \"<originale MHK2-XXL.exe>\" out\r\n"
          "\r\n"
          "Beschreibung: https://github.com/Markimk13/mhk2-experiments\r\n"
          "\r\n"
          "Inoffizielles Fan-Projekt. Moorhuhn Kart 2 gehoert seinen Rechteinhabern.\r\n",
    "en": "Moorhuhn Kart 2 XXL - patch %s (200 cc, 250 cc, tuning class, 60 FPS physics, own phantoms)\r\n"
          "\r\n"
          "Install: unpack the zip into the game folder\r\n"
          "(keep a backup of the original MHK2-XXL.exe). The exe and data are both needed.\r\n"
          "Only the patch's own menu texts are English; the game's own menus stay German.\r\n"
          "\r\n"
          "Unlock the classes (needs Python 3; in the game folder, with the game closed):\r\n"
          "  py tools\\patch_200cc.py --unlock settings.dat          50 to 250 cc, both championships each\r\n"
          "  py tools\\patch_200cc.py --unlock-tuning settings.dat   the same and the tuning class\r\n"
          "Build the exe yourself from the original one:\r\n"
          "  py tools\\patch_200cc.py \"<original MHK2-XXL.exe>\" out\r\n"
          "\r\n"
          "Description: https://github.com/Markimk13/mhk2-experiments\r\n"
          "\r\n"
          "Unofficial fan project. Moorhuhn Kart 2 belongs to its rights holders.\r\n",
}
assert NOTES.keys() == P.TEXTS.keys()


def main():
    if len(sys.argv) not in (2, 3):
        raise SystemExit(__doc__)
    exe = sys.argv[1]
    dist = sys.argv[2] if len(sys.argv) > 2 else os.path.join(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))), "dist")
    os.makedirs(dist, exist_ok=True)
    patched, _, patches = P.patch_exe(exe, (P.FACTOR_200, P.FACTOR_250), (P.PULL_200, P.PULL_250))
    for lang in sorted(P.TEXTS):
        out = os.path.join(dist, "mhk2-patch-%s-%s.zip" % (P.PATCH_VERSION, lang))
        with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr("MHK2-XXL.exe", patched)
            z.writestr("data/MK2/text-20.csv", P.text_overrides(lang).encode("cp1252"))
            z.write(P.__file__, "tools/patch_200cc.py")       # for --unlock and the other commands
            z.writestr("LIESMICH.txt" if lang == "de" else "README.txt",
                       (NOTES[lang] % P.PATCH_VERSION).encode("cp1252"))
        print("wrote %s (%d bytes, %d patch sites)" % (out, os.path.getsize(out), len(patches)))


if __name__ == "__main__":
    main()
