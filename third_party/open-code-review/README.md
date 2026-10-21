# open-code-review texts

Source: https://github.com/alibaba/open-code-review at commit
375f64cd6f67a48a135da83cfcf59c52669a09cb, under the Apache License 2.0
(`LICENSE`, verbatim).

- `prompts/main_task_system.md` - OCR's review prompt, verbatim from
  `internal/config/template/prompts/`. `tezgah-task` names it in the plan's
  verification step as an appendix each per-rule-group tezgah-reviewer reads.
- `prompts/review_filter_task_system.md` - OCR's reflection filter prompt,
  verbatim from the same directory. The refuter pass: one fresh tezgah-reviewer
  reads it as its instructions and removes only findings the diff proves wrong.

Each prompt carries one added first line, the modification notice; the rest of
the file is unchanged.
