# natural-voice-fit - what was established

An editing contract for prose written in more than one language, aimed at the reader
the text is for, the terms that must not be translated, and the writer's own voice.
Five hypotheses were pre-registered, all five ran, and one of them failed.

## Results, as measured

| Hypothesis | What the run produced | Verdict |
|---|---|---|
| H1 Turkish marker section | judged delta **-0.58** (95% CI -0.71 to -0.42); marker density per 100 words 0.00 in both arms | **refuted** |
| H2 register brief | audience-fit delta **+1.96** (95% CI 1.38 to 2.58) | supported |
| H3 writer samples | **0.67** of twelve blind forced-choice judgements | supported, thin margin |
| H4 keep-or-translate rail | terminology error points per 1,000 words **266.4 -> 0.00**; clarity 4.58 -> 4.67 | supported |
| H5 German rail instance | native-ness delta **+1.13** (95% CI 0.38 to 1.63); marker density 1.98 -> 1.01 | supported |

Every number above comes from one of the five `experiments/*/results.jsonl`, read out of
the run log committed beside it.

## The three findings that change the skill

1. **The reader has to be decomposed, not named.** A brief that lists the reader's
   vocabulary, what they need first and a length bound moved judged fit by about two points
   on a five-point scale, where one generic "write clearly" line moved it not at all.
2. **Terms need an explicit rail, and the rail is a published instrument.** Told to
   translate freely, the editor translated `Deadline` into `Teslim tarihinde` in the
   corporate-register draft - the exact failure the plaza-dili evidence predicts - and left
   calques standing. Handed the rail, it committed neither error and lost no clarity.
   Do-not-translate is a segment flag, an error class and a termbase in the standards, so
   the skill writes the decision down instead of trusting taste.
3. **The marker list does not earn its place.** The Turkish section, as written, made judges
   score the edits lower and moved a marker metric that was already at zero in both arms.
   The families the shipped contract already removes are not where the remaining defect
   lives; the language work belongs in the reader brief, the term rail and the voice
   samples, which is where the measurable effects were.

## What the evidence does not show

- **Every run is fixture-scoped.** The drafts, the rail, the briefs and the writer samples
  were authored in this session. The rows measure what two contract texts do to those
  drafts under one generator model. They say nothing about a real writer's workflow, and
  nothing about a real document set.
- **The judges are language models on cheap tiers, two of them, with no human reader.**
  A judge's opinion of Turkish or German naturalness is not a native speaker's. The narrow
  CIs reflect consistent judges, not a representative sample: six Turkish and four German
  items in total.
- **The audience result is partly circular.** The judges scored the draft against the same
  brief the arm was given, so part of the +1.96 is the brief being legible to the judge. A
  test with a reader who has not seen the brief was not run.
- **The rail is mine.** The keep list and the calque list follow the sources in
  `literature/`, but a different author would draw the boundaries elsewhere, and the items
  are seeded with the rail's own terms. The professional version of this check is a TBX
  termbase read by a checker; that was not run.
- **One language pair, one direction.** The pair was Turkish and German out of an
  English-shaped plan. No language whose rail is missing a leg was tested, and the coverage
  note measures how many of those there are.
- **Nothing here is an AI-detection result.** No run asked whether a machine wrote a text.
  The claims are about edits being more native, better fitted and more terminology-correct
  by blind judgement, and the falsified one is about a marker list, not about authorship.

## Where the work is

- `experiments/*/protocol.md` - what each run predicted, committed before it ran.
- `experiments/*/results.jsonl` - the rows, each carrying its source and its fixture scope.
- `experiments/*/analysis.md` - what the rows mean and what they do not.
- `experiments/*/raw/*.log` - the run logs, including both arms' texts for every item.
- `harness/` - the item sets, the rail, the briefs, the samples and the one script.
- `literature/` - 62 notes with the authorities behind every rule.
