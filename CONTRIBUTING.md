# Contributing

Small, single-purpose changes are the easiest to accept.

- A rule belongs in the shared core (`hooks/`) unless it is genuinely
  host-specific; a host difference belongs in its adapter under `hosts/<name>/`.
- Keep the diff as short as it can be while still correct — the project's own
  minimal-code rule applies to the project.

## Before a pull request

Run the same three checks CI runs:

```bash
python3 -m compileall -q hooks hosts bin statusline.py   # byte-compile every script
python3 -m unittest discover -s tests                     # stdlib test suite
ruff check .                                              # lint; config in pyproject.toml
```

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
