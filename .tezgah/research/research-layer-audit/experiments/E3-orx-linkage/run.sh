#!/bin/sh
# E3 cells: is any artifact of a research line joined to an orx run, and does
# anything tezgah ships read orx's output?
set -u
cd "$(git rev-parse --show-toplevel)" || exit 1
ORX=${ORX:-/Users/rizax/.cargo/bin/orx}

echo "== cell A: the registered orx project =="
"$ORX" projects --json 2>&1
PID=$("$ORX" projects --json 2>/dev/null | python3 -c 'import json,sys; p=json.load(sys.stdin); print(p[0]["id"] if p else "")')
[ -n "$PID" ] && "$ORX" project view "$PID" 2>&1 | head -6

echo
echo "== cell B: does the project's run command path exist? =="
ls -l benchmarks/arm-bench/orx-run.sh 2>&1
echo "-- the commit that took it out of the tree:"
git log --oneline -1 5af240b 2>&1
git log --all --oneline -- '*orx-run.sh' 2>&1 | head -3
echo "-- tracked files under benchmarks/ at HEAD:"
git ls-files benchmarks | wc -l

echo
echo "== cell C: orx run or experiment ids inside research lines =="
grep -rEo '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}' .tezgah/research --include='*' 2>/dev/null | wc -l
echo "-- mentions of the word orx anywhere under .tezgah/research:"
grep -rl "orx" .tezgah/research 2>/dev/null | wc -l

echo
echo "== cell D: code in tezgah that consumes orx output =="
grep -rn "orx_bin()" hooks bin hosts statusline.py 2>/dev/null | grep -v '^bin/__pycache__'
echo "-- subprocess calls naming orx:"
grep -rn 'ORX\|"orx"' hooks bin hosts statusline.py 2>/dev/null | grep -v '^bin/__pycache__' | grep -c .
