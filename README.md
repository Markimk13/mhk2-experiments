# Moorhuhn Kart 2 – 200 cc, 250 cc and a tuning class, 60 FPS physics switch, own phantom karts

A fan patch for **Moorhuhn Kart 2 XXL** (German version V1.0, exe build Mar 23 2004). It adds

- two engine classes, **200 cc** and **250 cc**, next to 50 / 100 / 150 cc,
- a sixth class, **Tuning**, whose kart and world you set up yourself in the game: gearing,
  pull, grip, weight, brakes, steering, downforce, gravity and the pace of the computer karts,
- a switch **60-FPS-Fahrphysik** in the options menu that makes the kart drive at any frame rate
  the way it does at 60 FPS (off by default), and
- **phantom karts without a helper program**: the game races against your own best run,
  replaces the phantom when you beat it, and labels new phantom files with data version and
  player name.

> **Kurz auf Deutsch:** Ein Fan-Patch für Moorhuhn Kart 2 XXL: zwei neue Leistungsklassen
> (200 cc, 250 cc), eine Tuning-Klasse mit eigenen Fahrwerten und Vorlagen, ein Schalter
> *60-FPS-Fahrphysik* (das Kart fährt bei 200 FPS wie bei 60 FPS) und eigene Phantom-Karts
> ohne Zusatzprogramm. Installation: das ZIP `…-de.zip` aus den
> [Releases](../../releases) in den Spielordner entpacken (vorher `MHK2-XXL.exe` sichern).
> Klassen ohne Meisterschaftssieg freischalten (Python 3, im Spielordner, Spiel beendet):
> `py tools\patch_200cc.py --unlock settings.dat` (50 bis 250 cc) oder
> `py tools\patch_200cc.py --unlock-tuning settings.dat` (dazu die Tuning-Klasse); die exe
> selbst bauen: siehe [Commands](#commands-unlock-the-classes-build-the-exe). Der Patch ist für
> die deutsche V1.0 von der *10 Jahre Moorhuhn*-CD gemacht; andere exe-Versionen (V1.1,
> englisch, …): siehe [Other versions of the exe](docs/building.md#other-versions-of-the-exe).
> Die Beschreibung unten ist auf Englisch; die Menüs im Spiel sind deutsch.

## Install

You need an installed **Moorhuhn Kart 2 XXL**; the patch does not include the game's data. Take
the zip from the [Releases](../../releases) page and unpack it into the game folder (the one with
`MHK2-XXL.exe`). Keep a backup of the original exe first.

| File | Purpose |
| --- | --- |
| `MHK2-XXL.exe` | patched executable |
| `data\MK2\text-20.csv` | new menu texts (plain text, editable) |
| `tools\patch_200cc.py` | the patcher, for unlocking the classes and the other [commands](#commands-unlock-the-classes-build-the-exe) (needs Python 3) |

There are two zips with the same exe: `…-de.zip` has the new menu texts in German, `…-en.zip`
in English. The English one translates only the patch's own texts; the game's own menus stay
German (*Weiter* = next, *Zurück* = back). The screenshots show the German texts.

Both files are needed – without the text file the new menu entries read `**TEXT*NOT*FOUND***`.
The main menu shows the patch version under its buttons. A release has two digits (1.8, 1.9);
builds in between have a third one that counts the changes since the last release (1.8.8 is
the eighth change after 1.8).

When updating from an earlier version of this patch, replace both again. `settings.dat` keeps its
size, so existing saves keep working. A save from version 1.6 or older gets the gravity (100 %)
added the first time the tuning class is opened, one from 1.8 or older *Gegner* (100 %); its
tuning values and own presets stay. Since 1.9 the tuning class has to be unlocked (see
[Unlocking](docs/engine-classes.md#unlocking-200-cc-250-cc-and-tuning));
on a save that has not won Meisterschaft 2 in 250 cc it is hidden until then.

## Commands: unlock the classes, build the exe

The patch comes with one Python script, `tools\patch_200cc.py` (in this repository and in the
release zips). It needs [Python 3](https://www.python.org/downloads/) and nothing else. Run it
in the game folder, with the game closed (the game writes `settings.dat` itself while it runs).

**Unlock the classes without winning the championships:**

```powershell
py tools\patch_200cc.py --unlock settings.dat
```

opens 50 cc to 250 cc, each with Meisterschaft 2 and tracks 5–8.

```powershell
py tools\patch_200cc.py --unlock-tuning settings.dat
```

does the same and opens the tuning class too.

**Other settings in `settings.dat`:** `--physics60 on|off settings.dat` (the [60 FPS
switch](docs/60fps-physics.md)) and `--player-name "Name" settings.dat` (the name in new phantom files, at most 12
characters).

**Build the patched exe yourself** instead of taking the one from the zip, from your own
original exe (for example the backup you made):

```powershell
py tools\patch_200cc.py "<original MHK2-XXL.exe>" out
```

writes `out\MHK2-XXL.exe` and `out\data\MK2\text-20.csv`, the same files as in the release zip;
copy both into the game folder. Add `--lang en` for the English menu texts. More in
[Building it yourself](docs/building.md).

## What the patch does

**200 cc and 250 cc.** Two engine classes above 150 cc. They have longer gearing and pull
harder: 200 cc is as fast as a 150 cc kart with the siren, 250 cc as fast as one with the power
can. Each is unlocked by winning Meisterschaft 2 in the class below, like the stock classes. The
computer karts are held back less than in the stock classes: by half as much in 200 cc, not at
all in 250 cc. → [200 cc, 250 cc and Tuning](docs/engine-classes.md)

![engine class menu](screenshots/01-engine-menu.png)

**Tuning class.** A sixth class, unlocked by winning Meisterschaft 2 in 250 cc, whose values you
set in the game: gearing, engine power, grip, weight, brakes, steering and downforce of the
kart, the gravity, and the pace of the computer karts. Built-in presets (the five classes and
fourteen more) and eight slots for your own; extreme values are allowed, and a line shows how
close they are to the limit of what still races well, and the top speed they give.
→ [Tuning class](docs/tuning-class.md)

![tuning page](screenshots/08-tuning-page.png)

**60 FPS physics switch.** *Einstellungen → 60-FPS-Fahrphysik*: the stock game's wheel springs
get softer the higher the frame rate, so at 200 FPS the kart sags, slides and hops. Switched on,
it drives at any frame rate as it does at 60 FPS. → [60 FPS physics switch](docs/60fps-physics.md)

**Phantom karts.** The game races against your own best run, replaces the phantom when you beat
it, and writes your name and the data version into new phantom files.
→ [Phantom karts](docs/phantom-karts.md)

**Smaller things.** The name page remembers the name you typed last. At high frame rates the
computer karts no longer fire their power-ups more often than at 60 FPS. The main menu shows the
patch version.

## Documentation

| Document | Content |
| --- | --- |
| [200 cc, 250 cc and Tuning](docs/engine-classes.md) | How the classes are unlocked, gearing and pull, measured speeds, the computer karts |
| [Tuning class](docs/tuning-class.md) | The tuning pages, every value, the *Am Limit* line, top speed, presets, own presets, the pause page, measurements, the downforce rules |
| [60 FPS physics switch](docs/60fps-physics.md) | Why the game drives differently at 200 FPS, what the switch changes, the computer karts' power-ups |
| [Phantom karts](docs/phantom-karts.md) | Own ghosts, the best run as phantom, version and name in the files |
| [Building it yourself](docs/building.md) | The patcher, building the exe from your own, other versions of the exe |
| [How it works](docs/how-it-works.md) | What the patch changes in the exe and where it keeps its data in `settings.dat` |
| [Good to know](docs/good-to-know.md) | Limits, things that were not tried, mhk2_manager |
| [Changelog](CHANGELOG.md) | What changed in each version |

## How this was made

The patch was made with **Claude**, Anthropic's AI model, working in Claude Code; Marki13 chose
the features, made the decisions and played the results. There is no source code of the game;
everything comes from the exe:

- Claude disassembled the original exe, traced the code it needed (classes, kart physics,
  menus, save file, phantom files) and wrote down what it found.
- Claude wrote the patcher, including the new x86 machine code it adds to the exe. Each new
  instruction was compared with a disassembler's reading of the built exe before it was used.
- Claude tested every version in a separate copy of the game, run in a window with simulated
  input, and took the measurements and screenshots in this README.

So the exe in the releases was edited by an AI, not by hand. It was tested, but report anything
odd.

## Related projects

- [mhk2_manager](https://github.com/Markimk13/mhk2_manager) – by Marki13, the author of this
  patch: a Java program that keeps your highscores of time trials, championships and duels and
  lets you pick the phantoms you race against, including imported ones from friends. From V1.1
  on it knows 200 ccm, 250 ccm and Tuning (see [Good to know](docs/good-to-know.md)).

Other Moorhuhn Kart projects by **SKevo**. This patch uses no code or data from them; they are
worth a look if you like this one:

- [idlemod](https://github.com/SKevo18/idlemod) – a command-line tool that unpacks, patches and
  repacks the data files of Moorhuhn Kart 1–4 and related games, with ready-made mods. Its
  `cheat_engine` folder has Cheat Engine tables (and a standalone trainer for Moorhuhn Kart 2)
  that change the running game: endless items, no falling off the track, respawn tweaks and more.
- [Moorhuhn Kart: Open Source](https://github.com/mhk-os/mhk-os) – a remake of the game with
  mod support; Moorhuhn Kart 2, 3, Extra and Thunder are converted into it as mods.

## Rights

Moorhuhn Kart 2 and everything in it belong to their rights holders. This is an unofficial fan
project, not connected to them. The release zips contain a modified copy of the game's exe and
are of no use without an installed game. If a rights holder objects, the files will be taken
down. The patcher script and the texts written for this project are under the MIT license
([LICENSE](LICENSE)).
