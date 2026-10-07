# Releasing

The version the public repository carries is the newest `## [x.y.z]` heading in
`CHANGELOG.md` plus the git tag; `bin/tezgah-setup --version` reads the local
plugin manifest when it is there and falls back to that heading. The manifest
itself (`.claude-plugin/plugin.json`, mirrored in
`.claude-plugin/marketplace.json`) is the maintainer's local, untracked file.

The numbering was reset on 2026-10-04: the repository was re-rooted and the
public line restarted at 0.1.1 after 0.32.0 (npm served 0.17.0-0.32.0 before
it). `hooks/tezgah_update.py::RETIRED` makes the update check offer 0.1.x to an
install still inside 0.2.0-0.32.0. Every install that carries the constant
treats that range as retired, and removing it later does not reach them. So the
next line after 0.1.x skips to 0.33.0 or later, never 0.2.0-0.32.0
(`tests/test_update.py::Reset` fails on a shipped version inside the range).

## Cut a release

1. Bump `version` in the local manifest's two files together (they are not
   tracked), and in `package.json`, which is tracked: npm publishes exactly the
   version it names and `release.yml` skips one npm already has, so a stale
   `package.json` ships nothing (`tests/test_packaging.py` holds it to step 2).
2. Add a `## [x.y.z] - YYYY-MM-DD` section to `CHANGELOG.md`, newest first, and
   add the tag link at the bottom.
3. Run the checks. All but the plan report also run in CI. The plan report reads
   the gitignored `.tezgah/`, so it runs only here:

   ```bash
   python3 -m compileall -q hooks hosts bin statusline.py
   python3 tests/impacted.py --all
   ruff check .
   python3 bin/tezgah-docs --citations
   python3 tests/e2e_packaged_install.py
   TEZGAH_E2E_STRICT=1 python3 tests/e2e_plan_flow.py
   python3 skills/plan-add/render_table.py --acceptance --strict
   ```

   Publishing waits for CI anyway: `release.yml` runs `ci.yml` as its `ci` job,
   and `npm-publish` and `brew-formula` start only after it passed.

4. Regenerate the tracked listing a plugin copy is made from and commit it with the
   changelog section - the release tarball has no `.git`, so
   `sync`/`plugin_copy_current` read `MANIFEST` there:

   ```bash
   bin/tezgah-setup --write-manifest
   git add MANIFEST CHANGELOG.md package.json && git commit -m "release: vX.Y.Z"
   ```

5. Build the release artifact and publish it with the notes - `build.sh` writes the
   tarball and its checksum from `MANIFEST`, and `install.sh` fetches exactly these
   two files, so a release without them is an install that cannot happen:

   ```bash
   bash packaging/build.sh --version X.Y.Z
   gh release create vX.Y.Z --target main --title "vX.Y.Z" --notes-file notes.md \
     dist/tezgah-X.Y.Z.tar.gz dist/tezgah-X.Y.Z.tar.gz.sha256
   ```

6. Publishing the release is what ships npm and Homebrew: `release.yml` runs on
   `release: published` - a pushed tag alone triggers nothing - and publishes
   `package.json`'s version to npm and rewrites the tap formula to this tarball.
   Check both afterwards: `npm view @r1z4x/tezgah version` and the formula's
   `url` in `r1z4x/homebrew-tezgah`. **A client's own cache answers this
   wrongly:** `brew info r1z4x/tezgah/tezgah` read the previous version a minute
   after a release because the machine's tap clone was stale - the write had
   landed, the read had not, and the run a second time after `brew update` showed
   the new one. So read the tap clone's own file
   (`brew --repository r1z4x/tezgah` plus `/Formula/tezgah.rb`) or run
   `brew update` first, and treat an old `npm view` the same way: the registry's
   version document (`/pkg/<version>`) is the authoritative read, while
   `dist-tags` can lag the publish by minutes.
7. Nothing else to edit: the `release`, `license` and `ci` badges in the READMEs
   read `github/v/release`, `github/license` and the workflow status live, and
   `bin/tezgah-setup --version` reports the new version for anyone who pulls.
