---
name: mhk2-notes-live-in-repo
description: "The user wants Claude's project knowledge, helper scripts and the test sandbox kept in the repo's .claude folder (rebuildable parts ignored by git), linked from CLAUDE.md"
metadata:
  node_type: memory
  type: feedback
  modified: 2026-11-18T13:00:03.505Z
---

On 2026-11-18 the user noticed that their private repository had no `.claude` folder and asked: "can you create it and write all things you put into memory, cache or whatever into there, with link from CLAUDE.md". Done the same day: `.claude/memory/` (copies of these notes), the helper scripts from the temp scratchpad, `.claude/README.md` and `CLAUDE.md` in the repo root (rules + note index).

On 2026-11-19 they added: "after commit, can you also move all other things you've created into this repo (like the sandbox)? resp. gitignore things that can be rebuilt". Done the same day: everything is in `.claude/sandbox/` now. Git keeps `tools/` (the scripts, formerly `.claude/scratch-tools/`) and `fixtures/` (the phantom folder and settings.dat the tests start from); `work/` (original exe, disassembly, extracted texts), `game/` (the game copy with the test builds), `builds/`, `runs/` and `shots/` are ignored. `setup_sandbox.py` rebuilds work/ and game/ from the game files (since the move to this public repository: the paths in `local.json`) and `output/`.

**Why:** my interpretation: the user wants what Claude knows and makes for the project to be visible and versioned with the project, not hidden in the user profile or lost with a temp folder (a temp scratchpad can be cleared by a reboot).

**How to apply:** when a memory note about this project is added or changed, change its copy in `.claude/memory/` too and keep the note list in `CLAUDE.md` current. Write helper scripts straight into `.claude/sandbox/tools/` and run tests in `.claude/sandbox/`; put builds to check under `builds/`, results under `runs/`. Do not start a new work folder in a temp directory. A new kind of generated file needs no ignore rule (everything in the sandbox except tools/ and fixtures/ is ignored); a new fixture the tests depend on goes into `fixtures/`. Repo changes are still committed only when the user says so. Related: [[mhk2-windowed-test-recipe]], [[mhk2-user-context]].
