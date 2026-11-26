---
name: mhk2-public-release
description: this public repo (Markimk13/mhk2-experiments) – how the project became public, what never goes in, the release zips, English texts, the game paths in local.json, version numbers, docs, issues
metadata:
  type: project
---

On 2026-11-19 the user decided to share the patch on a Moorhuhn Discord server, as ready-patched
exe zips (the game's 144 MB `mhk2-00.dat` is still needed, so the exe alone is useless). From
2026-11-19 this repository (github.com/Markimk13/mhk2-experiments, MIT license, fresh history)
held the release copy of the patcher and the player docs, while the work went on in the user's
private repository. Later the user made the whole project public: the private repository's
files moved into this one, without its history (first drafted on 2026-11-22, done on
2026-11-26).

- **What moved:** the patcher (it replaced the release copy), TODO, `.claude/` (notes, skills,
  sandbox tools, fixtures). README, `docs/`, CHANGELOG, screenshots and
  `tools/make_release.py` were here already. **Not moved:** the user's game folders (records,
  phantoms, the original exe), `output/` (generated; ignored here), the private repository's
  history (it holds the game files and commits under a personal e-mail address), the private
  one-file README (this repository's README and `docs/` replace it), the issue queue and the user's local hooks
  (ignored here, see `.gitignore`).
- **Game files** are never committed (`.gitignore`: `*.exe`, `*.dat`, `output/`, `dist/`; the
  fixture `settings.dat` is the one exception). The sandbox finds them through
  `.claude/sandbox/local.json` (ignored), read by `.claude/sandbox/tools/paths.py`; on the user's
  PC it points into their private repository's game folders.
- **Fixtures:** `fixtures/Phantom` holds the game's 24 original phantoms (from
  `data\Phantom\source`, where mhk2_manager keeps them; no player name, the developers' ids).
  `fixtures/settings.dat` is the user's save of 2026-11-18 with a second player name replaced by
  "Marki13" (79 name fields of 16 bytes; the file has no checksum), and the tail of the old
  name in seven empty fields (first byte 0, at 0xA050..0xA11C) zeroed. The PC's machine id (registry
  `HKCU\Software\mhk2`, in the phantom header table at +0x28 of each entry, 168 times) is
  replaced by 32 dashes, the placeholder of the game's own phantoms (2026-11-26; the game
  refills that table from the phantom files, classtest and ghosttest pass). ghosttest.py's `main` stamps
  its phantom-3-01 in `game/` (name "Test-200", 21.55 s) because it needs a fast, named ghost.
- **Privacy checks before a commit:** no absolute paths with the user name, no machine id in a
  save or phantom, no player name
  other than "Marki13" in screenshots, fixtures or notes (never write the user's real name), commits under the GitHub noreply address
  (set in this repo's git config). `07-phantom-name.png` had the name replaced by the game's "-".
- **Release:** `py tools\make_release.py "<original exe>"` writes
  `dist\mhk2-patch-<PATCH_VERSION>-de.zip` and `-en.zip` (same exe; `data/MK2/text-20.csv` in
  the language; LIESMICH.txt / README.txt with the unlock and build commands;
  `tools/patch_200cc.py`, so `py tools\patch_200cc.py --unlock settings.dat` works in the game
  folder). The user copies the release page text from a draft, `dist\release-<version>.md`
  (ignored by git); they want the unlock and build commands prominent there and in the README
  (2026-11-22). The zips go to a GitHub Release, not into git. `release_check.py` (jobs group
  `release`) builds both zips with `make_release.py` and checks them; `make_release.py` refuses
  to build without a `## <release>` section in CHANGELOG.md, so between releases that check
  fails on purpose.
- **Related projects** in the README (SKevo's idlemod with its Cheat Engine tables, mhk-os, the
  user's mhk2_manager): checked on 2026-11-22, the patch took no code or knowledge from them, so
  the section is a courtesy, not a credit.
- **English:** `--lang en` / `TEXTS["en"]` translates only the patch's ~60 texts; the stock
  texts (Weiter, Zurück, menu titles) stay German. The game's own `text.csv` has 383 lines
  (13 KB, `.claude/sandbox/work/txt/data/mk2/text.csv`), so a full English overlay in
  `text-20.csv` would be possible (not done). Checked on 2026-11-19: the English texts fit on
  the class menu, tuning, Kart, Welt and own-preset pages.
- Language number 20: the game builds `text-NN.csv` with the format `%s-%02d.%s` (call at
  0x491A96); where NN comes from was not traced.

- **Version numbers** (user, 2026-11-22; suffix 2026-11-23: "1.10-pre2 instead of 1.9.2 ... a
  pre-suffix which is removed on release"): `PATCH_RELEASE` in the patcher is the last release
  (tag `v<release>`). `patch_version()` gives `<next release>-preN` (N = `git rev-list --count
  v<PATCH_RELEASE>..HEAD` + 1, the commit the build goes into) in a git checkout, the next
  release anywhere else; `make_release.py` always builds the release number. The version goes
  into the signature in the exe and into text 305, under the main menu's buttons. Releases so
  far: 1.8, 1.9 (2026-11-23). Until the merge the private repository counted from its own tags;
  the tags `v1.8` and `v1.9` of this repository sit on its release commits, so the count here
  starts again from there.
- **Docs** (user, 2026-11-22: "moving all details into a docs folder"; 2026-11-26: skill
  `.claude/skills/public-docs`, "make sure that also non-developers understand it"):
  `README.md` is the overview, the details are in `docs/` (one page per feature, `building.md`,
  `how-it-works.md`, `good-to-know.md`, `docs/README.md` the index), `CHANGELOG.md` has one
  section per release. Every release brings them up to date with all changes since the last one
  (user, 2026-11-24; the 1.9 sync had missed parts). Until the merge the private one-file README
  described the work in progress; what it said about 1.10 is not in `docs/` yet.
- **Issues** (user, 2026-11-22: "instead of having a TODO file, I'd like to create github issues
  in the public repo"): the open points are issues of this repository, written for players (no
  exe addresses, no links into `.claude/`). Labels: type `bug` / `feature` / `question`,
  `area: …` (classes, tuning, computer karts, phantoms & records, tracks, physics, menus), status
  `needs info`, `feedback wanted`, `help wanted`, `duplicate`, `wontfix`. Milestone per release
  (`1.10`: better computer karts #12 with sub-issues #13-15, more opponents #16, tracks #28 with
  sub-issues #29-31). Issues are closed by hand when the release is out. Issue forms in
  `.github/ISSUE_TEMPLATE/` (bug, feature; English, German welcome; blank issues off; questions go
  to the Discord server). Since 2026-11-24 the issue texts follow
  `.claude/writing-style.md`.

**How to apply:** work in this repository; commit and push only when the user says so. Before a
commit, run the privacy checks above. Related: [[mhk2-notes-live-in-repo]],
[[mhk2-user-context]], [[mhk2-engine-classes]].
