# Constraint recogniser fixture

The sentences `hooks/tezgah_context.py::user_constraints` was measured on (plan
056 part h). `real` rows are sentences cut from user prompts in this machine's
omp and Claude transcripts (85 top-level sessions, 1,452 prompts under
`~/Projects`, mined 2026-10-06 with `bin/tezgah-taste`'s walkers; each row is the
one sentence, never the whole prompt, with markup, paths and names trimmed).
`hand` rows are written probes for the shapes the real set does not exercise.

Labels: `constraint` - a constraint the user issued, and the recogniser pins it;
`none` - not a constraint, and the recogniser leaves it; `missed` - a constraint
the recogniser does not pin (a false negative, kept so a widening is measured);
`false-positive` - not meant as a constraint, yet pinned.

On the real set the recogniser flagged 6 of 1,452 prompts, all six constraints:
no false positive. The false-positive rows below are hand probes that show the
recogniser's known limit - a prohibition verb read without its sense.

- constraint (real): Sadece sunucu; üretime dokunma.
- constraint (real): Target repository: the admin app. Do not modify tracked files: put any scratch output somewhere else.
- constraint (real): Başka repoya ve ~/.config'e dokunma.
- constraint (real): Do not remove necessary technical terms.
- constraint (real): Then get improvement prompts and apply them, but ask before applying.
- constraint (hand): don't touch hooks/hooks.json
- constraint (hand): never push to main without me
- constraint (hand): README'ye dokunma
- constraint (hand): bana sormadan push etme
- none (real): bana sormadan paralel olarak devam et
- none (real): devam et bana sormadan hızlıca sonlandır.
- none (real): Kontrast, dokunma hedefi, focus sırası → ölç ya da ekran görüntüsü
- none (real): Do not improvise a lighter method.
- none (real): Bitince: compileall + ruff + dokunduğun test modülleri; çıktıyı dosyaya yaz.
- none (real): Diğer projelerin volume'larına dokunmadım ve şu an da dokunmuyorum.
- none (real): Do not invent facts, requirements, measurements, sources, or implementation details.
- none (real): Don't paraphrase; don't skip the patches.
- none (real): Never run bare
- none (real): Continue the task you were working on when the limit was reached; do not repeat work that is already complete.
- none (hand): mobilde dokunma alanı çok küçük
- none (hand): add a docstring to parse_quantity
- missed (real): Ama önce bana sor.
- false-positive (hand): never change a winning team
- false-positive (hand): don't touch base with them until Monday
