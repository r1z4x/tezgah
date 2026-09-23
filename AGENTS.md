# AGENTS.md

Repository notes for coding agents. The always-on tezgah contract (Turkish BLUF
replies, ponytail, code-graph-first) is injected by the harness; this file only
records how to check this repo.

## Docs

`docs/README.md` is the router for how this thing works: architecture, hosts,
contract, gate, evidence, status line, skills, testing, operations, glossary.
Reach a page with `bin/tezgah-docs <words>` (it reads `docs/index.json`) instead
of grepping the tree; a page that is not in the index is not reachable, and
`tests/test_docs.py` keeps the two in step.

## Checks (run before every commit)

```sh
python3 -m compileall -q hooks hosts bin statusline.py   # byte-compile every script
python3 -m unittest discover -s tests                     # stdlib test suite
ruff check .                                              # lint; config in pyproject.toml
python3 bin/tezgah-docs --citations                       # every citation still shows what it names
python3 skills/plan-add/render_table.py --acceptance --strict  # an open plan names how it is proven
python3 tests/e2e_packaged_install.py                     # install from the built artifact, not the checkout
```

- `ruff` is installed as a uv tool (`uv tool install ruff`); without it, run the
  same check via `uvx ruff check .`. There is no other linter or type checker.
- CI (`.github/workflows/ci.yml`) runs the same checks on Python 3.10 and 3.12,
  so 3.10 is the floor: the checks run on it and on 3.12. An `apps-e2e` job runs
  the app-MCP handshake below on node 20. The last two are the audits the suite
  is silent about: a green run says nothing about a citation that moved with a
  file, or about an open plan's item that never said how it is proven.
- The artifact smoke is the one check that leaves the checkout: it builds
  `dist/tezgah-<version>.tar.gz` (`packaging/build.sh`), unpacks it in a temp
  dir and installs from the unpacked tree, so a broken manifest or a path that
  only resolves in a git checkout fails there and nowhere else. CI runs it as
  its own job on 3.10 and 3.12, and again on `windows-latest`, which is the only
  place the Windows claim is proven. Locally it prints `SKIP: ...` and exits 0
  when `sh`, `tar` or `python3` is missing, so read its output rather than its
  exit code; CI sets `TEZGAH_E2E_STRICT=1`, which turns that skip into a failure
  instead, because a runner that has all three has no reason to skip.

### App-analysis MCP, end to end

`TEZGAH_E2E_STRICT=1 python3 tests/e2e_analyze_wiring.py` starts the exact
`playwright` and `mobile-mcp` commands `tezgah-setup` writes, completes the MCP
handshake and asserts the tree tools exist - no browser, no device, so it is
deterministic in CI. `TEZGAH_E2E_APPS=1 python3 tests/e2e_analyze_web.py` and
`... e2e_analyze_mobile.py` go further (real navigation / a listed device) and
print `SKIP: ...` when node, a browser build or a device is missing; those two
are opt-in and local only. The shared spec is `hooks/tezgah_apps.py`.

### dsh Web status line, end to end

`python3 tests/e2e_dsh_statusline.py` boots the real `dsh --profile web` UI in
headless Chromium (Playwright), opens a persisted session, and asserts the
tezgah status string renders in the session header with a 200 from
`/api/tezgah.status`. It prints `SKIP: ...` when dsh, Playwright, a Chromium
build, or a persisted session is missing. Opt-in and local only; not part of CI.

### omp status line, end to end

`python3 tests/e2e_omp_statusline.py` starts the real `omp` TUI in a pty with no
prompt (so the run costs no model call), reads its output and asserts the tezgah
marks appear in the footer the extension writes them to. It prints `SKIP: ...`
when the omp binary or the installed extension is missing. Opt-in and local only;
not part of CI.

## Layout

- `hooks/` the shared Python contract and tool gate; `hosts/<name>/` per-host
  adapters and plugin bundles.
- `bin/tezgah-setup` owns install/uninstall and the `--status` report; its
  `host_checks_<host>` functions are the report's source of truth.
- The dsh Web status line plugin lives in `hosts/dsh/statusline/`; `tezgah-setup`
  links it into the dsh web profile and enables its patch row.
