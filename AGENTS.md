# AGENTS.md

Repository notes for coding agents. The always-on tezgah contract (Turkish BLUF
replies, ponytail, code-graph-first) is injected by the harness; this file only
records how to check this repo.

## Checks (run before every commit)

```sh
python3 -m compileall -q hooks hosts bin statusline.py   # byte-compile every script
python3 -m unittest discover -s tests                     # stdlib test suite
ruff check .                                              # lint; config in pyproject.toml
```

- `ruff` is installed as a uv tool (`uv tool install ruff`); without it, run the
  same check via `uvx ruff check .`. There is no other linter or type checker.
- CI (`.github/workflows/ci.yml`) runs the same three on Python 3.10 and 3.12.

### dsh Web status line, end to end

`python3 tests/e2e_dsh_statusline.py` boots the real `dsh --profile web` UI in
headless Chromium (Playwright), opens a persisted session, and asserts the
tezgah status string renders in the session header with a 200 from
`/api/tezgah.status`. It prints `SKIP: ...` when dsh, Playwright, a Chromium
build, or a persisted session is missing. Opt-in and local only; not part of CI.

## Layout

- `hooks/` the shared Python contract and tool gate; `hosts/<name>/` per-host
  adapters and plugin bundles.
- `bin/tezgah-setup` owns install/uninstall and the `--status` report; its
  `host_checks_<host>` functions are the report's source of truth.
- The dsh Web status line plugin lives in `hosts/dsh/statusline/`; `tezgah-setup`
  links it into the dsh web profile and enables its patch row.
