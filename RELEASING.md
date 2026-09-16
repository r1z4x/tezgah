# Releasing

The version lives in `.claude-plugin/plugin.json` (mirrored in
`.claude-plugin/marketplace.json`); `bin/tezgah-setup --version` reads it.

## Cut a release

1. Bump `version` to the same semantic version in both
   `.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`.
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
