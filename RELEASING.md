# Releasing

The version the public repository carries is the newest `## [x.y.z]` heading in
`CHANGELOG.md` plus the git tag; `bin/tezgah-setup --version` reads the local
plugin manifest when it is there and falls back to that heading. The manifest
itself (`.claude-plugin/plugin.json`, mirrored in
`.claude-plugin/marketplace.json`) is the maintainer's local, untracked file.

## Cut a release

1. Bump `version` in the local manifest's two files together (they are not
   tracked - nothing in the repository needs the edit to publish).
2. Add a `## [x.y.z] - YYYY-MM-DD` section to `CHANGELOG.md`, newest first, and
   add the tag link at the bottom.
3. Run the three checks CI runs:

   ```bash
   python3 -m compileall -q hooks hosts bin statusline.py
   python3 -m unittest discover -s tests
   ruff check .
   ```

4. Commit, then create the tag and release from the new changelog section
   (`gh release create` creates the tag on the remote):

   ```bash
   gh release create vX.Y.Z --target main --title "vX.Y.Z" --notes-file notes.md
   ```

5. Nothing else to edit: the `release`, `license` and `ci` badges in the READMEs
   read `github/v/release`, `github/license` and the workflow status live, and
   `bin/tezgah-setup --version` reports the new version for anyone who pulls.
