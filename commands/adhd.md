Run `tezgah-adhd $ARGUMENTS` and report the one line it prints.

The installed CLI owns the state: it writes or removes
`~/.config/tezgah/adhd-off`, the kill switch that drops the act-on-it rule from
the text every host injects. Never create or delete that file by hand, and never
edit any other rule's switch from here.

```sh
adhd=$(command -v tezgah-adhd || echo "$HOME/.config/tezgah/bin/tezgah-adhd")
"$adhd" $ARGUMENTS
```

- No argument: run it bare, which prints `on` or `off`.
- `off`: disarms the rule everywhere on this machine.
- `on`: arms it again (`off` is the default).
- Anything else: the CLI exits 2 with the usage on stderr - show that to the
  user and stop.

Then say the new state in one line, and nothing else. A repo opts out on its own
with a `.no-adhd` mark, which this command does not touch - if the user wants
that, they say so and you create the file in the repo.
