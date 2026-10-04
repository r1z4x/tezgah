Run `tezgah-pony $ARGUMENTS` and report the one line it prints.

The installed CLI is the source of truth for the level, and it owns the state
file (`~/.config/tezgah/ponytail.level`) - never edit that file by hand, and do
not argue for a level: the user's argument is the decision. Resolve the command
first, because this machine may not have tezgah's bin dir on PATH:

```sh
pony=$(command -v tezgah-pony || echo "$HOME/.config/tezgah/bin/tezgah-pony")
"$pony" $ARGUMENTS
```

- No argument: run it bare, which prints the level in force.
- `lite` / `full` / `ultra`: sets it. `full` prints the default and removes the
  file.
- Anything else: the CLI exits 2 with the usage on stderr - show that to the
  user and stop.

Then say the new level and what changed in one line, and nothing else. The level
rides the per-turn reminder from the next turn on, so there is nothing to
re-inject and no file to edit.
