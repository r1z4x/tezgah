# Releasing

The version the public repository carries is the newest `## [x.y.z]` heading in
`CHANGELOG.md` plus the git tag; `bin/tezgah-setup --version` reads the local
plugin manifest when it is there and falls back to that heading. The manifest
itself (`.claude-plugin/plugin.json`, mirrored in
`.claude-plugin/marketplace.json`) is the maintainer's local, untracked file.

## Cut a release

1. Bump `version` in the local manifest's two files together (they are not
   tracked), and in `package.json`, which is tracked: npm publishes exactly the
   version it names and `release.yml` skips one npm already has, so a stale
   `package.json` ships nothing (`tests/test_packaging.py` holds it to step 2).
2. Add a `## [x.y.z] - YYYY-MM-DD` section to `CHANGELOG.md`, newest first, and
   add the tag link at the bottom.
3. Run the checks CI runs:

   ```bash
   python3 -m compileall -q hooks hosts bin statusline.py
   python3 tests/impacted.py --all
   ruff check .
   python3 bin/tezgah-docs --citations
   python3 skills/plan-add/render_table.py --acceptance --strict
   ```

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
