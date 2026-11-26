---
name: public-docs
description: Structure and writing style for the docs of this repository (README.md, CHANGELOG.md, docs/*.md). Use before you write or change any of them, for example the docs update at a release.
---

# Docs of mhk2-experiments

The user asked for this on 2026-11-26: non-developers must understand the docs. Developer
things and detailed numbers stay in their own places, apart from what a player needs.

The repository is GitHub Markimk13/mhk2-experiments. Also read
[../../writing-style.md](../../writing-style.md). This skill adds the rules for the docs to it.

## The three readers

| Reader | Knows | Wants | Reads |
| --- | --- | --- | --- |
| **Player** | The game. No programming. English is often a second language, and the game is German. | Install the patch, find a setting, know what it does in the race. | `README.md`, the top part of each player page, `CHANGELOG.md` |
| **Curious player** | The same. Likes numbers. | Measured speeds, how a value was found, what earlier versions did. | The section `## Details` at the end of a player page |
| **Developer** | Python, x86, hex editors, modding. | How the patch changes the exe, the save file layout, building, other exe versions. | The developer pages |

Every sentence belongs to exactly one reader. Before you write a sentence, decide whose it is.
Then put it into that reader's place.

## Which text is whose

**Player text** may contain:
- menu paths with the German names (`*Hauptmenü → Einstellungen → 60-FPS-Fahrphysik*`),
- what a setting does in the race, its default, and when to use it,
- simple numbers that a player sees in the game: km/h, %, seconds, places, points,
- the commands that a player needs (`--unlock`, `--unlock-tuning`, `--physics60`,
  `--player-name`), each in its own copy-ready `powershell` block,
- file names that a player touches (`MHK2-XXL.exe`, `settings.dat`, `data\Phantom\…`).

**Details** (only in `## Details` at the end of a player page):
- tables of measurements, game units per second, test conditions (FPS, track, number of races),
- how a value or a line was found (fits, number of test races, badness values),
- values of earlier patch versions and why they changed.

**Developer text** (only on the developer pages):
- exe addresses, hooks, patch sites, x86 code, section names (`.mod200`),
- `settings.dat` offsets and markers (`TUNE`, `OWNP`, `GEGN`, …), text ids, menu page numbers,
- formulas as the code computes them (`t + (1 − t) · g`, the suspension parameters),
- patcher options for rebuilding (`--factor`, `--pull`, `--listing`, `--lang`), SHA-256 values,
  `make_release.py`.

If a player page needs a developer fact, write one plain sentence and link to the developer
page. Example: "The patch keeps these values in unused parts of `settings.dat`, so old saves
keep working ([How it works](how-it-works.md#save-file))."

## File map

Keep the file names. Release pages and issues link to them.

| File | Reader | Content |
| --- | --- | --- |
| `README.md` | Player | The overview, see below |
| `CHANGELOG.md` | Player (+ developer part) | What changed in each version, see below |
| `docs/README.md` | All | The index: the same two tables as in `README.md` |
| `docs/engine-classes.md` | Player | 200 cc and 250 cc, how to unlock every class |
| `docs/tuning-class.md` | Player | The tuning class: pages, values, presets, *Am Limit*, *Top speed* |
| `docs/opponents.md` | Player | The page *Gegner* (since 1.10): *Tempo*, *Verbesserte Gegner*, how the computer karts drive in each class |
| `docs/60fps-physics.md` | Player | The switch *60-FPS-Fahrphysik* |
| `docs/phantom-karts.md` | Player | Own phantoms, the best run as phantom, the name |
| `docs/good-to-know.md` | Player | Short answers: limits, known problems, things not tested, mhk2_manager, where to report |
| `docs/building.md` | Developer (first section: player) | First *Other versions of the exe* (player text: check your exe, try the zip, report it). Then building the exe, the patcher's options, the release zips |
| `docs/how-it-works.md` | Developer | Everything from the list "Developer text", one section for each feature, in the same order as the player pages |

A new feature gets a new player page when it has its own menu page or more than 3 settings.
Otherwise it goes into the player page it belongs to, or into `good-to-know.md`. Add every new
page to both tables (`README.md` and `docs/README.md`). The two tables must have the same rows.

## Structure of each file

### README.md

The sections in this order:

1. `# <title>`: the name of the patch and the main features, one line.
2. One paragraph: what the patch is, for which game version. Then a list of the main features,
   one line each, in player words.
3. `> **Kurz auf Deutsch:**`: a German summary of at most 10 lines: the features, how to
   install, the unlock command, the link to *Other versions of the exe*.
4. `## Install`: numbered steps. Then the file table, the two zips (de / en), the version number
   in the main menu, and updating from an earlier version.
5. `## Commands: build the exe, unlock the classes`: first the build command, then the
   commands that change `settings.dat`. One `powershell` block for each command, and one
   sentence before it about what it does. Keep this heading (user, 2026-11-26). Links point to
   its anchor `#commands-build-the-exe-unlock-the-classes`.
6. `## What the patch does`: one paragraph of at most 4 lines for each feature, with the menu
   path, what the player gets, a link `→ [Page](docs/page.md)`, and one screenshot. No numbers
   from measurements here.
7. `## Documentation`: two tables, `**For players**` and `**For developers**`. Columns:
   Document, Content. The content column names the topics in player words.
8. `## How this was made`, `## Related projects`, `## Rights`: keep them as they are, unless
   the user changes them.

### Player pages (docs/*.md)

1. The first line: `[← Overview](../README.md) · [All documents](README.md)`.
2. `# <feature name>`.
3. A summary of 1 to 3 sentences: what the feature is and what the player gets from it.
4. `## Where to find it`: the menu path, how to unlock it, a screenshot.
5. `## How to use it` or `## The settings`: one subsection or one table row for each setting.
   For each: the German name, an English explanation, the steps, the default, the effect in the
   race. Tables: Setting, Values, Default, What it does.
6. `## Good to know` (optional): limits, problems, tips. One bullet each.
7. `## Details` (optional, always last): the text from the list "Details". Start it with one
   sentence: "This section is for players who want the numbers."
8. At the end of the page, if it has a developer part: `How the patch does it:
   [How it works](how-it-works.md#<section>).`

### docs/good-to-know.md

Short bullets with a bold lead (`- **Speed while racing.** …`), at most 4 lines each. Group them
under `## Limits`, `## Not tested`, `## Other programs`, `## Problems and reports`. The last
bullet links to the GitHub issues.

### Developer pages

- `docs/how-it-works.md`: start with one sentence: "This page is for developers. Players find
  everything they need on the other pages." Then one `##` section for each feature, with the
  same name as its player page, plus `## Save file` for the `settings.dat` layout. Exact
  numbers, addresses and formulas are welcome here.
- `docs/building.md`: `## Other versions of the exe` first, in player text. Then
  `## Building it yourself`, then `## Release zips`.

### CHANGELOG.md

- At the top: one sentence about saves, as now.
- One section `## <version>` for each release, newest first. `make_release.py` needs it.
- Inside, these subsections in this order, only the ones that have entries:
  `### New`, `### Changed`, `### Fixed`, `### For developers`.
- One bullet for each change, at most 2 sentences, in player words. Start with the place in the
  game (`Tuning class:`, `Computer karts:`, `Menu:`). Link to the player page for more.
- Put patcher options, `settings.dat` markers and other developer facts only under
  `### For developers`.
- Keep the sections of 1.9 and older as they are. Old sections stay history.

## The general writing rules, applied to the docs

[../../writing-style.md](../../writing-style.md) holds for every Markdown file of this repository. This
is what each rule means in the docs. The current docs (up to 1.9) break most of these rules.
Fix a paragraph when you change it.

| Rule | In the docs | Not like this (current docs) | Like this |
| --- | --- | --- | --- |
| Short sentences: at most 20 words for steps, 25 for descriptions | Count the words. Player text: aim for 15. Details and developer pages: 25 at most too. | "The game only limits itself to 200 FPS and runs one physics step per frame whenever a frame is shorter than 1/60 s." | "The game runs at up to 200 FPS. It runs one physics step in each frame." |
| One idea per sentence | No semicolons, no dashes that join two ideas, no "so" or "which" that start a second idea. | "200 cc is as fast as 150 cc with the siren, 250 cc as fast as one with the power can." | "200 cc is as fast as 150 cc with the siren. 250 cc is as fast as 150 cc with the power can." |
| Active voice | Name who acts: you, the game, the patch, the computer karts. | "The class opens with a win of Meisterschaft 2." | "Win Meisterschaft 2 in 250 cc to unlock the class." |
| Imperative for instructions | Steps and commands start with the verb. | "To check yours, in PowerShell in the game folder:" | "Open PowerShell in the game folder. Run this command:" |
| One word, one meaning | Use the term list below on every page. | *ghosts*, *phantoms*, *phantom karts* mixed | *phantom* everywhere |
| Simple, common words | Write for a player with school English. | "lengthens the gearing", "parts", "settles" | "gives a higher top speed", "the karts separate", "stays at" |
| Do not omit articles or verbs | Also in table cells and lists. A list item may start with a noun only when it is a label in bold. | "Measured with Moorhuhn on a flat straight" | "The tests used Moorhuhn on a flat straight." |
| No phrasal verbs | Also in menu explanations. | "open up", "put back", "work around" | "open", "restore", "avoid" |
| No vague words | Give the number or the condition. "About" is allowed with a measured number. | "a little higher", "far more often", "may well" | "<n> pixels higher", "<n> times as often", "can" |
| Lists for sequences | Install steps, unlock steps, menu steps: numbered list, one action for each step. | Install as one paragraph | `1. Download the zip.` `2. Unpack it into the game folder.` |

These rules for the docs come on top:

- **"You" is the player.** "Press → to raise the value", not "The value is raised with →".
- **German names in italics, with English at the first use on a page:** "*Gegner* (opponents)".
  After that, use only the German name. Use the exact menu text from `text-20.csv`.
- **Menu paths with →:** `*Hauptmenü → Einstellungen → 60-FPS-Fahrphysik*`.
- **km/h for players, units/s only in Details.** 1 unit/s = 3.6 km/h.
- **One term for each thing**, the same on all pages: *computer karts* (not AI, bots,
  opponents), *class* (not engine class or ccm, except in the title of `engine-classes.md`),
  *phantom* (not ghost), *championship* or *Meisterschaft*, *preset* or *Vorlage*.
- **Paragraphs of at most 5 lines.** Use a list or a table when a paragraph names more than 3
  things.
- **Numbers with their meaning:** "100 % (no handicap, as in 250 cc)", not "100 %".
- **No history in player text.** "Up to 1.8 …" goes into `## Details` or into the changelog.
- **No open questions in player text.** Unknown things go into `good-to-know.md` under
  `## Not tested`, or into a GitHub issue.
- **Screenshots** are in `screenshots/`. From docs/, link them as `../screenshots/…`. A new
  screenshot with a highscore list needs a check for other players' names first.
- **Never in the docs:** links into `.claude\` (Claude's notes, not for readers), paths of the
  user's PC, the user's other player names, the machine id of phantom files.

## Where the facts come from

Until the merge into this repository (2026-11-26), a one-file README in the user's private
repository collected every feature, and a release copied its changes here. Now the facts of a
release come from:

1. The commits since the last release (`git log v<last release>..`, and
   `git diff v<last release> -- tools/patch_200cc.py` for the menus and texts).
2. The notes in `.claude/memory/` that those commits changed.
3. The patcher's texts (`TEXTS` in `tools/patch_200cc.py`) for the exact menu names.

Put each fact into the file that the file map gives, for the correct reader, in the style of
this skill.

## Checklist before you finish

1. Every new or changed sentence belongs to one reader and is in that reader's place.
2. No player section contains an address, offset, marker, text id, code formula or rebuild
   option.
3. Every player page has the summary, *Where to find it* and the settings, in this order.
   `## Details` is the last section.
4. Every German menu name has its English meaning at its first use on the page.
5. The two tables in `README.md` and `docs/README.md` have the same rows.
6. `CHANGELOG.md` has the section for the release, with player bullets and developer bullets
   apart.
7. Every changed sentence follows the table "The general writing rules, applied to the docs".
   Count the words of the long ones.
8. Every player-visible change since the last release is in the docs.
9. All links work. Check the anchors after you rename a heading: GitHub makes them from the
   heading text.
