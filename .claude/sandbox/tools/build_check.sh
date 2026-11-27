#!/bin/sh
# Build the patched exe into .claude/sandbox/builds/<name> and compare the new code with
# dumpbin's disassembly (the check of "Checking new patcher code" in .claude/README.md).
# usage (Git Bash, from the repository): sh .claude/sandbox/tools/build_check.sh [name]
# dumpbin exits with 157 when Git Bash starts it directly, so PowerShell runs it.
set -e
NAME=${1:-new}
OUT=.claude/sandbox/builds/$NAME
EXE=$(py -c "import json;print(json.load(open('.claude/sandbox/local.json'))['original_exe'])")
DUMPBIN=$(ls -d "/c/Program Files"*/"Microsoft Visual Studio"/*/*/VC/Tools/MSVC/*/bin/Hostx64/x86/dumpbin.exe | head -1)
WIN_DUMPBIN=$(cygpath -w "$DUMPBIN")
mkdir -p "$OUT"
rm -f "$OUT/listing.txt" "$OUT/mod200.dis.txt"
py tools/patch_200cc.py "$EXE" "$OUT" --listing "$OUT/listing.txt" > "$OUT/build.log" 2>&1 || { tail -5 "$OUT/build.log"; exit 1; }
tail -2 "$OUT/build.log"
powershell -NoProfile -Command "& '$WIN_DUMPBIN' /disasm /section:.mod200 '$OUT/MHK2-XXL.exe' | Out-File -Encoding ascii '$OUT/mod200.dis.txt'"
py .claude/sandbox/tools/verify_listing.py "$OUT/listing.txt" "$OUT/mod200.dis.txt" | sed 's/, data at.*//'
