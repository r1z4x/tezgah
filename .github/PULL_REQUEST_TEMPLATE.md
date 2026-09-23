## What and why

<!-- one or two sentences -->

## Checks

- [ ] `python3 -m compileall -q hooks hosts bin statusline.py`
- [ ] `python3 -m unittest discover -s tests`
- [ ] `ruff check .`

## Notes

- [ ] The diff is as short as it can be while still correct.
- [ ] A rule change sits in the shared core (`hooks/`); a host difference sits in
      its adapter under `hosts/<name>/`.
- [ ] No AI, model or vendor attribution in the commit, this PR, or any
      generated configuration.
