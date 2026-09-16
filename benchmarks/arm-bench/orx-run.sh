#!/usr/bin/env bash
# The project's run command. Identical on every node of tezgah-harness-research:
# a node varies only the committed configuration (arms.json and the contract
# variant its arms point at), never this file and never the environment.
set -euo pipefail
cd "$(dirname "$0")"

# The arms talk to a hosted provider. Take the key from the file
# unconditionally: an ambient OPENROUTER_API_KEY in the caller's shell may be a
# different, exhausted key, and the run contract must not depend on which shell
# launched it (this cost a block: omp answered 401 in 1.9s and every cell
# failed while the key in the file was fine).
if [ -f "$HOME/.config/openrouter/key" ]; then
  OPENROUTER_API_KEY="$(cat "$HOME/.config/openrouter/key")"
  export OPENROUTER_API_KEY
fi

exec python3 orx_block.py
