#!/bin/sh
# Full check of the patch in the repository's output folder, in the sandbox (Git Bash).
#
# usage: sh .claude/sandbox/tools/run_checks.sh [name] [selector ...]
#        results go to .claude/sandbox/runs/<name> (default: check)
#
# A wrapper around jobs.py: test builds from output\, then every check as a small job
# (classtest and ghosttest scenarios, the races of the tuning class at 60 and 200 FPS, single
# tuning values at their limits, straight runs of the tuning rows and of 200 cc / 250 cc, engine
# braking, a 250 cc race), three at a time in the game folders game, game2, game3. About 12 to
# 15 minutes for all; selectors pick a part (see py tools/jobs.py --list). Windowed, without
# keyboard, focus or mouse; nothing starts while the user's own game runs.
# "touch .claude/sandbox/runs/<name>/stop" ends it after the current jobs.
cd "$(dirname "$0")/.." || exit 1
name=${1:-check}
[ $# -gt 0 ] && shift
py tools/jobs.py "$name" "$@"
