# Contributing

Small, single-purpose changes are the easiest to accept.

- A rule belongs in the shared core (`hooks/`) unless it is genuinely
  host-specific; a host difference belongs in its adapter under `hosts/<name>/`.
- Keep the diff as short as it can be while still correct — the project's own
  minimal-code rule applies to the project.

## Before a pull request

Run these checks. CI runs the same kinds of check; `.github/workflows/ci.yml` is
the list of what it runs, on which Python versions:

```bash
python3 -m compileall -q hooks hosts bin statusline.py   # byte-compile every script
python3 tests/impacted.py --ref origin/main               # the modules your change touches
ruff check .                                              # lint; config in pyproject.toml
python3 tests/impacted.py --all                           # the sharded full suite, once
```

`tests/impacted.py --ref <ref>` maps every path your change touched to the test
modules that exercise it and runs them in parallel; `--all` shards the whole
suite (~105 s against ~570 s serial). A change to `tests/support.py` or an
unmapped path runs everything - that is the fail-safe.

`ruff` comes from `requirements-dev.txt` (`pip install -r requirements-dev.txt`),
the only development dependency.

## Style

- Stdlib only for anything under `hooks/`, `hosts/` and `bin/`.
- Tests are stdlib `unittest`, discovered from `tests/`.
- Comment only a non-obvious decision; do not narrate the code.

## Commit and PR hygiene

Do not credit an AI assistant, model or vendor as author or co-author, and do
not add "Generated with" lines, robot emoji or model names to commit messages,
pull requests, issues, notes, docs or generated configuration.
