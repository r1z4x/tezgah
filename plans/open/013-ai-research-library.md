---
id: 013
title: Convert the AI-research-SKILLs library into a shipped tezgah skill
status: open
branch: plan/013-ai-research-library
pr:
created: 2026-09-17
updated: 2026-09-17
---
## Goal
Vendor Orchestra Research's MIT-licensed `AI-research-SKILLs` library (98 skills,
23 categories) into tezgah as **one** shipped skill - converted, not cloned. The
content lives in this repository, reaches every host tezgah arms, and is read
during a research line when the work needs AI/ML machinery. No clone under
tezgah, no symlink into an external checkout, no runtime dependency on upstream.

## Why this reverses plan 008's decision
`plans/done/008-research-workspace.md` recorded: *"The library's 90+ ML-engineering
domain skills are deliberately not copied: tezgah is a general coding harness, and
copying them would bloat the router."* The real objection was the second half, and
it is answerable: the bloat is the 98 name+description entries a native host
injects into every request, not the content. One skill plus a generated index
costs **one** metadata entry - the installer's own report counts 5,207 chars of
skill metadata for 9 skills, about 0.6 KB per entry - and leaves the bodies on
disk, read on demand. The first half is now the user's call: a research line that needs
ML machinery should not have to improvise it.

## What exists today (measured 2026-09-17 at rev 773a529)

| Fact | Value | Evidence |
|---|---|---|
| Upstream revision | `773a529`, v1.7.2, 2026-06-15, MIT, `author: Orchestra Research` on 96 skills; `ml-training-recipes` and `a-evolve` name the contributing author | `git -C ~/Projects/AI-Research-SKILLs log -1`; `grep -rhoE '^author: .*' **/SKILL.md` |
| Inventory | 98 `SKILL.md`, 23 categories | recursive git tree, counted |
| Content | 24.6 MB without `.git`: `SKILL.md` 1.29 MB (39,657 lines), `references/` 5.20 MB, non-markdown assets 1.23 MB, repo furniture (`demos/`, `docs/`, `packages/`, `video-promo/`) 35.2 MB | `os.walk` byte counts |
| Upstream README's own category counts | stale in 5 rows (18-multimodal 7 vs 10 on disk, 20-ml-paper-writing 2 vs 4, 13-mlops 3 vs 4, 10-optimization 6 vs 7, 14-agents 4 vs 5) | README vs tree |
| Installed today | all 98 symlinked into `~/.config/opencode/skills/` → the external clone; the other five hosts get none | `readlink -f` over each host's skill dir |
| Surfaced today | opencode's generated router, bucket "AI research & engineering: 98 skills", on demand | `bin/tezgah-setup:96` (`AI_RESEARCH_SKILL_SOURCES`), `:580` (`skill_category`) |
| Adapted so far | 3 of 98 (`autoresearch`, `ara-rigor-reviewer`, `ara-research-manager`) → `skills/research`, attributed | `NOTICE:7-11`, test-pinned |
| tezgah repo today | 6.0 MB without `.git`; `skills/` 0.1 MB; 9 skills | byte counts |

Consequence: on Claude, Codex, Cursor, dsh and omp a research line cannot reach
any of the 98 today; on opencode it reaches them only when the clone happens to
be installed and the model picks a name out of a 98-line list.

## Target shape

```
skills/ai-research/                 the one shipped skill (one metadata entry)
  SKILL.md                          tezgah-written: what it is, when to read it, how, provenance, kill switch
  SOURCE                            upstream URL, revision, date, licence, extraction rules, drop list
  library.json                      generated manifest: 98 rows + flags, the tests' source of truth
  index/1-frame.md ... 6-write.md   generated stage indexes - the router a session actually reads
  0-autoresearch-skill/ 01-.../ ... 22-agent-native-research-artifact/   vendored, upstream layout kept
bin/tezgah-import-ai-research       dev-time converter (NOT linked into ~/.config/tezgah/bin); --check verifies
tests/test_ai_research_library.py
```

**Read path**: `skills/research/SKILL.md` → (when the hypothesis needs ML
machinery) `index/<stage>.md` (20-30 lines) → the entry's `SKILL.md` → its
`references/`. Three small steps, all on demand; the always-on cost is unchanged
apart from one metadata entry.

**Why the upstream layout survives verbatim.** A vendored path *is* its
provenance (`01-model-architecture/litgpt/references/training-recipes.md` maps
1:1 onto upstream), so a re-vendor or a dispute is a one-line diff, and the two
skills that cross-reference by relative path (`miles` →
`../slime/references/api-reference.md`) keep working.

### Wire changes (nothing else moves)

| File | Change |
|---|---|
| `bin/tezgah-setup` `SKILLS` | add `"ai-research"` → 9 → 10 skills linked into all six hosts |
| `bin/tezgah-setup` `skill_category` | `ai-research` → the on-demand `research & papers` bucket, not `tezgah core` |
| `hooks/tezgah_policy.py` `RESEARCH` | two lines naming the index, with the `{AI_RESEARCH_DIR}` placeholder |
| `hooks/tezgah_context.py` `render()` | `{AI_RESEARCH_DIR}` → `<plugin root>/skills/ai-research` (correct on Claude, which runs the plugin from a copy) |
| `hooks/tezgah_agents.py` `_researcher_body` | one sentence pointing the fallback researcher at the same path |
| `skills/research/SKILL.md` | new section `## Domain execution (the shipped library)` |
| `NOTICE` | new entry: vendored (not adapted), revision, MIT, per-file attribution |
| `README.md` + the translations | the research bullet gains the library; no new CLI row, no new kill-switch row. The switcher now lists six languages plus Turkish: English, 简体中文, Deutsch, Español, Français, 日本語, Português (Brasil), Türkçe - the other eleven READMEs were reduced away by a later commit on this branch |
| `CHANGELOG.md` | `### Added` under Unreleased |

**No new kill switch.** The library is only reachable through the research flow,
so `research-off` already covers it. A tenth switch would touch `CORE`,
`output-styles/tezgah.md` (pinned verbatim equal to `always_on_core()`), the
switch table in 15 READMEs and `tests/test_skills.py` for no gain.

## Alternatives considered

### Axis 1 - packaging

| # | Alternative | Metadata entries added (native hosts) | Reachable | Hosts | Repo size | Update path | Verdict |
|---|---|---|---|---|---|---|---|
| A | 98 tezgah skills, 1:1 | +98 ≈ 57 KB per request, ~10x the whole always-on contract (6.0 KB) | all | 6 | +4.2 MB | per skill | reject: this is exactly the bloat plan 008 feared, and it is real |
| B | 23 category skills | +23 ≈ 13 KB | all | 6 | +4.2 MB | per category | reject: 23 provenance pins, and a category is not what a session asks for |
| C | **one skill + generated index + vendored bodies** | **+1 ≈ 0.6 KB** | all | 6 | +4.2 MB | one importer, one revision pin | **adopt** |
| D | status quo: external clone, opencode-only router | 0 in tezgah (98 in the user's opencode) | opencode only | 1 | 0 | none | reject: violates the ask |
| E | orchestration layer only; domain work to `orx` | 0 | none | 6 | 0 | none | reject: that is plan 008 again, and the user overruled it |
| F | 3 lifecycle skills (train / measure+serve / write) | +3 ≈ 1.7 KB | all | 6 | +4.2 MB | 3 pins | runner-up: same content, better browsing; adopt later as an index change, not a re-vendor - the importer generates every index file from one manifest |

### Axis 2 - fidelity

| | Policy | Size | Verdict |
|---|---|---|---|
| F1 | verbatim everything, dumps and LaTeX trees included | 7.78 MB | reject: 3.6 MB of it is regenerable noise |
| F2 | **all 98 bodies + all `.md` references, minus an explicit drop list** | ~4.2 MB | **adopt** |
| F3 | bodies + only the references a scout called operational | ~2.4 MB | reject: saves 1.8 MB and costs the session the operational detail it opened the entry for; a hand-picked subset also drifts from upstream |

Drop list (F2; each item is named in `SOURCE` and in the entry's index line):

| Dropped | Bytes | Why |
|---|---|---|
| `03-fine-tuning/unsloth/references/llms-full.md`, `llms-txt.md` | 1.85 MB | machine-scraped GitBook concatenation (`{% content-ref %}` macros, raw HTML) |
| `08-distributed-training/deepspeed/references/tutorials.md` | 0.44 MB | 59 concatenated doc pages with `URL:` headers - a dump, not a guide |
| `20-ml-paper-writing/ml-paper-writing/templates/` (6 venues) | 1.13 MB | LaTeX class/bst/bib files plus 507 KB of example PDFs, re-downloadable per venue |
| `20-ml-paper-writing/systems-paper-writing/templates/` (4 venues) | 0.09 MB | same |
| `demos/`, `docs/`, `packages/`, `video-promo/`, `.github/` | 35.2 MB | repo furniture, not skill content |

Cap **5 MB**, asserted by a test. The drop list is one dict in the importer, so
F1 or F3 is a one-line flip.

## Scope

**WP1 - the importer** (`bin/tezgah-import-ai-research`, ~150 lines, dev-time,
not linked into `~/.config/tezgah/bin`). `--source <clone> --rev <sha>
[--out skills/ai-research]` and `--check`.
- refuses to run when `git -C <source> rev-parse HEAD` != `--rev` - a vendor step
  that silently takes a moving branch is how provenance dies;
- copies bodies plus `.md` references in the upstream layout, applies the drop list;
- prepends one attribution line to every vendored file that has no YAML
  frontmatter (`<!-- vendored from orchestra-research/AI-research-SKILLs@773a529 <path>; MIT (c) Orchestra Research -->`);
  the 98 `SKILL.md` files keep their own `author`/`license` frontmatter untouched
  (upstream attribution is required by MIT and is not the banned AI-credit line);
- writes `SOURCE` and `library.json`;
- generates the six `index/<stage>.md` files from the manifest plus a stage map;
- `--check` re-derives byte counts and sha256 for every vendored path, compares
  against `library.json`, exits 1 on drift - CI-safe, never needs the clone;
- deterministic: sorted walks, no timestamps; two runs are byte-identical.

**WP2 - the vendored tree** (`skills/ai-research/**`, generated, committed):
98 entries, 6 index files, `SOURCE`, `library.json`.

**WP3 - `skills/ai-research/SKILL.md`** (tezgah-written, must satisfy
`tests/test_skills.py`'s standards): what this is and its revision; the three-step
read path; what `generated` / `stale-api` / `dangling-link` mean; "a line with no
vendored body means upstream coverage is named and not copied - do not invent its
API"; the highest-value entries for a research line; provenance; `research-off`.

**WP4 - wiring**: the table above, file by file.

**WP5 - tests** (`tests/test_ai_research_library.py` plus updates):
- 98 manifest rows and 23 categories, one index line per entry, none twice;
- every manifest path exists, every sha256 matches, no unlisted file in the tree;
- every vendored file carries the attribution line or upstream frontmatter;
- `SOURCE` and `library.json` agree on the revision; the drop list is exactly the
  five entries above;
- `skills/ai-research` <= 5 MB;
- the importer is idempotent and its drop/frontmatter rules are exercised on a
  fixture clone (2 fake skills, one dump, one asset dir), so CI needs no upstream;
- `bin/tezgah-setup`: `ai-research` is in `SKILLS`, lands in `research & papers`,
  and the budget report says `skill metadata (10)`;
- `render()` resolves `{AI_RESEARCH_DIR}` to an existing directory (extends the
  existing unrendered-placeholder test);
- `tests/test_setup.py`'s two `skill metadata (9)` literals → `(10)`; the pinned
  budget block in `benchmarks/harness-vs-omp/README.md` regenerated.

**WP6 - make the vendored content bite** (each item is content the library
supplies and `skills/research` lacks; each is small and separately reviewable):
1. the six review dimensions gain the upstream 1-5 anchors and the mean→grade
   mapping - without anchors two sessions' scores are not comparable;
2. the finding record schema (`finding_id`, `dimension`, `severity`,
   `target_file`, `target_entity`, `evidence_span`, `observation`, `reasoning`,
   `suggestion`) plus D1's type-aware entailment table (a causal claim needs an
   isolating ablation, a generalization claim heterogeneous conditions, ...);
3. the citation rule from `20-ml-paper-writing/references/citation-workflow.md` -
   never write a reference from memory, verify in two of Semantic Scholar /
   CrossRef / arXiv / OpenAlex, `[CITATION NEEDED]` placeholder - because this
   repo's own log records three literature ids cited in briefs before they were
   in `literature/`;
4. the evidence-fidelity rules from `22-.../compiler` (exact numbers never
   rounded; a derived subset is never named `Table N`; every evidence file
   carries a `Source` field), and the reference-resolution half of its Level-1
   checklist added to `tezgah-research check`: a claim's `proof` must resolve to
   an experiment directory that has a `results.jsonl` - today `check` only
   asserts `proof` is non-empty (`hooks/tezgah_research.py:163`);
5. the ideation section gains `brainstorming-research-ideas`' framework chooser
   and kill criteria and `creative-thinking-for-research`' hidden-constraint
   move, folded into the existing four bullets;
6. `to_human/` gains the academic-plotting rules (chart-type table,
   colourblind-safe palette, PDF vector export, venue column widths) - every
   line produces a chart and tezgah has no figure spec at all.

## Acceptance
- [x] `bin/tezgah-import-ai-research --source ~/Projects/AI-Research-SKILLs --rev 773a529` produces `skills/ai-research/**`, and a second run is byte-identical (tree digest unchanged; `git status --porcelain` shows only the untracked tree).
- [x] `bin/tezgah-import-ai-research --check` exits 0 on the committed tree, and 1 after tampering with any one vendored file (proved on a fixture in `tests/test_ai_research_library.py`; the real tree reports `ok: 98 skills, 371 vendored files match library.json`).
- [x] `du -sk skills/ai-research` = 4980 KB (4.2 MB of content) inside the 5 MB cap, and the manifest lists 98 entries across 23 categories (test-pinned).
- [x] `python3 -m unittest discover -s tests` green - 525 tests, OK; `python3 -m compileall -q hooks hosts bin statusline.py`; `ruff check .` clean.
- [x] `bin/tezgah-setup --context` reports `skill metadata (10)`: 5,716 chars against 5,207 for nine - **+509 bytes** for the whole library.
- [x] `bin/tezgah-setup --install --hosts opencode` under a scratch `HOME`: the always-on router collapses the bucket to `research & papers: 1 skill`, the full router lists `- \`ai-research\` - Use when a research line needs AI or ML machinery ...`, and the skill dir is symlinked into `~/.config/opencode/skills/`.
- [x] Skill metadata grows by exactly one entry, measured by the same instrument the native hosts are sized with (`--context`, above).
- [x] **A real host ran it.** `opencode run` in an isolated `HOME` with this branch installed, on a research prompt: it read `skills/research/SKILL.md`, then `skills/ai-research/index/3-train.md` and `4-measure.md`, then `10-optimization/bitsandbytes/SKILL.md` with its `references/quantization-formats.md`, and answered with the vendored numbers (45.9% → 45.2% MMLU, perplexity 5.12 → 5.18, 14 GB → 3.5 GB), naming the file it read, with zero permission rejections. The first attempt failed in two ways that are now fixed (below).
- [x] `bin/tezgah-research check` is clean on `.tezgah/research/agent-failure-controls` - after the new proof rule caught stale pointers there (below).
- [x] `NOTICE` names the vendored library, revision and licence; every vendored body keeps upstream frontmatter (96 `Orchestra Research`, `dailycafi`, `A-EVO Lab`) and every reference file carries the attribution comment, both test-pinned.
- [x] `README.md`, the translations (reduced to six languages plus Turkish, seven files) and `CHANGELOG.md` updated. The line each translation carries about the library was re-read by an independent model through `consult --online`: French, Spanish, Italian and Brazilian Portuguese dropped their unnatural "vendored" loan word and Chinese its inline English term (the Italian and Thai files were later reduced away with the rest). The review covered all 18 before the reduction; Gemini answered off-topic on both packets, which is recorded rather than hidden.

## Risks

| Risk | Why it bites | Mitigation |
|---|---|---|
| a host scans the nested `SKILL.md` files as 98 skills | it defeats option C entirely | the index sits inside one skill dir, one level deeper than host scanners look; covered by the opencode-router test and a real-host metadata count in acceptance |
| context cost creeps back | 98 entries is the failure mode | the test asserts `skill metadata (10)`; the always-on router keeps counts, not lines |
| upstream drift and API staleness | bodies name pre-2.5 `dspy`, deprecated `langchain` chains, `outlines.models.*`; `awq` self-declares AutoAWQ dead | revision pinned in `SOURCE`; per-entry `stale-api` flag; a re-vendor is one importer run |
| broken upstream links (`mamba` 3 of 3, `flash-attention` 2 of 4, `ray-train` 2, `verl` 1, and all four `07-safety-alignment` skills cite a `references/` dir that does not exist) | a link that 404s inside the repo is worse than no link | `library.json` records `dangling_links` per entry and the index line carries the flag; nothing is silently deleted |
| 4 skills are scraper-generated stubs (`axolotl`, `llama-factory`, `unsloth`, `deepspeed`: template prose, one literal `*Quick reference patterns will be added...*`) | a session could read mangled fragments as guidance | `quality: generated` in the manifest and in the index line |
| licence | MIT upstream; individual skills reference other projects | `SOURCE` + `NOTICE` name MIT and the revision; the attribution line is per file |
| repo size | 6.0 MB → ~10.2 MB | 5 MB cap is a test; the drop list is the lever |

## Non-goals
- No runtime fetcher, no submodule, no clone: the tree is vendored and reviewed like any other file.
- No new user-facing CLI, no new kill switch, no per-skill host wiring (the `SKILLS` loop already covers all six).
- No removal of the user's existing `~/.config/opencode/skills` symlinks - a migration note only; `AI_RESEARCH_SKILL_SOURCES` keeps bucketing them if they stay.
- No rewriting of upstream prose: vendored files stay verbatim except the attribution line; tezgah's own words go in WP3 and WP6.

## Appendix A - all 98 entries, with what each gives a research line

`value` = how much the entry changes what a session does inside a research line
(`high` / `med` / `low`), from the six group analyses. `flags`: `gen` =
scraper-generated stub, `stale-api` = body names a superseded API, `dead-link` =
SKILL.md links a file that is not in the checkout, `orphan-ref` = a reference file
no SKILL.md links (kept anyway - the vendor step copies the whole `references/` dir).

### 0 / 21 / 22 - the research-process layer (10)

| skill | cat | value | what a research line gets |
|---|---|---|---|
| 0-autoresearch-skill | 0 | med | two-loop orchestration; tezgah already carries the engine, this adds the wall-clock continuity loop, the DEEPEN/BROADEN/PIVOT/CONCLUDE table, the git protocol, and `templates/progress-presentation.html` (8.5 KB) for `to_human/` |
| academic-plotting | 20 | high | chart-type decision table, Okabe-Ito palette, publication `rcParams`, venue column widths, PDF-vector export, Gemini diagram-prompt structure; tezgah has no figure spec |
| ml-paper-writing | 20 | med | `references/citation-workflow.md` is the prize (never cite from memory, verify in two sources, DOI content-negotiation); body adds the abstract formula and Gopen & Swan clarity rules **stale-api** |
| presenting-conference-talks | 20 | low | talk-type→slide-count table, slide skeletons, Beamer/pptx generators - only if a line ends in a talk slot |
| systems-paper-writing | 20 | low | "state every experimental conclusion three times", gap→answer enumeration, ablation as a required experiment type - venue-neutral rules worth folding into WP6 |
| brainstorming-research-ideas | 21 | high | framework chooser for a stuck agent, the four kill criteria (explain-it, problem-first, simplicity, stakeholder), seven ideation pitfalls, two-week pilot rule |
| creative-thinking-for-research | 21 | med | Boden's exploratory/combinational/transformational split with hard/soft/**hidden** constraints, Gentner structure-mapping depth table, adjacent-possible timing signal, Janusian thinking |
| compiler | 22 | high | the evidence-fidelity rules (exact numbers, derived-subset labelling, claim→experiment→evidence binding, `Source` fields) and the Level-1 checklist tezgah's `check` half-covers |
| research-manager | 22 | low-med | maturity tracker (3+ observations promote, conflicts flagged, stale after 3 sessions) and the `confirmation_rate` statistic; the provenance half duplicates tezgah's rule |
| rigor-reviewer | 22 | high | the six 1-5 scoring anchors, the mean→grade mapping, the finding record schema, D1's type-aware entailment table, per-check severity inventory |

### 01 / 02 / 05 / 10 - core modelling, data, optimization (16)

| skill | cat | value | what a research line gets |
|---|---|---|---|
| litgpt | 01 | low | LoRA rank guide r=8..64 and a VRAM ladder; otherwise a CLI tutorial |
| mamba | 01 | med | Mamba-1 vs Mamba-2 (d_state 16/128) and a 130M-2.8B VRAM ladder **dead-link** (all 3 refs) |
| nanogpt | 01 | high | the cheapest reproducible baseline in the library: 5-minute CPU Shakespeare config, GPT-2 124M wall-clock and VRAM figures |
| rwkv | 01 | low | RNN-mode state-must-be-passed pitfall only; RWKV-4-era examples, pinned `pytorch-lightning==1.9.5` **stale-api** |
| torchtitan | 01 | med | TOML parallelism-degree recipes, the seed-checkpoint-before-pipeline-parallel trap, H100 TPS/GPU table |
| huggingface-tokenizers | 02 | high | BPE/WordPiece/Unigram trade-offs and the normalizer→pre-tokenizer→model pipeline - the choice that decides whether BPB-style metrics are comparable across runs |
| sentencepiece | 02 | med | `character_coverage` table (1.0 for CJK) and subword-regularization sampling |
| nemo-curator | 05 | low | exact/fuzzy/semantic dedup chooser and a GPU-vs-CPU cost table; needs `nemo-curator[cuda12]` + RAPIDS + A100s |
| ray-data | 05 | low | `iter_batches` streaming for larger-than-memory corpora, repartition/batch-size tuning |
| awq | 10 | med | AWQ/GPTQ/bitsandbytes comparison and a perplexity-degradation table; **upstream says AutoAWQ is deprecated** **stale-api** |
| bitsandbytes | 10 | high | model-memory arithmetic (params x 2/1/0.5 bytes), VRAM-to-bits table, QLoRA recipe (0.06% trainable) |
| flash-attention | 10 | med | sequence-length thresholds (<512 minimal, 512-2K 2-3x, >2K 3-4x), fp16/bf16-only caveat **dead-link** (2 of 4) |
| gguf | 10 | med | the quant-level chooser: K-quant Q2_K..Q8_0 bits/size/quality plus the imatrix-for-Q4-and-below rule |
| gptq | 10 | med | group_size trade-off and `references/calibration.md` (128-256 samples x 512 tokens, domain-matched; bad calibration costs 5-10% perplexity) |
| hqq | 10 | low | nbits 1-8 plus backend-selection table; the only calibration-free option |
| ml-training-recipes | 10 | high | **highest-value body in the library**: `references/experiment-loop.md` is a fixed-time-budget keep/discard/crash TSV loop that mirrors tezgah's protocol-before-run, plus a size→architecture matrix, Chinchilla 20 tok/param and an OOM/loss-spike checklist |

### 03 / 06 / 08 - fine-tuning, post-training, distributed (18)

| skill | cat | value | what a research line gets |
|---|---|---|---|
| axolotl | 03 | low | YAML fine-tuning recipes **gen** (template prose; `dataset-formats.md` 45 KB and `advanced.md` 47 KB carry the value) |
| llama-factory | 03 | low | WebUI no-code fine-tuning; body is an empty template **gen** |
| peft | 03 | high | LoRA/QLoRA with per-architecture `target_modules`, rank/alpha tables, adapter merge/serve, memory-speed-quality benchmarks |
| unsloth | 03 | low | 2-5x faster QLoRA; body is a stub, the 1.85 MB reference set is a scraped dump **gen** (dumps dropped) |
| grpo-rl-training | 06 | high | GRPO mechanics, reward-function design, `GRPOConfig` memory-vs-perf, and the "watch `reward_std`, not loss" healthy/warning metric table; ships `templates/` + `examples/` instead of `references/` |
| miles | 06 | med | FP8/INT4 QAT, Rollout Routing Replay, speculative RL; H100/H200 cluster only; cross-references `../slime/references/api-reference.md` |
| openrlhf | 06 | med | Ray+vLLM RLHF CLI recipes and a hardware table (7B = 8xA100 40GB, 70B = 48xA100); `references/custom-rewards.md` is unique in the group |
| simpo | 06 | high | reference-free preference optimization with `beta`/`gamma_beta_ratio`/`sft_weight` guidance and divergence→LR/beta decision rules |
| slime | 06 | med | Megatron+SGLang RL, async mode, multi-turn agentic custom-generate functions, `Sample` dataclass for custom generation |
| torchforge | 06 | med | Meta's Monarch-based RL: GRPO/SFT launch, custom loss class, multi-GPU/SLURM config |
| trl-fine-tuning | 06 | high | SFT→RewardModel→PPO pipeline, DPO, GRPO with reward functions, hyperparameter troubleshooting, VRAM table |
| verl | 06 | med | `adv_estimator` table and large-scale RL backends; `references/multi-turn.md` is advertised and absent **dead-link** |
| accelerate | 08 | high | the 4-line `prepare`/`backward` conversion that makes any torch script distributed; CPU/MPS-capable |
| deepspeed | 08 | low | ZeRO stages and 1-bit Adam, in scraper-template prose **gen** (the 443 KB tutorials dump is dropped) |
| megatron-core | 08 | med | parallelism guide and training recipes for 2B-462B models, MFU>40% target with a low-MFU cause list |
| pytorch-fsdp2 | 08 | high | `fully_shard` init/sharding/mixed-precision config, the 5-rule agent contract and a 5-item debug checklist |
| pytorch-lightning | 08 | med | Trainer-class distribution and callback recipes; CPU/1-GPU reachable |
| ray-train | 08 | med | cluster-scale orchestration and multi-node.md; `hyperparameter-tuning.md` and `custom-loops.md` are linked and absent **dead-link** |

### 04 / 07 / 11 / 19 - interpretability, safety, evaluation, emerging (17)

| skill | cat | value | what a research line gets |
|---|---|---|---|
| nnsight | 04 | high | in-trace proxy edits (`h[8].output[0][:] = clean`), cross-prompt sharing, NDIF remote execution for models that do not fit locally |
| pyvene | 04 | high | declarative interventions, activation patching, causal tracing and DAS; saved interventions are HF-shareable |
| saelens | 04 | med | `LanguageModelSAERunnerConfig` hyperparameter table plus eval targets (L0, CE-loss score, dead-feature %) |
| transformer-lens | 04 | high | HookPoint and weight-shape tables, `run_with_cache`/`run_with_hooks` patching recipes, hook-reset and tokenization pitfalls |
| constitutional-ai | 07 | med | the two-phase CAI recipe (critique/revise then reward model + PPO); all three cited references are absent **dead-link** |
| llamaguard | 07 | med | runnable moderation recipe: `moderate()` on HF or vLLM, S1-S6 category codes, 94-95% accuracy; gated HF token |
| nemo-guardrails | 07 | low | Colang rails for jailbreak/self-check/PII/fact-check, CPU-only, sub-ms to 500 ms overhead **dead-link** |
| prompt-guard | 07 | med | `get_jailbreak_score` with a threshold table (0.3/0.5/0.7 with TPR/FPR) and sliding-window handling **dead-link** |
| bigcode-evaluation-harness | 11 | med | runnable pass@k recipe for code models; needs the upstream repo clone + Docker |
| lm-evaluation-harness | 11 | high | runnable `lm_eval --model hf --tasks mmlu,gsm8k --num_fewshot 5 --log_samples`, and a 60+ task guide with interpretation notes - the metric a research line usually quotes |
| nemo-evaluator | 11 | med | YAML execution/deployment/target configs and launcher run/export into MLflow/W&B; needs Docker + NGC key |
| knowledge-distillation | 19 | med | `DistillationTrainer.compute_loss` (T=2, alpha=0.7) and a reverse-KLD variant, with teacher/student size-ratio and data-mix rules |
| long-context | 19 | med | method table (RoPE/YaRN/ALiBi/PI: max context, training cost, extrapolation) plus the `rope_scaling` config |
| model-merging | 19 | high | mergekit YAML per method and label-free coefficient search by generation consistency |
| model-pruning | 19 | high | one-shot Wanda/SparseGPT pruning with no retraining, sparsity-vs-accuracy-loss table, lm-eval degradation check |
| moe-training | 19 | low | aux-loss and router z-loss formulas, capacity-factor math; the scripts assume 8+ GPUs |
| speculative-decoding | 19 | low | method table (speedup, training needed, draft model) and the HF `assistant_model=` one-liner **dead-link** (`references/draft_model.md`) |

### 09 / 12 / 13 / 17 - infrastructure, serving, tracking, observability (13)

| skill | cat | value | what a research line gets |
|---|---|---|---|
| lambda-labs | 09 | low | GPU price/VRAM table and a REST launch/terminate recipe; paid account |
| modal | 09 | med | `@modal.enter()` warm-load, Volume model caching, GPU fallback list; cold-start and GPU-fit decisions |
| skypilot | 09 | med | `sky launch --dryrun` cost optimizer and managed-job spot recovery with checkpointing |
| llama-cpp | 12 | med | GGUF Q2..Q8 bits/size/speed/quality table and `-ngl` hybrid offload; runs on this M1 Pro with no account |
| sglang | 12 | med | JSON-schema/regex/grammar constrained generation and RadixAttention prefix reuse (5-10x on shared prefixes) |
| tensorrt-llm | 12 | low | FP8/INT4 and TP/PP flags; heaviest dependency (CUDA 13 + TensorRT 10.13), A100/H100 only |
| vllm | 12 | med | quantization-method choice (AWQ/GPTQ/FP8), TP sizing by model size, TTFT/throughput targets, Prometheus metrics |
| mlflow | 13 | high | local run/param/metric/artifact tracking with queryable lineage - the closest thing in the library to a research line's protocol/results/claims provenance |
| swanlab | 13 | med | `mode="local"` account-free tracking with media logging |
| tensorboard | 13 | med | `torch.profiler` → `tensorboard_trace_handler` bottleneck workflow, scalars/hparams/embeddings |
| weights-and-biases | 13 | med | sweep configuration (bayes/grid/random, log_uniform, early termination) - the HPO decision artifact; account needed |
| langsmith | 17 | med | `evaluate()` with score-returning evaluators, assertable for CI thresholds - maps to a claim's falsification; API key |
| phoenix | 17 | med | self-hosted OTel tracing (SQLite default, no account) plus LLM-as-judge evaluators |

### 14 / 15 / 16 / 18 - agents, retrieval, structured output, multimodal (24)

| skill | cat | value | what a research line gets |
|---|---|---|---|
| a-evolve | 14 | high | a gated evolve loop (solve→observe→evolve→gate→reload) with `holdout_ratio` acceptance and git rollback - the closest external analogue of protocol-before-run |
| autogpt | 14 | low | visual agent platform; only portable nugget is VCR-cassette benchmark replay |
| crewai | 14 | low | role-based crews vs event-driven flows, `max_iter`/`max_rpm` loop guards |
| langchain | 14 | med | splitter chunking (500-1000 / 200 overlap) and `with_structured_output`; body uses removed APIs **stale-api** |
| llamaindex | 14 | med | Faithfulness/Relevancy evaluators (groundedness for a claim), `similarity_top_k`, `response_mode`, metadata filters |
| chroma | 15 | med | embedded vector store with a metadata operator table; no server **orphan-ref** |
| faiss | 15 | med | the dataset-size→index table (<10K Flat, 10K-1M IVF, 1M-10M HNSW, >10M IVF+PQ) and nprobe tuning **orphan-ref** |
| pinecone | 15 | low | managed serverless vector DB; paid account. Portable idea: hybrid dense/sparse blending and namespaces **orphan-ref** |
| qdrant | 15 | med | HNSW `m`/`ef_construct` table, payload-index-for-filters fix, scalar quantization recipe |
| sentence-transformers | 15 | med | model-selection table (dim/speed/memory, MiniLM→RoBERTa) and `CosineSimilarityLoss` fine-tuning; runs locally **orphan-ref** |
| dspy | 16 | high | optimizer-selection table (data needed per optimizer) and the `Evaluate` metric harness - a metric-locked baseline expressed in code **stale-api** |
| guidance | 16 | high | a 674-line regex/grammar constraint catalog for exact-format fields; token healing **stale-api** |
| instructor | 16 | high | `response_model` + `max_retries` error-feedback loop - the cleanest way to emit typed `claims.jsonl` rows |
| outlines | 16 | high | FSM schema→grammar pipeline: 100% valid JSON with no retry; needs local weights **stale-api** |
| audiocraft | 18 | low | MusicGen/AudioGen generation parameters and VRAM tables; GPU + multi-GB weights |
| blip-2 | 18 | low | captioning/VQA; INT8/INT4 fitting notes and Q-Former feature shapes |
| clip | 18 | med | zero-shot image-text similarity cheap enough to run on CPU; label-set wording matters **orphan-ref** |
| cosmos-policy | 18 | low | NVIDIA VLA evaluation on LIBERO/RoboCasa; A40/A100 + EGL MuJoCo |
| llava | 18 | low | vision chat; the orphaned `training.md` documents the 2-stage recipe (558K align + 150K instruct, 8xA100) **orphan-ref** |
| openpi | 18 | low | pi0/pi0.5 fine-tune and serve; best-written reference set in the group (`pytorch-gotchas`, config recipes), but robot hardware bound |
| openvla-oft | 18 | low | LoRA fine-tuning of OpenVLA-OFT with exact pins; durable nugget is the train↔eval flag-parity invariant table |
| segment-anything | 18 | low | CPU-viable ViT-B segmentation; `SamAutomaticMaskGenerator` parameters |
| stable-diffusion | 18 | low | Diffusers text-to-image; scheduler comparison and the LCM 4-step recipe |
| whisper | 18 | med | local speech-to-text for turning talks and interviews into research input; model/VRAM table and WER tiers by language **orphan-ref** |

## Appendix B - upstream defects the vendor step must carry, not hide
- **Dangling links** (SKILL.md links a file that is not in the checkout): `mamba`
  3 of 3, `flash-attention` 2 of 4, `ray-train` 2, `verl` 1,
  `speculative-decoding` 1, and all of `constitutional-ai`, `llamaguard`,
  `nemo-guardrails`, `prompt-guard`, which cite a `references/` dir that does not exist.
- **Scraper-generated bodies**: `axolotl`, `llama-factory`, `unsloth`,
  `deepspeed` (template prose, mangled fragments, one literal placeholder line,
  and an unsloth frontmatter artifact `<!-- Trigger re-upload 1763621536 -->`).
- **Orphan references** (a file no SKILL.md links, kept because it is often the
  best artifact): `chroma`, `faiss`, `pinecone`, `sentence-transformers`, `clip`,
  `llava`, `whisper`, `a-evolve/references/README.md`.
- **Superseded APIs in bodies**: `langchain` (removed chains/memory),
  `dspy` (pre-2.5), `guidance` (`models.Anthropic`), `outlines`
  (`outlines.models.*`), `awq` (AutoAWQ deprecated), `rwkv`
  (`pytorch-lightning==1.9.5`).
- **Cross-skill relative paths that must stay valid**: `miles` →
  `../slime/references/api-reference.md`.

## State
**Implemented** on `plan/013-ai-research-library`, one commit (408 files,
+148,772 lines). The 98-row analysis and the design were recorded before the
work; what landed is below, with the command that shows it.

| claim | how it was checked | result |
|---|---|---|
| the tree is complete and matches its manifest | `bin/tezgah-import-ai-research --check` | `ok: 98 skills, 371 vendored files match library.json` |
| a re-run changes nothing | import twice, compare the digest of every file in the tree | identical |
| the drop list and the filters hold | `tests/test_ai_research_library.py` (fixture upstream) | no `.png`, no `.gitkeep`, no dump, no template tree in the output |
| `--check` can fail | tamper with one file / delete it / add an unlisted one | exit 1 for each, exit 0 when restored |
| an unexpected upstream stops the import | fixture with a changed skill count, a category outside the stage map, or a dirty markdown file | `SystemExit` naming the count, the category or the file |
| attribution survives | per-file assertion over all 365 vendored files | bodies byte-for-byte upstream (frontmatter `license: MIT`, author line intact: 96 `Orchestra Research`, `dailycafi`, `A-EVO Lab`), references carry the comment |
| size | `du -sk skills/ai-research` | 4,980 KB (4.2 MB of content) against the 5 MB cap test |
| context cost | `bin/tezgah-setup --context` | `skill metadata (10)  ~ 1.4k tok  5716 chars` - **+509 bytes** over nine skills |
| opencode wiring | `bin/tezgah-setup --install --hosts opencode` in a scratch HOME | always-on router: `research & papers: 1 skill`; full router: the `ai-research` line with its trigger; dir symlinked |
| it is usable end to end | a read-only agent given only the library and a research question | `SKILL.md` → `index/3-train.md` → `10-optimization/gguf/SKILL.md` + `references/troubleshooting.md`, and it answered with the K-quant table (`Q4_K_M 4.5 bits ~4.1 GB High (recommended default)`, fp16 `~13.5 GB`) |
| a real host reads it | `opencode run` in an isolated `HOME`, research prompt, first attempt | 6 tool calls, 0 file reads: it globbed its own project, found nothing, and reported *"Domain kütüphanesi bulunamadı"* with estimates, flagging that exact numbers were unavailable |
| the same host, after the two wiring fixes | the same prompt, same isolated `HOME` | **7 tool calls, 0 auto-rejections**: `skills/research/SKILL.md` → `ai-research/index/3-train.md` + `4-measure.md` → `10-optimization/bitsandbytes/SKILL.md` + `references/quantization-formats.md`, answered `45.9% → 45.2%` MMLU, perplexity `5.12 → 5.18`, `14 GB → 3.5 GB`, and named the file it read |
| every evidence pointer resolves | a sweep of `experiments/`, `to_human/blocks/` and `literature/` paths in the line, not just the two the check named | four stale pointers (claims ×2, `state.json` H7, the E4 log line) all corrected; the block's protocol annotated, not rewritten; the move recorded in `log.md` |
| the checks still pass | `python3 -m unittest discover -s tests`, `python3 -m compileall -q ...`, `ruff check .` | 527 tests OK (482 before), lint and compile clean |

### Live turns, host by host

| host | result |
|---|---|
| opencode | ✅ read `skills/research/SKILL.md` → `ai-research/index/3-train.md` + `4-measure.md` → `bitsandbytes/SKILL.md` + `references/quantization-formats.md`, answered the vendored numbers (45.9% → 45.2% MMLU, 5.12 → 5.18 perplexity, 14 GB → 3.5 GB), 0 permission rejections - after the two fixes below |
| codex | ✅ read `ai-research/index/3-train.md` → `gguf/SKILL.md` → `references/troubleshooting.md` through the host's own symlinked skill dir, answered the K-quant table with line references, and flagged that the sizes are library figures rather than M1 Pro measurements |
| omp | ✅ (on the second attempt) loaded the skill through its native `skill://ai-research/10-optimization/gguf/SKILL.md` and answered; the first clean attempt was blocked by the OpenRouter credit wall, not by tezgah |
| claude | ❌ not authenticated in a non-interactive run (`Not logged in · Please run /login`); the plugin's own SessionStart hooks did load and exit 0 |
| cursor | ❌ `cursor-agent -p` needs an interactive sign-in (`Press any key to sign in...`); its skill dir was linked correctly |

**How to run a clean live turn** (the recipe that made the omp rerun work, for whoever checks the two hosts above): a scratch `HOME`, the host's own auth file symlinked in (opencode `~/.local/share/opencode/auth.json`, codex `~/.codex/auth.json`, cursor `~/.cursor/cli-config.json`), `bin/tezgah-setup --install --hosts <host>`, a scratch git repo inside `$HOME/Projects` so tezgah is armed, then the host's print mode on the research prompt. omp needs one extra flag after the OpenRouter key ran down to ~64.9k affordable tokens: `--config <overlay.yml>` with `modelRoles.default: deepseek/deepseek-chat`, because its default request asks for 65,536 output tokens and a 402 is what you get instead. Copying the real `~/.omp/agent` wholesale also drags the user's session DB in, which is why the first omp attempt answered a conversation that was already open.

Four things the work itself surfaced, all recorded rather than smoothed over:

- **`tezgah-research check` found real drift in this repository's own research
  line, and the sweep found more of it.** The new proof-resolution rule refused
  `C10`/`C11`, which cited `experiments/E4-mechanical-off-effect/results.jsonl`.
  `bd68a36` had filed that block under `to_human/blocks/` after its run, and four
  pointers were left behind: two claims, `state.json`'s H7 and the E4 log line.
  All four now name the real location, the block's own protocol keeps its
  pre-move command (annotated, not rewritten), and `log.md` records the move so
  the correction cannot read as history rewriting.
- **Upstream authorship is not uniform.** `ml-training-recipes` (`dailycafi`) and
  `a-evolve` (`A-EVO Lab`) are third-party contributions; NOTICE, `SOURCE` and
  the entry point say so, and a test pins the three-name set so a re-vendor
  cannot quietly change it.
- **The library was unreachable on opencode until the live turn proved it.** The
  first `opencode run` read nothing and answered with estimates; the event stream
  showed why - the router named `ai-research` only in the on-demand file, and
  opencode auto-rejected the out-of-project read (`external_directory`) that
  followed. Both are fixed (always-on router section for tezgah's own on-demand
  skills; `external_directory` grants for `<checkout>/skills/**` and
  `~/.config/tezgah/bin/**`, leaving an explicit user action alone, removed by
  `--uninstall`), and the same prompt then read the library and quoted it.
- **The translations needed a terminology pass, not just a sentence.** The Thai
  README says ทักษะ where the added line said สกิล; each file's own term is now
  used. No native proofread was performed.

## Next
PR [#21](https://github.com/r1z4x/tezgah/pull/21) is open for
`plan/013-ai-research-library`; after it merges, `/tezgah:plan-sync` closes this
plan. Two host checks remain, both blocked by the host's own auth rather than by
tezgah - Claude's `-p` mode wants an interactive login (`Not logged in · Please
run /login`) and `cursor-agent -p` wants a sign-in - and the live-turn recipe
above is what makes either one a ten-minute repeat.
